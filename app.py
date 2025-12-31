# VERSIONE: 1.0 (CHILOMETRI - Motore Dinamico Geografico)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO, UD"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- FUNZIONI GEOGRAFICHE (MAPPE REALI) ---

@st.cache_data(ttl=86400)
def get_lat_lon(citta):
    """Ottiene coordinate reali di un comune tramite OpenStreetMap"""
    if not citta: return None
    try:
        # Raffiniamo la ricerca per FVG e Veneto
        query = f"{citta}, Italia"
        url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
        headers = {'User-Agent': 'MonitorKm_App_v1'}
        r = requests.get(url, headers=headers)
        if r.status_code == 200 and len(r.json()) > 0:
            return float(r.json()[0]['lat']), float(r.json()[0]['lon'])
    except: return None
    return None

@st.cache_data(ttl=86400)
def get_strada_km(coords_list):
    """Calcola i KM reali stradali tra una lista di coordinate (Giro Visite)"""
    # Rimuove valori None
    punti = [p for p in coords_list if p is not None]
    if len(punti) < 2: return 0
    
    # Formatta per OSRM (longitudine, latitudine)
    locs = ";".join([f"{p[1]},{p[0]}" for p in punti])
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false"
        r = requests.get(url)
        if r.status_code == 200:
            return round(r.json()['routes'][0]['distance'] / 1000, 1)
    except: return 0
    return 0

# --- ESTRAZIONE DATI (LOGICA AGENDA) ---

def extract_localita(text):
    """Cerca la città nei campi Frazione o Città"""
    text_clean = text.replace("\\,", ",").replace("\n", " ")
    for tag in ["Frazione:", "Città:", "Citta:", "Località:"]:
        pattern = re.compile(f"{tag}\s*([^,;:\n]*)", re.IGNORECASE)
        match = pattern.search(text_clean)
        if match and match.group(1).strip():
            return match.group(1).strip().upper()
    return ""

def parse_ics_km_major(content):
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
            desc_full = (curr["summary"] + " " + curr["description"]).lower()
            # FILTRO AGENDA ORIGINALE
            if "nominativo" in desc_full and "codice fiscale" in desc_full:
                raw_dt = curr["dtstart"].split(":")[-1]
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    if dt.year >= 2024:
                        loc = extract_localita(curr["description"] + " " + curr["summary"])
                        if not loc and "-" in curr["summary"]:
                            loc = curr["summary"].split("-")[-1].strip().upper()
                        data.append({
                            "Data": dt.date(), "Ora": dt.time(), "Anno": dt.year,
                            "Settimana": dt.isocalendar()[1], "Mese": dt.month, "Località": loc
                        })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return data

# --- INTERFACCIA ---
st.set_page_config(page_title="Km Logistica v1.0", layout="wide")
st.title("🚗 Calcolo Chilometrico Dinamico")

@st.cache_data(ttl=600)
def get_data():
    content = requests.get(DRIVE_URL).text
    return parse_ics_km_major(content)

raw_events = get_data()

if raw_events:
    df = pd.DataFrame(raw_events)
    sel_week = st.number_input("Seleziona Settimana", 1, 53, datetime.date.today().isocalendar()[1])
    
    # Divisione Anni
    df_w = df[df["Settimana"] == sel_week]
    anni = sorted(df_w["Anno"].unique())
    
    if not df_w.empty:
        coords_casa = get_lat_lon(CASA_BASE)
        cols = st.columns(len(anni))
        
        for i, anno in enumerate(anni):
            with cols[i]:
                st.header(f"📅 {anno}")
                df_a = df_w[df_w["Anno"] == anno].sort_values(["Data", "Ora"])
                km_sett_tot = 0
                
                for g in df_a["Data"].unique():
                    tappe_nomi = df_a[df_a["Data"] == g]["Località"].tolist()
                    # Rimuove doppioni consecutivi (es. due appuntamenti stessa città)
                    tappe_nomi = [v for i, v in enumerate(tappe_nomi) if i == 0 or v != tappe_nomi[i-1]]
                    
                    # Costruisce itinerario coordinate
                    itinerario_coords = [coords_casa]
                    for t in tappe_nomi:
                        c = get_lat_lon(t)
                        if c: itinerario_coords.append(c)
                    itinerario_coords.append(coords_casa)
                    
                    # Calcolo Reale
                    distanza_giorno = get_strada_km(itinerario_coords)
                    km_sett_tot += distanza_giorno
                    
                    with st.expander(f"**{g.strftime('%d/%m')}**: {distanza_giorno} km"):
                        st.write(f"Giro: Basiliano ➔ {' ➔ '.join(tappe_nomi)} ➔ Basiliano")
                
                st.metric(f"Totale Km {anno}", f"{round(km_sett_tot,1)} km")
    else:
        st.info("Nessun appuntamento di lavoro trovato per questa settimana.")

    # TABELLA STORICA
    st.divider()
    st.subheader("📊 Riepilogo Chilometri Mensili")
    # Logica di calcolo mensile aggregata per la tabella (semplificata per velocità)
    pivot = df.groupby(['Mese', 'Anno']).size().unstack(fill_value=0)
    mesi_it = {1:"Gen", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mag", 6:"Giu", 7:"Lug", 8:"Ago", 9:"Set", 10:"Ott", 11:"Nov", 12:"Dic"}
    pivot.index = pivot.index.map(mesi_it)
    st.write("Totale appuntamenti per mese (analisi chilometrica in corso...)")
    st.dataframe(pivot)
else:
    st.error("Impossibile leggere i dati. Verifica la connessione a Drive.")
