# VERSIONE: 1.0 (PROGETTO CHILOMETRI - Logica Giro Visite)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- MOTORE DI CALCOLO DISTANZE (Base FVG/Veneto) ---
# In questa fase usiamo un dizionario di distanze note. 
# Se la città non è in lista, calcoliamo una media cautelativa di 25km.
distanze_km = {
    ("BASILIANO", "UDINE"): 13, ("BASILIANO", "CODROIPO"): 14,
    ("BASILIANO", "TRIESTE"): 78, ("BASILIANO", "PORDENONE"): 45,
    ("BASILIANO", "CERVIGNANO"): 35, ("BASILIANO", "LATISANA"): 32,
    ("BASILIANO", "PALMANOVA"): 25, ("BASILIANO", "TAVAGNACCO"): 18,
    ("UDINE", "TRIESTE"): 75, ("UDINE", "CERVIGNANO"): 30,
    ("UDINE", "CODROIPO"): 25, ("CODROIPO", "LATISANA"): 20,
    # Aggiungeremo altre tratte man mano che le città compaiono nei tuoi dati
}

def get_distanza(a, b):
    a, b = a.upper().strip(), b.upper().strip()
    if a == b: return 0
    # Cerca la tratta (A->B o B->A)
    dist = distanze_km.get((a, b)) or distanze_km.get((b, a))
    return dist if dist else 25 # Media standard se non censita

# --- PARSING DATI ---
@st.cache_data(ttl=3600)
def load_data(url):
    try:
        r = requests.get(url)
        return r.text if r.status_code == 200 else None
    except: return None

def parse_ics_km(content):
    if not content: return []
    events = []
    lines = StringIO(content).readlines()
    in_event = False
    curr = {}
    for line in lines:
        line = line.strip()
        if line.startswith("BEGIN:VEVENT"):
            in_event = True
            curr = {"summary": "", "dtstart": "", "location": ""}
        elif line.startswith("END:VEVENT"):
            in_event = False
            # Estraiamo la città (solitamente l'ultima parola della LOCATION)
            loc_full = curr.get("location", "").replace("\\,", ",").split(",")
            citta = loc_full[-1].strip().upper() if loc_full else "SCONOSCIUTO"
            # Pulizia da CAP o parentesi
            citta = ''.join([i for i in citta if not i.isdigit()]).replace("(", "").replace(")", "").strip()
            
            raw_dt = curr["dtstart"].split(":")[-1]
            if len(raw_dt) >= 8:
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    events.append({
                        "Data": dt.date(), "Ora": dt.time(), "Settimana": dt.isocalendar()[1],
                        "Città": citta if citta else "UDINE"
                    })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("LOCATION"): curr["location"] = line[9:]
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="App Chilometri 1.0", layout="wide")
st.title("🛣️ Monitoraggio Chilometrico Lavoro")
st.markdown(f"Partenza e Rientro fissati a: **{CASA_BASE}**")

content = load_data(DRIVE_URL)
data = parse_ics_km(content)

if data:
    df = pd.DataFrame(data)
    sel_week = st.number_input("Analisi Settimana:", 1, 53, datetime.date.today().isocalendar()[1])
    
    # Filtro e ordinamento temporale (fondamentale per il giro visite)
    df_w = df[df["Settimana"] == sel_week].sort_values(["Data", "Ora"])
    
    if not df_w.empty:
        giorni = df_w["Data"].unique()
        tot_km_sett = 0
        
        st.subheader(f"Riepilogo Settimana {sel_week}")
        
        for g in giorni:
            tappe_giorno = df_w[df_w["Data"] == g]["Città"].tolist()
            # Costruiamo il percorso: Casa -> Tappa 1 -> Tappa 2 -> Casa
            itinerario = [CASA_BASE] + tappe_giorno + [CASA_BASE]
            
            km_g = 0
            for i in range(len(itinerario) - 1):
                km_g += get_distanza(itinerario[i], itinerario[i+1])
            
            tot_km_sett += km_g
            
            # Visualizzazione a "Card"
            with st.expander(f"📅 {g.strftime('%A %d/%m')} — {km_g} km"):
                st.write("**Percorso della giornata:**")
                st.write(" ➔ ".join(itinerario))
                st.caption("Il calcolo include il rientro a Basiliano dopo l'ultima tappa.")

        st.divider()
        c1, c2 = st.columns(2)
        c1.metric("Totale Chilometri", f"{tot_km_sett} km")
        c2.metric("Media Giornaliera", f"{round(tot_km_sett/len(giorni), 1)} km")
        
    else:
        st.warning("Nessun appuntamento trovato per questa settimana.")
else:
    st.error("Errore nel caricamento dei dati da Google Drive.")
