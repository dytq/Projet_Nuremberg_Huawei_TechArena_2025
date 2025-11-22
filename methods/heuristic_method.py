# main.py

import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Robust helpers for numeric coercion and stats
def num_series(s):
    return pd.to_numeric(s, errors="coerce")

def num_median(s):
    x = num_series(s)
    if x.notna().any():
        return float(np.nanmedian(x.values.astype(float)))
    return 0.0

#Get the thresholds
def num_quantile(s, q):
    x = num_series(s)
    if x.notna().any():
        return float(x.quantile(q))
    return 0.0

# Paths
DATA_XLS = Path(__file__).parent / "../input/TechArena2025_data.xlsx"
OUT_DIR = Path(__file__).parent / "../output"

# Similated duration
LIMIT_DAYS = 365

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

def load_prices(xls_path=DATA_XLS):
    # Day-ahead
    raw = pd.read_excel(xls_path, sheet_name="Day-ahead prices", header=None)
    hdr = raw.iloc[1].tolist()
    cols = ["Timestep"] + hdr[1:6]
    da_clean = raw.iloc[2:, 0:6]
    da_clean.columns = cols
    da_clean["Timestep"] = pd.to_datetime(da_clean["Timestep"])
    da = da_clean.set_index("Timestep").rename(columns={"DE_LU": "DE"})
    da = da.apply(num_series)  # <-- coercition numérique

    # FCR
    raw = pd.read_excel(xls_path, sheet_name="FCR prices", header=None)
    hdr = raw.iloc[1].tolist()
    cols = ["Timestep"] + hdr[1:6]
    fcr_clean = raw.iloc[2:, 0:6]
    fcr_clean.columns = cols
    fcr_clean["Timestep"] = pd.to_datetime(fcr_clean["Timestep"])
    fcr = fcr_clean.set_index("Timestep")
    fcr = fcr.apply(num_series)  # <-- coercition numérique

    # aFRR capacity
    raw = pd.read_excel(xls_path, sheet_name="aFRR capacity prices", header=None)
    countries_row = 1
    dir_row = 2
    timestamps_start = 3
    countries = raw.iloc[countries_row, 1:11].tolist()
    dirs = raw.iloc[dir_row, 1:11].tolist()
    mcols = pd.MultiIndex.from_arrays([countries, dirs])
    afrr_data = raw.iloc[timestamps_start:, [0] + list(range(1, 11))].copy()
    afrr_data.columns = ["Timestep"] + list(mcols)
    afrr_data["Timestep"] = pd.to_datetime(afrr_data["Timestep"])
    afrr = afrr_data.set_index("Timestep")

    # Clean multiindex columns + numeric coercion
    clean_cols = []
    c_prec = "UNK"
    for c, d in afrr.columns:
        cc = c if isinstance(c, str) else c_prec
        clean_cols.append((cc, d))
        c_prec = cc

    afrr.columns = pd.MultiIndex.from_tuples(clean_cols, names=["Country", "Dir"])
    afrr.sort_index(axis=1, inplace=True)
    afrr = afrr.apply(num_series)  # <-- global numeric coercion
    avail_countries = set(afrr.columns.get_level_values(0))
    return da, fcr, afrr, avail_countries

def load_finance(xls_path=DATA_XLS):
    d = pd.read_excel(xls_path, sheet_name="Data description")
    t2 = d.iloc[19:29, 0:3].copy()
    t2.columns = ["Country", "WACC", "Inflation"]
    t2 = t2.dropna().reset_index(drop=True)
    t2["Code"] = t2["Country"].str.extract(r"\((\w+)\)").iloc[:, 0]
    return t2[["Code", "WACC", "Inflation"]]

