import math
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

DATA_XLS = Path("input/TechArena2025_Phase2_data.xlsx")
OUT_DIR = Path("output")
LIMIT_DAYS = 365 * 10 # Simulation length (10 years)


# --- Utility numeric conversion functions ---
def num_series(s):
    # Convert a pandas Series to numeric values, coercing errors to NaN
    return pd.to_numeric(s, errors="coerce")


def num_median(s):
    # Compute median of numeric series, ignoring NaN values
    x = num_series(s)
    return float(np.nanmedian(x)) if x.notna().any() else 0.0


def num_quantile(s, q):
    # Compute a specific quantile (used for price thresholds)
    x = num_series(s)
    return float(x.quantile(q)) if x.notna().any() else 0.0


# --- Activation rate model based on Huawei curve (simplified version) ---
# Defines how often aFRR bids are activated depending on their bid price.
# Lower bids are activated more frequently, higher bids less.
def activation_factor(price, direction="Pos"):
    if direction == "Pos":
        if price < 10: return 0.45
        elif price < 20: return 0.32
        elif price < 40: return 0.22
        elif price < 60: return 0.13
        elif price < 100: return 0.07
        else: return 0.03
    else:  # Negative direction
        if price < 10: return 0.10
        elif price < 20: return 0.08
        elif price < 40: return 0.06
        elif price < 60: return 0.04
        elif price < 100: return 0.025
        else: return 0.01


# --- Load all price datasets from Excel ---
def load_prices():
    # --- Day-ahead prices ---
    raw = pd.read_excel(DATA_XLS, sheet_name="Day-ahead prices", header=None)
    hdr = raw.iloc[1].tolist()
    da_clean = raw.iloc[2:, 0:6]
    da_clean.columns = ["Timestep"] + hdr[1:6]
    da_clean["Timestep"] = pd.to_datetime(da_clean["Timestep"])
    da = da_clean.set_index("Timestep").rename(columns={"DE_LU": "DE"})
    da = da.apply(num_series)

    # --- FCR prices ---
    raw = pd.read_excel(DATA_XLS, sheet_name="FCR prices", header=None)
    hdr = raw.iloc[1].tolist()
    fcr_clean = raw.iloc[2:, 0:6]
    fcr_clean.columns = ["Timestep"] + hdr[1:6]
    fcr_clean["Timestep"] = pd.to_datetime(fcr_clean["Timestep"])
    fcr = fcr_clean.set_index("Timestep").apply(num_series)

    # aFRR capacity
    raw = pd.read_excel(DATA_XLS, sheet_name="aFRR capacity prices", header=None)
    countries_row = 1
    dir_row = 2
    timestamps_start = 3
    countries = raw.iloc[countries_row, 1:11].tolist()
    dirs = raw.iloc[dir_row, 1:11].tolist()
    mcols = pd.MultiIndex.from_arrays([countries, dirs])
    afrr_cap_data = raw.iloc[timestamps_start:, [0] + list(range(1, 11))].copy()
    afrr_cap_data.columns = ["Timestep"] + list(mcols)
    afrr_cap_data["Timestep"] = pd.to_datetime(afrr_cap_data["Timestep"])
    afrr_cap = afrr_cap_data.set_index("Timestep")

    # Clean multiindex columns + numeric coercion
    clean_cols = []
    c_prec = "UNK"
    for c, d in afrr_cap.columns:
        cc = c if isinstance(c, str) else c_prec
        clean_cols.append((cc, d))
        c_prec = cc
    afrr_cap.columns = pd.MultiIndex.from_tuples(clean_cols, names=["Country", "Dir"])
    afrr_cap.sort_index(axis=1, inplace=True)
    afrr_cap = afrr_cap.apply(num_series)  # <-- global numeric coercion

    avail_countries = set(afrr_cap.columns.get_level_values(0))

    # aFRR energ
    raw = pd.read_excel(DATA_XLS, sheet_name="aFRR energy prices", header=None)
    countries_row = 1
    dir_row = 2
    timestamps_start = 3
    countries = raw.iloc[countries_row, 1:11].tolist()
    dirs = raw.iloc[dir_row, 1:11].tolist()
    mcols = pd.MultiIndex.from_arrays([countries, dirs])
    afrr_en_data = raw.iloc[timestamps_start:, [0] + list(range(1, 11))].copy()
    afrr_en_data.columns = ["Timestep"] + list(mcols)
    afrr_en_data["Timestep"] = pd.to_datetime(afrr_en_data["Timestep"])
    afrr_en = afrr_en_data.set_index("Timestep")

    # Clean multiindex columns + numeric coercion
    clean_cols = []
    c_prec = "UNK"
    for c, d in afrr_en.columns:
        cc = c if isinstance(c, str) else c_prec
        clean_cols.append((cc, d))
        c_prec = cc
    afrr_en.columns = pd.MultiIndex.from_tuples(clean_cols, names=["Country", "Dir"])
    afrr_en.sort_index(axis=1, inplace=True)
    afrr_en = afrr_en.apply(num_series)  # <-- global numeric coercion

    avail_countries = set(afrr_en.columns.get_level_values(0))

    return da, fcr, afrr_cap, afrr_en, avail_countries


