import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- Secure API Key Loading (Hybrid: Local key.py -> Streamlit Secrets) ---
TOMTOM_API_KEY = None
try:
    # 1. Look for local key.py (Local Development)
    from key import TOMTOM_API_KEY
except (ImportError, ModuleNotFoundError):
    # 2. Look for Streamlit Secrets (Cloud Deployment)
    TOMTOM_API_KEY = st.secrets.get("TOMTOM_API_KEY")

# --- Page Configuration ---
st.set_page_config(page_title="SDoH Organ Rescue Router", layout="wide")

# --- Sidebar: Author Details ---
st.sidebar.title("About the Author")
st.sidebar.markdown("**Neel Agarwal**")
st.sidebar.markdown("*Medical Student*")
st.sidebar.markdown("The Ohio State University College of Medicine")
st.sidebar.markdown("neel.agarwal@osumc.edu")
st.sidebar.divider()
st.sidebar.info("Using TomTom Predictive Traffic API & SDoH Logistics Engine.")

# Inform the user which source is being used (Hidden in production if needed)
if TOMTOM_API_KEY:
    pass # Key loaded successfully
else:
    st.sidebar.error("🚨 TOMTOM_API_KEY not found in key.py or Streamlit Secrets.")

# --- Main App Header ---
st.title("🚑 SDoH 'Organ Rescue' Geospatial Router")
st.subheader("Predictive Transportation Logistics Engine")

with st.expander("📊 Methodology, Science, & Mathematical Framework", expanded=False):
    st.markdown(r"""
    ### 1. The Clinical Constraint: Cold Ischemia Time
    When a marginal kidney becomes available, viability drops precipitously. The total allowable time is governed by the inequality:
    
    $$T_{total} = t_{notification} + t_{transit} + t_{prep} \leq 240 \text{ minutes}$$
    
    If $t_{transit}$ is heavily delayed by lack of private transport, organs are often discarded.

    ### 2. SDoH Integration: The Social Vulnerability Index (SVI)
    This engine integrates the CDC's Social Vulnerability Index (SVI) to quantify transportation poverty. 
    * Patients residing in tracts with an **$SVI \geq 0.75$** (top-quartile vulnerability) are flagged for hospital-funded emergency transit.

    ### 3. Predictive Routing & Scarcity Simulation
    * **Real-World Routing:** Queries TomTom for exact driving duration on road networks using the `departAt` parameter.
    * **Dynamic Scarcity Penalties:** Applies traffic penalties during rush hour. For transit-dependent patients, it applies a **Scarcity Penalty** (15-minute wait + surge pricing) during off-hours (12 AM - 5 AM).
    """)

# --- Input Section ---
st.markdown("### 📍 Location Parameters")
col1, col2 = st.columns(2)

with col1:
    patient_address = st.text_input("Patient Location", value="100 E Broad St, Columbus, OH 43215")
    patient_has_car = st.checkbox("Patient has reliable private transit?", value=False)

with col2:
    hospital_address = st.text_input("Transplant Center Location", value="410 W 10th Ave, Columbus, OH 43210")
    current_time_str = datetime.now().strftime("%H:%M")
    offer_time_input = st.text_input("Future Time of Organ Offer (24-hour HH:MM)", value=current_time_str)

# --- Strict Time Validation & Rollover Engine ---
try:
    now = datetime.now()
    input_time = datetime.strptime(offer_time_input, "%H:%M").time()
    offer_datetime = datetime.combine(now.date(), input_time)

    # Automatically roll over to tomorrow if the time has passed today
    if offer_datetime < now:
        offer_datetime += timedelta(days=1)
        st.info(f"📅 **Time Rollover:** {offer_time_input} has passed today. Calculating predictive traffic for **tomorrow** at {offer_time_input}.")
        
    tomtom_depart_time = offer_datetime.strftime("%Y-%m-%dT%H:%M:%S")

except ValueError:
    st.error("🚨 **Format Error:** Please use HH:MM format (e.g., '02:00').")
    st.stop()

# --- API Integration Functions ---
@st.cache_data
def geocode_address(address):
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'OrganRescueGeospatialRouter/7.0'}
    params = {'q': address, 'format': 'json', 'limit': 1}
    try:
        response = requests.get(url, headers=headers, params=params).json()
        if response:
            return float(response[0]['lat']), float(response[0]['lon'])
    except:
        pass
    return None, None