def simulate_country(
    da, fcr, afrr, avail_countries, code, c_rate, cycles_per_day,
    eta_rt=0.88, soc_min=0.1, soc_max=0.9, e_nom_mwh=4.472, limit_days=LIMIT_DAYS
):
    eta_c = math.sqrt(eta_rt)
    eta_d = math.sqrt(eta_rt)
    p_max = c_rate * e_nom_mwh  # MW

    # DA prices 15 min
    prices_full = num_series(da[code]).dropna()
    start = prices_full.index.min()
    end = start + pd.Timedelta(days=limit_days)
    prices = prices_full.loc[start:end]
    dt_h = 0.25
    prices = num_series(prices).dropna()  # sécurise

    # FCR 4h -> 15min
    fcr_series_full = num_series(fcr[code]).dropna()
    fcr_series = fcr_series_full.loc[
        fcr_series_full.index.min(): fcr_series_full.index.min() + pd.Timedelta(days=limit_days)
    ]
    fcr_15 = fcr_series.resample("15min").ffill().reindex(prices.index, method="ffill")
    fcr_15 = num_series(fcr_15).fillna(0.0)  # sécurise

    # aFRR Pos/Neg -> 15min
    # Sélection de la série aFRR POS pour le pays
    afr_pos_series_full = afrr[(code, "Pos")].dropna()

    # Limiter à la période souhaitée
    start_time = afr_pos_series_full.index.min()
    end_time = start_time + pd.Timedelta(days=limit_days)
    afr_pos_series = afr_pos_series_full.loc[start_time:end_time]

    # Sélection de la série aFRR NEG pour le pays
    afr_neg_series_full = afrr[(code, "Neg")].dropna()
    afr_neg_series = afr_neg_series_full.loc[start_time:end_time]

    # Resample à 15 min et aligner avec l'index des prix
    afr_pos_15 = afr_pos_series.resample("15min").ffill().reindex(prices.index, method="ffill").fillna(0.0)
    afr_neg_15 = afr_neg_series.resample("15min").ffill().reindex(prices.index, method="ffill").fillna(0.0)
    
    rows = []
    soc = 0.6
    last_day = None
    fce_today = 0.0

    # robust thresholds
    fcr_med     = num_median(fcr_15)
    afr_pos_med = num_median(afr_pos_15)
    afr_neg_med = num_median(afr_neg_15)
    q_low  = num_quantile(prices, 0.30)
    q_high = num_quantile(prices, 0.70)
    
    for ts, price in prices.items():
        if pd.isna(price):
            continue
        day = ts.date()
        if last_day is None or day != last_day:
            fce_today = 0.0
            last_day = day

        # Secured step values
        cfcr_price    = float(fcr_15.get(ts, 0.0)) or 0.0
        afr_pos_price = float(afr_pos_15.get(ts, 0.0)) or 0.0
        afr_neg_price = float(afr_neg_15.get(ts, 0.0)) or 0.0

        # reserves
        # Coefficient basé sur le SOC
        soc_available = max(0.0, soc - soc_min)  # SOC disponible au-dessus du minimum
        soc_range = soc_max - soc_min
        soc_factor = soc_available / soc_range  # normalisé entre 0 et 1

        # Capacité FCR indexée sur le SOC
        cfcr_base = min(0.8 * p_max, 0.5 * p_max) if cfcr_price >= fcr_med else 0.0
        cfcr = cfcr_base * soc_factor
    
        cap_pos = min(0.5 * (p_max - cfcr), max(0.0, p_max - cfcr)) if afr_pos_price > afr_pos_med else 0.0
        cap_neg = min(0.5 * (p_max - cfcr), max(0.0, p_max - cfcr)) if afr_neg_price > afr_neg_med else 0.0

        total_res = cfcr + cap_pos + cap_neg
        if total_res > p_max and total_res > 0:
            scale = p_max / total_res
            cfcr *= scale
            cap_pos *= scale
            cap_neg *= scale

        p_avail = max(0.0, p_max - (cfcr + cap_pos + cap_neg))

        # Remaining cycles
        remaining_fce = max(0.0, cycles_per_day - fce_today)
        e_headroom = remaining_fce * e_nom_mwh

        # decisions
        p_ch = 0.0
        p_dis = 0.0
        if price <= q_low and soc < soc_max and e_headroom > 0:
            e_allow = min(p_avail * dt_h, (soc_max - soc) * e_nom_mwh, e_headroom)
            p_ch = e_allow / dt_h if e_allow > 0 else 0.0
        if price >= q_high and soc > soc_min and e_headroom > 0:
            e_allow = min(p_avail * dt_h, (soc - soc_min) * e_nom_mwh, e_headroom)
            p_dis = e_allow / dt_h if e_allow > 0 else 0.0

        e_ch = p_ch * dt_h
        e_dis = p_dis * dt_h

        soc = soc + (e_ch * eta_c - e_dis / eta_d) / e_nom_mwh
        soc = min(max(soc, soc_min), soc_max)

        fce_today += (e_ch + e_dis) / (2 * e_nom_mwh)

        rev_energy = e_dis * price - e_ch * price
        rev_capacity = (cfcr * cfcr_price + cap_pos * afr_pos_price + cap_neg * afr_neg_price) * dt_h
          
        rows.append(
            {
                "Timestamp": ts,
                "Stored energy [MWh]": soc * e_nom_mwh,
                "SoC [-]": soc,
                "Charge [MWh]": e_ch,
                "Discharge [MWh]": e_dis,
                "Day-ahead buy [MWh]": e_ch,
                "Day-ahead sell [MWh]": e_dis,
                "FCR Capacity [MW]": cfcr,
                "aFRR Capacity POS [MW]": cap_pos,
                "aFRR Capacity NEG [MW]": cap_neg,
                "Energy revenue [EUR]": rev_energy,
                "Capacity revenue [EUR]": rev_capacity,
            }
        )
    
    op = pd.DataFrame(rows).set_index("Timestamp")
    op["Total revenue [EUR]"] = op["Energy revenue [EUR]"] + op["Capacity revenue [EUR]"]
    year_profit_scaled = op["Total revenue [EUR]"].sum() * (365 / limit_days)
    return op, year_profit_scaled, p_max

