# VERSIONE: 2.1 (CHILOMETRI - Database Comuni FVG/Veneto Integrato)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- DATABASE INTEGRATO (FVG + VENETO) ---
# Lista ottimizzata dei comuni delle tue zone di lavoro
DB_LOCALE = {
    # FRIULI VENEZIA GIULIA
    "BASILIANO": (46.01, 13.10), "UDINE": (46.06, 13.24), "PORDENONE": (45.95, 12.66), 
    "GORIZIA": (45.94, 13.62), "TRIESTE": (45.65, 13.77), "SAGRADO": (45.87, 13.48), 
    "CODROIPO": (45.96, 12.97), "LATISANA": (45.78, 13.00), "CERVIGNANO": (45.82, 13.33), 
    "PALMANOVA": (45.90, 13.31), "TAVAGNACCO": (46.12, 13.21), "MARTIGNACCO": (46.10, 13.13),
    "GEMONA": (46.27, 13.13), "TOLMEZZO": (46.40, 13.02), "SACILE": (45.95, 12.50),
    "SPILIMBERGO": (46.11, 12.90), "SAN DANIELE": (46.16, 13.01), "MONFALCONE": (45.81, 13.53),
    "CORMANS": (45.91, 13.47), "GRADISCA": (45.89, 13.47), "RONCHI": (45.82, 13.50),
    "MANZANO": (45.99, 13.38), "BUTTRIO": (46.01, 13.33), "SAN GIORGIO": (45.82, 13.20),
    
    # VENETO
    "PORTOGRUARO": (45.77, 12.83), "CONCORDIA SAGITTARIA": (45.75, 12.84), "SAN DONA": (45.63, 12.56),
    "JESOLO": (45.53, 12.64), "CAORLE": (45.59, 12.88), "TREVISO": (45.66, 12.24), 
    "MIRANO": (45.49, 12.11), "SPINEA": (45.49, 12.16), "VENEZIA": (45.44, 12.31),
    "MESTRE": (45.49, 12.24), "NOALE": (45.55, 12.07), "MARTELLAGO": (45.54, 12.15),
    "PADOVA": (45.40, 11.87), "VICENZA": (45.54, 11.54), "VERONA": (45.43, 10.99),
    "CONEGLIANO": (45.88, 12.29), "ODERZO": (45.78, 12.49), "CASTELFRANCO": (45.67, 11.92)
}

def identifica_comune_serio(testo):
    """Cerca i comuni nel testo in modo intelligente"""
    testo_up = testo.upper()
    # Ordiniamo per lunghezza decrescente per non confondere "San Donà" con "San"
    for comune in sorted(DB_LOCALE.keys(), key=len, reverse=True):
        if comune in testo_up:
            return comune, DB_LOCALE[comune]
    return "UDINE", DB_LOCALE["UDINE"] # Fallback se non trova nulla

@st.cache_data(ttl=86400)
def calcola_distanza_reale(itinerario_nomi):
    """Interroga OSRM per i km stradali effettivi"""
    punti = [DB_LOCALE[n] for n in itinerario_nomi if n in DB_LOCALE]
    if len(punti) < 2: return 0
    
    locs = ";".join([f"{p[1]},{p[0]}" for p in punti])
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return round(r.json()['routes'][0]['distance'] / 1000, 1)
    except: return 0
    return 0

# --- MOTORE DI RECUPERO DATI (STESSA LOGICA AGENDA) ---
def parse_ics_km_v21(content):
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
            full_text = f"{curr['summary']} {curr['description']}".upper()
            if "NOMINATIVO" in full_text and "CODICE FISCALE" in full_text:
                raw_dt = curr["dtstart"].split(":")[-1]
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    if dt.year >= 2024:
                        nome_citta, coords = identifica_comune_serio(full_text)
                        data.append({
                            "Data": dt.date(), "Settimana": dt.isocalendar()[1], "Anno": dt.year,
                            "Ora": dt.time(), "Comune": nome_citta
                        })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return data

# --- INTERFACCIA ---
st.set_page_config(page_title="KM App 2.1", layout="wide")
st.title("🛣️ Monitoraggio Chilometri FVG & Veneto")

@st.cache_data(ttl=600)
def fetch():
    r = requests.get(DRIVE_URL)
    return parse_ics_km_v21(r.text) if r.status_code == 200 else []

events = fetch()

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
                df_a = df_w[df_w["Anno"] == anno].sort_values(["Data", "Ora"])
                tot_km = 0
                for g in df_a["Data"].unique():
                    tappe = df_a[df_a["Data"] == g]["Comune"].tolist()
                    percorso = ["BASILIANO"] + tappe + ["BASILIANO"]
                    km_giorno = calcola_distanza_reale(percorso)
                    tot_km += km_giorno
                    with st.expander(f"**{g.strftime('%d/%m')}**: {km_giorno} km"):
                        st.write(f"Giro: {' ➔ '.join(percorso)}")
                st.metric(f"Totale Settimana", f"{round(tot_km,1)} km")
    else:
        st.info("Nessun dato per questa settimana.")
else:
    st.error("Connessione a Drive fallita.")    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return round(r.json()['routes'][0]['distance'] / 1000, 1)
    except: return 0
    return 0

# --- MOTORE PARSING (AGENDA) ---
def parse_ics_km_v2(content):
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
            desc_full = (curr["summary"] + " " + curr["description"]).upper()
            if "NOMINATIVO" in desc_full and "CODICE FISCALE" in desc_full:
                raw_dt = curr["dtstart"].split(":")[-1]
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    if dt.year >= 2024:
                        citta = identifica_citta(desc_full)
                        events.append({
                            "Data": dt.date(), "Ora": dt.time(), "Anno": dt.year,
                            "Settimana": dt.isocalendar()[1], "Città": citta if citta else "UDINE"
                        })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="Chilometri 2.0", layout="wide")
st.title("🚗 Riepilogo Chilometri FVG & Veneto")

@st.cache_data(ttl=600)
def load_and_fix():
    r = requests.get(DRIVE_URL)
    return parse_ics_km_v2(r.text) if r.status_code == 200 else []

data = load_and_fix()

if data:
    df = pd.DataFrame(data)
    sel_week = st.number_input("Settimana", 1, 53, datetime.date.today().isocalendar()[1])
    df_w = df[df["Settimana"] == sel_week]

    if not df_w.empty:
        anni = sorted(df_w["Anno"].unique())
        cols = st.columns(len(anni))
        for i, anno in enumerate(anni):
            with cols[i]:
                st.subheader(f"📅 {anno}")
                df_a = df_w[df_w["Anno"] == anno].sort_values(["Data", "Ora"])
                km_sett = 0
                for g in df_a["Data"].unique():
                    tappe = df_a[df_a["Data"] == g]["Città"].tolist()
                    percorso = ["BASILIANO"] + tappe + ["BASILIANO"]
                    distanza = calcola_distanza_stradale(percorso)
                    km_sett += distanza
                    with st.expander(f"**{g.strftime('%d/%m')}**: {distanza} km"):
                        st.write(f"Percorso: {' ➔ '.join(percorso)}")
                st.metric(f"Totale {anno}", f"{round(km_sett, 1)} km")
    else:
        st.info("Nessun appuntamento trovato.")
else:
    st.error("Errore caricamento dati.")

