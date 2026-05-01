# 🚑 SDoH 'Organ Rescue' Geospatial Router
### Addressing Transportation Poverty in Transplant Logistics

This tool is a predictive logistics engine designed to prevent the discard of viable "marginal" kidneys. It integrates real-time geospatial routing with Social Determinants of Health (SDoH) data to identify patients who may face transportation barriers during urgent, off-hour organ offers.

## 🛠️ Methodology
- **Real-Time Routing:** Uses the TomTom Predictive Traffic API to calculate drive times based on future departure times.
- **SDoH Integration:** Pulls the **CDC Social Vulnerability Index (SVI)** at the census tract level.
- **Logistics Simulation:** Factors in rideshare scarcity and price surges for transit-dependent patients during late-night (12 AM - 5 AM) windows.

## 🚀 Setup
1. Clone the repo.
2. Create a `key.py` file in the root directory.
3. Add your `TOMTOM_API_KEY = "YOUR_KEY_HERE"` to `key.py`.
4. Run `pip install -r requirements.txt`.
5. Launch with `streamlit run app.py`.

**Author:** Neel, Medical Student at The Ohio State University College of Medicine.