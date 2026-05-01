import streamlit as st
import requests
from datetime import datetime, timedelta, timezone
import time
import base64
from zoneinfo import ZoneInfo

# --- KONFIGURAATIO ---
LOCAL_TZ = ZoneInfo("Europe/Helsinki")

# --- FUNKTIO: Ladataan ikoni ---
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

# --- HTML/META-KIKAT ---
if icon_data:
    st.markdown(f'''
        <style>
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header {{visibility: hidden;}}
            .stDeployButton {{display:none;}}
        </style>
        <link rel="apple-touch-icon" href="{icon_data}?v={version_tag}">
        <link rel="icon" type="image/png" href="{icon_data}?v={version_tag}">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    ''', unsafe_allow_html=True)

# --- CSS-MUOTOILU ---
st.markdown("""
    <style>
    .block-container { padding-top: 4.5rem !important; }
    .main-title { font-size: 2.2rem; font-weight: 800; margin-bottom: 0px; color: #ffffff; }
    .sub-title { font-size: 0.9rem; color: #888; margin-bottom: 25px; font-style: italic; }
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
PITKAT_KEIKAT = ["KEF", "MAN", "DUS", "WAW"] # Kohteet, jotka eivät ole yöpyviä

# --- OTSAKKEET ---
st.markdown('<p class="main-title">Emppukuskin päivystysvahti ✈️</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">(Yöpyvien vahti toimii luotettavasti vain iltapäivystyksessä)</p>', unsafe_allow_html=True)

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
    my_bar = st.progress(0, text="Yhdistetään tutkaan...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.flightradar24.com/"
    }
    ts = int(time.time())

    try:
        my_bar.progress(25, text="Haetaan lähtöjä...")
        dep_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=departures&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=15)
        
        if dep_res.status_code != 200:
            st.error(f"Lähtöjen haku epäonnistui (Status: {dep_res.status_code}).")
            st.stop()

        my_bar.progress(50, text="Haetaan saapuvia...")
        arr_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=arrivals&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=15)
        
        if arr_res.status_code != 200:
            st.error(f"Saapuvien haku epäonnistui (Status: {arr_res.status_code}).")
            st.stop()
            
        departures_data = dep_res.json()
        arrivals_data = arr_res.json()

        departures = departures_data.get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('departures', {}).get('data', [])
        arrivals = arrivals_data.get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('arrivals', {}).get('data', [])

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
                        # POHDINTA: Nostettu ikkuna 12 tuntiin (43200 sek), jotta pitkät kierrot löytyvät
                        if arr_ts and dep_ts < arr_ts <= (dep_ts + 43200):
                            paluu_aika_lt = datetime.fromtimestamp(arr_ts, tz=timezone.utc).astimezone(LOCAL_TZ)
                            break
                
                # Yöpyvä vain, jos paluuta ei löydy 12h sisään EIKÄ kohde ole erikoislistalla
                on_yopyva = (paluu_aika_lt is None) and (kohde not in PITKAT_KEIKAT)
                
                info = {
                    "reg": reg, "lento": f.get('identification', {}).get('number', {}).get('default', '???'), 
                    "kohde": kohde, "lahto": lahto_dt_lt, "ilmo": ilmo_dt_lt, "soitto_min": min_lahtoon - 140, 
                    "paluu": paluu_aika_lt, "yopyva": on_yopyva
                }

                if min_lahtoon >= 140 and ilmo_dt_lt <= paivystys_loppu_dt:
                    if paivystys_tyyppi == "1 pv" and info["yopyva"]:
                        info["syy"] = "Yöpyvä"
                        ohitetut.append(info)
                    else:
                        loydetyt.append(info)
                else:
                    info["syy"] = "Ikkunan ulkopuolella"
                    ohitetut.append(info)

        my_bar.empty()

        if loydetyt:
            for k in sorted(loydetyt, key=lambda x: x['ilmo']):
                c1, c2, c3 = st.columns([1, 2.5, 2.5])
                with c1:
                    st.markdown(f"### {k['reg']}")
                with c2:
                    if k['paluu']:
                        paluu_str = k['paluu'].strftime('%H:%M')
                    elif k['kohde'] in PITKAT_KEIKAT:
                        paluu_str = "—" 
                    else:
                        paluu_str = "🌙 Yöpyvä"
                        
                    st.markdown(f"**{k['lento']}** ➡️ **{k['kohde']}**")
                    st.markdown(f"<span class='info-label'>Lähtö (LT):</span> **{k['lahto'].strftime('%H:%M')}** | <span class='info-label'>Paluu (LT):</span> **{paluu_str}**", unsafe_allow_html=True)
                with c3:
                    color = "#00ff00" if k['soitto_min'] > 30 else "#ff4b4b"
                    st.markdown(f"<div style='text-align:right;'><span style='color:{color}; font-size: 0.8rem;'>Soittoaikaa:</span><br><b style='font-size: 1.4rem; color:{color};'>{k['soitto_min']} min</b></div>", unsafe_allow_html=True)
                st.divider()
        else:
            st.info("Ei aktiivisia keikkoja.")

        with st.expander("Muut havainnot"):
            for o in sorted(ohitetut, key=lambda x: x['lahto']):
                st.caption(f"{o['lahto'].strftime('%H:%M')} | {o['reg']} | {o['lento']} ➡️ {o['kohde']} | {o['syy']}")

    except Exception as e:
        st.error(f"Virhe: {e}")

st.markdown('<div class="footer">Emppukuskin työkalu • Flightradar24 API</div>', unsafe_allow_html=True)
