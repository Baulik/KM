# VERSIONE: 1.3 (CORREZIONE FILTRI: Nominativo + Frazione + 2024)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO

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
    return dist if dist else 25 # Media standard se non in DB

# --- PARSING ROBUSTO ---
@st.cache_data(ttl=600)
def load_data(url):
    try:
        r = requests.get(url)
        return r.text if r.status_code == 200 else None
    except: return None

def parse_ics_km_final(content):
    if not content: return []
    events = []
    lines = StringIO(content).readlines()
    in_event = False
    curr = {"summary": "", "description": "", "dtstart": "", "location": ""}
    
    for line in lines:
        line = line.strip()
        if line.startswith("BEGIN:VEVENT"):
            in_event = True
            curr = {"summary": "", "description": "", "dtstart": "", "location": ""}
        elif line.startswith("END:VEVENT"):
            in_event = False
            
            # UNIAMO TUTTI I TESTI PER LA RICERCA
            testo_completo = f"{curr['summary']} {curr['description']} {curr['location']}".lower()
            
            # FILTRO: Deve contenere SIA 'nominativo' SIA 'frazione'
            if "nominativo" in testo_completo and "frazione" in testo_completo:
                raw_dt = curr["dtstart"].split(":")[-1]
                if len(raw_dt) >= 8:
                    try:
                        dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                        dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                        
                        # FILTRO: Solo dal 2024
                        if dt.year >= 2024:
                            # Estrazione città dalla location o dal summary
                            loc_raw = curr["location"].replace("\\,", ",").split(",")
                            citta = loc_raw[-1].strip().upper() if loc_raw and loc_raw[-1] else "UDINE"
                            # Pulizia caratteri non alfabetici
                            citta = ''.join([i for i in citta if i.isalpha() or i.isspace()]).strip()
                            
                            events.append({
                                "Data": dt.date(), "Ora": dt.time(), 
                                "Settimana": dt.isocalendar()[1], "Mese": dt.month,
                                "Anno": dt.year, "Città": citta if citta else "UDINE"
                            })
                    except: continue
        elif in_event:
            if line.startswith("DTSTART"): curr["dtstart"] = line
            elif line.startswith("LOCATION"): curr["location"] = line[9:]
            elif line.startswith("SUMMARY"): curr["summary"] = line[8:]
            elif line.startswith("DESCRIPTION"): curr["description"] += line[12:]
            
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="App KM 1.3", layout="wide")
st.title("🚗 Calcolo Chilometri Professionale")

content = load_data(DRIVE_URL)
data = parse_ics_km_final(content)

if data:
    df = pd.DataFrame(data)
    mesi_it = {1:"Gennaio", 2:"Febbraio", 3:"Marzo", 4:"Aprile", 5:"Maggio", 6:"Giugno", 7:"Luglio", 8:"Agosto", 9:"Settembre", 10:"Ottobre", 11:"Novembre", 12:"Dicembre"}
    
    # 1. ANALISI SETTIMANALE (DETTAGLIO GIORNI)
    sel_week = st.number_input("Settimana da analizzare:", 1, 53, datetime.date.today().isocalendar()[1])
    df_w = df[df["Settimana"] == sel_week].sort_values(["Data", "Ora"])
    
    if not df_w.empty:
        st.subheader(f"📊 Dettaglio Giornaliero Settimana {sel_week}")
        giorni = df_w["Data"].unique()
        tot_km_sett = 0
        
        for g in giorni:
            tappe = df_w[df_w["Data"] == g]["Città"].tolist()
            itinerario = [CASA_BASE] + tappe + [CASA_BASE]
            km_g = sum(get_distanza(itinerario[i], itinerario[i+1]) for i in range(len(itinerario)-1))
            tot_km_sett += km_g
            st.info(f"📅 **{g.strftime('%d/%m')}**: {' ➔ '.join(itinerario)} | **{km_g} km**")
        
        st.metric("TOTALE KM SETTIMANA", f"{tot_km_sett} km")
    else:
        st.warning(f"Nessun appuntamento valido trovato per la settimana {sel_week}.")

    st.divider()

    # 2. RIEPILOGO MENSILE
    st.subheader("📅 Riepilogo Mensile per Settimane")
    df_m = df[df["Mese"] == datetime.date.today().month]
    if not df_m.empty:
        report_mese = []
        for sett in sorted(df_m["Settimana"].unique()):
            df_s = df_m[df_m["Settimana"] == sett]
            km_s = sum(sum(get_distanza(([CASA_BASE]+df_s[df_s["Data"]==g]["Città"].tolist()+[CASA_BASE])[i], ([CASA_BASE]+df_s[df_s["Data"]==g]["Città"].tolist()+[CASA_BASE])[i+1]) for i in range(len([CASA_BASE]+df_s[df_s["Data"]==g]["Città"].tolist()+[CASA_BASE])-1)) for g in df_s["Data"].unique())
            report_mese.append({"Settimana": f"Sett. {sett}", "Km": km_s})
        st.table(pd.DataFrame(report_mese))

    # 3. STORICO ANNUALE
    st.subheader("📈 Storico Chilometrico (Confronto Anni)")
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
        st.dataframe(pivot.style.background_gradient(cmap="Reds"), use_container_width=True)
else:
    st.error("Nessun dato trovato con i criteri: 'Nominativo' + 'Frazione' + 'Anno >= 2024'.")
