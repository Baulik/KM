# VERSIONE: 1.3 (CHILOMETRI - Database Integrato FVG & VENETO)
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
# Contiene i principali comuni e province per calcolo immediato
DB_GEOGRAFICO = {
    # FRIULI VENEZIA GIULIA
    "BASILIANO": (46.013, 13.104), "UDINE": (46.063, 13.243), "CODROIPO": (45.961, 12.977),
    "TAVAGNACCO": (46.126, 13.216), "CERVIGNANO": (45.823, 13.336), "LATISANA": (45.782, 13.001),
    "PALMANOVA": (45.905, 13.310), "GORIZIA": (45.940, 13.621), "PORDENONE": (45.956, 12.660),
    "TRIESTE": (45.649, 13.776), "SAGRADO": (45.874, 13.483), "MONFALCONE": (45.810, 13.530),
    "SPILIMBERGO": (46.110, 12.903), "SAN DANIELE": (46.160, 13.010), "GEMONA": (46.275, 13.138),
    "TOLMEZZO": (46.398, 13.020), "LIGNANO": (45.674, 13.111), "MARTIGNACCO": (46.100, 13.133),
    "PASIAN DI PRATO": (46.046, 13.190), "AZZANO DECIMO": (45.890, 12.710), "SACILE": (45.954, 12.503),
    "CORDOVADO": (45.850, 12.880), "FAGAGNA": (46.112, 13.087), "GONARS": (45.895, 13.232),
    "MANZANO": (45.990, 13.380), "TRICESIMO": (46.161, 13.213),
    
    # VENETO
    "VENEZIA": (45.440, 12.315), "PADOVA": (45.406, 11.876), "TREVISO": (45.666, 12.245),
    "VERONA": (45.438, 10.991), "VICENZA": (45.547, 11.546), "BELLUNO": (46.142, 12.216),
    "ROVIGO": (45.070, 11.790), "MESTRE": (45.490, 12.242), "MIRANO": (45.492, 12.112),
    "SPINEA": (45.491, 12.160), "MARCON": (45.560, 12.300), "NOALE": (45.550, 12.070),
    "MARTELLAGO": (45.545, 12.158), "PORTOGRUARO": (45.776, 12.837), "SAN DONA": (45.631, 12.564),
    "CONCORDIA SAGITTARIA": (45.756, 12.846), "CAORLE": (45.599, 12.887), "JESOLO": (45.534, 12.643),
    "MIRA": (45.437, 12.133), "DOLO": (45.426, 12.076), "MOGLIANO": (45.560, 12.240),
    "CONEGLIANO": (45.885, 12.296), "CASTELFRANCO": (45.671, 11.927), "MONTEBELLUNA": (45.775, 12.045)
}

def identifica_comune(testo):
    """Scansiona il testo e restituisce le coordinate del primo comune trovato in lista"""
    testo_upper = testo.upper()
    # Cerchiamo prima i nomi composti lunghi per evitare errori (es. Pasian di Prato)
    for comune in sorted(DB_GEOGRAFICO.keys(), key=len, reverse=True):
        if comune in testo_upper:
            return DB_GEOGRAFICO[comune], comune
    return None, None

@st.cache_data(ttl=3600)
def calcola_distanza_osrm(coords_percorso):
    """Calcola la distanza stradale tramite OSRM (itinerario reale)"""
    if len(coords_percorso) < 2: return 0
    # Invertiamo per OSRM: (lon, lat)
    locs = ";".join([f"{p[1]},{p[0]}" for p in coords_percorso])
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return round(r.json()['routes'][0]['distance'] / 1000, 1)
    except:
        return 0
    return 0

# --- MOTORE DI RECUPERO DATI (STESSA LOGICA AGENDA) ---

def parse_ics_km_v13(content):
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
            full_text = f"{curr['summary']} {curr['description']}"
            # Filtro Lavoro (Nominativo + CF)
            if "nominativo" in full_text.lower() and "codice fiscale" in full_text.lower():
                raw_dt = curr["dtstart"].split(":")[-1]
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    if dt.year >= 2024:
                        coords, nome_comune = identifica_comune(full_text)
                        events.append({
                            "Data": dt.date(), "Settimana": dt.isocalendar()[1], "Anno": dt.year,
                            "Ora": dt.time(), "Comune": nome_comune if nome_comune else "UDINE",
                            "Coords": coords if coords else DB_GEOGRAFICO["UDINE"]
                        })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return events

# --- INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="Monitor KM 1.3", layout="wide")
st.title("🚗 Chilometri Reali FVG & Veneto")

@st.cache_data(ttl=600)
def load_data():
    r = requests.get(DRIVE_URL)
    return parse_ics_km_v13(r.text) if r.status_code == 200 else []

all_events = load_data()

if all_events:
    df = pd.DataFrame(all_events)
    sel_week = st.number_input("Seleziona Settimana", 1, 53, datetime.date.today().isocalendar()[1])
    
    df_week = df[df["Settimana"] == sel_week]
    anni = sorted(df_week["Anno"].unique())
    
    if not df_week.empty:
        home_coords = DB_GEOGRAFICO["BASILIANO"]
        cols = st.columns(len(anni))
        
        for i, anno in enumerate(anni):
            with cols[i]:
                st.header(f"📅 {anno}")
                df_a = df_week[df_week["Anno"] == anno].sort_values(["Data", "Ora"])
                km_settimanali = 0
                
                for g in df_a["Data"].unique():
                    giorno_data = df_a[df_a["Data"] == g]
                    itinerario = [home_coords]
                    tappe_nomi = []
                    
                    for _, row in giorno_data.iterrows():
                        itinerario.append(row["Coords"])
                        tappe_nomi.append(row["Comune"])
                    
                    itinerario.append(home_coords)
                    distanza_giorno = calcola_distanza_osrm(itinerario)
                    km_settimanali += distanza_giorno
                    
                    with st.expander(f"**{g.strftime('%d/%m')}**: {distanza_giorno} km"):
                        st.write(f"Giro: Basiliano ➔ {' ➔ '.join(tappe_nomi)} ➔ Basiliano")
                
                st.metric(f"Totale {anno}", f"{round(km_settimanali, 1)} km")
    else:
        st.info("Nessun appuntamento trovato per questa settimana.")
else:
    st.error("Errore nel caricamento del calendario.")
