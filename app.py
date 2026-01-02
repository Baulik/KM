# VERSIONE: 3.1 (CHILOMETRI - Velocità Ottimizzata & Cache)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import os

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- CARICAMENTO DATABASE COMUNI ---
@st.cache_resource
def load_db():
    db = {}
    errori = []
    for f in ["comuni_fvg.csv", "comuni_veneto.csv"]:
        if os.path.exists(f):
            try:
                temp_df = pd.read_csv(f)
                for _, row in temp_df.iterrows():
                    # Salviamo in minuscolo per velocizzare il confronto dopo
                    db[str(row['nome']).lower().strip()] = (row['lat'], row['lon'])
            except: errori.append(f"Errore lettura {f}")
        else:
            errori.append(f"File {f} non trovato")
    db["basiliano"] = (46.01, 13.10)
    return db, errori

# --- CALCOLO KM ---
@st.cache_data(ttl=3600)
def get_dist(coords_list):
    if len(coords_list) < 2: return 0
    locs = ";".join([f"{p[1]},{p[0]}" for p in coords_list])
    try:
        r = requests.get(f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false", timeout=5)
        return round(r.json()['routes'][0]['distance'] / 1000, 1) if r.status_code == 200 else 0
    except: return 0

# --- PARSING CALENDARIO OTTIMIZZATO ---
@st.cache_data(ttl=600)
def get_and_parse_calendar(url, db):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return []
        
        lines = StringIO(r.text).readlines()
        events = []
        curr = {"sum": "", "desc": "", "start": ""}
        
        for line in lines:
            line = line.strip()
            if line.startswith("BEGIN:VEVENT"): curr = {"sum": "", "desc": "", "start": ""}
            elif line.startswith("SUMMARY"): curr["sum"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["desc"] = line[12:]
            elif line.startswith("DTSTART"): curr["start"] = line
            elif line.startswith("END:VEVENT"):
                txt = (curr["sum"] + " " + curr["desc"]).lower()
                if "nominativo" in txt and "codice fiscale" in txt:
                    # Riconoscimento rapido comune
                    found_city = "udine" # Fallback
                    for city in db.keys():
                        if city in txt:
                            found_city = city
                            break
                    
                    raw_dt = curr["start"].split(":")[-1]
                    try:
                        dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                        dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                        if dt.year >= 2024:
                            events.append({
                                "Data": dt.date(), "Settimana": dt.isocalendar()[1], 
                                "Anno": dt.year, "Ora": dt.time(), "Comune": found_city
                            })
                    except: continue
        return events
    except: return []

# --- INTERFACCIA ---
st.set_page_config(page_title="KM Monitor 3.1", layout="wide")
st.title("🚗 Chilometri Giornalieri")

db_mappa, errori = load_db()
for err in errori: st.warning(err)

# Caricamento dati con barra di attesa limitata
with st.spinner("Recupero dati in corso..."):
    data = get_and_parse_calendar(DRIVE_URL, db_mappa)

if data:
    df = pd.DataFrame(data)
    sel_week = st.sidebar.number_input("Settimana", 1, 53, datetime.date.today().isocalendar()[1])
    
    df_w = df[df["Settimana"] == sel_week]
    
    if not df_w.empty:
        anni = sorted(df_w["Anno"].unique())
        cols = st.columns(len(anni))
        
        for i, anno in enumerate(anni):
            with cols[i]:
                st.header(f"📅 {anno}")
                df_a = df_w[df_w["Anno"] == anno].sort_values(["Data", "Ora"])
                tot_km = 0
                
                for g in df_a["Data"].unique():
                    tappe = df_a[df_a["Data"] == g]["Comune"].tolist()
                    giro = ["basiliano"] + tappe + ["basiliano"]
                    coords = [db_mappa.get(t, db_mappa["udine"]) for t in giro]
                    
                    dist = get_dist(coords)
                    tot_km += dist
                    
                    with st.expander(f"**{g.strftime('%d/%m')}**: {dist} km"):
                        st.write(f"🚩 {' ➔ '.join(giro).upper()}")
                
                st.metric(f"Totale {anno}", f"{round(tot_km, 1)} km")
    else:
        st.info("Nessun appuntamento per questa settimana.")
else:
    st.error("Nessun dato trovato nel calendario. Verifica il file su Drive.")