def levelized_roi(
    year_profit_eur, p_max_mw,
    capex_per_mwh=380000, e_nom_mwh=4.472, capex_power_per_mw=200000,
    wacc=0.10, years=10, opex_rate=0.02, inflation=0.02
):
    profit_per_mw = year_profit_eur / p_max_mw if p_max_mw > 0 else 0.0
    inv = capex_per_mwh * e_nom_mwh + capex_power_per_mw * p_max_mw
    opex = inv * opex_rate
    cashflows = []
    for y in range(1, years + 1):
        prof = year_profit_eur * (1 + inflation) ** (y - 1)
        cf = prof - opex
        disc = cf / ((1 + wacc) ** y)
        cashflows.append(disc)
    npv = -inv + sum(cashflows)
    lvl_roi = npv / inv if inv > 0 else 0.0
    return profit_per_mw / 1000.0, lvl_roi

def run():
    da, fcr, afrr, avail_countries = load_prices()
    finance = load_finance()

    countries = ["DE", "AT", "CH", "CZ", "HU"]
    configs = [
        (0.25, 1.0), (0.25, 1.5), (0.25, 2.0),
        (0.33, 1.0), (0.33, 1.5), (0.33, 2.0),
        (0.50, 1.0), (0.50, 1.5), (0.50, 2.0),
    ]

    results = []
    best = None
    best_tuple = None
    best_op = None

    for ctry in countries:
        for c_rate, cycles in configs:
            op, profit, p_max = simulate_country(
                da, fcr, afrr, avail_countries, ctry, c_rate, cycles, limit_days=LIMIT_DAYS
            )
            wacc = float(finance.loc[finance["Code"] == ctry, "WACC"].iloc[0])
            infl = float(finance.loc[finance["Code"] == ctry, "Inflation"].iloc[0])
            kEUR_MW, lvl_roi = levelized_roi(profit, p_max, wacc=wacc, inflation=infl)
            results.append(
                {
                    "Country": ctry,
                    "C-rate": c_rate,
                    "number of cycles": cycles,
                    "yearly profits [kEUR/MW]": round(kEUR_MW, 2),
                    "levelized ROI [%]": round(100 * lvl_roi, 2),
                }
            )
            if best is None or lvl_roi > best:
                best = lvl_roi
                best_tuple = (ctry, c_rate, cycles)
                best_op = op

    cfg = pd.DataFrame(results).sort_values(["levelized ROI [%]"], ascending=False)

    # Best case
    ctry, c_rate, cycles = best_tuple
    op, profit, p_max = simulate_country(
        da, fcr, afrr, avail_countries, ctry, c_rate, cycles, limit_days=LIMIT_DAYS
    )
    wacc = float(finance.loc[finance["Code"] == ctry, "WACC"].iloc[0])
    infl = float(finance.loc[finance["Code"] == ctry, "Inflation"].iloc[0])

    capex_per_mwh = 380000
    e_nom_mwh = 4.472
    capex_power_per_mw = 200000
    opex_rate = 0.02
    years = 10

    inv = capex_per_mwh * e_nom_mwh + capex_power_per_mw * p_max
    opex = inv * opex_rate

    yearly_rows = []
    npv = -inv
    for y in range(1, years + 1):
        prof = profit * (1 + infl) ** (y - 1)
        cf = prof - opex
        disc = cf / ((1 + wacc) ** y)
        yearly_rows.append(
            {
                "Year": y,
                "Yearly profits [EUR]": prof,
                "OPEX [EUR]": opex,
                "Discount factor": 1 / ((1 + wacc) ** y),
                "Discounted CF [EUR]": disc,
            }
        )
        npv += disc
    lvl_roi = npv / inv
    inv_df = pd.DataFrame(yearly_rows)

    inv_summary = pd.DataFrame(
        [{
            "Country": ctry, "C-rate": c_rate, "number of cycles": cycles,
            "WACC": wacc, "inflation rate": infl, "discount rate": wacc,
            "CAPEX [EUR]": inv, "OPEX rate": opex_rate, "levelized ROI": lvl_roi
        }]
    )

    # outputs
    (OUT_DIR / "TechArena_Phase1_Configuration.csv").write_text(
        cfg[["Country", "C-rate", "number of cycles", "yearly profits [kEUR/MW]", "levelized ROI [%]"]]
        .to_csv(index=False)
    )
    with open(OUT_DIR / "TechArena_Phase1_Investment.csv", "w", encoding="utf-8") as f:
        f.write(inv_summary.to_csv(index=False))
        f.write("\n")
        f.write(inv_df.to_csv(index=False))
    best_op[
        ["Stored energy [MWh]", "SoC [-]", "Charge [MWh]", "Discharge [MWh]",
         "Day-ahead buy [MWh]", "Day-ahead sell [MWh]",
         "FCR Capacity [MW]", "aFRR Capacity POS [MW]", "aFRR Capacity NEG [MW]"]
    ].to_csv(OUT_DIR / "TechArena_Phase1_Operation.csv")

    print("Fichiers générés dans", OUT_DIR.resolve())
    print(" -", OUT_DIR / "output/TechArena_Phase1_Configuration.csv")
    print(" -", OUT_DIR / "output/TechArena_Phase1_Investment.csv")
    print(" -", OUT_DIR / "output/TechArena_Phase1_Operation.csv")
