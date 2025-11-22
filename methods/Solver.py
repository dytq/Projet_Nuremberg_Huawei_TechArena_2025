import pyomo.environ as pyo
import pandas as pd
import numpy as np

class Solver:
    n_quarters = 96
    dt = 0.25       # heures (15 min)
    dt_block = 4.0  # heures (4h)

    eta_ch = 0.95  # ignore
    eta_dis = 0.95 # ignore

    model = pyo.ConcreteModel()

    def __init__(self, battery, market_da_prices, market_fcr_prices, market_afrr_prices_pos, market_afrr_prices_neg, c_rate= 0.25, daily_cycle= 1.0):
        # init battery s parameters:
        self.C_rate = battery.c_rate_max # per hour
        self.cycles_max = battery.cycles_max
        self.Pnom = battery.power_kw / 1000
        self.P = battery.c_rate_max * self.Pnom
        self.Cap_nom = battery.capacity_kwh / 1000
        self.E_step_15 = self.P * 0.25

        # mes listes
        da_lst = list(market_da_prices.values())
        fcr_lst = list(market_fcr_prices.values())
        afrr_pos_lst = list(market_afrr_prices_pos.values())
        afrr_neg_lst = list(market_afrr_prices_neg.values())

        # init market : c_*
        self.c_DA = da_lst[0:96*1]
        self.c_FCR_block = fcr_lst[0:6*1]
        self.c_aFRR_pos_block = afrr_pos_lst[0:6*1]
        self.c_aFRR_neg_block = afrr_neg_lst[0:6*1]

        # number of time
        self.model.T = pyo.RangeSet(0, len(self.c_DA)-1)
        self.model.B = pyo.RangeSet(0, len(self.c_FCR_block)-1)
        n_steps = len(self.c_DA)+1   # nombre de pas
        self.steps_per_day = int(24 / self.dt) # ex: 24h / 0.25h = 96
        n_days = n_steps // self.steps_per_day
        self.model.D = pyo.RangeSet(0, n_days-1)
        
        # Variables pour ne pas avoir la charge et la décharge en même temps
        self.model.u_ch  = pyo.Var(self.model.T, within=pyo.Binary)
        self.model.u_dis = pyo.Var(self.model.T, within=pyo.Binary)
        
        # Variables par pas de temps
        self.model.Pch   = pyo.Var(self.model.T, bounds=(0, self.P*self.C_rate))        # MW
        self.model.Pdis  = pyo.Var(self.model.T, bounds=(0, self.P*self.C_rate))        # MW
        self.model.SoC   = pyo.Var(self.model.T, bounds=(0, 1))      # pourcentage
        
        self.model.P_DA  = pyo.Var(self.model.T, bounds=(-self.Pnom,self.Pnom))      
        self.model.R_FCR = pyo.Var(self.model.B, bounds=(0,self.Pnom))    
        self.model.R_aFRR_pos = pyo.Var(self.model.B, bounds=(0, self.P*self.C_rate))
        self.model.R_aFRR_neg = pyo.Var(self.model.B, bounds=(0, self.P*self.C_rate))

        # init model:
        # Objective function
        self.model.obj = pyo.Objective(rule=lambda m: self.objective_rule(m), sense=pyo.maximize)

        # Constraints
        self.model.fcr_rule = pyo.Constraint(self.model.B,rule=lambda m,b:self.fcr_rule(m,b))
        self.model.soc_cons = pyo.Constraint(self.model.T,rule=lambda m,t: self.soc_rule(m,t))
        self.model.afrr_pos = pyo.Constraint(self.model.B, rule=lambda m,b: self.afrr_pos_rule(m,b))
        self.model.afrr_neg = pyo.Constraint(self.model.B, rule=lambda m,b: self.afrr_neg_rule(m,b))
        self.model.fcr_availability_rule = pyo.Constraint(self.model.T, rule=lambda m,t: self.fcr_availability_rule(m,t))
        self.model.no_simul = pyo.Constraint(self.model.T, rule=lambda m,t: self.no_simul_rule(m,t))
        self.model.bind_ch = pyo.Constraint(self.model.T, rule=lambda m,t: self.bind_ch_rule(m,t))
        self.model.crate_dis = pyo.Constraint(self.model.T, rule=lambda m,t: self.crate_dis_rule(m,t))
        self.model.bind_dis = pyo.Constraint(self.model.T, rule=lambda m,t: self.bind_dis_rule(m,t))
        self.model.crate_ch = pyo.Constraint(self.model.T, rule=lambda m,t: self.crate_ch_rule(m,t))
        self.model.power_cap = pyo.Constraint(self.model.T, rule=lambda m,t: self.power_cap_rule(m,t))
        self.model.cycles_rule_day = pyo.Constraint(self.model.D, rule=lambda m,d: self.cycles_rule_day(m,d))
               
    def objective_rule(self,m):
        # DA revenue (sum over quarters)
        term_DA = sum(self.c_DA[t] * (m.Pdis[t] - m.Pch[t]) * self.dt for t in m.T)

        # revenue per block (multiply price by block duration)
        term_FCR = sum(self.c_FCR_block[b] * m.R_FCR[b] * self.dt_block for b in m.B)
        term_aFRR = sum((self.c_aFRR_pos_block[b] * m.R_aFRR_pos[b] +
                         self.c_aFRR_neg_block[b] * m.R_aFRR_neg[b]) * self.dt_block
                        for b in m.B)

        return term_DA + term_FCR + term_aFRR

    def fcr_rule(self,m,b):
        return m.R_FCR[b] <= m.SoC[b] * self.Cap_nom

    def fcr_availability_rule(self, m, t):
        b = int(t // 16)  # bloc correspondant
        return m.R_FCR[b] <= (1 - m.u_ch[t] - m.u_dis[t]) * self.Pnom
    
    def afrr_pos_rule(self, m, b):
        t_end = min((b+1)*16 - 1, max(m.T))
        return m.R_aFRR_pos[b] * self.dt_block <= m.SoC[t_end] * self.Cap_nom
    
    def afrr_neg_rule(self, m, b):
        t_end = min((b+1)*16 - 1, max(m.T))
        return m.R_aFRR_neg[b] * self.dt_block <= (1 - m.SoC[t_end]) * self.Cap_nom

    # SoC dynamics
    def soc_rule(self, m, t):
        if t == 0:
            SoC0 = 0  # SoC initial
            return m.SoC[t] == SoC0
        else:
            b = int(t // 16)
            return m.SoC[t] == m.SoC[t-1] + (
                (m.Pch[t] - m.Pdis[t]) * self.dt
                + (m.R_aFRR_neg[b] * self.dt_block)   # réserve négative = charge
                - (m.R_aFRR_pos[b] * self.dt_block)   # réserve positive = décharge
            ) / self.Cap_nom


    # No simultaneous charge & discharge
    def no_simul_rule(self, m, t):
        return m.u_ch[t] + m.u_dis[t] <= 1

    def bind_ch_rule(self, m, t):
        b = int(t // 16)  # bloc 4h correspondant
        return m.Pch[t] + m.R_aFRR_neg[b] <= self.Pnom * m.u_ch[t]

    def bind_dis_rule(self, m, t):
        b = int(t // 16)
        return m.Pdis[t] + m.R_aFRR_pos[b] <= self.Pnom * m.u_dis[t]

    # C-rate limit (per-step)
    def crate_ch_rule(self, m, t):
        b = int(t // 16)  # bloc 4h correspondant
        return m.Pch[t] + m.R_aFRR_neg[b] <= self.P 
    
    def crate_dis_rule(self, m, t):
        b = int(t // 16)  # bloc 4h correspondant
        return m.Pdis[t] + m.R_aFRR_pos[b] <= self.P 

    # Power capacity (reservations + operation) <= Pn
    def power_cap_rule(self, m, t):
        # find block index for this quarter
        b = int(t // 16)
        return m.Pdis[t] + m.Pch[t] + m.R_FCR[b] + m.R_aFRR_pos[b] + m.R_aFRR_neg[b] <= self.Pnom

    # Daily cycles limit (approx. throughput)
    def cycles_rule_day(self,m, d):
        start = d * self.steps_per_day
        end   = (d+1) * self.steps_per_day - 1

        if end > max(m.T):
            end = max(m.T)

        return sum((m.Pch[t] + m.Pdis[t]) * self.dt 
                for t in range(start, end+1)) <= self.cycles_max * self.Cap_nom

    def solve(self):
        solver = pyo.SolverFactory('highs')   # ou 'gurobi'
        res = solver.solve(self.model, tee=False)
        print(res.solver.status, res.solver.termination_condition)
    
    def print_result(self):
        obj_val = pyo.value(self.model.obj)
        print("Objective (EUR or unité):", obj_val)
    
        # Créer des listes pour chaque variable
        time_steps = []
        Pch_values = []
        Pdis_values = []
        SoC_values = []
        P_DA_values = []
        R_FCR_values = []
        R_AFRR_values_pos = []
        R_AFRR_values_neg = []

        for t in self.model.T:
            time_steps.append(t)
            Pch_values.append(pyo.value(self.model.Pch[t]))
            Pdis_values.append(pyo.value(self.model.Pdis[t]))
            SoC_values.append(pyo.value(self.model.SoC[t]))
            if t%16 == 0 and t//16 < len(self.model.R_FCR):
                R_FCR_values.append(pyo.value(self.model.R_FCR[t//16]))
                R_AFRR_values_pos.append(pyo.value(self.model.R_aFRR_pos[t//16]))
                R_AFRR_values_neg.append(pyo.value(self.model.R_aFRR_neg[t//16]))
            else:
                R_FCR_values.append(0)
                R_AFRR_values_pos.append(0)
                R_AFRR_values_neg.append(0)

        # Créer le DataFrame
        df_results = pd.DataFrame({
            'time_step': time_steps,
            'P_charge_MW': Pch_values,
            'P_discharge_MW': Pdis_values,
            'SoC': SoC_values,
            'R_FCR': R_FCR_values,
            'R_AFRR_neg': R_AFRR_values_neg,
            'R_AFRR_pos': R_AFRR_values_pos
        })
        
        return df_results