# VERSIONE: 2.4 (CHILOMETRI - Ricerca Flessibile & Pulizia Testo)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re
import unicodedata

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- DATABASE UNIFICATO (FVG + VENETO) ---
DB_MAPPA = {
    "BASILIANO": (46.01, 13.10), "UDINE": (46.06, 13.24), "PORDENONE": (45.95, 12.66), 
    "GORIZIA": (45.94, 13.62), "TRIESTE": (45.65, 13.77), "SAGRADO": (45.87, 13.48), 
    "CODROIPO": (45.96, 12.97), "LATISANA": (45.78, 13.00), "CERVIGNANO": (45.82, 13.33), 
    "PALMANOVA": (45.90, 13.31), "TAVAGNACCO": (46.12, 13.21), "MARTIGNACCO": (46.10, 13.13),
    "GEMONA": (46.27, 13.13), "TOLMEZZO": (46.40, 13.02), "SACILE": (45.95, 12.50),
    "SPILIMBERGO": (46.11, 12.90), "SAN DANIELE": (46.16, 13.01), "MONFALCONE": (45.81, 13.53),
    "CORMONS": (45.91, 13.47), "GRADISCA": (45.89, 13.47), "RONCHI": (45.82, 13.50),
    "MANZANO": (45.99, 13.38), "BUTTRIO": (46.01, 13.33), "SAN GIORGIO": (45.82, 13.20),
    "REANA": (46.13, 13.23), "POZZUOLO": (45.98, 13.19), "CAMPOFORMIDO": (46.01, 13.15),
    "PORTOGRUARO": (45.77, 12.83), "CONCORDIA SAGITTARIA": (45.75, 12.84), "SAN DONA": (45.63, 12.56),
    "JESOLO": (45.53, 12.64), "CAORLE": (45.59, 12.88), "TREVISO": (45.66, 12.24), 
    "MIRANO": (45.49, 12.11), "SPINEA": (45.49, 12.16), "VENEZIA": (45.44, 12.31),
    "MESTRE": (45.49, 12.24), "NOALE": (45.55, 12.07), "MARTELLAGO": (45.54, 12.15),
    "PADOVA": (45.40, 11.87), "VICENZA": (45.54, 11.54), "VERONA": (45.43, 10.99),
    "CONEGLIANO": (45.88, 12.29), "ODERZO": (45.78, 12.49), "CASTELFRANCO": (45.67, 11.92),
    "VITTORIO VENETO": (45.99, 12.29), "MONTEBELLUNA": (45.77, 12.04), "MOGLIANO": (45.56, 12.24)
}

def pulisci_testo(testo):
    """Rimuove accenti e rende tutto maiuscolo per facilitare il confronto"""
    if not testo: return ""
    testo = testo.upper()
    # Rimuove accenti (es. à -> a)
    testo = ''.join(c for c in unicodedata.normalize('NFD', testo) if unicodedata.category(c) != 'Mn')
    # Sostituisce l'apostrofo con lo spazio per nomi tipo San Dona'
    testo = testo.replace("'", " ").replace("-", " ")
    return testo

def identifica_comune_sicuro(testo):
    """Cerca il comune nel testo pulito"""
    testo_pulito = pulisci_testo(testo)
    # Cerca prima i nomi più lunghi
    for comune in sorted(DB_MAPPA.keys(), key=len, reverse=True):
        comune_pulito = pulisci_testo(comune)
        if comune_pulito in testo_pulito:
            return comune
    return "UDINE"

@st.cache_data(ttl=86400)
def calcola_distanza_osrm(nomi_tappe):
    punti = [DB_MAPPA.get(n, DB_MAPPA["UDINE"]) for n in nomi_tappe]
    if len(punti) < 2: return 0
    locs = ";".join([f"{p[1]},{p[0]}" for p in punti])
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return round(r.json()['routes'][0]['distance'] / 1000, 1)
    except: return 0
    return 0

def parse_ics_km_v24(content):
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
            # Uniamo i campi per la ricerca
            full_text = f"{curr['summary']} {curr['description']}"
            if "nominativo" in full_text.lower() and "codice fiscale" in full_text.lower():
                raw_dt = curr["dtstart"].split(":")[-1]
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    if dt.year >= 2024:
                        comune = identifica_comune_sicuro(full_text)
                        data.append({
                            "Data": dt.date(), "Settimana": dt.isocalendar()[1], "Anno": dt.year,
                            "Ora": dt.time(), "Comune": comune
                        })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return data

# --- INTERFACCIA ---
st.set_page_config(page_title="KM Monitor 2.4", layout="wide")
st.title("🛣️ Monitoraggio Chilometri (Ricerca Avanzata)")

@st.cache_data(ttl=600)
def fetch_data():
    try:
        r = requests.get(DRIVE_URL)
        return parse_ics_km_v24(r.text) if r.status_code == 200 else []
    except: return []

events = fetch_data()

if events:
    df = pd.DataFrame(events)
    sel_week = st.number_input("Seleziona Settimana", 1, 53, datetime.date.today().isocalendar()[1])
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
                    km_giorno = calcola_distanza_osrm(percorso)
                    tot_km += km_giorno
                    with st.expander(f"**{g.strftime('%d/%m')}**: {km_giorno} km"):
                        st.write(f"Tappe trovate: {' ➔ '.join(tappe)}")
                st.metric(f"Totale {anno}", f"{round(tot_km,1)} km")
    else:
        st.info("Nessun appuntamento trovato per questa settimana.")
else:
    st.error("Nessun dato trovato o errore di connessione.")
