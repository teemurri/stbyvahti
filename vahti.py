import streamlit as st
import requests
from datetime import datetime, timedelta
import time
import base64

# --- FUNKTIO: Ladataan ikoni ja luodaan siitä base64-merkkijono ---
def get_base64_icon():
    try:
        with open("ikoni.png", "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            return f"data:image/png;base64,{encoded_string}"
    except FileNotFoundError:
        return None

# Luodaan uniikki aikaleima pakottamaan selaimen välimuistin päivitys
version_tag = int(time.time())
icon_data = get_base64_icon()

# --- SIVUN KONFIGURAATIO ---
st.set_page_config(
    page_title="Päivystysvahti",
    layout="wide",
    page_icon=icon_data if icon_data else "✈️"
)

# --- HTML/META-KIKAT IPADIA VARTEN ---
if icon_data:
    st.markdown(f'''
        <style>
            /* Piilotetaan Streamlitin yläpalkki ja brändäys heti alussa */
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header {{visibility: hidden;}}
            .stDeployButton {{display:none;}}
        </style>
        
        <!-- Apple Touch Icon iPadin kotinäyttöä varten -->
        <link rel="apple-touch-icon" href="{icon_data}?v={version_tag}">
        <link rel="apple-touch-icon-precomposed" href="{icon_data}?v={version_tag}">
        
        <!-- Favicon-linkit selaimen välilehdelle -->
        <link rel="icon" type="image/png" href="{icon_data}?v={version_tag}">
        <link rel="shortcut icon" href="{icon_data}?v={version_tag}">
        
        <!-- Kerrotaan iPadille, että tämä on web-appi -->
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="apple-mobile-web-app-title" content="Päivystysvahti">
    ''', unsafe_allow_html=True)

# --- CSS-MUOTOILU ---
st.markdown("""
    <style>
    .block-container { 
        padding-top: 4.5rem !important; 
    }
    [data-testid="stVerticalBlock"] { gap: 0.4rem !important; }
    hr { margin-top: 0.2rem !important; margin-bottom: 0.2rem !important; }
    
    .main-title { 
        font-size: 2.2rem; 
        font-weight: 800; 
        margin-top: 0px;
        margin-bottom: 0px; 
        color: #ffffff; 
    }
    .sub-title { font-size: 0.9rem; color: #888; margin-bottom: 25px; font-style: italic; }
    .label-text { font-size: 14px; font-weight: bold; margin-bottom: 5px; color: #eee; }
    .info-label { color: #aaa; font-size: 12px; }
    
    .footer { 
        position: fixed; 
        left: 0; 
        bottom: 0; 
        width: 100%; 
        color: #444; 
        text-align: center; 
        font-size: 10px;
        padding: 10px;
    }
    div[data-testid="stButton"] { margin-top: 21px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ASETUKSET ---
REKKARIT_RAAKA = "EFGHIKLMNOPR"
REKKARIT = [f"OH-LK{l}" for l in REKKARIT_RAAKA]
IATA_HEL = "HEL"

# --- OTSAKKEET ---
st.markdown('<p class="main-title">Emppukuskin päivystysvahti ✈️</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">(Yöpyvien vahti toimii luotettavasti vain iltapäivystyksessä)</p>', unsafe_allow_html=True)

# --- SYÖTTEET ---
col_ui = st.columns([1.5, 1, 1.2, 0.5])

with col_ui[0]:
    st.markdown('<p class="label-text">Päivystyksen pituus</p>', unsafe_allow_html=True)
    paivystys_tyyppi = st.selectbox("Pituus", ["1 pv", "2 pv"], label_visibility="collapsed")
with col_ui[1]:
    st.markdown('<p class="label-text">Päivystys päättyy</p>', unsafe_allow_html=True)
    paattymisaika = st.time_input("Päättyy", value=datetime.strptime("20:00", "%H:%M").time(), label_visibility="collapsed")
with col_ui[2]:
    tarkista = st.button('HAE LENTOJA 🔍', use_container_width=True, type="primary")

nykyhetki = datetime.now()
paivystys_loppu_dt = datetime.combine(nykyhetki.date(), paattymisaika)

if tarkista:
    progress_text = "Yhdistetään tutkaan..."
    my_bar = st.progress(0, text=progress_text)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.flightradar24.com/"
    }
    ts = int(nykyhetki.timestamp())

    try:
        for percent_complete in range(100):
            time.sleep(0.002)
            if percent_complete == 40: progress_text = "Päivitetään Helsinki-Vantaan tilannetta... 📡"
            my_bar.progress(percent_complete + 1, text=progress_text)

        dep_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=departures&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=10)
        arr_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=arrivals&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=10)
        
        dep_res.raise_for_status()
        arr_res.raise_for_status()
        
        departures = dep_res.json().get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('departures', {}).get('data', [])
        arrivals = arr_res.json().get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('arrivals', {}).get('data', [])

        loydetyt = []
        ohitetut = []

        for item in departures:
            f = item.get('flight', {})
            if not f: continue
            reg = f.get('aircraft', {}).get('registration')
            
            if reg in REKKARIT:
                dep_ts = f.get('time', {}).get('scheduled', {}).get('departure')
                if not dep_ts: continue
                
                lahto_dt = datetime.fromtimestamp(dep_ts)
                ilmo_dt = lahto_dt - timedelta(minutes=50)
                min_lahtoon = int((lahto_dt - nykyhetki).total_seconds() / 60)
                
                paluu_aika = None
                for arr_item in arrivals:
                    af = arr_item.get('flight', {})
                    if af.get('aircraft', {}).get('registration') == reg:
                        arr_ts = af.get('time', {}).get('scheduled', {}).get('arrival')
                        if arr_ts and dep_ts < arr_ts <= (dep_ts + 25200):
                            paluu_aika = datetime.fromtimestamp(arr_ts)
                            break
                
                info = {
                    "reg": reg, "lento": f.get('identification', {}).get('number', {}).get('default', '???'), 
                    "kohde": f.get('airport', {}).get('destination', {}).get('code', {}).get('iata', '???'), 
                    "lahto": lahto_dt, "ilmo": ilmo_dt, "soitto_min": min_lahtoon - 140, 
                    "paluu": paluu_aika, "yopyva": paluu_aika is None
                }

                if min_lahtoon >= 140 and ilmo_dt <= paivystys_loppu_dt:
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
                    paluu_str = f"{k['paluu'].strftime('%H:%M')}" if k['paluu'] else "🌙 Yöpyvä"
                    st.markdown(f"**{k['lento']}** ➡️ **{k['kohde']}**")
                    st.markdown(f"<span class='info-label'>Lähtö:</span> **{k['lahto'].strftime('%H:%M')}** | <span class='info-label'>Paluu:</span> **{paluu_str}**", unsafe_allow_html=True)
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
        st.error(f"Virhe datan hakemisessa: {e}")

st.markdown('<div class="footer">Emppukuskin työkalu • Flightradar24 API</div>', unsafe_allow_html=True)
