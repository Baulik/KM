# VERSIONE: 1.5 (Sperimentale - Contatore Appuntamenti Giornaliero)
import streamlit as st
import pandas as pd
import datetime
from io import StringIO

# --- FUNZIONI DI SUPPORTO ---

def calcola_pasqua(anno):
    a = anno % 19
    b = anno // 100
    c = anno % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = ((h + l - 7 * m + 114) % 31) + 1
    pasqua = datetime.date(anno, mese, giorno)
    pasquetta = pasqua + datetime.timedelta(days=1)
    return pasqua, pasquetta

def get_festivita(anno):
    pasqua, pasquetta = calcola_pasqua(anno)
    return {
        datetime.date(anno, 1, 1): "Capodanno",
        datetime.date(anno, 1, 6): "Epifania",
        datetime.date(anno, 4, 25): "Liberazione",
        datetime.date(anno, 5, 1): "1 Maggio",
        datetime.date(anno, 6, 2): "Repubblica",
        datetime.date(anno, 8, 15): "Ferragosto",
        datetime.date(anno, 11, 1): "Ognissanti",
        datetime.date(anno, 12, 8): "Immacolata",
        datetime.date(anno, 12, 25): "Natale",
        datetime.date(anno, 12, 26): "S. Stefano",
        pasqua: "Pasqua",
        pasquetta: "Pasquetta"
    }

def assegna_corsia(ora_str):
    try:
        h = int(ora_str.split(":")[0])
        m = int(ora_str.split(":")[1])
        tempo = h + m/60
        if tempo <= 11.75: return 0    
        elif 12.0 <= tempo <= 17.25: return 1 
        else: return 2                 
    except: return 1

def get_fascia_oraria(hour): 
    if hour < 9: return "08:00-09:00"
    elif 9 <= hour < 11: return "09:00-11:00"
    elif 11 <= hour < 13: return "11:00-13:00"
    elif 13 <= hour < 15: return "13:00-15:00"
    elif 15 <= hour < 17: return "15:00-17:00"
    elif 17 <= hour < 19: return "17:00-19:00"
    else: return "19:00-22:00"

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Dashboard Appuntamenti PRO", layout="wide")

