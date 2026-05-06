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
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; color: #444; text-align: center; font-size: 10px; padding: 10px; }
    div[data-testid="stButton"] { margin-top: 21px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ASETUKSET ---
REKKARIT_RAAKA = "EFGHIKLMNOPR"
REKKARIT = [f"OH-LK{l}" for l in REKKARIT_RAAKA]
IATA_HEL = "HEL"
YOPYVAT_KOHTEET = ["ARN", "BRU", "CDG", "CPH", "GOT", "RVN", "TLL"]

# --- OTSAKKEET ---
st.markdown('<p class="main-title">Emppukuskin päivystysvahti ✈️</p>', unsafe_allow_html=True)

# --- SYÖTTEET ---
col_ui = st.columns([1.5, 1.2, 1.2, 0.5])

with col_ui[0]:
    st.markdown('<p class="label-text">Päivystyksen pituus</p>', unsafe_allow_html=True)
    paivystys_tyyppi = st.selectbox("Pituus", ["1 pv", "2 pv"], label_visibility="collapsed")
with col_ui[1]:
    st.markdown('<p class="label-text">Päivystys päättyy (LT)</p>', unsafe_allow_html=True)
    paattymisaika = st.time_input("Päättyy", value=datetime.strptime("20:00", "%H:%M").time(), label_visibility="collapsed")
with col_ui[2]:
    tarkista = st.button('HAE LENTOJA 🔍', use_container_width=True, type="primary")

nykyhetki_paikallinen = datetime.now(LOCAL_TZ)
paivystys_loppu_dt = datetime.combine(nykyhetki_paikallinen.date(), paattymisaika).replace(tzinfo=LOCAL_TZ)

if tarkista:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    ts = int(time.time())

    try:
        dep_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=departures&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=15)
        arr_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=arrivals&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=15)
        
        departures = dep_res.json().get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('departures', {}).get('data', [])
        arrivals = arr_res.json().get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('arrivals', {}).get('data', [])

        loydetyt = []
        ohitetut = []

        for item in departures:
            f = item.get('flight', {})
            reg = f.get('aircraft', {}).get('registration')
            
            if reg in REKKARIT:
                dep_ts = f.get('time', {}).get('scheduled', {}).get('departure')
                if not dep_ts: continue
                
                lahto_dt_lt = datetime.fromtimestamp(dep_ts, tz=timezone.utc).astimezone(LOCAL_TZ)
                ilmo_dt_lt = lahto_dt_lt - timedelta(minutes=50)
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
                
                on_yopyva = False
                if paluu_aika_lt is None and kohde in YOPYVAT_KOHTEET and lahto_dt_lt.hour >= 20:
                    on_yopyva = True
                
                info = {
                    "reg": reg, "lento": f.get('identification', {}).get('number', {}).get('default', '???'), 
                    "kohde": kohde, "lahto": lahto_dt_lt, "ilmo": ilmo_dt_lt, "soitto_min": min_lahtoon - 140, 
                    "paluu": paluu_aika_lt, "yopyva": on_yopyva
                }

                if min_lahtoon >= 140 and ilmo_dt_lt <= paivystys_loppu_dt:
                    if paivystys_tyyppi == "1 pv" and info["yopyva"]:
                        info["syy"] = "Yöpyvä (klo 20+)"
                        ohitetut.append(info)
                    else:
                        loydetyt.append(info)
                else:
                    info["syy"] = "Ikkunan ulkopuolella / jo mennyt"
                    ohitetut.append(info)

        if loydetyt:
            for k in sorted(loydetyt, key=lambda x: x['ilmo']):
                c1, c2, c3 = st.columns([1, 2.5, 2.5])
                with c1:
                    st.markdown(f"### {k['reg']}")
                with c2:
                    paluu_str = k['paluu'].strftime('%H:%M') if k['paluu'] else ("🌙 Yöpyvä" if k['yopyva'] else "—")
                    st.markdown(f"**{k['lento']}** ➡️ **{k['kohde']}**")
                    st.markdown(f"<span class='info-label'>Lähtö:</span> **{k['lahto'].strftime('%H:%M')}** | <span class='info-label'>Paluu:</span> **{paluu_str}**", unsafe_allow_html=True)
                with c3:
                    color = "#00ff00" if k['soitto_min'] > 30 else "#ff4b4b"
                    st.markdown(f"<div style='text-align:right;'><span style='color:{color}; font-size: 0.8rem;'>Soittoaikaa:</span><br><b style='font-size: 1.4rem; color:{color};'>{k['soitto_min']} min</b></div>", unsafe_allow_html=True)
                st.divider()
        else:
            st.info("Ei aktiivisia keikkoja.")

        # --- HYLÄTYT LISTA ALAS ---
        if ohitetut:
            with st.expander("Muut havainnot (Hylätyt/Ohitetut)"):
                for o in sorted(ohitetut, key=lambda x: x['lahto']):
                    st.caption(f"{o['lahto'].strftime('%H:%M')} | {o['reg']} | {o['lento']} ➡️ {o['kohde']} | Syy: {o['syy']}")

    except Exception as e:
        st.error("Haku epäonnistui.")

st.markdown('<div class="footer">Emppukuskin työkalu</div>', unsafe_allow_html=True)