# --- Load financial parameters (WACC, inflation) ---
def load_finance():
    d = pd.read_excel(DATA_XLS, sheet_name="Data description")
    t2 = d.iloc[19:34, 0:3].copy()
    t2.columns = ["Country", "WACC", "Inflation"]
    t2 = t2.dropna().reset_index(drop=True)
    t2["Code"] = t2["Country"].str.extract(r"\((\w+)\)").iloc[:, 0]
    return t2[["Code", "WACC", "Inflation"]]


# --- Main country simulation ---
def simulate_country(da, fcr, afrr_cap, afrr_en, avail_countries, code, c_rate, cycles_per_day):
    # Battery technical parameters
    e_nom_mwh = 4.472
    soc = 0.6
    soh = 1.0
    eta_rt = 0.88
    eta_c = np.sqrt(eta_rt)
    eta_d = np.sqrt(eta_rt)
    soc_min, soc_max = 0.1, 0.9
    c_aging, soh_eol, cycle_life = 50, 0.7, 4000
    Ea, R, k_cal, dt_h = 30000, 8.314, 1e-5, 0.25  # Degradation constants

    # Day-ahead energy prices
    prices = num_series(da[code]).dropna()
    start, end = prices.index.min(), prices.index.min() + pd.Timedelta(days=LIMIT_DAYS)
    prices = prices.loc[start:end]

    # Convert FCR prices from 4h resolution to 15min
    fcr_series_full = num_series(fcr[code]).dropna()
    fcr_series = fcr_series_full.loc[fcr_series_full.index.min():end]
    fcr_15 = fcr_series.resample("15min").ffill().reindex(prices.index, method="ffill").fillna(0.0)

    # aFRR capacity (positive and negative)
    # AFRR cap pos/neg 4h -> 15 min
    # Sélection de la série aFRR POS pour le pays
    afr_cap_pos_series_full = afrr_cap[(code, "Pos")].dropna()
    # Limiter à la période souhaitée
    start_time = afr_cap_pos_series_full.index.min()
    end_time = start_time + pd.Timedelta(days=LIMIT_DAYS)
    afr_pos_series = afr_cap_pos_series_full.loc[start_time:end_time]
    # Sélection de la série aFRR NEG pour le pays
    afr_neg_series_full = afrr_cap[(code, "Neg")].dropna()
    afr_neg_series = afr_neg_series_full.loc[start_time:end_time]
    # Resample à 15 min et aligner avec l'index des prix
    afr_cap_pos = afr_pos_series.resample("15min").ffill().reindex(prices.index, method="ffill").fillna(0.0)
    afr_cap_neg = afr_neg_series.resample("15min").ffill().reindex(prices.index, method="ffill").fillna(0.0)

    # AFRR energy pos/neg 4h -> 15 min
    # Sélection de la série aFRR POS pour le pays
    afr_en_pos_series_full = afrr_en[(code, "Pos")].dropna()
    # Limiter à la période souhaitée
    start_time = afr_en_pos_series_full.index.min()
    end_time = start_time + pd.Timedelta(days=LIMIT_DAYS)
    afr_pos_series = afr_en_pos_series_full.loc[start_time:end_time]
    # Sélection de la série aFRR NEG pour le pays
    afr_neg_series_full = afrr_en[(code, "Neg")].dropna()
    afr_neg_series = afr_neg_series_full.loc[start_time:end_time]
    # Resample à 15 min et aligner avec l'index des prix
    afr_en_pos = afr_pos_series.resample("15min").ffill().reindex(prices.index, method="ffill").fillna(0.0)
    afr_en_neg = afr_neg_series.resample("15min").ffill().reindex(prices.index, method="ffill").fillna(0.0)
    
    # Median prices for bid selection
    fcr_med, afr_pos_med, afr_neg_med, afrE_pos_med, afrE_neg_med = num_median(fcr_15), num_median(afr_cap_pos), num_median(afr_cap_neg), num_median(afr_en_pos), num_median(afr_en_neg)
    q_low, q_high = num_quantile(prices, 0.30), num_quantile(prices, 0.70)

    # --- Temperature model ---
    # Synthetic temperature variation (daily + seasonal)
    temp_country = {"DE": 10, "AT": 9, "CH": 8, "CZ": 9, "HU": 13}
    A_year, A_day = 12, 5
    times = prices.index
    T_moy = temp_country.get(code, 25)
    T_ext = T_moy + A_year * np.sin(2 * np.pi * (times.day_of_year / 365)) + A_day * np.sin(2 * np.pi * (times.hour / 24))

    # --- Time simulation loop ---
    rows = []
    fce_today = 0.0
    for i, (ts, price) in enumerate(prices.items()):
        # Temperature and power setup
        temp, temp_K = T_ext[i], T_ext[i] + 273.15
        e_nom_eff, p_max = e_nom_mwh * soh, c_rate * e_nom_mwh * soh

        # Get market prices
        cfcr_price = fcr_15.get(ts, 0.0)
        afr_pos_price, afr_neg_price = afr_cap_pos.get(ts, 0.0), afr_cap_neg.get(ts, 0.0)
        afrE_pos_price, afrE_neg_price = afr_en_pos.get(ts, 0.0), afr_en_neg.get(ts, 0.0)

        # Capacity commitments
        cfcr = 0.5 * p_max if cfcr_price >= fcr_med else 0.0
        cap_pos = 0.3 * p_max if afr_pos_price >= afr_pos_med else 0.0
        cap_neg = 0.3 * p_max if afr_neg_price >= afr_neg_med else 0.0

        # Enforce total limit
        total_res = cfcr + cap_pos + cap_neg
        if total_res > p_max:
            scale = p_max / total_res
            cfcr, cap_pos, cap_neg = cfcr * scale, cap_pos * scale, cap_neg * scale

        # Available power for day-ahead arbitrage
        p_avail = max(0.0, p_max - (cfcr + cap_pos + cap_neg))
        e_ch = e_dis = 0.0

        # Charge/discharge logic based on price quantiles
        p_avail = max(0.0, p_max - (cfcr + cap_pos + cap_neg))

        # Remaining cycles
        remaining_fce = max(0.0, cycles_per_day - fce_today)
        e_headroom = remaining_fce * e_nom_mwh
        e_nom_effective = e_nom_mwh * soh

        
        da_charge_signal = price <= q_low
        da_discharge_signal = price >= q_high

        afrr_charge_signal = afrE_neg_price> afrE_neg_med
        afrr_discharge_signal = afrE_pos_price > afrE_pos_med

        if(afrr_charge_signal == True and da_discharge_signal == True):
            da_discharge_signal = False
        if(afrr_discharge_signal == True and da_charge_signal == True):
            da_charge_signal = False

        if(afrr_charge_signal == True and afrr_discharge_signal == True):
            afrr_charge_signal = False

        p_ch_DA = 0.0
        p_dis_DA = 0.0
        p_ch_aFRR = 0.0
        p_dis_aFRR = 0.0

        # --- Day-Ahead ---
        if da_charge_signal and soc < soc_max and e_headroom > 0:
            e_allow = min(p_avail * dt_h, (soc_max - soc) * e_nom_effective, e_headroom)
            p_ch_DA = e_allow / dt_h if e_allow > 0 else 0.0

        if da_discharge_signal and soc > soc_min and e_headroom > 0:
            e_allow = min(p_avail * dt_h, (soc - soc_min) * e_nom_effective, e_headroom)
            p_dis_DA = e_allow / dt_h if e_allow > 0 else 0.0
        
        # --- aFRR Energy (with activation factor) ---
        if afrr_charge_signal and soc < soc_max and e_headroom > 0:
            e_allow = min(p_avail * dt_h, (soc_max - soc) * e_nom_effective, e_headroom)
            if e_allow > 0:
                p_ch_aFRR = (e_allow / dt_h) * activation_factor(afrE_neg_price, "Neg")
            else:
                p_ch_aFRR = 0.0
        else:
            p_ch_aFRR = 0.0

        if afrr_discharge_signal and soc > soc_min and e_headroom > 0:
            e_allow = min(p_avail * dt_h, (soc - soc_min) * e_nom_effective, e_headroom)
            if e_allow > 0:
                p_dis_aFRR = (e_allow / dt_h) * activation_factor(afrE_pos_price, "Pos")
            else:
                p_dis_aFRR = 0.0
        else:
            p_dis_aFRR = 0.0

        p_ch = p_ch_DA + p_ch_aFRR
        p_dis = p_dis_DA + p_dis_aFRR

        # Énergies [MWh]
        e_ch_DA = p_ch_DA * dt_h
        e_dis_DA = p_dis_DA * dt_h
        e_ch_aFRR = p_ch_aFRR * dt_h
        e_dis_aFRR = p_dis_aFRR * dt_h

        # --- Degradation model ---
        # Cycle degradation (depends on Depth of Discharge)
        dod = (e_ch + e_dis) / e_nom_mwh
        deg_cycle = (dod ** 1.1) / cycle_life

        # Calendar degradation (temperature-dependent)
        deg_cal = k_cal * np.exp(-Ea / (R * temp_K)) * dt_h

        # Total degradation increment
        delta_soh = deg_cycle + deg_cal
        soh = max(soh_eol, soh - delta_soh)

        # Economic cost of aging
        aging_cost = (c_aging * e_nom_mwh * 1000 / (1 - soh_eol)) * delta_soh

        # --- Revenue calculations ---
        rev_DA_energy = e_dis_DA * price - e_ch_DA * price
        rev_aFRR_energy = e_dis_aFRR * afrE_pos_price - e_ch_aFRR * afrE_neg_price

        e_ch = e_ch_DA + e_ch_aFRR
        e_dis = e_dis_DA + e_dis_aFRR

        fce_today += (e_ch + e_dis) / (2 * e_nom_mwh)

        # SOC
        soc = soc + (e_ch * eta_c - e_dis / eta_d) / e_nom_mwh
        soc = min(max(soc, soc_min), soc_max)

        rev_capacity = (cfcr * cfcr_price + cap_pos * afr_pos_price + cap_neg * afr_neg_price) * dt_h

        # Store timestep results
        rows.append({
            "Timestamp": ts,
            "Temperature [°C]": temp,
            "Stored energy [MWh]": soc * e_nom_eff,
            "SoC [-]": soc,
            "SoH [-]": soh,
            "Charge [MWh]": e_ch,
            "Discharge [MWh]": e_dis,
            "Day-ahead buy [MWh]": e_ch,
            "Day-ahead sell [MWh]": e_dis,
            "FCR Capacity [MW]": cfcr,
            "aFRR Capacity POS [MW]": cap_pos,
            "aFRR Capacity NEG [MW]": cap_neg,
            "aFRR Energy POS [MW]": e_dis_aFRR,
            "aFRR Energy NEG [MW]": e_ch_aFRR,
            "Energy revenue [EUR]": rev_DA_energy + rev_aFRR_energy,
            "Capacity revenue [EUR]": rev_capacity,
            "Aging cost [EUR]": aging_cost,
            "Total revenue [EUR]": rev_capacity + rev_DA_energy + rev_aFRR_energy
        })

    # Convert results to DataFrame
    df = pd.DataFrame(rows).set_index("Timestamp")

    # Annualized profit (normalized to one year)
    total_profit = df["Total revenue [EUR]"].sum() * (365 / LIMIT_DAYS)
    p_max_ref = c_rate * e_nom_mwh
    return df, total_profit, p_max_ref


