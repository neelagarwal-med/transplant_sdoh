import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- Secure API Key Loading ---
try:
    from key import TOMTOM_API_KEY
except ImportError:
    TOMTOM_API_KEY = None

# --- Page Configuration ---
st.set_page_config(page_title="SDoH Organ Rescue Router", layout="wide")

st.sidebar.title("About the Author")
st.sidebar.markdown("**Neel Agarwal**")
st.sidebar.markdown("*Medical Student*")
st.sidebar.markdown("The Ohio State University College of Medicine")
st.sidebar.markdown("neel.agarwal@osumc.edu")
st.sidebar.divider()
st.sidebar.info("Using TomTom Predictive Traffic API & SDoH Logistics Engine.")

if not TOMTOM_API_KEY:
    st.sidebar.error("🚨 TOMTOM_API_KEY missing from key.py. Real traffic routing will fail.")

# --- Main App Header ---
st.title("🚑 SDoH 'Organ Rescue' Geospatial Router")
st.subheader("Predictive Transportation Logistics Engine")

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
    
    # Combine today's date with the input time
    offer_datetime = datetime.combine(now.date(), input_time)

    # If the time is in the past, automatically roll it over to tomorrow
    if offer_datetime < now:
        offer_datetime += timedelta(days=1)
        st.info(f"📅 **Time Rollover:** {offer_time_input} has passed today. Calculating predictive traffic for **tomorrow** at {offer_time_input}.")
        
    # TomTom requires ISO 8601 format for the departAt parameter
    tomtom_depart_time = offer_datetime.strftime("%Y-%m-%dT%H:%M:%S")

except ValueError:
    st.error("🚨 **Format Error:** Please enter a valid 24-hour time (e.g., '14:30' or '02:00').")
    st.stop()

# --- API Integration Functions ---
@st.cache_data
def geocode_address(address):
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'OrganRescueGeospatialRouter/6.0'}
    params = {'q': address, 'format': 'json', 'limit': 1}
    try:
        response = requests.get(url, headers=headers, params=params).json()
        if response:
            return float(response[0]['lat']), float(response[0]['lon'])
    except Exception as e:
        st.error(f"Geocoding error: {e}")
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
            svi_score = float(cdc_res[0].get('rpl_themes', 0.5))
            return svi_score if svi_score >= 0 else 0.5 
    except Exception:
        pass 
    return 0.82 

def get_tomtom_traffic_route(lat1, lon1, lat2, lon2, api_key, depart_time):
    """Pulls REAL predictive traffic data using TomTom API."""
    if not api_key:
        return None, None, None
        
    locations = f"{lat1},{lon1}:{lat2},{lon2}"
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
    
    params = {
        'key': api_key,
        'departAt': depart_time,
        'traffic': 'true',
        'routeType': 'fastest'
    }
    
    try:
        response = requests.get(url, params=params).json()
        if 'routes' in response:
            route = response['routes'][0]
            
            # TomTom returns time in seconds and distance in meters
            duration_mins = route['summary']['travelTimeInSeconds'] / 60.0
            distance_miles = route['summary']['lengthInMeters'] * 0.000621371
            
            # Extract points for Folium Map
            points = route['legs'][0]['points']
            geometry = [[p['latitude'], p['longitude']] for p in points]
            
            return duration_mins, distance_miles, geometry
        else:
            error_msg = response.get('error', {}).get('description', 'Verify your API key and limits.')
            st.error(f"TomTom API Error: {error_msg}")
    except Exception as e:
        st.error(f"Routing Connection Error: {e}")
        
    return None, None, None

# --- Execution Engine ---
st.divider()

