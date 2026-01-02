# VERSIONE: 1.1 (CHILOMETRI - Ricerca Dinamica Intelligente)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO, UD"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- MOTORE GEOGRAFICO ---

@st.cache_data(ttl=86400)
def trova_coordinate_comune(testo_appuntamento):
    """Analizza il testo e cerca di identificare una località valida nel FVG o Veneto"""
    # Puliamo il testo da caratteri speciali
    parole = re.findall(r'\b[A-ZÀ-Ú]{3,}\b', testo_appuntamento.upper())
    
    # Proviamo a cercare le coordinate per le parole sospette (partendo dalle ultime che spesso sono le città)
    for parola in reversed(parole):
        if parola in ["NOMINATIVO", "FISCALE", "FRAZIONE", "VIA", "PIAZZA"]: continue
        try:
            url = f"https://nominatim.openstreetmap.org/search?city={parola}&county=Udine&format=json&limit=1"
            # Se non trova in provincia di Udine, cerca in tutto il Nord Italia
            headers = {'User-Agent': 'MonitorKm_App_v1.1'}
            r = requests.get(url, headers=headers)
            if r.status_code == 200 and len(r.json()) > 0:
                return r.json()[0]['lat'], r.json()[0]['lon'], parola
        except: continue
    return None, None, "SCONOSCIUTO"

@st.cache_data(ttl=86400)
def calcola_percorso_stradale(lista_coords):
    """Interroga il motore OSRM per chilometri stradali reali"""
    punti = [p for p in lista_coords if p[0] is not None]
    if len(punti) < 2: return 0
    
    locs = ";".join([f"{p[1]},{p[0]}" for p in punti])
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false"
        r = requests.get(url)
        if r.status_code == 200:
            return round(r.json()['routes'][0]['distance'] / 1000, 1)
    except: return 0
    return 0

# --- ESTRAZIONE DATI ---

def parse_ics_km_v11(content):
    if not content: return []
    data = []
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
            full_text = f"{curr['summary']} {curr['description']}"
            # Usa lo stesso filtro dell'Agenda
            if "nominativo" in full_text.lower() and "codice fiscale" in full_text.lower():
                raw_dt = curr["dtstart"].split(":")[-1]
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    if dt.year >= 2024:
                        lat, lon, citta_rilevata = trova_coordinate_comune(full_text)
                        data.append({
                            "Data": dt.date(), "Ora": dt.time(), "Anno": dt.year,
                            "Settimana": dt.isocalendar()[1], "Testo": full_text,
                            "Città": citta_rilevata, "Coords": (lat, lon)
                        })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return data

# --- INTERFACCIA ---
st.set_page_config(page_title="Km Dinamici 1.1", layout="wide")
st.title("🚗 Calcolo Chilometri Dinamico")

@st.cache_data(ttl=600)
def get_data():
    r = requests.get(DRIVE_URL)
    return parse_ics_km_v11(r.text) if r.status_code == 200 else []

raw_events = get_data()

if raw_events:
    df = pd.DataFrame(raw_events)
    sel_week = st.number_input("Seleziona Settimana", 1, 53, datetime.date.today().isocalendar()[1])
    
    df_w = df[df["Settimana"] == sel_week]
    anni = sorted(df_w["Anno"].unique())
    
    if not df_w.empty:
        # Coordinate Basiliano
        lat_b, lon_b, _ = trova_coordinate_comune("BASILIANO")
        coords_casa = (lat_b, lon_b)
        
        cols = st.columns(len(anni))
        for i, anno in enumerate(anni):
            with cols[i]:
                st.header(f"📅 {anno}")
                df_a = df_w[df_w["Anno"] == anno].sort_values(["Data", "Ora"])
                km_sett = 0
                
                for g in df_a["Data"].unique():
                    giorno_data = df_a[df_a["Data"] == g]
                    tappe_coords = [coords_casa]
                    nomi_citta = []
                    
                    for _, row in giorno_data.iterrows():
                        if row["Coords"][0]:
                            tappe_coords.append(row["Coords"])
                            nomi_citta.append(row["Città"])
                    
                    tappe_coords.append(coords_casa)
                    distanza = calcola_percorso_stradale(tappe_coords)
                    km_sett += distanza
                    
                    with st.expander(f"**{g.strftime('%d/%m')}**: {distanza} km"):
                        st.write(f"Località rilevate: {', '.join(nomi_citta)}")
                        st.caption(f"Percorso: Basiliano ➔ {' ➔ '.join(nomi_citta)} ➔ Basiliano")
                
                st.metric(f"Totale {anno}", f"{round(km_sett, 1)} km")
    else:
        st.info("Nessun appuntamento di lavoro trovato.")
else:
    st.error("Errore nel caricamento dati.")
