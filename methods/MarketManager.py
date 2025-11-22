import pandas as pd

class DA:
    prices = {}

    def __init__(self,DA_prices):
        self.prices = DA_prices
    
    def get_daily_prices(self, date):
        hourly_totals = {h: [] for h in range(24)}

        # Parcourir toutes les données du mois
        for k, price in self.prices.items():
            key_str = str(k)
            if key_str.startswith(date):
                try:
                    # Extraire l'heure de manière plus robuste
                    if ' ' in key_str or ':' in key_str:
                        # Format avec espace ou deux-points (YYYY-MM-DD HH:MM:SS)
                        hour_part = key_str.split()[1] if ' ' in key_str else key_str
                        hour = int(hour_part.split(':')[0])
                    else:
                        # Format timestamp ou autre format
                        hour = pd.to_datetime(key_str).hour
                    
                    if 0 <= hour <= 23:
                        hourly_totals[hour].append(price)
                except (ValueError, IndexError):
                    # Gérer les formats de date invalides
                    continue

        # Calculer la moyenne pour chaque heure
        hourly_avg = {}
        for hour in range(24):
            if hourly_totals[hour]:
                hourly_avg[hour] = sum(hourly_totals[hour]) / len(hourly_totals[hour])
            else:
                hourly_avg[hour] = None  # Pas de données pour cette heure

        # Créer la Series pandas avec un index datetime correct
        hours = list(hourly_avg.keys())
        dates = [f"{date} {hour:02d}:00:00" for hour in hours]
        
        return pd.Series([hourly_avg[h] for h in hours], 
                    index=pd.to_datetime(dates))

class FCR:
    prices = {}

    def __init__(self,FCR_prices):
        self.prices = FCR_prices
    
    def get_daily_prices(self, date):
        hourly_totals = {h: [] for h in range(24)}

        # Parcourir toutes les données du mois
        for k, price in self.prices.items():
            key_str = str(k)
            if key_str.startswith(date):
                try:
                    # Extraire l'heure de manière plus robuste
                    if ' ' in key_str or ':' in key_str:
                        # Format avec espace ou deux-points (YYYY-MM-DD HH:MM:SS)
                        hour_part = key_str.split()[1] if ' ' in key_str else key_str
                        hour = int(hour_part.split(':')[0])
                    else:
                        # Format timestamp ou autre format
                        hour = pd.to_datetime(key_str).hour
                    
                    if 0 <= hour <= 23:
                        hourly_totals[hour].append(price)
                except (ValueError, IndexError):
                    # Gérer les formats de date invalides
                    continue

        # Calculer la moyenne pour chaque heure
        hourly_avg = {}
        for hour in range(24):
            if hourly_totals[hour]:
                hourly_avg[hour] = sum(hourly_totals[hour]) / len(hourly_totals[hour])
            else:
                pass # Pas de données pour cette heure

        # Créer la Series pandas avec un index datetime correct
        hours = list(hourly_avg.keys())
        dates = [f"{date} {hour:02d}:00:00" for hour in hours]
        
        return pd.Series([hourly_avg[h] for h in hours], 
                    index=pd.to_datetime(dates))

class AFRR:
    prices = {}

    def __init__(self,AFRR_prices):
        self.prices = AFRR_prices
    
    def get_daily_prices(self, date):
        hourly_totals_pos = {h: [] for h in range(24)}
        hourly_totals_neg = {h: [] for h in range(24)}

        # Parcourir les prix positifs
        for k, price in self.prices['Pos'].items():
            key_str = str(k)
            if key_str.startswith(date):
                try:
                    if ' ' in key_str or ':' in key_str:
                        hour_part = key_str.split()[1] if ' ' in key_str else key_str
                        hour = int(hour_part.split(':')[0])
                    else:
                        hour = pd.to_datetime(key_str).hour
                    
                    if 0 <= hour <= 23:
                        hourly_totals_pos[hour].append(price)
                except (ValueError, IndexError):
                    continue

        # Parcourir les prix négatifs
        for k, price in self.prices['Neg'].items():
            key_str = str(k)
            if key_str.startswith(date):
                try:
                    if ' ' in key_str or ':' in key_str:
                        hour_part = key_str.split()[1] if ' ' in key_str else key_str
                        hour = int(hour_part.split(':')[0])
                    else:
                        hour = pd.to_datetime(key_str).hour
                    
                    if 0 <= hour <= 23:
                        hourly_totals_neg[hour].append(price)
                except (ValueError, IndexError):
                    continue

        # Calcul des moyennes par heure
        hourly_avg_pos = {}
        hourly_avg_neg = {}
        for hour in range(24):
            if hourly_totals_pos[hour]:
                hourly_avg_pos[hour] = sum(hourly_totals_pos[hour]) / len(hourly_totals_pos[hour])
            if hourly_totals_neg[hour]:
                hourly_avg_neg[hour] = sum(hourly_totals_neg[hour]) / len(hourly_totals_neg[hour])

        # Construire les pandas Series avec un index datetime correct
        hours = sorted(set(list(hourly_avg_pos.keys()) + list(hourly_avg_neg.keys())))
        dates = [f"{date} {hour:02d}:00:00" for hour in hours]
        
        result = pd.DataFrame({
            "positive": [hourly_avg_pos.get(h, None) for h in hours],
            "negative": [hourly_avg_neg.get(h, None) for h in hours],
        }, index=pd.to_datetime(dates))
        
        return {
            "positive": pd.Series([hourly_avg_pos.get(h, None) for h in hours], index=pd.to_datetime(dates)),
            "negative": pd.Series([hourly_avg_neg.get(h, None) for h in hours], index=pd.to_datetime(dates))   
        }
    
    def get_daily_prices_per_month(self,date):        
        return result
    
class Country_Market:
    country = "Fr"

    da = None
    fcr = None
    afrr = None

    waac = 0.0
    inflation_rate = 0.0
    
    def __init__(self,country,da,fcr,afrr,waac,inflation_rate):
        self.country = country

        self.da = da
        self.fcr = fcr
        self. afrr = afrr

        self.waac = waac
        self.inflation_rate = inflation_rate
    
    def get_da_prices(self):
        return self.da.prices
    
    def get_da(self):
        return self.da
    
    def get_fcr(self):
        return self.fcr

    def get_afrr(self):
        return self.afrr

    def get_fcr_prices(self):
        return self.fcr.prices

    def get_afrr_prices(self,price_type):
        if price_type == "Neg":
            return self.afrr.prices['Neg']
        if price_type == "Pos":
            return self.afrr.prices['Pos']
        # TODO: raise error 
        return None