if st.button("🚀 Evaluate Logistics & Dispatch"):
    with st.spinner("Pinging TomTom Predictive Traffic & CDC APIs..."):
        p_lat, p_lon = geocode_address(patient_address)
        h_lat, h_lon = geocode_address(hospital_address)

        if not all([p_lat, p_lon, h_lat, h_lon]):
            st.error("Could not locate one of the addresses. Please try again.")
        else:
            svi_score = get_fips_and_svi(p_lat, p_lon)
            
            # 1. Pull Real Predictive Traffic
            duration, distance, geometry = get_tomtom_traffic_route(p_lat, p_lon, h_lat, h_lon, TOMTOM_API_KEY, tomtom_depart_time)
            
            if duration is None or distance is None:
                st.error("🚨 Critical routing failure. Please verify your TomTom API Key.")
            else:
                offer_hour = offer_datetime.hour
                surge_multiplier = 1.0
                intervention = "None (Has Car)"
                cost = 0.0
                wait_time_penalty = 0.0
                
                # 2. Scarcity & Surge Simulation (ONLY for patients needing Uber)
                if not patient_has_car:
                    if offer_hour in [0, 1, 2, 3, 4]:
                        wait_time_penalty = 15.0 
                        surge_multiplier = 2.0
                        st.info(f"🌙 **Uber Scarcity Simulation:** 15-minute wait for late-night driver added to real traffic time.")
                    elif offer_hour in [7, 8, 16, 17]:
                        wait_time_penalty = 5.0
                        surge_multiplier = 1.8
                        st.info(f"🚗 **Uber Surge Simulation:** Rush hour pricing applied.")
                    else:
                        wait_time_penalty = 8.0 # Standard wait time
                        
                    duration += wait_time_penalty
                        
                    base_cost = 5.0 + (distance * 1.50) + (duration * 0.25)
                    cost = base_cost * surge_multiplier
                    
                    if svi_score >= 0.75:
                        intervention = f"🚨 Hospital-Funded Emergency Rideshare"
                    else:
                        intervention = "Patient-Funded Rideshare"
                else:
                    st.success("🚗 Patient has private transport. Using raw predictive traffic drive-time.")

                # 3. Final Viability Check & Absolute Time Math
                arrival_datetime = offer_datetime + timedelta(minutes=duration)
                expiration_datetime = offer_datetime + timedelta(minutes=240)
                
                is_viable = arrival_datetime <= expiration_datetime

                # --- Results Display ---
                st.markdown("### 📊 Logistics Assessment")
                st.caption(f"*Calculated using real predictive traffic data for {offer_datetime.strftime('%m/%d/%Y %I:%M %p')} via TomTom*")
                
                # Explicit Timeline Display to prevent user confusion
                if is_viable:
                    st.info(f"⏱️ **Timeline Status:** Organ expires at **{expiration_datetime.strftime('%I:%M %p')}**. Estimated patient arrival is **{arrival_datetime.strftime('%I:%M %p')}** (Clear by {int(240 - duration)} mins).")
                else:
                    st.error(f"⏱️ **Timeline Status:** Organ expires at **{expiration_datetime.strftime('%I:%M %p')}**. Estimated patient arrival is **{arrival_datetime.strftime('%I:%M %p')}** (Late by {int(duration - 240)} mins).")
                
                metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
                metrics_col1.metric("CDC SVI Score", f"{svi_score:.2f}", "Top Quartile" if svi_score >= 0.75 else "Standard")
                metrics_col2.metric("Total Transit Time", f"{duration:.1f} mins")
                metrics_col3.metric("Distance", f"{distance:.1f} miles")
                metrics_col4.metric("Estimated Cost", f"${cost:.2f}")

                if is_viable:
                    st.success(f"**Status:** Viable Candidate. **Action:** {intervention}")
                else:
                    st.error("**Status:** Ischemia time exceeded. Bypass candidate.")

                # --- Map Generation ---
                st.markdown("### 🗺️ Route Visualization")
                
                mid_lat = (p_lat + h_lat) / 2
                mid_lon = (p_lon + h_lon) / 2
                m = folium.Map(location=[mid_lat, mid_lon], zoom_start=12)

                folium.Marker([p_lat, p_lon], popup="Patient Location", icon=folium.Icon(color="red", icon="user")).add_to(m)
                folium.Marker([h_lat, h_lon], popup="Transplant Center", icon=folium.Icon(color="blue", icon="plus")).add_to(m)

                if geometry:
                    folium.PolyLine(geometry, color="purple", weight=4, opacity=0.8).add_to(m)

                st_folium(m, width=1200, height=400, returned_objects=[])