st.markdown("""
<style>
    thead tr th:first-child {display:none}
    tbody th {display:none}
    div[data-testid="stNumberInput"] input { font-size: 24px !important; font-weight: bold; color: #c0392b; text-align: center; }
    
    .year-card { border: 1px solid #dcdde1; border-radius: 12px; padding: 15px; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .grid-table { width: 100%; border-collapse: separate; border-spacing: 2px; table-layout: fixed; }
    .grid-table td { border-bottom: 1px solid #f1f2f6; padding: 8px 2px; vertical-align: middle; height: 50px; border-radius: 4px; }
    
    .day-label { width: 22%; font-weight: bold; font-size: 11px; color: #7f8c8d; text-transform: uppercase; background-color: white !important; }
    .time-slot { width: 26%; text-align: center; font-size: 13px; color: #2c3e50; font-weight: bold; line-height: 1.1; }
    
    .free-slot { background-color: #d1dce5; border: 1px solid #b8c5d1; }
    .busy-slot { background-color: #ffffff; border: 1px solid #e1e8ed; color: #2980b9; }
    
    .holiday-label { display: block; font-size: 9px; color: #e67e22; font-weight: normal; }
    .insight-box { background-color: #f8f9fa; border-left: 5px solid #2980b9; padding: 15px; border-radius: 8px; margin-bottom: 20px; }

    /* MOBILE RESPONSIVE */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] { flex-direction: column !important; }
        .day-label { font-size: 10px; width: 20%; }
        .time-slot { font-size: 11px; }
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Carico di Lavoro Storico")

uploaded_file = st.file_uploader("📂 Carica il file .ics", type="ics")

if uploaded_file:
    stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
    data = []
    current_event = {"summary": "", "description": "", "dtstart": ""}
    in_event = False
    
    for line in stringio:
        line = line.strip()
        if line.startswith("BEGIN:VEVENT"):
            in_event = True
            current_event = {"summary": "", "description": "", "dtstart": ""}
        elif line.startswith("END:VEVENT"):
            in_event = False
            full_text = (current_event["summary"] + " " + current_event["description"]).lower()
            if "nominativo" in full_text and "codice fiscale" in full_text:
                raw_dt = current_event["dtstart"].split(":")[-1]
                if len(raw_dt) >= 8:
                    try:
                        dt_obj = datetime.datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                        dt_obj += datetime.timedelta(hours=(2 if 3 < dt_obj.month < 10 else 1))
                        data.append({
                            "Data": dt_obj.date(), "Anno": dt_obj.year, "Settimana": dt_obj.isocalendar()[1],
                            "Giorno": dt_obj.weekday(), "Ora_Esatta": dt_obj.strftime("%H:%M"),
                            "Ora_Num": dt_obj.hour, "Fascia": get_fascia_oraria(dt_obj.hour)
                        })
                    except: continue
        elif in_event:
            if line.startswith("DTSTART"): current_event["dtstart"] = line
            elif line.startswith("SUMMARY:"): current_event["summary"] = line[8:]
            elif "Nominativo" in line or "Codice fiscale" in line: current_event["description"] += line

    if data:
        df = pd.DataFrame(data)
        mesi_it = {1:"Gennaio", 2:"Febbraio", 3:"Marzo", 4:"Aprile", 5:"Maggio", 6:"Giugno", 7:"Luglio", 8:"Agosto", 9:"Settembre", 10:"Ottobre", 11:"Novembre", 12:"Dicembre"}
        giorni_it_comp = {0:"Lunedì", 1:"Martedì", 2:"Mercoledì", 3:"Giovedì", 4:"Venerdì", 5:"Sabato"}
        giorni_it_abr = {0:"Lun", 1:"Mar", 2:"Mer", 3:"Gio", 4:"Ven", 5:"Sab"}
        
        oggi = datetime.date.today()
        sett_corrente = oggi.isocalendar()[1]
        
        c_sel, c_info = st.columns([1, 2])
        with c_sel:
            sel_week = st.number_input("Settimana:", 1, 53, sett_corrente)
        
        ref_start = datetime.date.fromisocalendar(oggi.year, sel_week, 1)
        ref_end = datetime.date.fromisocalendar(oggi.year, sel_week, 7)
        c_info.info(f"Riferimento Settimana {sel_week}: dal **{ref_start.day} {mesi_it[ref_start.month]}** al **{ref_end.day} {mesi_it[ref_end.month]}**")

        df_week = df[df["Settimana"] == sel_week]
        
        if not df_week.empty:
            # --- INSIGHT STORICO ---
            stats = df_week.groupby("Giorno")["Ora_Esatta"].count()
            giorno_piu_carico = giorni_it_comp[stats.idxmax()]
            liberi = [g for g in range(6) if g not in stats.index]
            giorni_liberi_txt = "nessuno" if not liberi else ", ".join([giorni_it_comp[g] for g in liberi])
            
            st.markdown(f"""
            <div class='insight-box'>
                <b>💡 Analisi Storica Settimana {sel_week}</b><br>
                • Solitamente il giorno più impegnato è il <b>{giorno_piu_carico}</b>.<br>
                • Storicamente sei rimasto libero nei giorni di: <b>{giorni_liberi_txt}</b>.<br>
            </div>
            """, unsafe_allow_html=True)

            # --- CARD ANNI ---
            anni = sorted(df_week["Anno"].unique()) 
            cols = st.columns(len(anni))
            
            for idx, anno in enumerate(anni):
                with cols[idx]:
                    df_anno = df_week[df_week["Anno"] == anno]
                    feste_anno = get_festivita(anno)
                    
                    rows_html = ""
                    for g_idx in range(6): 
                        g_nome = giorni_it_abr[g_idx]
                        data_precisa = datetime.date.fromisocalendar(anno, sel_week, g_idx+1)
                        festa_nome = feste_anno.get(data_precisa, "")
                        festa_label = f"<span class='holiday-label'>{festa_nome}</span>" if festa_nome else ""
                        
                        eventi_giorno = df_anno[df_anno["Giorno"] == g_idx]
                        num_app = len(eventi_giorno) # Conteggio per il giorno
                        
                        corsie = ["", "", ""]
                        for _, row in eventi_giorno.sort_values("Ora_Esatta").iterrows():
                            c_idx = assegna_corsia(row["Ora_Esatta"])
                            corsie[c_idx] += f"<div>{row['Ora_Esatta']}</div>"

                        cls = ["time-slot " + ("busy-slot" if c else "free-slot") for c in corsie]

                        rows_html += f"""
                        <tr>
                            <td class="day-label">{g_nome} ({num_app}) {festa_label}</td>
                            <td class="{cls[0]}">{corsie[0]}</td>
                            <td class="{cls[1]}">{corsie[1]}</td>
                            <td class="{cls[2]}">{corsie[2]}</td>
                        </tr>"""

                    st.markdown(f"""
                    <div class="year-card">
                        <h3 style="text-align:center; color:#2d3436; margin-bottom:10px;">{anno}</h3>
                        <table class="grid-table">{rows_html}</table>
                        <div style="text-align:center; font-size:12px; color:#95a5a6; margin-top:10px;">{len(df_anno)} appuntamenti totali</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.warning("Nessun dato storico per questa settimana.")

        # --- PANORAMICA ANNUALE ---
        st.markdown("---")
        st.subheader("📊 Panoramica Annuale")
        df["Mese_Testo"] = df["Data"].apply(lambda x: mesi_it[x.month])
        pivot = df.pivot_table(index="Mese_Testo", columns="Anno", values="Ora_Num", aggfunc="count", fill_value=0)
        pivot = pivot.reindex([m for m in mesi_it.values() if m in pivot.index])
        st.dataframe(pivot.style.background_gradient(cmap="Reds"), use_container_width=True)

        c_sx, c_dx = st.columns([1, 2])
        with c_sx:
            st.write("### Giorno più carico")
            st.bar_chart(df["Giorno"].map(giorni_it_abr).value_counts())
        with c_dx:
            st.write("### Mappa Oraria (Fasce)")
            p_orari = df.pivot_table(index="Giorno", columns="Fascia", values="Anno", aggfunc="count", fill_value=0)
            p_orari.index = p_orari.index.map({0:"Lun", 1:"Mar", 2:"Mer", 3:"Gio", 4:"Ven", 5:"Sab", 6:"Dom"})
            st.dataframe(p_orari.style.background_gradient(cmap="Blues"), use_container_width=True)