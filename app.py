# VERSIONE: 1.6 (CHILOMETRI - Sintetica con Expander e Divisione Anni)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- DATABASE DISTANZE (Esempio per calcolo) ---
distanze_km = {
    ("BASILIANO", "UDINE"): 13, ("BASILIANO", "GORIZIA"): 42,
    ("BASILIANO", "SAGRADO"): 38, ("BASILIANO", "PORDENONE"): 45,
    ("UDINE", "GORIZIA"): 28, ("SAGRADO", "PORDENONE"): 75,
    ("BASILIANO", "CODROIPO"): 14, ("BASILIANO", "TRIESTE"): 78
}

def get_distanza(a, b):
    a, b = a.upper().strip(), b.upper().strip()
    if a == b: return 0
    dist = distanze_km.get((a, b)) or distanze_km.get((b, a))
    return dist if dist else 25 # Chilometraggio medio se non in tabella

# --- MOTORE DI RICERCA ---
@st.cache_data(ttl=600)
def load_data(url):
    try:
        r = requests.get(url)
        return r.text if r.status_code == 200 else None
    except: return None

def extract_city(text):
    text_clean = text.replace("\\,", ",").replace("\n", " ")
    for tag in ["Frazione:", "Città:", "Citta:"]:
        if tag.lower() in text_clean.lower():
            pattern = re.compile(f"{tag}\s*([^,;:\n]*)", re.IGNORECASE)
            match = pattern.search(text_clean)
            if match and match.group(1).strip():
                return match.group(1).strip().upper()
    return ""

def parse_ics_km_clean(content):
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
            full_text = (curr["summary"] + " " + curr["description"]).lower()
            
            # FILTRO: Nominativo + Presenza di una località
            if "nominativo" in full_text:
                citta = extract_city(curr["description"] + " " + curr["summary"])
                if not citta: # Se non trova Frazione/Città prova a pulire il titolo
                    citta = curr["summary"].split("-")[-1].strip().upper()
                
                raw_dt = curr["dtstart"].split(":")[-1]
                if len(raw_dt) >= 8:
                    try:
                        dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                        dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                        if dt.year >= 2024:
                            events.append({
                                "Data": dt.date(), "Ora": dt.time(), 
                                "Settimana": dt.isocalendar()[1],
                                "Anno": dt.year, "Città": citta if citta else "UDINE"
                            })
                    except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return events

# --- INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="KM App 1.6", layout="wide")
st.title("🚗 Riepilogo Chilometri")

content = load_data(DRIVE_URL)
data = parse_ics_km_clean(content)

if data:
    df = pd.DataFrame(data)
    
    # Selezione Settimana
    current_week = datetime.date.today().isocalendar()[1]
    sel_week = st.sidebar.number_input("Settimana", 1, 53, current_week)
    
    df_w = df[df["Settimana"] == sel_week]
    
    if not df_w.empty:
        # Divisione in colonne per Anno
        anni = sorted(df_w["Anno"].unique())
        cols = st.columns(len(anni))
        
        for i, anno in enumerate(anni):
            with cols[i]:
                df_a = df_w[df_w["Anno"] == anno].sort_values(["Data", "Ora"])
                
                # Calcolo chilometri totali dell'anno per quella settimana
                sett_km = 0
                giorni_data = []
                
                for g in df_a["Data"].unique():
                    tappe = df_a[df_a["Data"] == g]["Città"].tolist()
                    percorso = [CASA_BASE] + tappe + [CASA_BASE]
                    km_g = sum(get_distanza(percorso[j], percorso[j+1]) for j in range(len(percorso)-1))
                    sett_km += km_g
                    giorni_data.append({"data": g, "km": km_g, "giro": " ➔ ".join(percorso)})
                
                # Visualizzazione Card
                st.subheader(f"📅 {anno}")
                st.metric("Totale Settimana", f"{sett_km} km")
                
                for item in giorni_data:
                    with st.expander(f"**{item['data'].strftime('%a %d/%m')}**: {item['km']} km"):
                        st.caption(f"Percorso analizzato:")
                        st.write(item['giro'])
    else:
        st.info(f"Nessun dato trovato per la settimana {sel_week}")

    # Riepilogo Mensile in fondo
    st.divider()
    st.subheader("📊 Confronto Mensile")
    storico = []
    for (anno, mese), group in df.groupby(["Anno", "Mese"]):
        km_mese = 0
        for g in group["Data"].unique():
            t = group[group["Data"] == g]["Città"].tolist()
            iti = [CASA_BASE] + t + [CASA_BASE]
            km_mese += sum(get_distanza(iti[j], iti[j+1]) for j in range(len(iti)-1))
        storico.append({"Anno": anno, "Mese": mese, "Km": km_mese})
    
    if storico:
        df_h = pd.DataFrame(storico)
        mesi_it = {1:"Gen", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mag", 6:"Giu", 7:"Lug", 8:"Ago", 9:"Set", 10:"Ott", 11:"Nov", 12:"Dic"}
        pivot = df_h.pivot(index="Mese", columns="Anno", values="Km").fillna(0).astype(int)
        pivot.index = pivot.index.map(mesi_it)
        st.table(pivot)
else:
    st.error("Nessun appuntamento rilevato nel calendario.")
