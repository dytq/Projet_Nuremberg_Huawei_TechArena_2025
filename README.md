# TechArena 2025 – EMS Battery Optimizer (Team Master Poulet)

# Last Update 
To run the program, the input data file (../input/TechArena2025_data.xlsx) is required. To obtain it, please contact the owner of the file.

## **Description**
This project was developed as part of the **Huawei TechArena 2025 (Nuremberg)** competition.  
The objective is to design an **Energy Management System (EMS)** to optimize the operation of a battery energy storage system (**BESS**) connected to the power grid and participating in different markets:

- **Day-Ahead (DA)**: energy arbitrage (buy low, sell high).  
- **Frequency Containment Reserve (FCR)**: ancillary service for frequency stabilization (4h).  
- **Automatic Frequency Restoration Reserve (aFRR)**: secondary reserve (Pos/Neg).

The code produces three output files:  
1. **TechArena_Phase1_Configuration.csv** : tested configurations (C-rate, cycles, ROI).  
2. **TechArena_Phase1_Investment.csv** : financial analysis (CAPEX, OPEX, annualized ROI).  
3. **TechArena_Phase1_Operation.csv** : operational trajectory (SoC, charge/discharge, market participation).




## **Project Structure**

For this project, we have implemented two different approaches : The heuristic method and an experimental MIP optimization algorithm

### **The Heuristic method**


#### **1. General principle** 
The battery generates revenues by:
- **charging (buying)** when Day-Ahead (DA) market prices are low,  
- **discharging (selling)** when DA prices are high,  
- while respecting the physical constraints of the BESS (capacity, C-rate, SOC limits).

In addition, a portion of the battery power is **reserved** for ancillary services:
- **FCR (Frequency Containment Reserve)**: remuneration based on available MW every 4h,  
- **aFRR (automatic Frequency Restoration Reserve)**: remuneration for upward (Pos) and downward (Neg) capacity, also in 4h blocks.

#### **2. Strategy** ####
The year is splitted into days ans we pick the lowest-price slots of the day for the charging intervals and the highest-price slots of the day.for discharging intervals. After that, we apply physical constraints such as :
   - Charging/discharging limited by `puissance_max`,  
   - SOC must remain between `SOC_min` and `SOC_max`,  
   - Round-trip efficiency (≈ 90%) is enforced.
To obtain the total profit, we compute the day-ahead revenues + FCR and aFRR revenues. 

#### **3. Advantages and limitations** ####
✅ Advantages:
- Very fast to compute (runs on a laptop in seconds).  
- Intuitive and easy to explain.  
- Provides a realistic estimate of BESS potential.  

⚠️ Limitations:
- Does not guarantee global optimality.  
- Does not capture market uncertainty.  
- Simplified allocation between DA, FCR, and aFRR (fixed share).  

#### **4. Scripts** ####
Inside the `heuristic_method` folder, we only need :
- `main.py` : main script (simulation and CSV generation).

The results are stored inside the `output` folder and the data used are stored inside the `input` folder


#### **5. Call the method**  
Use
 ```bash
python main.py
```



### **The Mixed-Integer Programming (MIP) Method**

#### **1. General principle** 
The optimization problem is formulated as a **Mixed-Integer Linear Program (MILP)** using **Pyomo**.  
The goal is to **maximize yearly revenues** from:
- **Day-Ahead (DA) trading**: buy energy when prices are low, sell when prices are high,  
- **Ancillary services**: FCR and aFRR capacity revenues (4h blocks).

The novelty of the MIP approach is that it considers **all timesteps simultaneously**, and uses **binary variables** to prevent simultaneous charging and discharging.

#### **2. Strategy**
The model is built with:
- **Decision variables**:
  - `Pch(t)` = charging power at timestep *t*,  
  - `Pdis(t)` = discharging power at timestep *t*,  
  - `SoC(t)` = state of charge,  
  - `u_ch(t), u_dis(t)` = binary on/off variables (charging or discharging).  

- **Constraints**:
  - SOC dynamics:  
    $$
    SOC(t+1) = SOC(t) + \eta_{ch} P_{ch}(t)\Delta t - \frac{1}{\eta_{dis}} P_{dis}(t)\Delta t
    $$
  - SOC bounds: $$ SOC_{min} \leq SOC(t) \leq SOC_{max} $$  
  - Power limits: $$ 0 \leq P_{ch}(t) \leq P_{max} \cdot u_{ch}(t) $$  
  - No simultaneous charging/discharging: $$ u_{ch}(t) + u_{dis}(t) \leq 1 $$  

