# VERSIONE: 3.0 (CHILOMETRI - Motore di Parsing Avanzato ICS)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# Coordinate dei centri (Database espandibile)
DB_COORDS = {
    "BASILIANO": (46.01, 13.10), "ARTEGNA": (46.23, 13.15), "NIMIS": (46.19, 13.26),
    "GORIZIA": (45.94, 13.62), "SESTO AL REGHENA": (45.85, 12.81), "UDINE": (46.06, 13.24)
}

def pulisci_ics_text(testo_grezzo):
    """Rimuove i ritorni a capo di Google e riunisce le parole spezzate"""
    # Rimuove l'andata a capo con spazio (tipico di Google ICS)
    testo = testo_grezzo.replace("\n ", "").replace("\r ", "")
    # Sostituisce i \n letterali con spazi veri
    testo = testo.replace("\\n", " ")
    return testo

def estrai_citta_ics(testo_pulito):
    """Cerca il valore dopo la parola 'Città'"""
    # Cerca 'Città' seguito da qualsiasi carattere fino a un'altra etichetta o fine riga
    match = re.search(r"Città\s+([A-Z][a-z]+(?:\s[a-z]+)*)", testo_pulito, re.IGNORECASE)
    if match:
        return match.group(1).strip().upper()
    
    # Fallback: cerca i comuni noti nel testo
    for comune in DB_COORDS.keys():
        if comune in testo_pulito.upper():
            return comune
    return "UDINE"

@st.cache_data(ttl=86400)
def calcola_distanza(nomi_tappe):
    """Calcola distanza stradale reale tramite OSRM"""
    punti = []
    for n in nomi_tappe:
        if n in DB_COORDS: punti.append(DB_COORDS[n])
        else: punti.append(DB_COORDS["UDINE"]) # Fallback
    
    if len(punti) < 2: return 0
    locs = ";".join([f"{p[1]},{p[0]}" for p in punti])
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false"
        r = requests.get(url, timeout=10)
        return round(r.json()['routes'][0]['distance'] / 1000, 1)
    except: return 0

def parse_ics_v3(content):
    if not content: return []
    events = []
    # Prima di tutto puliamo il file dai "salti riga" di Google che spezzano le parole
    content_fixed = content.replace("\r\n ", "").replace("\n ", "")
    
    segments = content_fixed.split("BEGIN:VEVENT")
    for seg in segments:
        if "END:VEVENT" in seg:
            # Estrazione Data
            start_match = re.search(r"DTSTART:(\d{8})", seg)
            if start_match:
                data_str = start_match.group(1)
                dt = datetime.datetime.strptime(data_str, "%Y%m%d")
                
                # Estrazione Testo Totale (Summary + Description)
                summary = re.search(r"SUMMARY:(.*?)TRANSP:", seg, re.DOTALL)
                full_text = pulisci_ics_text(summary.group(1)) if summary else ""
                
                if "NOMINATIVO" in full_text.upper():
                    citta = estrai_citta_ics(full_text)
                    events.append({
                        "Data": dt.date(),
                        "Settimana": dt.isocalendar()[1],
                        "Anno": dt.year,
                        "Città": citta
                    })
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="KM Monitor 3.0", layout="wide")
st.title("🚗 Calcolo Chilometri dai tuoi Appuntamenti")

@st.cache_data(ttl=600)
def get_data():
    r = requests.get(DRIVE_URL)
    return parse_ics_v3(r.text) if r.status_code == 200 else []

data = get_data()

if data:
    df = pd.DataFrame(data)
    sel_week = st.number_input("Seleziona Settimana", 1, 53, datetime.date.today().isocalendar()[1])
    df_w = df[df["Settimana"] == sel_week]
    
    if not df_w.empty:
        anni = sorted(df_w["Anno"].unique())
        cols = st.columns(len(anni))
        for i, anno in enumerate(anni):
            with cols[i]:
                st.header(f"📅 {anno}")
                df_a = df_w[df_w["Anno"] == anno].sort_values("Data")
                tot_km_sett = 0
                for g in df_a["Data"].unique():
                    tappe = df_a[df_a["Data"] == g]["Città"].tolist()
                    percorso = ["BASILIANO"] + tappe + ["BASILIANO"]
                    dist = calcola_distanza(percorso)
                    tot_km_sett += dist
                    with st.expander(f"**{g.strftime('%d/%m')}**: {dist} km"):
                        st.write(f"Tappe trovate: {' ➔ '.join(tappe)}")
                st.metric("Totale Km", f"{round(tot_km_sett,1)} km")
    else:
        st.info("Nessun appuntamento trovato per questa settimana.")
else:
    st.error("Nessun dato caricato. Controlla il link Drive.")
