import numpy as np
import pandas as pd

from methods.Billing import *

class LUNA2000Battery:
    action = "idle"
    status = "empty"
    last_transaction = None

    def __init__(self, capacity_kwh=4472, power_kw=2236, cycles_max=1.0):
        # Specifications
        self.model = "LUNA2000-4.5MWH-2H1"
        self.capacity_kwh = capacity_kwh
        self.power_kw = power_kw
        self.cycles_max = cycles_max
        
        # State Of Charge (SOC) in kWh
        self.soc_kwh = 0.0
        
        # Realistic operational limits
        self.soc_min = 0.05  # 5% Minimum SOC to avoid degradation
        self.soc_max = 0.95  # 95% Maximum SOC for longevity
        
        # Efficiencies (Yields)
        self.efficiency_charge = 0.92   # 92% d'efficacité en charge
        self.efficiency_discharge = 0.94 # 94% d'efficacité en décharge
        
        # Degradation Factors by Temperature (°C)
        self.temp_current = 25  # Current operating temperature
        self.temp_optimal = 25  # Optimale temperature
        
        # Power curve as a function of SOC
        self.power_derating_low_soc = 0.1   # SOC where the discharge begins to decrease
        self.power_derating_high_soc = 0.9  # SOC where the charge begins to decrease
        
        # maximum C-rate (0.5C according to the specifications)
        self.c_rate_max = 0.5
        
        # Cycle counter for degradation
        self.cycle_count = 0.0
        self.dod_weighted_cycles = 0.0  # Cycles weighted by depth of discharge
        
        # Residual capacity (degradation)
        self.capacity_fade = 1.0  # 1.0 = No degradation, 0.8 = 80% of the remaining capacity
        
        # create billing
        self.billing = Billing()
        
    def get_soc_percentage(self):
        """Retourne le SOC en pourcentage"""
        return (self.soc_kwh / (self.capacity_kwh * self.capacity_fade)) * 100
        
    def get_usable_capacity(self):
        """Capacité utilisable en tenant compte des limites SOC et de la dégradation"""
        total_capacity = self.capacity_kwh * self.capacity_fade
        return total_capacity * (self.soc_max - self.soc_min)

    def get_temperature_factor(self):
        """Facteur de correction pour la température"""
        temp_diff = abs(self.temp_current - self.temp_optimal)
        if self.temp_current < -10:
            return 0.7  # Reduced performance in extreme cold
        elif self.temp_current > 45:
            return 0.8  # Reduced performance in extreme heat
        elif temp_diff <= 10:
            return 1.0
        else:
            return max(0.85, 1.0 - (temp_diff - 10) * 0.01)

    def get_power_limit_charge(self):
        """Limite de puissance en charge selon SOC et température"""
        soc_pct = self.get_soc_percentage() / 100
        temp_factor = self.get_temperature_factor()
        
        # Power reduction when SOC > 90%
        if soc_pct > self.power_derating_high_soc:
            soc_factor = max(0.2, 1.0 - 2 * (soc_pct - self.power_derating_high_soc))
        else:
            soc_factor = 1.0
            
        # Limit C-rate
        max_power_crate = self.capacity_kwh * self.capacity_fade * self.c_rate_max
        
        return min(self.power_kw, max_power_crate) * temp_factor * soc_factor

    def get_power_limit_discharge(self):
        """Limite de puissance en décharge selon SOC et température"""
        soc_pct = self.get_soc_percentage() / 100
        temp_factor = self.get_temperature_factor()
        
        # Power reduxtion when SOC < 10%
        if soc_pct < self.power_derating_low_soc:
            soc_factor = max(0.2, soc_pct / self.power_derating_low_soc)
        else:
            soc_factor = 1.0
            
        # Limite C-rate
        max_power_crate = self.capacity_kwh * self.capacity_fade * self.c_rate_max
        
        return min(self.power_kw, max_power_crate) * temp_factor * soc_factor

    def update_degradation(self, energy_processed, is_charge=True):
        """Met à jour la dégradation basée sur les cycles"""
        # Calculate the DOD (Depth of Discharge) for partial cycle
        dod = energy_processed / (self.capacity_kwh * self.capacity_fade)
        
        # Weighting of the cycle according to depth (deeper cycles = more degradation)
        cycle_weight = 1.0 if dod > 0.8 else 0.5 if dod > 0.5 else 0.2
        
        self.dod_weighted_cycles += dod * cycle_weight
        
        # Calendar degradation (0.05% per 100 equivalent cycles)
        if self.dod_weighted_cycles >= 100:
            cycles_passed = int(self.dod_weighted_cycles / 100)
            self.capacity_fade *= (0.9995 ** cycles_passed)  # 0.05% of loss
            self.dod_weighted_cycles %= 100

    def fcr_capacite(self, price=0, power_kw=None, duration_hours=4.0, temperature_c=25):
        """
        Provides stored energy (FCR capacity discharge)."
        
        "Args:
        price: Selling price of the energy (€/kWh or other unit)
        power_kw: Requested power (None = maximum available power)
        duration_hours: Duration of the discharge
        temperature_c: Ambient temperature
        
        Returns:
        dict: Information about the operation (energy delivered, actual power, cost, etc.)
        """

        self.temp_current = temperature_c

        # Current battery capacity
        current_capacity = self.capacity_kwh * self.capacity_fade
        max_soc_kwh = current_capacity * self.soc_max
        
        if self.soc_kwh <= 0.0:
            return {
                'energy_delivered': 0.0,
                'power_actual': 0.0,
                'soc_final': self.get_soc_percentage(),
                'status': 'Batterie vide',
                'efficiency': 1.0,
                'revenue': 0.0
            }
        
        # Discharge power limit
        power_limit = self.get_power_limit_discharge()
        power_actual = min(power_kw or power_limit, power_limit)
        
       # Energy Requested
        energy_demanded = power_actual * duration_hours
        
        # Limitation by available energy
        energy_available = self.soc_kwh  # all that's left
        energy_delivered = min(energy_demanded, energy_available)
        
        # No losses (efficiency = 100%)
        energy_consumed = energy_delivered
        
        # Average real power
        power_real = energy_delivered / duration_hours if duration_hours > 0 else 0
        
        # SOC update
        # # self.soc_kwh -= energy_delivered
        
        self.update_degradation(energy_delivered, is_charge=False)
        
        # Generated Revenues
        self.last_transaction = self.billing.sell(price/1000, energy_delivered, 30)
    
        return {
            'energy_delivered': energy_delivered,   # kWh supplied to the network
            'energy_consumed': energy_consumed,    # identical since 100% efficient
            'power_actual': power_real,
            'soc_final': self.get_soc_percentage(),
            'power_limit': power_limit,
            'efficiency': 1.0,                     # No losses
            'status': 'Décharge réussie',
            'temperature_factor': self.get_temperature_factor(),
            'revenue': self.last_transaction       # what you earn
        }

    def charge(self, price = 0, power_kw=None, duration_hours=1.0,day=1, intake=False, temperature_c=25):
        """
        Charge the battery with realistic modeling
        
        Args:
            power_kw: Requested power (None = maximum power)
            duration_hours:Charging time in hours
            temperature_c: Room temperature
            
        Returns:
            dict: Information about the operation (charged energy, actual power, etc.)
        """
        self.temp_current = temperature_c

        # Preliminary Checks
        current_capacity = self.capacity_kwh * self.capacity_fade
        max_soc_kwh = current_capacity * self.soc_max
        
        if self.soc_kwh >= max_soc_kwh:
            self.status = "full"
            return {
                'energy_charged': 0.0,
                'power_actual': 0.0,
                'soc_final': self.get_soc_percentage(),
                'status': 'Batterie déjà pleine',
                'efficiency': 0.0
            }
        
        # Maximum power according to battery status
        power_limit = self.get_power_limit_charge()
        power_actual = min(power_kw or power_limit, power_limit)
        
        # Requested gross energy
        energy_demanded = power_actual * duration_hours
        
        # Net storable energy (after efficiency)
        energy_net = energy_demanded * self.efficiency_charge
        
        # Limitation by available space
        space_available = max_soc_kwh - self.soc_kwh
        energy_stored = min(energy_net, space_available)
        
        # Actual energy consumed from the grid
        energy_consumed = energy_stored / self.efficiency_charge
        
        # Average Real Power
        power_real = energy_consumed / duration_hours if duration_hours > 0 else 0
        
        # SOC Update
        self.soc_kwh += energy_stored
        
        # Update on degradation
        self.update_degradation(energy_stored, is_charge=True)
        
        # Cost of the load
        if intake == True:
            self.last_transaction = self.billing.sell(price/1000,energy_consumed,day) # on vend car c'est une absorbtion de charge
        else:
            self.last_transaction = self.billing.buy(price/1000,energy_consumed,day)

        if self.soc_kwh >= self.capacity_kwh-(self.capacity_kwh*.06):
            self.status = "full"
        else:
            self.status = "process"
        return {
            'energy_charged': energy_stored,
            'energy_consumed': energy_consumed,
            'power_actual': power_real,
            'soc_final': self.get_soc_percentage(),
            'power_limit': power_limit,
            'efficiency': self.efficiency_charge,
            'status': 'Charge réussie',
            'temperature_factor': self.get_temperature_factor()
        }

    def discharge(self, price = 0, power_kw=None, duration_hours=1.0, day=1,temperature_c=25):
        """
        Discharge the battery with realistic modeling
        
        Args:
            power_kw: Requested power (None = maximum power)
            duration_hours:Discharge duration in hours
            temperature_c: Room temperature
            
        Returns:
            dict: Operation information (energy supplied, actual power, etc.)
        """
        self.temp_current = temperature_c
        
        # Preliminary checks
        current_capacity = self.capacity_kwh * self.capacity_fade
        min_soc_kwh = current_capacity * self.soc_min
        
        if self.soc_kwh <= min_soc_kwh:
            self.status = "empty"  
            return {
                'energy_discharged': 0.0,
                'power_actual': 0.0,
                'soc_final': self.get_soc_percentage(),
                'status': 'Batterie déjà vide (SOC minimum atteint)',
                'efficiency': 0.0
            }
        
        # Power limit according to battery status
        power_limit = self.get_power_limit_discharge()
        power_actual = min(power_kw or power_limit, power_limit)
        
        # Requested energy
        energy_demanded = power_actual * duration_hours
        
        # Energy available in the battery
        energy_available = self.soc_kwh - min_soc_kwh
        
        # Consumed internal energy (before efficiency)
        energy_internal = min(energy_demanded / self.efficiency_discharge, energy_available)
        
        # Energy actually supplied to the grid
        energy_delivered = energy_internal * self.efficiency_discharge
        
        # Average real power
        power_real = energy_delivered / duration_hours if duration_hours > 0 else 0
        
        # Update on the SOC
        self.soc_kwh -= energy_internal
        
        # Update on the degradation
        self.update_degradation(energy_internal, is_charge=False)
        
        # Load cost
        self.last_transaction = self.billing.sell(price/1000,energy_delivered,day)
         
        if self.soc_kwh <= self.capacity_kwh-(self.capacity_kwh*.96):
            self.status = "empty"       
        else:
            self.status = "process"

        return {
            'energy_discharged': energy_delivered,
            'energy_internal': energy_internal,
            'power_actual': power_real,
            'soc_final': self.get_soc_percentage(),
            'power_limit': power_limit,
            'efficiency': self.efficiency_discharge,
            'status': 'Décharge réussie',
            'temperature_factor': self.get_temperature_factor()
        }

    def get_status(self):
        return self.status
    
    def set_status(self,status):
        self.status = status
    
    def get_action(self):
        return self.action
    
    def set_action(self,action):
        self.action = action

    # function that allows updating the battery (timestamp)
    def update(self):
        pass

    def simulate_battery_day(self, prices):
        soc_history = []
        action_history = []
        revenue_history = []
        cycles = 0
        last_action = self.get_action()
        status_history = []

        # troughs/peaks
        low_thresh = np.percentile(prices, 25)
        high_thresh = np.percentile(prices, 75)
        
        for price in prices:
            if cycles < self.cycles_max:
                if price <= low_thresh and self.get_status() != "full":
                    # Charge
                    bat_info_charge = self.charge(price,None,1.0,30)
                    print(self.last_transaction)
                    revenue = self.last_transaction.get("amount")
                    self.set_action("charge")
                    if bat_info_charge.get('status') == "Batterie déjà pleine" or self.get_status() == "full":
                        cycles += 0.5
                    else:
                        self.set_status("process")
                elif price >= high_thresh and self.get_status() != "empty":
                    # Discharge
                    bat_info_charge = self.discharge(price,None,1.0,30)
                    print(self.last_transaction)
                    revenue = self.last_transaction.get("amount")
                    self.set_action("discharge")
                    if bat_info_charge.get('status') == "Batterie déjà vide (SOC minimum atteint)" or self.get_status() == "empty":
                        cycles += 0.5
                    else:
                        self.set_status("process")
                else:
                    self.set_action("idle")
                    revenue = 0
            else:
                revenue = 0
                self.set_action("idle")

            soc_history.append(self.soc_kwh)
            action_history.append(self.get_action())
            last_action = self.get_action()
            revenue_history.append(revenue)
            status_history.append(self.get_status())
        
        df = pd.DataFrame({
            "Hour": range(24),
            "Price": prices,
            "SoC": soc_history,
            "Action": action_history,
            "Status": status_history,
            "Revenue": revenue_history
        })
        return df

    def simulate_battery_fcr_day(self, prices):
        """
        Simulate a day participating in the FCR capacity market.

        Args:
            prices: FCR hourly price list (€/MW/h or €/kW/h)
            power_kw: Power made available each hour (kW)
        
        Returns:
            pd.DataFrame: Simulation history (price, SoC, action, revenues)
        """
        soc_history = []
        action_history = []
        revenue_history = []
        status_history = []

        self.set_status("ready")
        self.set_action("idle")

        for price in prices:
            # Check if the battery can supply the required power
            if self.soc_kwh >= self.power_kw:  
                # Here, no actual discharge (zero rate), just a reservation
                fcr_info = self.fcr_capacite(price=price, power_kw=self.power_kw, duration_hours=1.0)
                
                self.set_action("reserve")
                revenue = fcr_info.get("revenue", 0.0)
                
            else:
                # Battery too low to be available
                self.set_action("idle")
                revenue = 0.0
            
            soc_history.append(self.soc_kwh)
            action_history.append(self.get_action())
            status_history.append(self.get_status())
            revenue_history.append(revenue)
        
        df = pd.DataFrame({
            "Hour": range(len(prices)),
            "Price": prices,
            "SoC": soc_history,
            "Action": action_history,
            "Revenue": revenue_history
        })
        
        return df

    def simulate_battery_afrr_day(self, prices_pos, prices_neg):
        soc_history = []
        action_history = []
        status_history = []
        cycles = 0
        revenue_history = []
        self.set_action("idle")
        for d in range(0,len(prices_pos),6):
            # thresholds to distinguish "high price" and "low price"
            prices_day_pos = prices_pos[(d):d+6]
            prices_day_neg = prices_neg[(d):d+6]
            high_thresh_pos = np.percentile(prices_day_pos, 75)  # POS → discharge
            high_thresh_neg = np.percentile(prices_day_neg, 75)  # NEG → charge

            for pos, neg in zip(prices_day_pos, prices_day_neg):
                if cycles < self.cycles_max:
                    # If POS price is high → it is advantageous to be full in order to unload
                    if pos >= high_thresh_pos and self.get_status() != "full":
                        bat_info_charge = self.charge(pos,None,4,1,True)
                        print(self.last_transaction)
                        revenue = self.last_transaction.get("amount")
                        self.set_action("charge")
                        if bat_info_charge.get('status') == "Batterie déjà pleine" or self.get_status() == "full":
                            cycles += 0.5

                    # If NEG price is high → it is worthwhile to be empty to load
                    elif neg >= high_thresh_neg and self.get_status() != "empty":
                        bat_info_discharge = self.discharge(neg,None,4,1)
                        print(self.last_transaction)
                        revenue = self.last_transaction.get("amount")
                        self.set_action("discharge")
                        if bat_info_discharge.get('status') == "Batterie déjà vide (SOC minimum atteint)" or self.get_status() == "empty":
                            cycles += 0.5

                    else:
                        self.set_action("idle")
                        revenue = 0
                else:
                    self.set_action("idle")
                    revenue = 0

                soc_history.append(self.soc_kwh)
                action_history.append(self.get_action())
                status_history.append(self.get_status())
                revenue_history.append(revenue)
            cycles = 0
        print("Revenue history " + str(revenue_history))
        df = pd.DataFrame({
            "Hour": range(len(prices_pos)),
            "Price_Pos": prices_pos,
            "Price_Neg": prices_neg,
            "SoC": soc_history,
            "Action": action_history,
            "Status": status_history,
            "Revenue": revenue_history
        })
        
        return df