- **Objective function**:
  $$
  \max \sum_t \Big( P_{dis}(t) \cdot price(t) - P_{ch}(t) \cdot price(t) \Big)\Delta t + Revenues_{FCR} + Revenues_{aFRR}
  $$
  
  
For this method, we did not generate the csv files due to the heavy computational time. We have decided to generate a simple prompt using the DE market data for 1 day. The output is an approximation of the maximun profit that can be earned for a determined configuration.

#### **3. Advantages and limitations**
✅ Advantages:
- Guarantees a **globally optimal schedule** under given assumptions,  
- Explicitly handles binary decisions (charge/discharge/idle),  
- Flexible framework (can include more markets, degradation costs, uncertainty).

⚠️ Limitations:
- Computationally heavy: solving a full year with 96 intervals/day can take **minutes to hours**,  
- Requires a solver (e.g., GLPK, CBC, Gurobi),  
- Sensitive to data quality (NaNs or missing prices must be cleaned).

#### **4. Scripts**
Inside the `mip_method` folder, we only need:
- `Solver.py` : main Pyomo model (definition, constraints, solver call).  
- `main.py` : script that loads the input, runs the model, and exports results.

**Input data processing**
- `LUNA2000Battery.py` : battery model (capacity, SOC, efficiencies).  
- `XLSManager.py` : Excel data management (DA, FCR, aFRR prices).  
- `MarketManager.py` : market classes for DA, FCR, aFRR.  
- `input/TechArena2025_data.xlsx` : competition dataset.  



#### **5. Call the method**  
Use
 ```bash
python main.py optimize
```



### **Dependencies**
- `requirements.txt` contains the external packages:  
  - `pyomo`, `pandas`, `numpy`, `scipy`, `openpyxl`, `matplotlib`, `highspy`.

### **Documentation**
- `README.md` : this file.




## **Installation**

### 1. Prerequisites
- Make sure you have access to requirements.txt and use this prompts
```bash
python -m venv .venv
.venv\Scripts\Activate
pip install -r requirements.txt
```

If there is a problem, please make sure you are using the latest version of pip and check the online documentation for each package.
```bash
python.exe -m pip install --upgrade pip
```

### 2. File Organization
Place the file **TechArena2025_data.xlsx** in the `input/` folder.
Create an `output/` folder if necessary.




## Usage

### Run the main simulation
```bash
python main.py
```
Depending on the usage you can run the heuristic method or the MIP model. Make sur to enter the desired folder before launching the program.
This will automatically generate the 3 CSV files in the `output/` folder.




## **Main Hypothesis**
- Huawei Battery **LUNA2000-4.5MWh-2H1**:
  - Nominal capacity: 4.472 MWh
  - Max power: depends on the chosen **C-rate**
  - Round-trip efficiency: 88–92%
- Constraints respected:
  - Min/max SOC = 10–90%
  - Daily cycle number limited (1.0, 1.5, or 2.0)
  - Simultaneous participation in DA, FCR, and aFRR possible with capacity allocation.


## Expected outcomes

### 1. **Configuration**
Example (`TechArena_Phase1_Configuration.csv`) :
```
Country : DE,
C-rate : 0.5,
number of cycles : 1.0,
yearly profits [kEUR/MW] : 122.5,
levelized ROI [%] : 9.8
```

### 2. **Investment**
Example (`TechArena_Phase1_Investment.csv`) :
```
Country : DE,
C-rate : 0.5,
number of cycles : 1.0,WACC : 0.083,
inflation rate : 0.02,
discount rate : 0.083,
CAPEX [EUR] : 2,000,000,
OPEX rate 0.02,
levelized ROI : 0.095
```

### 3. **Operation**
Example (`TechArena_Phase1_Operation.csv`) :
```
Timestamp : 2024-01-01 00:00:00,
Stored energy [MWh] : 2.5,
SoC [-] : 0.55,
Charge [MWh] : 0.1,
Discharge [MWh] : 0.0,
Day-ahead buy [MWh] : 0.1,
Day-ahead sell [MWh] : 0.0,
FCR Capacity [MW] : 2.0,
aFRR Capacity POS [MW] : 1.0,
aFRR Capacity NEG [MW] : 1.0
```




## 👤 Authors
Project develop for the **Huawei TechArena 2025**.  
Authors : *DEDARALLY Taariq, DOUIRI Smahane, KAMGUE Ange*  
