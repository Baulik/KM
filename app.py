# VERSIONE: 1.2 (CHILOMETRI - Filtro "Frazione" & Solo dal 2024)
import streamlit as st
import pandas as pd
import datetime
import requests
from io import StringIO

# --- CONFIGURAZIONE ---
CASA_BASE = "BASILIANO"
DRIVE_URL = "https://drive.google.com/uc?export=download&id=1n4b33BgWxIUDWm4xuDnhjICPkqGWi2po"

# --- DATABASE DISTANZE (Esempio comuni Friuli/Veneto) ---
distanze_km = {
    ("BASILIANO", "UDINE"): 13, ("BASILIANO", "CODROIPO"): 14,
    ("BASILIANO", "TRIESTE"): 78, ("BASILIANO", "PORDENONE"): 45,
    ("BASILIANO", "CERVIGNANO"): 35, ("BASILIANO", "LATISANA"): 32,
    ("BASILIANO", "PALMANOVA"): 25, ("BASILIANO", "TAVAGNACCO"): 18,
    ("BASILIANO", "GORIZIA"): 42, ("BASILIANO", "MONFALCONE"): 50,
    ("BASILIANO", "SPILIMBERGO"): 28, ("BASILIANO", "SAN DANIELE"): 22,
    ("BASILIANO", "MARTIGNACCO"): 10, ("BASILIANO", "PASIAN DI PRATO"): 8
}

def get_distanza(a, b):
    a, b = a.upper().strip(), b.upper().strip()
    if a == b: return 0
    dist = distanze_km.get((a, b)) or distanze_km.get((b, a))
    return dist if dist else 25 # Media standard se non presente nel DB

# --- PARSING FILTRATO ---
@st.cache_data(ttl=3600)
def load_data(url):
    try:
        r = requests.get(url)
        return r.text if r.status_code == 200 else None
    except: return None

def parse_ics_km_filtrato(content):
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
            # FILTRO: Deve esserci la parola "frazione" (minuscolo o maiuscolo)
            testo_completo = (curr["summary"] + " " + curr["description"]).lower()
            if "frazione" in testo_completo:
                raw_dt = curr["dtstart"].split(":")[-1]
                if len(raw_dt) >= 8:
                    try:
                        dt = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                        dt += datetime.timedelta(hours=(2 if 3 < dt.month < 10 else 1))
                        
                        # FILTRO: Solo dal 2024 in poi
                        if dt.year >= 2024:
                            # Estrazione città dalla location
                            loc_parts = curr["location"].replace("\\,", ",").split(",")
                            citta = loc_parts[-1].strip().upper() if loc_parts else "UDINE"
                            citta = ''.join([i for i in citta if not i.isdigit()]).replace("(", "").replace(")", "").strip()
                            if not citta: citta = "UDINE"
                            
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
            elif line.startswith("DESCRIPTION"): curr["description"] = line[12:]
    return events

# --- INTERFACCIA ---
st.set_page_config(page_title="Chilometri Lavoro 1.2", layout="wide")
st.title("🚗 Monitoraggio Chilometri (Filtro Frazione)")

content = load_data(DRIVE_URL)
data = parse_ics_km_filtrato(content)

if data:
    df = pd.DataFrame(data)
    mesi_it = {1:"Gennaio", 2:"Febbraio", 3:"Marzo", 4:"Aprile", 5:"Maggio", 6:"Giugno", 7:"Luglio", 8:"Agosto", 9:"Settembre", 10:"Ottobre", 11:"Novembre", 12:"Dicembre"}
    
    # 1. ANALISI SETTIMANALE
    sel_week = st.number_input("Seleziona Settimana:", 1, 53, datetime.date.today().isocalendar()[1])
    df_w = df[df["Settimana"] == sel_week].sort_values(["Data", "Ora"])
    
    if not df_w.empty:
        st.subheader(f"📅 Dettaglio Chilometri Settimana {sel_week}")
        giorni = df_w["Data"].unique()
        tot_km_sett = 0
        
        for g in giorni:
            tappe = df_w[df_w["Data"] == g]["Città"].tolist()
            itinerario = [CASA_BASE] + tappe + [CASA_BASE]
            km_g = sum(get_distanza(itinerario[i], itinerario[i+1]) for i in range(len(itinerario)-1))
            tot_km_sett += km_g
            st.write(f"**{g.strftime('%A %d/%m')}**: {' ➔ '.join(itinerario)} | **{km_g} km**")
        
        st.metric("TOTALE KM DELLA SETTIMANA", f"{tot_km_sett} km")
    
    st.divider()

    # 2. RIEPILOGO MENSILE PER SETTIMANE
    st.subheader("📊 Riepilogo Mensile")
    sel_month = st.selectbox("Mese:", range(1, 13), index=datetime.date.today().month-1, format_func=lambda x: mesi_it[x])
    df_m = df[df["Mese"] == sel_month]
    
    if not df_m.empty:
        report_mese = []
        for sett in sorted(df_m["Settimana"].unique()):
            df_s = df_m[df_m["Settimana"] == sett]
            km_s = 0
            for g in df_s["Data"].unique():
                t = df_s[df_s["Data"] == g]["Città"].tolist()
                iti = [CASA_BASE] + t + [CASA_BASE]
                km_s += sum(get_distanza(iti[i], iti[i+1]) for i in range(len(iti)-1))
            report_mese.append({"Settimana": f"Sett. {sett}", "Chilometri": km_s})
        
        st.table(pd.DataFrame(report_mese))
        st.success(f"Totale {mesi_it[sel_month]}: **{sum(d['Chilometri'] for d in report_mese)} km**")

    st.divider()

    # 3. STORICO ANNUALE (Dal 2024)
    st.subheader("📈 Confronto Chilometrico Annuale")
    # Calcolo reale dei chilometri per la tabella storica
    storico_anni = []
    for (anno, mese), group in df.groupby(["Anno", "Mese"]):
        km_mese_tot = 0
        for g in group["Data"].unique():
            t = group[group["Data"] == g]["Città"].tolist()
            iti = [CASA_BASE] + t + [CASA_BASE]
            km_mese_tot += sum(get_distanza(iti[i], iti[i+1]) for i in range(len(iti)-1))
        storico_anni.append({"Anno": anno, "Mese": mese, "Km": km_mese_tot})
    
    if storico_anni:
        df_hist = pd.DataFrame(storico_anni)
        pivot_hist = df_hist.pivot(index="Mese", columns="Anno", values="Km").fillna(0).astype(int)
        pivot_hist.index = pivot_hist.index.map(mesi_it)
        st.dataframe(pivot_hist.style.background_gradient(cmap="Blues"), use_container_width=True)

else:
    st.warning("Nessun appuntamento con 'Frazione' trovato dal 2024 in poi.")