# --- Compute Levelized ROI (financial evaluation) ---
def levelized_roi(year_profit_eur, p_max_mw, wacc, inflation,
                  e_nom_mwh=4.472, capex_per_mwh=380000,
                  capex_power_per_mw=200000, opex_rate=0.02, years=10):
    inv = capex_per_mwh * e_nom_mwh + capex_power_per_mw * p_max_mw
    opex = inv * opex_rate
    npv = -inv
    yearly_rows = []

    # Discounted cash flow analysis for ROI
    for y in range(1, years + 1):
        prof = year_profit_eur * (1 + inflation) ** (y - 1)
        cf = prof - opex
        disc = cf / ((1 + wacc) ** y)
        yearly_rows.append({
            "Year": y,
            "Yearly profits [EUR]": prof,
            "OPEX [EUR]": opex,
            "Discount factor": 1 / ((1 + wacc) ** y),
            "Discounted CF [EUR]": disc
        })
        npv += disc

    lvl_roi = npv / inv
    return lvl_roi, inv, opex, pd.DataFrame(yearly_rows)


# --- Main simulation and output generation ---
def run():
    da, fcr, afrr, afrrE, avail_countries = load_prices()
    finance = load_finance()

    countries = ["DE", "AT", "CH", "CZ", "HU"]
    configs = [
        (0.25, 1.0), (0.25, 1.5), (0.25, 2.0),
        (0.33, 1.0), (0.33, 1.5), (0.33, 2.0),
        (0.50, 1.0), (0.50, 1.5), (0.50, 2.0),
    ]

    results, best, best_tuple, best_df = [], -999, None, None

    # Simulate all country/config combinations
    for ctry in countries:
        for c_rate, cycles in configs:
            df, profit, p_max = simulate_country(da, fcr, afrr, afrrE, avail_countries, ctry, c_rate, cycles)
            sub = finance.loc[finance["Code"] == ctry]
            if sub.empty:
                continue
            wacc, infl = float(sub["WACC"]), float(sub["Inflation"])
            lvl_roi, inv, opex, inv_df = levelized_roi(profit, p_max, wacc, infl)

            results.append({
                "Country": ctry,
                "C-rate": c_rate,
                "number of cycles": cycles,
                "yearly profits [kEUR/MW]": round(profit / p_max / 1000, 2),
                "levelized ROI [%]": round(lvl_roi * 100, 2)
            })

            if lvl_roi > best:
                best = lvl_roi
                best_tuple = (ctry, c_rate, cycles, wacc, infl, inv, opex, inv_df)
                best_df = df

    # --- Export results ---
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Configuration file
    cfg = pd.DataFrame(results).sort_values("levelized ROI [%]", ascending=False)
    cfg.to_csv(OUT_DIR / "TechArena_Phase2_Configuration.csv", index=False)

    # 2. Investment file (best configuration)
    ctry, c_rate, cycles, wacc, infl, inv, opex, inv_df = best_tuple
    inv_summary = pd.DataFrame([{
        "Country": ctry,
        "C-rate": c_rate,
        "number of cycles": cycles,
        "WACC": wacc,
        "inflation rate": infl,
        "discount rate": wacc,
        "CAPEX [EUR]": inv,
        "OPEX [EUR]": opex,
        "levelized ROI": best
    }])
    with open(OUT_DIR / "TechArena_Phase2_Investment.csv", "w", encoding="utf-8") as f:
        f.write(inv_summary.to_csv(index=False))
        f.write("\n")
        f.write(inv_df.to_csv(index=False))

    # 3. Operation file (detailed energy and revenue time series)
    best_df[
        ["Stored energy [MWh]", "SoC [-]", "SoH [-]", "Charge [MWh]", "Discharge [MWh]",
         "Day-ahead buy [MWh]", "Day-ahead sell [MWh]",
         "FCR Capacity [MW]", "aFRR Capacity POS [MW]", "aFRR Capacity NEG [MW]", "aFRR Energy POS [MW]", "aFRR Energy NEG [MW]"]
    ].to_csv(OUT_DIR / "TechArena_Phase2_Operation.csv")
