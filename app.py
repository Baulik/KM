# VERSIONE: 1.7 (OTTIMIZZAZIONE RICERCA LOCALITÀ E SINTESI KM)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- DATABASE DISTANZE (FVG/VENETO) ---
distanze_km = {
    ("BASILIANO", "UDINE"): 13, ("BASILIANO", "GORIZIA"): 42,
    ("BASILIANO", "SAGRADO"): 38, ("BASILIANO", "PORDENONE"): 45,
    ("BASILIANO", "CODROIPO"): 14, ("BASILIANO", "TRIESTE"): 78,
    ("UDINE", "GORIZIA"): 28, ("SAGRADO", "PORDENONE"): 75,
    ("UDINE", "CERVIGNANO"): 30, ("BASILIANO", "CERVIGNANO"): 35,
}

def get_distanza(a, b):
    a, b = a.upper().strip(), b.upper().strip()
    if a == b: return 0
    # Cerca la combinazione nel DB (in entrambi i sensi)
    dist = distanze_km.get((a, b)) or distanze_km.get((b, a))
    return dist if dist else 25 # Media standard se la città è nuova

# --- LOGICA DI ESTRAZIONE ---
@st.cache_data(ttl=600)
def load_data(url):
    try:
        r = requests.get(url)
        return r.text if r.status_code == 200 else None
    except: return None

def extract_city(description, summary):
    """Cerca la città nei campi dell'appuntamento"""
    full_text = f"{summary} {description}".replace("\\,", ",").replace("\n", " ")
    
    # 1. Prova con etichette esplicite
    for tag in ["Frazione:", "Città:", "Citta:", "Località:"]:
        pattern = re.compile(f"{tag}\s*([^,;:\n]*)", re.IGNORECASE)
        match = pattern.search(full_text)
        if match and match.group(1).strip():
            return match.group(1).strip().upper()
    
    # 2. Fallback: se il titolo contiene un trattino, spesso la città è l'ultima parte
    if "-" in summary:
        parts = summary.split("-")
        return parts[-1].strip().upper()
        
    return ""

def parse_ics_km_v17(content):
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
            
            # FILTRO: Deve essere un appuntamento di lavoro (Nominativo)
            if "nominativo" in full_text:
                citta = extract_city(curr["description"], curr["summary"])
                
                raw_dt = curr["dtstart"].split(":")[-1]
                if len(raw_dt) >= 8:
                    try:
                        dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                        dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                        
                        # Solo dal 2024 in poi
                        if dt.year >= 2024:
                            events.append({
                                "Data": dt.date(), "Ora": dt.time(), 
                                "Settimana": dt.isocalendar()[1], "Mese": dt.month,
                                "Anno": dt.year, "Città": citta if citta else "UDINE"
                            })
                    except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="KM Monitor 1.7", layout="wide")
st.title("🚗 Riepilogo Chilometraggio Lavoro")

content = load_data(DRIVE_URL)
data = parse_ics_km_v17(content)

if data:
    df = pd.DataFrame(data)
    
    # Selettore Settimana
    sel_week = st.sidebar.number_input("Seleziona Settimana:", 1, 53, datetime.date.today().isocalendar()[1])
    df_w = df[df["Settimana"] == sel_week]
    
    if not df_w.empty:
        # Mostra Anni in colonne (es. 2024 e 2025 affiancati)
        anni = sorted(df_w["Anno"].unique())
        cols = st.columns(len(anni))
        
        for i, anno in enumerate(anni):
            with cols[i]:
                st.markdown(f"### 📅 Anno {anno}")
                df_a = df_w[df_w["Anno"] == anno].sort_values(["Data", "Ora"])
                
                tot_km_sett = 0
                giorni = df_a["Data"].unique()
                
                for g in giorni:
                    tappe = df_a[df_a["Data"] == g]["Città"].tolist()
                    percorso = [CASA_BASE] + tappe + [CASA_BASE]
                    
                    # Calcolo km del giorno
                    km_g = sum(get_distanza(percorso[j], percorso[j+1]) for j in range(len(percorso)-1))
                    tot_km_sett += km_g
                    
                    # Visualizzazione pulita con expander per il dettaglio
                    with st.expander(f"**{g.strftime('%a %d/%m')}**: {km_g} km"):
                        st.write(f"🚩 Giro: {' ➔ '.join(percorso)}")
                
                st.metric(f"Totale Settimana {sel_week}", f"{tot_km_sett} km")
    else:
        st.info(f"Nessun dato per la settimana {sel_week}")

    # --- TABELLA STORICA MENSILE ---
    st.divider()
    st.subheader("📊 Confronto Chilometri Mensili")
    storico = []
    for (anno, mese), group in df.groupby(["Anno", "Mese"]):
        km_m = 0
        for g in group["Data"].unique():
            t = group[group["Data"] == g]["Città"].tolist()
            iti = [CASA_BASE] + t + [CASA_BASE]
            km_m += sum(get_distanza(iti[j], iti[j+1]) for j in range(len(iti)-1))
        storico.append({"Anno": anno, "Mese": mese, "Km": km_m})
    
    if storico:
        df_h = pd.DataFrame(storico)
        mesi_it = {1:"Gen", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mag", 6:"Giu", 7:"Lug", 8:"Ago", 9:"Set", 10:"Ott", 11:"Nov", 12:"Dic"}
        pivot = df_h.pivot(index="Mese", columns="Anno", values="Km").fillna(0).astype(int)
        pivot.index = pivot.index.map(mesi_it)
        st.dataframe(pivot.style.background_gradient(cmap="YlGn"), use_container_width=True)

else:
    st.error("Dati non trovati. Verifica che il file Drive sia accessibile.")
