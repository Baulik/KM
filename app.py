# VERSIONE: 1.4 (CHILOMETRI - Stessa logica Agenda + Estrazione Frazione/Città)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- DATABASE DISTANZE (Base FVG) ---
distanze_km = {
    ("BASILIANO", "UDINE"): 13, ("BASILIANO", "TRIESTE"): 78,
    ("BASILIANO", "CODROIPO"): 14, ("BASILIANO", "PORDENONE"): 45,
    ("BASILIANO", "CERVIGNANO"): 35, ("BASILIANO", "LATISANA"): 32,
    ("BASILIANO", "PALMANOVA"): 25, ("BASILIANO", "TAVAGNACCO"): 18,
    ("BASILIANO", "GORIZIA"): 42, ("BASILIANO", "MONFALCONE"): 50,
    ("BASILIANO", "SPILIMBERGO"): 28, ("BASILIANO", "SAN DANIELE"): 22,
}

def get_distanza(a, b):
    a, b = a.upper().strip(), b.upper().strip()
    if a == b: return 0
    dist = distanze_km.get((a, b)) or distanze_km.get((b, a))
    return dist if dist else 25 # Media cautelativa

# --- PARSING IDENTICO ALL'AGENDA ---
@st.cache_data(ttl=600)
def load_data(url):
    try:
        r = requests.get(url)
        return r.text if r.status_code == 200 else None
    except: return None

def extract_city(text):
    """Cerca la località dopo 'Frazione:' o 'Città:'"""
    text_clean = text.replace("\\,", ",").replace("\n", " ")
    # Cerca prima Frazione, poi Città
    for tag in ["Frazione:", "Città:", "Citta:"]:
        if tag.lower() in text_clean.lower():
            pattern = re.compile(f"{tag}\s*([^,;:\n]*)", re.IGNORECASE)
            match = pattern.search(text_clean)
            if match and match.group(1).strip():
                return match.group(1).strip().upper()
    return "UDINE" # Fallback se non trova nulla

def parse_ics_km_mirror(content):
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
            
            # STESSA LOGICA RICERCA AGENDA: Nominativo + Codice Fiscale
            desc_lower = (curr["summary"] + " " + curr["description"]).lower()
            if "nominativo" in desc_lower and "codice fiscale" in desc_lower:
                raw_dt = curr["dtstart"].split(":")[-1]
                if len(raw_dt) >= 8:
                    try:
                        dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                        dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                        
                        # FILTRO: Solo dal 2024
                        if dt.year >= 2024:
                            # ESTRAZIONE LOCALITÀ
                            citta = extract_city(curr["description"] + " " + curr["summary"])
                            events.append({
                                "Data": dt.date(), "Ora": dt.time(), 
                                "Settimana": dt.isocalendar()[1], "Mese": dt.month,
                                "Anno": dt.year, "Città": citta
                            })
                    except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
            
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="KM Logistica 1.4", layout="wide")
st.title("🚗 Percorsi e Chilometri")

content = load_data(DRIVE_URL)
data = parse_ics_km_mirror(content)

if data:
    df = pd.DataFrame(data)
    mesi_it = {1:"Gennaio", 2:"Febbraio", 3:"Marzo", 4:"Aprile", 5:"Maggio", 6:"Giugno", 7:"Luglio", 8:"Agosto", 9:"Settembre", 10:"Ottobre", 11:"Novembre", 12:"Dicembre"}
    
    sel_week = st.number_input("Settimana:", 1, 53, datetime.date.today().isocalendar()[1])
    df_w = df[df["Settimana"] == sel_week].sort_values(["Data", "Ora"])
    
    if not df_w.empty:
        st.subheader(f"📊 Percorsi Settimana {sel_week}")
        tot_km_sett = 0
        for g in df_w["Data"].unique():
            tappe = df_w[df_w["Data"] == g]["Città"].tolist()
            iti = [CASA_BASE] + tappe + [CASA_BASE]
            km_g = sum(get_distanza(iti[i], iti[i+1]) for i in range(len(iti)-1))
            tot_km_sett += km_g
            st.info(f"📅 **{g.strftime('%d/%m')}**: {' ➔ '.join(iti)} | **{km_g} km**")
        st.metric("CHILOMETRI TOTALI SETTIMANA", f"{tot_km_sett} km")
    
    st.divider()
    
    # RIEPILOGO STORICO
    st.subheader("📈 Riepilogo Mensile Annuo")
    storico = []
    for (anno, mese), group in df.groupby(["Anno", "Mese"]):
        km_m = 0
        for g in group["Data"].unique():
            t = group[group["Data"] == g]["Città"].tolist()
            iti = [CASA_BASE] + t + [CASA_BASE]
            km_m += sum(get_distanza(iti[i], iti[i+1]) for i in range(len(iti)-1))
        storico.append({"Anno": anno, "Mese": mese, "Km": km_m})
    
    if storico:
        df_h = pd.DataFrame(storico)
        pivot = df_h.pivot(index="Mese", columns="Anno", values="Km").fillna(0).astype(int)
        pivot.index = pivot.index.map(mesi_it)
        st.dataframe(pivot.style.background_gradient(cmap="Blues"), use_container_width=True)
else:
    st.error("Nessun appuntamento trovato. Verifica che i dati siano dal 2024 e contengano 'Nominativo' e 'Codice Fiscale'.")
