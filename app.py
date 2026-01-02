# VERSIONE: 3.2 (CHILOMETRI - Multi-Database CSV Friuli & Veneto)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO
import re

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- CARICAMENTO DATABASE COMUNI ---
@st.cache_data
def load_full_db():
    try:
        # Carica Friuli
        df_f = pd.read_csv("friuli.csv")
        # Carica Veneto
        df_v = pd.read_csv("veneto.csv")
        
        # Unisce i due database
        df_full = pd.concat([df_f, df_v], ignore_index=True)
        df_full['comune'] = df_full['comune'].str.upper().str.strip()
        
        # Rimuove eventuali duplicati e crea il dizionario delle coordinate
        return pd.Series(list(zip(df_full.lat, df_full.lon)), index=df_full.comune).to_dict()
    except Exception as e:
        st.error(f"Errore nel caricamento dei file CSV: {e}")
        return {"BASILIANO": (46.01, 13.10), "UDINE": (46.06, 13.24)}

DB_COORDS = load_full_db()

# --- LOGICA DI PULIZIA E RICERCA ---

def pulisci_ics_text(testo_grezzo):
    """Sana i testi spezzati da Google ICS"""
    testo = testo_grezzo.replace("\n ", "").replace("\r ", "")
    testo = testo.replace("\\n", " ").replace("\\,", ",")
    return testo

def estrai_citta_intelligente(testo_pulito):
    """Radar di ricerca: cerca match esatti nel database partendo dai nomi più lunghi"""
    testo_up = testo_pulito.upper()
    
    # Priorità 1: Cerca il valore dopo l'etichetta 'Città'
    match = re.search(r"CITTÀ\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s[A-ZÀ-Ú][a-zà-ú]+)*)", testo_up)
    if match:
        citta_potenziale = match.group(1).strip()
        if citta_potenziale in DB_COORDS:
            return citta_potenziale

    # Priorità 2: Scansione Radar su tutto il testo (per i nomi composti come 'SESTO AL REGHENA')
    # Ordiniamo le chiavi per lunghezza decrescente per evitare match parziali
    for comune in sorted(DB_COORDS.keys(), key=len, reverse=True):
        if comune in testo_up:
            return comune
            
    return "UDINE" # Fallback standard

@st.cache_data(ttl=86400)
def calcola_distanza_osrm(nomi_tappe):
    """Calcola l'itinerario stradale reale"""
    punti = [DB_COORDS.get(n, DB_COORDS["UDINE"]) for n in nomi_tappe]
    if len(punti) < 2: return 0
    
    # Formato OSRM: lon,lat
    locs = ";".join([f"{p[1]},{p[0]}" for p in punti])
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{locs}?overview=false"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return round(r.json()['routes'][0]['distance'] / 1000, 1)
    except:
        return 0
    return 0

# --- PARSING CALENDARIO ---

def parse_ics_v32(content):
    if not content: return []
    events = []
    # Rimuove i salti riga che spezzano le parole
    content_fixed = content.replace("\r\n ", "").replace("\n ", "")
    
    segments = content_fixed.split("BEGIN:VEVENT")
    for seg in segments:
        if "END:VEVENT" in seg:
            # Data inizio
            start_match = re.search(r"DTSTART:(\d{8})", seg)
            if start_match:
                dt = datetime.datetime.strptime(start_match.group(1), "%Y%m%d")
                
                # Estrazione corpo testo
                summary_match = re.search(r"SUMMARY:(.*?)TRANSP:", seg, re.DOTALL)
                text = pulisci_ics_text(summary_match.group(1)) if summary_match else ""
                
                # Filtro: Solo appuntamenti con Nominativo
                if "NOMINATIVO" in text.upper():
                    citta = estrai_citta_intelligente(text)
                    events.append({
                        "Data": dt.date(),
                        "Settimana": dt.isocalendar()[1],
                        "Anno": dt.year,
                        "Città": citta
                    })
    return events

# --- INTERFACCIA STREAMLIT ---

st.set_page_config(page_title="KM Monitor 3.2", layout="wide")
st.title("🚗 Monitor Chilometri FVG & Veneto")

try:
    response = requests.get(DRIVE_URL)
    data = parse_ics_v32(response.text) if response.status_code == 200 else []
except:
    data = []

if data:
    df = pd.DataFrame(data)
    sel_week = st.number_input("Seleziona Settimana", 1, 53, datetime.date.today().isocalendar()[1])
    df_w = df[df["Settimana"] == sel_week]
    
    if not df_w.empty:
        for anno in sorted(df_w["Anno"].unique()):
            st.subheader(f"📅 Anno {anno}")
            df_a = df_w[df_w["Anno"] == anno].sort_values("Data")
            tot_km_anno = 0
            
            for g in df_a["Data"].unique():
                tappe = df_a[df_a["Data"] == g]["Città"].tolist()
                # Costruisce il giro: Casa -> Tappe -> Casa
                percorso = [CASA_BASE] + tappe + [CASA_BASE]
                dist = calcola_distanza_osrm(percorso)
                tot_km_anno += dist
                
                with st.expander(f"**{g.strftime('%d/%m')}**: {dist} km"):
                    st.write(f"🚩 Percorso: {' ➔ '.join(percorso)}")
            
            st.metric(f"Totale Settimanale {anno}", f"{round(tot_km_anno, 1)} km")
    else:
        st.info(f"Nessun appuntamento trovato per la settimana {sel_week}")
else:
    st.error("Dati non caricati. Verifica la connessione o i file CSV.")
