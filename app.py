# VERSIONE: 3.0 (CHILOMETRI - Calcolo Stradale Dinamico OSRM)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re
import math

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO, UD, FRIULI VENEZIA GIULIA"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- MOTORE GEOGRAFICO (OSRM + NOMINATIM) ---
@st.cache_data(ttl=86400) # Cache di 24 ore per le coordinate
def get_coords(citta):
    """Ricava Latitudine e Longitudine di un comune"""
    try:
        url = f"https://nominatim.openstreetmap.org/search?city={citta}&format=json&limit=1"
        headers = {'User-Agent': 'MonitorChilometriApp/1.0'}
        r = requests.get(url, headers=headers)
        if r.status_code == 200 and len(r.json()) > 0:
            return r.json()[0]['lat'], r.json()[0]['lon']
    except:
        return None
    return None

@st.cache_data(ttl=86400)
def get_road_distance(points):
    """Calcola la distanza stradale reale tra una lista di coordinate"""
    if len(points) < 2: return 0
    coords_str = ";".join([f"{p[1]},{p[0]}" for p in points]) # OSRM vuole lon,lat
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=false"
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            # Distanza restituita in metri, convertiamo in km
            return round(data['routes'][0]['distance'] / 1000, 1)
    except:
        return 0
    return 0

# --- PARSING DATI (STESSA LOGICA AGENDA) ---
@st.cache_data(ttl=600)
def load_data(url):
    try:
        r = requests.get(url)
        return r.text if r.status_code == 200 else None
    except: return None

def extract_city(description):
    text_clean = description.replace("\\,", ",").replace("\n", " ")
    for tag in ["Frazione:", "Città:", "Citta:", "Località:"]:
        if tag.lower() in text_clean.lower():
            pattern = re.compile(f"{tag}\s*([^,;:\n]*)", re.IGNORECASE)
            match = pattern.search(text_clean)
            if match and match.group(1).strip():
                return match.group(1).strip().upper()
    return ""

def parse_ics_km_v3(content):
    if not content: return []
    events = []
    lines = StringIO(content).readlines()
    in_event = False
    curr = {"summary": "", "description": "", "dtstart": ""}
    for line in lines:
        line = line.strip()
        if line.startswith("BEGIN:VEVENT"):
            in_event = True
            curr = {"summary": "", "description": "", "dtstart": ""}
        elif line.startswith("END:VEVENT"):
            in_event = False
            desc_lower = (curr["summary"] + " " + curr["description"]).lower()
            if "nominativo" in desc_lower and "codice fiscale" in desc_lower:
                raw_dt = curr["dtstart"].split(":")[-1]
                if len(raw_dt) >= 8:
                    try:
                        dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                        dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                        if dt.year >= 2024:
                            citta = extract_city(curr["description"])
                            if not citta and "-" in curr["summary"]:
                                citta = curr["summary"].split("-")[-1].strip().upper()
                            events.append({
                                "Data": dt.date(), "Ora": dt.time(), 
                                "Settimana": dt.isocalendar()[1], "Mese": dt.month,
                                "Anno": dt.year, "Città": citta if citta else "UDINE"
                            })
                    except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="KM Real-Time 3.0", layout="wide")
st.title("🛣️ Monitoraggio Chilometri Reali (OSRM)")

content = load_data(DRIVE_URL)
data = parse_ics_km_v3(content)

if data:
    df = pd.DataFrame(data)
    sel_week = st.number_input("Seleziona Settimana", 1, 53, datetime.date.today().isocalendar()[1])
    df_week = df[df["Settimana"] == sel_week]

    if not df_week.empty:
        anni = sorted(df_week["Anno"].unique())
        cols = st.columns(len(anni))
        
        # Coordinate fisse di Basiliano
        coords_casa = get_coords("BASILIANO")

        for i, anno in enumerate(anni):
            with cols[i]:
                st.header(f"📅 {anno}")
                df_a = df_week[df_week["Anno"] == anno].sort_values(["Data", "Ora"])
                tot_km_sett = 0
                
                for g in df_a["Data"].unique():
                    tappe_nomi = df_a[df_a["Data"] == g]["Città"].tolist()
                    
                    # Convertiamo nomi città in coordinate
                    tappe_coords = [coords_casa]
                    for t in tappe_nomi:
                        c = get_coords(t)
                        if c: tappe_coords.append(c)
                    tappe_coords.append(coords_casa)
                    
                    # Calcolo distanza reale
                    km_g = get_road_distance(tappe_coords)
                    tot_km_sett += km_g
                    
                    with st.expander(f"**{g.strftime('%d/%m')}**: {km_g} km"):
                        st.write(f"Percorso: Basiliano ➔ {' ➔ '.join(tappe_nomi)} ➔ Basiliano")
                
                st.metric(f"Totale {anno}", f"{tot_km_sett} km")
    
    st.divider()
    st.info("Nota: Le distanze sono calcolate tramite itinerari stradali reali (OSRM).")
else:
    st.warning("Dati non trovati.")
