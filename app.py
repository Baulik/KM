# VERSIONE: 2.3 (CHILOMETRI - Radar di ricerca potenziato)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- DATABASE COMUNI (Focus FVG e VENETO) ---
# Ho inserito le coordinate per i comuni e le province principali
DB_LOCALE = {
    "BASILIANO": (46.01, 13.10), "UDINE": (46.06, 13.24), "PORDENONE": (45.95, 12.66), 
    "GORIZIA": (45.94, 13.62), "TRIESTE": (45.65, 13.77), "SAGRADO": (45.87, 13.48), 
    "CODROIPO": (45.96, 12.97), "LATISANA": (45.78, 13.00), "CERVIGNANO": (45.82, 13.33), 
    "PALMANOVA": (45.90, 13.31), "TAVAGNACCO": (46.12, 13.21), "MARTIGNACCO": (46.10, 13.13),
    "GEMONA": (46.27, 13.13), "TOLMEZZO": (46.40, 13.02), "SACILE": (45.95, 12.50),
    "SPILIMBERGO": (46.11, 12.90), "SAN DANIELE": (46.16, 13.01), "MONFALCONE": (45.81, 13.53),
    "CORMONS": (45.91, 13.47), "GRADISCA": (45.89, 13.47), "RONCHI": (45.82, 13.50),
    "MANZANO": (45.99, 13.38), "BUTTRIO": (46.01, 13.33), "SAN GIORGIO": (45.82, 13.20),
    "PORTOGRUARO": (45.77, 12.83), "CONCORDIA SAGITTARIA": (45.75, 12.84), "SAN DONA": (45.63, 12.56),
    "JESOLO": (45.53, 12.64), "CAORLE": (45.59, 12.88), "TREVISO": (45.66, 12.24), 
    "MIRANO": (45.49, 12.11), "SPINEA": (45.49, 12.16), "VENEZIA": (45.44, 12.31),
    "MESTRE": (45.49, 12.24), "NOALE": (45.55, 12.07), "MARTELLAGO": (45.54, 12.15),
    "PADOVA": (45.40, 11.87), "VICENZA": (45.54, 11.54), "VERONA": (45.43, 10.99),
    "CONEGLIANO": (45.88, 12.29), "ODERZO": (45.78, 12.49), "CASTELFRANCO": (45.67, 11.92),
    "MOGLIANO": (45.56, 12.24), "REANA": (46.13, 13.23), "POZZUOLO": (45.98, 13.19)
}

def identifica_comune_radar(testo):
    """Scansiona il testo parola per parola cercando match nel database"""
    # Puliamo il testo da simboli e rendiamolo maiuscolo
    testo_pulito = re.sub(r'[^\w\s]', ' ', testo.upper())
    parole = testo_pulito.split()
    
    # Cerchiamo prima i nomi composti (es. SAN GIORGIO)
    for comune in sorted(DB_LOCALE.keys(), key=len, reverse=True):
        if comune in testo_pulito:
            return comune, DB_LOCALE[comune]
            
    return "UDINE", DB_LOCALE["UDINE"]

@st.cache_data(ttl=86400)
def calcola_strada(itinerario_nomi):
    punti = [DB_LOCALE[n] for n in itinerario_nomi if n in DB_LOCALE]
    if len(punti) < 2: return 0
    locs = ";".join([f"{p[1]},{p[0]}" for p in punti])
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false"
        r = requests.get(url, timeout=10)
        return round(r.json()['routes'][0]['distance'] / 1000, 1) if r.status_code == 200 else 0
    except: return 0

def parse_ics_km_v23(content):
    if not content: return []
    data = []
    lines = StringIO(content).readlines()
    curr = {"summary": "", "description": "", "dtstart": ""}
    in_event = False
    
    for line in lines:
        if line.startswith("BEGIN:VEVENT"):
            in_event = True
            curr = {"summary": "", "description": "", "dtstart": ""}
        elif line.startswith("END:VEVENT") and in_event:
            full_text = f"{curr['summary']} {curr['description']}".upper()
            # LOGICA AGENDA: Deve esserci NOMINATIVO e CODICE FISCALE
            if "NOMINATIVO" in full_text and "CODICE FISCALE" in full_text:
                try:
                    raw_dt = curr["dtstart"].split(":")[-1]
                    dt = datetime.datetime.strptime(raw_dt[:8], "%Y%m%d")
                    if dt.year >= 2024:
                        nome_c, _ = identifica_comune_radar(full_text)
                        data.append({"Data": dt.date(), "Settimana": dt.isocalendar()[1], "Anno": dt.year, "Comune": nome_c})
                except: pass
            in_event = False
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return data

# --- INTERFACCIA ---
st.set_page_config(page_title="KM Radar 2.3", layout="wide")
st.title("🚗 Monitoraggio Chilometri Reali")

@st.cache_data(ttl=600)
def get_data():
    try:
        r = requests.get(DRIVE_URL)
        return parse_ics_km_v23(r.text) if r.status_code == 200 else []
    except: return []

events = get_data()

if events:
    df = pd.DataFrame(events)
    sel_week = st.number_input("Settimana", 1, 53, datetime.date.today().isocalendar()[1])
    df_w = df[df["Settimana"] == sel_week]
    
    if not df_w.empty:
        anni = sorted(df_w["Anno"].unique())
        cols = st.columns(len(anni))
        for i, anno in enumerate(anni):
            with cols[i]:
                st.header(f"📅 {anno}")
                df_a = df_w[df_w["Anno"] == anno].sort_values("Data")
                tot_km = 0
                for g in df_a["Data"].unique():
                    tappe = df_a[df_a["Data"] == g]["Comune"].tolist()
                    percorso = ["BASILIANO"] + tappe + ["BASILIANO"]
                    dist = calcola_strada(percorso)
                    tot_km += dist
                    with st.expander(f"**{g.strftime('%d/%m')}**: {dist} km"):
                        st.write(f"Percorso rilevato: {' ➔ '.join(percorso)}")
                st.metric(f"Totale {anno}", f"{round(tot_km, 1)} km")
    else: st.info("Nessun dato per questa settimana.")
else: st.error("Dati non trovati.")
