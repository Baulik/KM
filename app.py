# VERSIONE: 1.0 (PROGETTO CHILOMETRI - Base Basiliano)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO

# --- CONFIGURAZIONE E DISTANZE (Esempio Database) ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# Tabella distanze approssimative da/per Basiliano e tra città comuni (in km)
# Potremo espandere questa tabella o usare un'API in futuro
distanze_db = {
    ("BASILIANO", "UDINE"): 13, ("UDINE", "BASILIANO"): 13,
    ("BASILIANO", "TRIESTE"): 75, ("TRIESTE", "BASILIANO"): 75,
    ("BASILIANO", "CERVIGNANO"): 35, ("CERVIGNANO", "BASILIANO"): 35,
    ("UDINE", "TRIESTE"): 70, ("TRIESTE", "UDINE"): 70,
    ("UDINE", "CERVIGNANO"): 30, ("CERVIGNANO", "UDINE"): 30,
    ("TRIESTE", "CERVIGNANO"): 50, ("CERVIGNANO", "TRIESTE"): 50,
    # Default per città non censite (stima media FVG)
    "DEFAULT": 20 
}

def calcola_distanza(orig, dest):
    orig = orig.upper().strip()
    dest = dest.upper().strip()
    if orig == dest: return 0
    return distanze_db.get((orig, dest), distanze_db.get("DEFAULT"))

# --- FUNZIONI DI SUPPORTO ---

@st.cache_data(ttl=3600)
def load_data_from_drive(url):
    try:
        r = requests.get(url)
        return r.text if r.status_code == 200 else None
    except: return None

def parse_ics_locations(content):
    if not content: return []
    data = []
    lines = StringIO(content).readlines()
    in_event = False
    current_event = {"summary": "", "dtstart": "", "location": ""}
    
    for line in lines:
        line = line.strip()
        if line.startswith("BEGIN:VEVENT"):
            in_event = True
            current_event = {"summary": "", "dtstart": "", "location": ""}
        elif line.startswith("END:VEVENT"):
            in_event = False
            # Estrazione città dalla location o dal summary
            # Cerchiamo di pulire la stringa per avere solo il nome comune
            loc = current_event["location"].split(",")[-1].strip().upper()
            if not loc: # fallback su summary se location vuota
                loc = "UDINE" # Default cautelativo
            
            raw_dt = current_event["dtstart"].split(":")[-1]
            if len(raw_dt) >= 8:
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    data.append({
                        "Data": dt.date(),
                        "Ora": dt.time(),
                        "Settimana": dt.isocalendar()[1],
                        "Anno": dt.year,
                        "Città": loc
                    })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): current_event["dtstart"] = line
            elif line.startswith("LOCATION"): current_event["location"] = line[9:]
            elif line.startswith("SUMMARY"): current_event["summary"] = line[8:]
    return data

# --- INTERFACCIA ---
st.set_page_config(page_title="Logistica Chilometri 1.0", layout="wide")

st.title("🚗 Calcolo Chilometrico Settimanale")
st.info(f"Punto di partenza e rientro: **{CASA_BASE}**")

content = load_data_from_drive(DRIVE_URL)
raw_data = parse_ics_locations(content)

if raw_data:
    df = pd.DataFrame(raw_data)
    sel_week = st.number_input("Seleziona Settimana:", 1, 53, datetime.date.today().isocalendar()[1])
    
    df_week = df[df["Settimana"] == sel_week].sort_values(["Data", "Ora"])
    
    if not df_week.empty:
        giorni = df_week["Data"].unique()
        km_totali_settimana = 0
        
        for giorno in giorni:
            df_giorno = df_week[df_week["Data"] == giorno]
            citta_tappa = df_giorno["Città"].tolist()
            
            # Costruzione Percorso: Casa -> Tappe -> Casa
            percorso = [CASA_BASE] + citta_tappa + [CASA_BASE]
            
            km_giorno = 0
            for i in range(len(percorso) - 1):
                km_giorno += calcola_distanza(percorso[i], percorso[i+1])
            
            km_totali_settimana += km_giorno
            
            with st.expander(f"📅 {giorno.strftime('%A %d/%m')} - Totale: {km_giorno} km"):
                st.write(f"**Percorso:** {' ➔ '.join(percorso)}")
                st.write(f"Numero tappe: {len(citta_tappa)}")

        st.metric(" Chilometri Totali Settimana", f"{km_totali_settimana} km")
        
        # Grafico semplice
        st.bar_chart(df_week.groupby("Data").size())
    else:
        st.warning("Nessun dato per questa settimana.")
