# TechArena 2025 – EMS Battery Optimizer (Team Master Poulet)


## **Description**
This project was developed as part of the **Huawei TechArena 2025 (Nuremberg)** competition.  
The objective is to design an **Energy Management System (EMS)** to optimize the operation of a battery energy storage system (**BESS**) connected to the power grid and participating in different markets:

- **Day-Ahead (DA)**: energy arbitrage (buy low, sell high).  
- **Frequency Containment Reserve (FCR)**: ancillary service for frequency stabilization (4h).  
- **Automatic Frequency Restoration Reserve (aFRR)**: secondary reserve (Pos/Neg).

The code produces three output files:  
1. **TechArena_Phase2_Configuration.csv** : tested configurations (C-rate, cycles, ROI).  
2. **TechArena_Phase2_Investment.csv** : financial analysis (CAPEX, OPEX, annualized ROI).  
3. **TechArena_Phase2_Operation.csv** : operational trajectory (SoC, charge/discharge, market participation).

### **The Heuristic method**


#### **1. General principle** 
The battery generates revenues by:
- **charging (buying)** when Day-Ahead (DA) market prices are low,  
- **discharging (selling)** when DA prices are high,  
- while respecting the physical constraints of the BESS (capacity, C-rate, SOC limits).
- **AFRR Energie** we used an activation factor to charge and discharge the batterie.

A portion of the battery power is **reserved** for ancillary services:
- **FCR (Frequency Containment Reserve)**: remuneration based on available MW every 4h,  
- **aFRR (automatic Frequency Restoration Reserve)**: remuneration for upward (Pos) and downward (Neg) capacity, also in 4h blocks.
Additionally, the model now includes battery degradation and temperature effects, to better capture real-world behavior and lifecycle economics.

#### **2. Strategy** ####
The year is splitted into days ans we pick the lowest-price slots of the day for the charging intervals and the highest-price slots of the day.for discharging intervals. After that, we apply physical constraints such as :
   - Charging/discharging limited by `puissance_max`,  
   - SOC must remain between `SOC_min` and `SOC_max`,  
   - Round-trip efficiency (≈ 90%) is enforced.
To obtain the total profit, we compute the day-ahead revenues + FCR and aFRR revenues. 

#### **3. Degradation Model** ####

In Phase 2, we introduced two key mechanisms:

a. **Cycle aging** – linked to the **Depth of Discharge (DoD)** and number of charge/discharge cycles.
   $$\\Delta SoH_{cycle} = \\frac{k_{cycle} \\cdot (DoD)^{1.1}}{N_{life}}$$

b. **Calendar aging** – linked to **time** and **temperature** via the **Arrhenius law**:
   $$k_{cal}(T) = k_0 \\cdot e^{-\\frac{E_a}{R(T+273.15)}}$$
   $$\\Delta SoH_{calendar} = k_{cal}(T) \\cdot \\Delta t$$

   Where:  
   - $E_a$ = activation energy (≈ 30,000 J/mol),  
   - $R$ = 8.314 J/mol/K (gas constant),  
   - $k_0$ = base degradation constant (≈ 1e−7),  
   - $T$ = ambient temperature (°C).

c. **Total SoH update**
   $$SoH_{t+1} = SoH_t - (\\Delta SoH_{cycle} + \\Delta SoH_{calendar})$$

d. **Effective capacity update**
   $$E_{nom,eff}(t) = E_{nom} \\times SoH(t)$$

This degradation mechanism dynamically affects energy storage and power output, reducing the usable capacity as the battery ages.

---

#### **4. Temperature Impact**
Temperature impacts both efficiency and degradation:
- The **optimal temperature** is around **25°C**.  
- Above or below this range, efficiency decreases slightly and **aging accelerates** exponentially.

The model includes a temperature factor:
$$f_T = e^{-((T - 25)/15)^2}$$
that scales degradation rates.


#### **5. Advantages and limitations** ####
✅ Advantages:
- Very fast to compute (runs on a laptop in seconds).  
- Intuitive and easy to explain.  
- Provides a realistic estimate of BESS potential.  

⚠️ Limitations:
- Does not guarantee global optimality.  
- Does not capture market uncertainty.  
- Simplified allocation between DA, FCR, and aFRR (fixed share).  

#### **6. Scripts** ####
Inside the `heuristic_method` folder, we only need :
- `main.py` : main script (simulation and CSV generation).

The results are stored inside the `output` folder and the data used are stored inside the `input` folder


#### **7. Call the method**  
Use
 ```bash
python main.py
```

### **Dependencies**
- `requirements.txt` contains the external packages:  
  - `pandas`, `numpy`

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
