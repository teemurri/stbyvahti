import streamlit as st
import requests
from datetime import datetime, timedelta, timezone
import time
import base64
from zoneinfo import ZoneInfo

# --- KONFIGURAATIO ---
LOCAL_TZ = ZoneInfo("Europe/Helsinki")

def get_base64_icon():
    try:
        with open("ikoni.png", "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            return f"data:image/png;base64,{encoded_string}"
    except FileNotFoundError:
        return None

version_tag = int(time.time())
icon_data = get_base64_icon()

st.set_page_config(
    page_title="Päivystysvahti",
    layout="wide",
    page_icon=icon_data if icon_data else "✈️"
)

# --- CSS-MUOTOILU ---
st.markdown("""
    <style>
    .block-container { padding-top: 4.5rem !important; }
    .main-title { font-size: 2.2rem; font-weight: 800; margin-bottom: 0px; color: #ffffff; }
    .label-text { font-size: 14px; font-weight: bold; margin-bottom: 5px; color: #eee; }
    .info-label { color: #aaa; font-size: 12px; }
    .status-box { 
        background-color: #1e1e1e; 
        padding: 10px; 
        border-radius: 5px; 
        border-left: 5px solid #333;
        margin-bottom: 20px;
        font-size: 0.9rem;
    }
    .ilmo-highlight { color: #ffaa00; font-weight: bold; }
    .soitto-kello { font-size: 0.85rem; color: #888; font-weight: normal; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; color: #444; text-align: center; font-size: 10px; padding: 10px; }
    div[data-testid="stButton"] { margin-top: 28px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ASETUKSET ---
REKKARIT_RAAKA = "EFGHIKLMNOPR"
REKKARIT = [f"OH-LK{l}" for l in REKKARIT_RAAKA]
IATA_HEL = "HEL"
YOPYVAT_KOHTEET = ["ARN", "BRU", "CDG", "CPH", "GOT", "RVN", "TLL"]
KELLO_VAIHTOEHDOT = [f"{h:02d}:00" for h in range(6, 25)]

if 'loydetyt' not in st.session_state:
    st.session_state.loydetyt = []
if 'ohitetut' not in st.session_state:
    st.session_state.ohitetut = []
if 'viimeisin_data' not in st.session_state:
    st.session_state.viimeisin_data = None
if 'haettu' not in st.session_state:
    st.session_state.haettu = False

# --- OTSAKKEET ---
st.markdown('<p class="main-title">Emppukuskin päivystysvahti ✈️</p>', unsafe_allow_html=True)

# --- SYÖTTEET ---
col_ui = st.columns([1.5, 1.0, 1.0])

with col_ui[0]:
    st.markdown('<p class="label-text">Päivystys päättyy (LT)</p>', unsafe_allow_html=True)
    paattymisaika_str = st.selectbox("Päättyy", KELLO_VAIHTOEHDOT, index=14, label_visibility="collapsed") # Default 20:00
with col_ui[1]:
    tarkista = st.button('HAE LENTOJA 🔍', use_container_width=True, type="primary")
with col_ui[2]:
    tyhjenna = st.button('TYHJENNÄ 🗑️', use_container_width=True)

if tyhjenna:
    st.session_state.loydetyt = []
    st.session_state.ohitetut = []
    st.session_state.viimeisin_data = None
    st.session_state.haettu = False
    st.rerun()

nykyhetki_paikallinen = datetime.now(LOCAL_TZ)
valittu_tunti = int(paattymisaika_str.split(':')[0])
if valittu_tunti == 24:
    paivystys_loppu_dt = datetime.combine(nykyhetki_paikallinen.date(), datetime.min.time()).replace(tzinfo=LOCAL_TZ) + timedelta(days=1)
else:
    paivystys_loppu_dt = datetime.combine(nykyhetki_paikallinen.date(), datetime.strptime(paattymisaika_str, "%H:%M").time()).replace(tzinfo=LOCAL_TZ)

if tarkista:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.flightradar24.com/"
    }
    ts = int(time.time())

    try:
        dep_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=departures&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=15)
        arr_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=arrivals&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=15)
        
        if dep_res.status_code == 200:
            departures = dep_res.json().get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('departures', {}).get('data', [])
            arrivals = arr_res.json().get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('arrivals', {}).get('data', [])

            if departures:
                last_f = departures[-1].get('flight', {})
                last_ts = last_f.get('time', {}).get('scheduled', {}).get('departure')
                if last_ts:
                    st.session_state.viimeisin_data = datetime.fromtimestamp(last_ts, tz=timezone.utc).astimezone(LOCAL_TZ).strftime('%H:%M')

            temp_loydetyt = []
            temp_ohitetut = []

            for item in departures:
                f = item.get('flight', {})
                reg = f.get('aircraft', {}).get('registration')
                
                if reg in REKKARIT:
                    dep_ts = f.get('time', {}).get('scheduled', {}).get('departure')
                    if not dep_ts: continue
                    
                    lahto_dt_lt = datetime.fromtimestamp(dep_ts, tz=timezone.utc).astimezone(LOCAL_TZ)
                    ilmo_dt_lt = lahto_dt_lt - timedelta(minutes=50)
                    soitto_raja_dt = lahto_dt_lt - timedelta(minutes=140)
                    min_lahtoon = int((lahto_dt_lt - nykyhetki_paikallinen).total_seconds() / 60)
                    kohde = f.get('airport', {}).get('destination', {}).get('code', {}).get('iata', '???')
                    
                    paluu_aika_lt = None
                    for arr_item in arrivals:
                        af = arr_item.get('flight', {})
                        if af.get('aircraft', {}).get('registration') == reg:
                            arr_ts = af.get('time', {}).get('scheduled', {}).get('arrival')
                            if arr_ts and dep_ts < arr_ts <= (dep_ts + 43200):
                                paluu_aika_lt = datetime.fromtimestamp(arr_ts, tz=timezone.utc).astimezone(LOCAL_TZ)
                                break
                    
                    # Jos paluu puuttuu ja lähtö on klo 20 tai myöhemmin, tulkitaan yöpyväksi
                    on_yopyva = (paluu_aika_lt is None and kohde in YOPYVAT_KOHTEET and lahto_dt_lt.hour >= 20)
                    
                    info = {
                        "reg": reg, "lento": f.get('identification', {}).get('number', {}).get('default', '???'), 
                        "kohde": kohde, "lahto": lahto_dt_lt, "ilmo": ilmo_dt_lt, "soitto_kello": soitto_raja_dt,
                        "soitto_min": min_lahtoon - 140, "paluu": paluu_aika_lt, "yopyva": on_yopyva
                    }

                    if min_lahtoon >= 140 and ilmo_dt_lt <= paivystys_loppu_dt:
                        if on_yopyva:
                            info["syy"] = "Yöpyvä (klo 20+)"
                            temp_ohitetut.append(info)
                        else:
                            temp_loydetyt.append(info)
                    else:
                        info["syy"] = "Päivystyksen jälkeinen" if ilmo_dt_lt > paivystys_loppu_dt else "Menneet"
                        temp_ohitetut.append(info)

            st.session_state.loydetyt = temp_loydetyt
            st.session_state.ohitetut = temp_ohitetut
            st.session_state.haettu = True

    except Exception:
        st.error("Tekninen häiriö.")

# --- TULOSTUS ---
if st.session_state.haettu:
    if st.session_state.viimeisin_data:
        st.markdown(f'<div class="status-box">🔍 <b>Datan kattavuus:</b> Lähtöjä klo <b>{st.session_state.viimeisin_data}</b> asti.</div>', unsafe_allow_html=True)

    if st.session_state.loydetyt:
        for k in sorted(st.session_state.loydetyt, key=lambda x: x['ilmo']):
            c1, c2, c3 = st.columns([1, 2.5, 2.5])
            with c1: st.markdown(f"### {k['reg']}")
            with c2:
                paluu_str = k['paluu'].strftime('%H:%M') if k['paluu'] else ("🌙 Yöpyvä" if k['yopyva'] else "—")
                st.markdown(f"**{k['lento']}** ➡️ **{k['kohde']}**")
                st.markdown(f"<span class='info-label'>Lähtö:</span> **{k['lahto'].strftime('%H:%M')}** | <span class='info-label'>Paluu:</span> **{paluu_str}**", unsafe_allow_html=True)
                st.markdown(f"<span class='info-label'>Ilmoittautuminen (LT):</span> <span class='ilmo-highlight'>{k['ilmo'].strftime('%H:%M')}</span>", unsafe_allow_html=True)
            with c3:
                color = "#00ff00" if k['soitto_min'] > 30 else "#ff4b4b"
                st.markdown(f"""
                    <div style='text-align:right;'>
                        <span style='color:{color}; font-size: 0.8rem;'>Soittoaikaa:</span><br>
                        <b style='font-size: 1.4rem; color:{color};'>{k['soitto_min']} min</b><br>
                        <span class='soitto-kello'>(viim. klo {k['soitto_kello'].strftime('%H:%M')})</span>
                    </div>
                """, unsafe_allow_html=True)
            st.divider()
    else:
        st.info("Ei aktiivisia keikkoja.")

    if st.session_state.ohitetut:
        with st.expander("Muut havainnot (Hylätyt/Ohitetut)"):
            for o in sorted(st.session_state.ohitetut, key=lambda x: x['lahto']):
                st.caption(f"{o['lahto'].strftime('%H:%M')} | {o['reg']} | {o['lento']} ➡️ {o['kohde']} | Syy: {o['syy']}")

st.markdown('<div class="footer">Emppukuskin työkalu</div>', unsafe_allow_html=True)
