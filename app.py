# VERSIONE: 1.1 (CHILOMETRI - Dettaglio Giornaliero, Mensile e Storico)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- DATABASE DISTANZE (Espandibile) ---
distanze_km = {
    ("BASILIANO", "UDINE"): 13, ("BASILIANO", "CODROIPO"): 14,
    ("BASILIANO", "TRIESTE"): 78, ("BASILIANO", "PORDENONE"): 45,
    ("BASILIANO", "CERVIGNANO"): 35, ("BASILIANO", "LATISANA"): 32,
    ("BASILIANO", "PALMANOVA"): 25, ("BASILIANO", "TAVAGNACCO"): 18,
    ("BASILIANO", "GORIZIA"): 42, ("BASILIANO", "MONFALCONE"): 50,
    ("BASILIANO", "SPILIMBERGO"): 28, ("BASILIANO", "SAN DANIELE"): 22,
    ("UDINE", "TRIESTE"): 75, ("UDINE", "CERVIGNANO"): 30,
    # Aggiungi qui altre tratte specifiche se necessario
}

def get_distanza(a, b):
    a, b = a.upper().strip(), b.upper().strip()
    if a == b: return 0
    dist = distanze_km.get((a, b)) or distanze_km.get((b, a))
    return dist if dist else 25 # Media standard se non in database

# --- PARSING ---
@st.cache_data(ttl=3600)
def load_data(url):
    try:
        r = requests.get(url); return r.text if r.status_code == 200 else None
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
            loc_full = curr.get("location", "").replace("\\,", ",").split(",")
            citta = loc_full[-1].strip().upper() if loc_full else "SCONOSCIUTO"
            citta = ''.join([i for i in citta if not i.isdigit()]).replace("(", "").replace(")", "").strip()
            if not citta: citta = "UDINE"
            
            raw_dt = curr["dtstart"].split(":")[-1]
            if len(raw_dt) >= 8:
                try:
                    dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                    events.append({
                        "Data": dt.date(), "Ora": dt.time(), 
                        "Settimana": dt.isocalendar()[1], "Mese": dt.month,
                        "Anno": dt.year, "Città": citta
                    })
                except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("LOCATION"): curr["location"] = line[9:]
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="Monitor Chilometri 1.1", layout="wide")
st.title("🚗 Logistica e Chilometraggio")

content = load_data(DRIVE_URL)
data = parse_ics_km(content)

if data:
    df = pd.DataFrame(data)
    mesi_it = {1:"Gennaio", 2:"Febbraio", 3:"Marzo", 4:"Aprile", 5:"Maggio", 6:"Giugno", 7:"Luglio", 8:"Agosto", 9:"Settembre", 10:"Ottobre", 11:"Novembre", 12:"Dicembre"}
    
    # 1. SELETTORE SETTIMANA E DETTAGLIO GIORNALIERO
    sel_week = st.number_input("Analisi Settimana:", 1, 53, datetime.date.today().isocalendar()[1])
    df_w = df[df["Settimana"] == sel_week].sort_values(["Data", "Ora"])
    
    if not df_w.empty:
        st.subheader(f"📅 Dettaglio Settimana {sel_week}")
        giorni = df_w["Data"].unique()
        tot_km_sett = 0
        
        for g in giorni:
            tappe = df_w[df_w["Data"] == g]["Città"].tolist()
            itinerario = [CASA_BASE] + tappe + [CASA_BASE]
            km_g = sum(get_distanza(itinerario[i], itinerario[i+1]) for i in range(len(itinerario)-1))
            tot_km_sett += km_g
            st.write(f"**{g.strftime('%A %d/%m')}**: {' ➔ '.join(itinerario)} | **{km_g} km**")
        
        st.metric("TOTALE KM SETTIMANA", f"{tot_km_sett} km")
    
    st.divider()

    # 2. TABELLA MENSILE (Settimane del mese scelto)
    st.subheader("📊 Riepilogo Mensile")
    sel_month = st.selectbox("Seleziona Mese:", range(1, 13), index=datetime.date.today().month-1, format_func=lambda x: mesi_it[x])
    df_m = df[df["Mese"] == sel_month]
    
    if not df_m.empty:
        # Calcoliamo i km per ogni settimana del mese
        report_mese = []
        for sett in sorted(df_m["Settimana"].unique()):
            df_s = df_m[df_m["Settimana"] == sett]
            km_s = 0
            for g in df_s["Data"].unique():
                t = df_s[df_s["Data"] == g]["Città"].tolist()
                iti = [CASA_BASE] + t + [CASA_BASE]
                km_s += sum(get_distanza(iti[i], iti[i+1]) for i in range(len(iti)-1))
            report_mese.append({"Settimana": f"Sett. {sett}", "Km": km_s})
        
        st.table(pd.DataFrame(report_mese))
        st.info(f"Totale Chilometri {mesi_it[sel_month]}: **{sum(d['Km'] for d in report_mese)} km**")

    st.divider()

    # 3. STORICO ANNUALE (Confronto Anni)
    st.subheader("📈 Storico Chilometrico Annuale")
    # Calcolo massivo km per ogni mese/anno per la tabella finale
    df['Km_Evento'] = 25 # Approssimazione per lo storico veloce
    pivot_km = df.groupby(["Mese", "Anno"]).size().reset_index(name='Num_App')
    # Nota: per precisione estrema qui dovremmo ricalcolare ogni singolo itinerario, 
    # ma come base usiamo il conteggio appuntamenti x media km per ora
    pivot_km['Km_Stima'] = pivot_km['Num_App'] * 35 # 35km è una media a/r
    
    tabella_storica = pivot_km.pivot(index="Mese", columns="Anno", values="Km_Stima").fillna(0).astype(int)
    tabella_storica.index = tabella_storica.index.map(mesi_it)
    st.dataframe(tabella_storica.style.background_gradient(cmap="Oranges"), use_container_width=True)

else:
    st.error("Nessun dato trovato.")