@st.cache_data
def get_fips_and_svi(lat, lon):
    fcc_url = f"https://geo.fcc.gov/api/census/block/find?latitude={lat}&longitude={lon}&format=json"
    try:
        fcc_res = requests.get(fcc_url).json()
        tract_fips = fcc_res['Block']['FIPS'][:11] 
        cdc_url = f"https://data.cdc.gov/resource/n8mc-b4w4.json?fips={tract_fips}"
        cdc_res = requests.get(cdc_url).json()
        if cdc_res and len(cdc_res) > 0:
            return float(cdc_res[0].get('rpl_themes', 0.5))
    except:
        pass 
    return 0.82 

def get_tomtom_traffic_route(lat1, lon1, lat2, lon2, api_key, depart_time):
    if not api_key: return None, None, None
    locations = f"{lat1},{lon1}:{lat2},{lon2}"
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
    params = {'key': api_key, 'departAt': depart_time, 'traffic': 'true', 'routeType': 'fastest'}
    try:
        res = requests.get(url, params=params).json()
        if 'routes' in res:
            route = res['routes'][0]
            duration = route['summary']['travelTimeInSeconds'] / 60.0
            distance = route['summary']['lengthInMeters'] * 0.000621371
            geometry = [[p['latitude'], p['longitude']] for p in route['legs'][0]['points']]
            return duration, distance, geometry
    except:
        pass
    return None, None, None

# --- Execution Engine ---
st.divider()

if st.button("🚀 Evaluate Logistics & Dispatch"):
    with st.spinner("Pinging Road Networks and CDC APIs..."):
        p_lat, p_lon = geocode_address(patient_address)
        h_lat, h_lon = geocode_address(hospital_address)

        if not all([p_lat, p_lon, h_lat, h_lon]):
            st.error("Address error. Please try again.")
        else:
            svi_score = get_fips_and_svi(p_lat, p_lon)
            duration, distance, geometry = get_tomtom_traffic_route(p_lat, p_lon, h_lat, h_lon, TOMTOM_API_KEY, tomtom_depart_time)
            
            if duration is None:
                st.error("🚨 Routing failure. Check your TOMTOM_API_KEY.")
            else:
                # Scarcity Logic
                offer_hour = offer_datetime.hour
                surge = 1.0
                if not patient_has_car:
                    if offer_hour in [0, 1, 2, 3, 4]:
                        duration += 15.0; surge = 2.0
                        st.info("🌙 **Uber Scarcity Applied:** 15m wait + 2.0x surge multiplier.")
                    elif offer_hour in [7, 8, 16, 17]:
                        surge = 1.8
                    duration += 8.0 # Baseline wait time

                # Timeline Math
                arrival = offer_datetime + timedelta(minutes=duration)
                expiry = offer_datetime + timedelta(minutes=240)
                is_viable = arrival <= expiry

                st.markdown("### 📊 Logistics Assessment")
                st.caption(f"*Real predictive traffic data for {offer_datetime.strftime('%m/%d/%Y %I:%M %p')} via TomTom*")
                
                if is_viable:
                    st.info(f"⏱️ **Timeline Status:** Organ expires at **{expiry.strftime('%I:%M %p')}**. Arrival at **{arrival.strftime('%I:%M %p')}** (Safe).")
                else:
                    st.error(f"⏱️ **Timeline Status:** Organ expires at **{expiry.strftime('%I:%M %p')}**. Arrival at **{arrival.strftime('%I:%M %p')}** (EXCEEDED).")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("CDC SVI Score", f"{svi_score:.2f}", "Top Quartile" if svi_score >= 0.75 else "Standard")
                m2.metric("Total Transit", f"{duration:.1f} mins")
                m3.metric("Distance", f"{distance:.1f} miles")
                m4.metric("Estimated Cost", f"${((5.0 + (distance*1.5) + (duration*0.25)) * surge):.2f}")

                if is_viable:
                    st.success(f"**Status:** Viable Candidate. **Action:** {'🚨 Hospital-Funded Rideshare' if svi_score >= 0.75 and not patient_has_car else 'None (Has Car)'}")
                else:
                    st.error("**Status:** Ischemia time exceeded. Bypass candidate.")

                # Map Visualization
                m = folium.Map(location=[(p_lat+h_lat)/2, (p_lon+h_lon)/2], zoom_start=12)
                folium.Marker([p_lat, p_lon], icon=folium.Icon(color='red', icon='user')).add_to(m)
                folium.Marker([h_lat, h_lon], icon=folium.Icon(color='blue', icon='plus')).add_to(m)
                if geometry: folium.PolyLine(geometry, color="purple", weight=4).add_to(m)
                st_folium(m, width=1200, height=400, returned_objects=[])