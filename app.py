# VERSIONE: 1.1 (CHILOMETRI - Database Completo da CSV)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO

# --- CONFIGURAZIONE ---
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- CARICAMENTO DATI ---
@st.cache_data
def load_full_db():
    try:
        fvg = pd.read_csv('distanze_basiliano_fvg.csv')
        ven = pd.read_csv('distanze_basiliano_veneto.csv')
        df_tot = pd.concat([fvg, ven])
        # Creiamo dizionario: { 'COMUNE': Distanza_AR }
        return dict(zip(df_tot['comune'].str.upper(), df_tot['Distanza_AR']))
    except:
        return {}

db_km = load_full_db()

def calcola_km(tappe):
    if not tappe: return 0
    # Somma delle distanze AR di tutte le tappe trovate
    somma_ar = sum(db_km.get(t.upper(), 26.0) for t in tappe)
    
    # REGOLA: 1 tappa = 100%, 2+ tappe = Somma - 25%
    if len(tappe) == 1:
        return round(somma_ar, 1)
    return round(somma_ar * 0.75, 1)

def parse_ics(content):
    if not content: return []
    events = []
    lines = StringIO(content).readlines()
    in_event = False
    curr = {"summary": "", "description": "", "dtstart": ""}
    
    comuni_lista = list(db_km.keys())
    # Ordiniamo per lunghezza decrescente per evitare match parziali errati
    comuni_lista.sort(key=len, reverse=True)

    for line in lines:
        line = line.strip()
        if line.startswith("BEGIN:VEVENT"):
            in_event = True
            curr = {"summary": "", "description": "", "dtstart": ""}
        elif line.startswith("END:VEVENT"):
            in_event = False
            full_text = f"{curr['summary']} {curr['description']}".upper()
            if "NOMINATIVO" in full_text and "CODICE FISCALE" in full_text:
                # Trova tutte le tappe del giorno nel database
                tappe_rilevate = []
                for c in comuni_lista:
                    if c in full_text:
                        tappe_rilevate.append(c)
                        break # Prende il primo comune trovato nell'evento
                
                raw_dt = curr["dtstart"].split(":")[-1]
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    events.append({
                        "Data": dt.date(),
                        "Anno": dt.year,
                        "Settimana": dt.isocalendar()[1],
                        "Comune": tappe_rilevate[0] if tappe_rilevate else "UDINE"
                    })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="KM Monitor 1.1", layout="wide")

if not db_km:
    st.error("File CSV non trovati! Carica distanze_basiliano_fvg.csv e distanze_basiliano_veneto.csv")
else:
    r = requests.get(DRIVE_URL)
    data = parse_ics(r.text) if r.status_code == 200 else []
    
    if data:
        df = pd.DataFrame(data)
        week = st.number_input("Settimana", 1, 53, datetime.date.today().isocalendar()[1])
        df_w = df[df["Settimana"] == week]
        
        if not df_w.empty:
            anni = sorted(df_w["Anno"].unique())
            cols = st.columns(len(anni))
            for i, anno in enumerate(anni):
                with cols[i]:
                    st.header(f"📅 {anno}")
                    df_a = df_w[df_w["Anno"] == anno].sort_values("Data")
                    tot_km_sett = 0
                    for g in df_a["Data"].unique():
                        tappe_g = df_a[df_a["Data"] == g]["Comune"].tolist()
                        km_g = calcola_km(tappe_g)
                        tot_km_sett += km_g
                        with st.expander(f"{g.strftime('%d/%m')} - {km_g} km"):
                            st.write(f"Tappe: {', '.join(tappe_g)}")
                    st.metric(f"Totale {anno}", f"{round(tot_km_sett,1)} km")
