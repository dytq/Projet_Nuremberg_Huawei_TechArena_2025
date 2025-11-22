import pandas as pd 

class xls_sheet:
    xls_file_name = ""

    # all sheets
    da_prices_sheet = None
    fcr_prices_sheet = None
    afrr_prices_sheet = None

    da_sheet_name = "Day-ahead prices"
    fcr_sheet_name = "FCR prices"
    afrr_sheet_name = "aFRR capacity prices"

    def __init__(self, xls_file_name):
        self.xls_file_name = xls_file_name
        # import all sheets (skiprows=1 to skip the title)
        self.da_prices_sheet = pd.read_excel(xls_file_name, sheet_name=self.da_sheet_name, skiprows=1)
        self.fcr_prices_sheet = pd.read_excel(xls_file_name, sheet_name=self.fcr_sheet_name, skiprows=1)
        self.afrr_prices_sheet = pd.read_excel(xls_file_name, sheet_name=self.afrr_sheet_name, skiprows=1, header=[0, 1], index_col=0, decimal=',')
        print("All input sheets are imported successfully")
    
    def _normalize_timestamp(self, timestamp):
        """Normalize a timestamp by removing the seconds and microseconds"""
        return timestamp.replace(second=0, microsecond=0)

    def get_da_prices_dict(self, country):
        if country not in self.da_prices_sheet.columns:
            raise ValueError(f"The country  '{country}' does not exist in the columns  ({list(self.da_prices_sheet.columns)})")
        
        timestamps = self.da_prices_sheet.iloc[:, 0].tolist()  # First column = timestamps
        prices = self.da_prices_sheet[country].tolist()
        normalized_timestamps = [self._normalize_timestamp(ts) for ts in timestamps]
        return dict(zip(normalized_timestamps, prices))

    def get_fcr_prices_dict(self, country):
        if country not in self.fcr_prices_sheet.columns:
            raise ValueError(f"Le pays '{country}' n'existe pas dans les colonnes ({list(self.fcr_prices_sheet.columns)})")
        
        timestamps = self.fcr_prices_sheet.iloc[:, 0].tolist()  # First column = timestamps
        prices = self.fcr_prices_sheet[country].tolist()
        normalized_timestamps = [self._normalize_timestamp(ts) for ts in timestamps]
        return dict(zip(normalized_timestamps, prices))

    def get_afrr_prices_dict(self, country):
        if country not in self.afrr_prices_sheet.columns.get_level_values(0):
            raise ValueError(
                f"The country '{country}' does not exist in the columns ({list(self.afrr_prices_sheet.columns.get_level_values(0))})"
            )
        
        timestamps = self.afrr_prices_sheet.index.tolist()  # Index = timestamps
        pos_prices = self.afrr_prices_sheet[country]['Pos'].tolist()
        neg_prices = self.afrr_prices_sheet[country]['Neg'].tolist()
        
        normalized_timestamps = [self._normalize_timestamp(ts) for ts in timestamps]
        return {
            'Pos': dict(zip(timestamps, pos_prices)),
            'Neg': dict(zip(normalized_timestamps, neg_prices))
        }