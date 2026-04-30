import streamlit as st
import requests
from datetime import datetime, timedelta
import time
import base64

# --- ASETUKSET ---
# Tähän listataan ne rekisteritunnukset, joita sovellus seuraa (OH-prefixi lisätään myöhemmin)
# Esimerkiksi: LK + jokin kirjain (E, F, G, H, I, K, L, M, N, O, P, R)
REKKARIT_RAAKA = "EFGHIKLMNOPR"
REKKARIT = [f"OH-LK{l}" for l in REKKARIT_RAAKA]
IATA_HEL = "HEL" # Seurattava lentoasema (Helsinki-Vantaa)

# --- SIVUN KONFIGURAATIO ---
st.set_page_config(
    page_title="Päivystysvahti",
    layout="wide",
    page_icon="✈️" # Selaimen välilehdessä näkyvä emoji
)

# --- FUNKTIO: Ladataan ikoni paikallisesta tiedostosta ja muunnetaan base64-muotoon ---
# Tämä kikka mahdollistaa sen, että iPad tunnistaa ikonin ilman ulkoista linkkiä
def get_base64_icon():
    try:
        with open("ikoni.png", "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            return f"data:image/png;base64,{encoded_string}"
    except FileNotFoundError:
        # Jos ikonia ei löydy, sovellus toimii silti ilman sitä
        return None

icon_base64 = get_base64_icon()

# --- HTML-KIKKA: Lisätään apple-touch-icon sivun <head>-osaan ---
if icon_base64:
    st.markdown(f'''
        <link rel="apple-touch-icon" href="{icon_base64}">
        ''', unsafe_allow_html=True)

# --- CSS: ULKOASU JA TÄSMÄLLINEN LINJAUS ---
# Tällä muokataan Streamlitin oletusasettelua sopivammaksi tiiviille mobiilinäytölle.
st.markdown("""
    <style>
    /* Nostettu koko sisältöä reilusti, jotta otsikko ei huku yläpalkin alle iPadilla */
    .block-container { 
        padding-top: 5.5rem !important; 
    }
    
    /* Pienennetään widgettien välejä */
    [data-testid="stVerticalBlock"] { gap: 0.4rem !important; }
    hr { margin-top: 0.2rem !important; margin-bottom: 0.2rem !important; }
    
    /* Päivystysvahti-otsikon tyyli */
    .main-title { 
        font-size: 2.2rem; 
        font-weight: 800; 
        margin-top: 10px;
        margin-bottom: 0px; 
        color: #ffffff; 
    }
    /* Pieni sulkuteksti otsikon alla */
    .sub-title { font-size: 0.9rem; color: #888; margin-bottom: 25px; font-style: italic; }
    
    /* Tekstien tyylit */
    .label-text { font-size: 14px; font-weight: bold; margin-bottom: 5px; color: #eee; }
    .info-label { color: #aaa; font-size: 12px; }
    
    /* Alaviitteen tyyli sivun alareunassa */
    .footer { 
        position: fixed; 
        left: 0; 
        bottom: 0; 
        width: 100%; 
        background-color: transparent; 
        color: #444; 
        text-align: center; 
        font-size: 10px;
        padding: 10px;
    }

    /* Kohdistetaan nappi riviin muiden widgettien kanssa */
    div[data-testid="stButton"] { margin-top: 21px !important; }
    /* Piilotetaan Streamlitin oma lataus-statuspalkki */
    div[data-testid="stStatusWidget"] { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

# --- OTSAKKEET ---
st.markdown('<p class="main-title">Emppukuskin päivystysvahti ✈️</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">(Yöpyvien vahti toimii luotettavasti vain iltapäivystyksessä)</p>', unsafe_allow_html=True)

# --- KÄYTTÖLIITTYMÄ / SYÖTTEET ---
# Luodaan neljä saraketta: päivystyksen pituus, päättymisaika ja hakunappi.
col_ui = st.columns([1.5, 1, 1.2, 0.5])

with col_ui[0]:
    st.markdown('<p class="label-text">Päivystyksen pituus</p>', unsafe_allow_html=True)
    paivystys_tyyppi = st.selectbox("Pituus", ["1 pv", "2 pv"], label_visibility="collapsed")
with col_ui[1]:
    st.markdown('<p class="label-text">Päivystys päättyy</p>', unsafe_allow_html=True)
    # Asetetaan oletukseksi klo 20:00
    paattymisaika = st.time_input("Päättyy", value=datetime.strptime("20:00", "%H:%M").time(), label_visibility="collapsed")
with col_ui[2]:
    tarkista = st.button('HAE LENTOJA 🔍', use_container_width=True, type="primary")

# --- LENTODATAN HAKU JA KÄSITTELY ---
nykyhetki = datetime.now()
# Muunnetaan päättymisaika täydeksi datetime-objektiksi
paivystys_loppu_dt = datetime.combine(nykyhetki.date(), paattymisaika)

if tarkista:
    # Luodaan latauspalkki hakuprosessin ajaksi
    progress_text = "Yhdistetään tutkaan..."
    my_bar = st.progress(0, text=progress_text)
    
    # Määritetään User-Agent, jotta haku ei esty
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.flightradar24.com/"
    }
    # Nykyinen aikaleima hakua varten
    ts = int(nykyhetki.timestamp())

    try:
        # Pieni animaatio latauspalkille
        for percent_complete in range(100):
            time.sleep(0.003)
            if percent_complete == 40: progress_text = "Päivitetään Helsinki-Vantaan tilannetta... 📡"
            my_bar.progress(percent_complete + 1, text=progress_text)

        # Haetaan lähtevät ja saapuvat lennot Flightradar24 JSON API:sta
        dep_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=departures&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=10)
        arr_res = requests.get(f"https://api.flightradar24.com/common/v1/airport.json?code={IATA_HEL}&plugin[]=&plugin-setting[schedule][mode]=arrivals&plugin-setting[schedule][timestamp]={ts}", headers=headers, timeout=10)
        
        # Tarkistetaan, että haut onnistuivat
        dep_res.raise_for_status()
        arr_res.raise_for_status()
        
        # Erotetaan varsinainen lentodata JSON-vastauksesta
        departures = dep_res.json().get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('departures', {}).get('data', [])
        arrivals = arr_res.json().get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get('arrivals', {}).get('data', [])

        loydetyt = [] # Aktiiviset keikat
        ohitetut = []  # Muut havainnot

        # KÄYTTÖÖN LÄHTEVÄT LENNOT
        for item in departures:
            f = item.get('flight', {})
            if not f: continue
            reg = f.get('aircraft', {}).get('registration')
            
            # Tarkistetaan, onko kone seurattujen listalla
            if reg in REKKARIT:
                dep_ts = f.get('time', {}).get('scheduled', {}).get('departure')
                if not dep_ts: continue
                
                lahto_dt = datetime.fromtimestamp(dep_ts)
                # Ilmoittautumisaika on 50min ennen lähtöä
                ilmo_dt = lahto_dt - timedelta(minutes=50)
                # Lasketaan minuutit nykyhetkestä lähtöön
                min_lahtoon = int((lahto_dt - nykyhetki).total_seconds() / 60)
                
                # ETSITÄÄN KONEEN PALUUASETUS SAAPUVISTA LENNOISTA
                # (Lento, joka saapuu 7 tunnin kuluessa lähdöstä samalla koneella)
                paluu_aika = None
                for arr_item in arrivals:
                    af = arr_item.get('flight', {})
                    if af.get('aircraft', {}).get('registration') == reg:
                        arr_ts = af.get('time', {}).get('scheduled', {}).get('arrival')
                        # Jos saapumisaika on lähdön jälkeen, mutta 7h sisällä, se on paluu
                        if arr_ts and dep_ts < arr_ts <= (dep_ts + 25200):
                            paluu_aika = datetime.fromtimestamp(arr_ts)
                            break # Löydetty, lopetetaan haku
                
                # Koostetaan tiedot yhteen sanakirjaan
                info = {
                    "reg": reg, "lento": f.get('identification', {}).get('number', {}).get('default', '???'), 
                    "kohde": f.get('airport', {}).get('destination', {}).get('code', {}).get('iata', '???'), 
                    "lahto": lahto_dt, "ilmo": ilmo_dt, "soitto_min": min_lahtoon - 140, 
                    "paluu": paluu_aika, "yopyva": paluu_aika is None
                }

                # SUODATUS: Näytetään vain keikat, joihin on soittoaikaa jäljellä
                # ja joiden ilmoittautuminen on päivystyksen aikana.
                if min_lahtoon >= 140 and ilmo_dt <= paivystys_loppu_dt:
                    # Jos on 1 pv päivystys, ohitetaan yöpyvät lennot
                    if paivystys_tyyppi == "1 pv" and info["yopyva"]:
                        info["syy"] = "Yöpyvä"
                        ohitetut.append(info)
                    else:
                        loydetyt.append(info) # Tärkein tulos
                else:
                    # Muuten ohitetaan ja tallennetaan syy
                    info["syy"] = "Ikkunan ulkopuolella"
                    ohitetut.append(info)

        # Poistetaan latauspalkki
        my_bar.empty()

        # --- TULOSTUS ---
        if loydetyt:
            # Lajitellaan ilmoittautumisajan mukaan
            for k in sorted(loydetyt, key=lambda x: x['ilmo']):
                # Luodaan kolme saraketta per keikka
                c1, c2, c3 = st.columns([1, 2.5, 2.5])
                with c1:
                    # Rekisteritunnus isona
                    st.markdown(f"### {k['reg']}")
                with c2:
                    # Lentotiedot ja saapumisaika
                    paluu_str = f"{k['paluu'].strftime('%H:%M')}" if k['paluu'] else "🌙 Yöpyvä"
                    st.markdown(f"**{k['lento']}** ➡️ **{k['kohde']}**")
                    st.markdown(f"<span class='info-label'>Lähtöaika:</span> **{k['lahto'].strftime('%H:%M')}**  \n"
                                f"<span class='info-label'>Saapuminen:</span> **{paluu_str}**", unsafe_allow_html=True)
                with c3:
                    # Soittoaika-laskuri oikealle, väri muuttuu jos kiire
                    color = "#00ff00" if k['soitto_min'] > 30 else "#ff4b4b" # Vihreä > 30min, muuten punainen
                    st.markdown(f"<div style='text-align:right;'><span style='color:{color}; font-size: 0.85rem;'>Soittoaikaa jäljellä:</span><br><b style='font-size: 1.3rem; color:{color};'>{k['soitto_min']} min</b></div>", unsafe_allow_html=True)
                st.divider() # Erotinviiva keikkojen väliin
        else:
            st.info("Ei aktiivisia keikkoja.")

        # --- MUUT HAVAINNOT -LAATIKKO ---
        with st.expander("Muut havainnot"):
            # Lajitellaan lähtöajan mukaan
            for o in sorted(ohitetut, key=lambda x: x['lahto']):
                # Lyhyt kuvausteksti
                st.caption(f"{o['lahto'].strftime('%H:%M')} | {o['reg']} | {o['lento']} ➡️ {o['kohde']} | {o['syy']}")

    except Exception as e:
        # Tulostetaan virheilmoitus, jos haku epäonnistuu
        st.error(f"Virhe: {e}")

# --- FOOTER / ALAVIITE ---
st.markdown('<div class="footer">Data: Flightradar24 API • Emppukuskin työkalu</div>', unsafe_allow_html=True)
