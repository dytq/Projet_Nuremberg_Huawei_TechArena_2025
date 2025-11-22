import os
import numpy as np
import pandas as pd

# Helper  classes
from methods.LUNA2000Battery import *
from methods.XLSManager import *
from methods.MarketManager import *
from methods.Solver import *

#############################################
## Experimental Optimizer 🦆 (using pyomo) ##
#############################################

# backup of log data of the minimization function
def save_dataframe(df, market_name="default", file_format="csv"):
    # Create ouptput folder
    output_dir = os.path.join("output", "experimental", market_name)
    os.makedirs(output_dir, exist_ok=True)

    # Define file path
    if file_format == "csv":
        filename = os.path.join(output_dir, f"{market_name}_data.csv")
        df.to_csv(filename, index=False, encoding="utf-8")
    elif file_format == "excel":
        filename = os.path.join(output_dir, f"{market_name}_data.xlsx")
        df.to_excel(filename, index=False, engine="openpyxl")
    else:
        raise ValueError("Format non supporté : choisis 'csv' ou 'excel'")

    print(f" DataFrame sauvegardé dans : {filename}")

def experimental_test_solver():
    
    my_xls_sheet = xls_sheet("input/TechArena2025_data.xlsx")

    # load market data
    DE_market = Country_Market(
        "DE",
        DA(my_xls_sheet.get_da_prices_dict("DE_LU")),
        FCR(my_xls_sheet.get_fcr_prices_dict("DE")),
        AFRR(my_xls_sheet.get_afrr_prices_dict("DE")),
        8.3,
        2.0)
   
    AT_market = Country_Market(
        "AT",
        DA(my_xls_sheet.get_da_prices_dict("AT")),
        FCR(my_xls_sheet.get_fcr_prices_dict("AT")),
        AFRR(my_xls_sheet.get_afrr_prices_dict("AT")),
        8.3,
        3.30)

    CH_market = Country_Market(
        "CH",
        DA(my_xls_sheet.get_da_prices_dict("CH")),
        FCR(my_xls_sheet.get_fcr_prices_dict("CH")),
        AFRR(my_xls_sheet.get_afrr_prices_dict("CH")),
        8.3,
        0.10)

    CZ_market = Country_Market(
        "CZ",
        DA(my_xls_sheet.get_da_prices_dict("CZ")),
        FCR(my_xls_sheet.get_fcr_prices_dict("CZ")),
        AFRR(my_xls_sheet.get_afrr_prices_dict("CZ")),
        12,
        2.90)

    HU_market = Country_Market(
        "HU",
        DA(my_xls_sheet.get_da_prices_dict("HU")),
        FCR(my_xls_sheet.get_fcr_prices_dict("HU")),
        AFRR(my_xls_sheet.get_afrr_prices_dict("HU")),
        15,
        4.60)

    print("Market data are loaded successfully")

    # Create a battery instance
    battery1 = LUNA2000Battery()
    da = DE_market.get_da()
    fcr = DE_market.get_fcr()
    afrr = DE_market.get_afrr()
    
    # Initialize data (For DE market)
    my_solver = Solver(battery1,DE_market.get_da_prices(),DE_market.get_fcr_prices(),DE_market.get_afrr_prices('Pos'),DE_market.get_afrr_prices('Neg'))
    # Resolve the problem
    my_solver.solve()
    # Display the result
    df_result = my_solver.print_result()
    save_dataframe(df_result,"DE_market_data")
    
    print(" All output files generated successfully!")


def run ():
    experimental_test_solver()
