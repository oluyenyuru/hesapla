from datetime import date, datetime
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# --- Sayfa Yapılandırması ---
st.set_page_config(
    page_title="Kamu Doğrudan Temin & İhale Fiyat Analiz Sistemi",
    page_icon="⚖️",
    layout="wide",
)

# --- EVDS API Bilgileri ---
EVDS_KEY = "J12vgkw87j"

# --- Canlı Döviz Çekme Fonksiyonu (USD & EUR - TRY Bazlı) ---
@st.cache_data(ttl=3600)
def fetch_currency_rates(date_str):
    rates = {"USD": 35.0, "EUR": 38.0}
    try:
        url = f"https://api.frankfurter.app/{date_str}?from=USD&to=TRY,EUR"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if "rates" in data:
                rates["USD"] = data["rates"].get("TRY", rates["USD"])
                eur_to_usd = data["rates"].get("EUR", 1.0)
                if eur_to_usd > 0:
                    rates["EUR"] = rates["USD"] / eur_to_usd
                return rates
    except Exception:
        pass

    try:
        url_latest = "https://api.frankfurter.app/latest?from=USD&to=TRY,EUR"
        res = requests.get(url_latest, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if "rates" in data:
                rates["USD"] = data["rates"].get("TRY", rates["USD"])
                eur_to_usd = data["rates"].get("EUR", 1.0)
                if eur_to_usd > 0:
                    rates["EUR"] = rates["USD"] / eur_to_usd
    except Exception:
        pass

    return rates


# --- TCMB EVDS API Üzerinden TÜFE ve Yİ-ÜFE Çekme Fonksiyonu ---
@st.cache_data(ttl=86400)
def fetch_evds_indexes(start_date, end_date):
    start_str = start_date.strftime("%d-%m-%Y")
    end_str = end_date.strftime("%d-%m-%Y")
    
    fallback = {"tufe": 2500.0, "yiufe": 3500.0}
    
    try:
        url = f"https://evds2.tcmb.gov.tr/service/evds/series=TP.FG.J0,TP.WI.YI01&startDate={start_str}&endDate={end_str}&type=json"
        headers = {"key": EVDS_KEY}
        res = requests.get(url, headers=headers, timeout=5)
        
        if res.status_code == 200:
            data = res.json().get("items", [])
            if data:
                first_item = data[0]
                last_item = data[-1]
                
                init_vals = {
                    "tufe": float(first_item.get("TP_FG_J0", 2500.0) or 2500.0),
                    "yiufe": float(first_item.get("TP_WI_YI01", 3500.0) or 3500.0)
                }
                tend_vals = {
                    "tufe": float(last_item.get("TP_FG_J0", 2500.0) or 2500.0),
                    "yiufe": float(last_item.get("TP_WI_YI01", 3500.0) or 3500.0)
                }
                return init_vals, tend_vals
    except Exception:
        pass
        
    return {"tufe": 1983.83, "yiufe": 2715.10}, {"tufe": 3510.00, "yiufe": 5020.00}


# --- Arayüz Başlığı ---
st.title("⚖️ Kamu İhale & Doğrudan Temin Fiyat Analiz Portalı")
st.caption("TCMB EVDS ve Canlı Döviz Kurları Destekli Otomatik Fiyat Araştırması")

st.divider()

# --- Girdiler ---
col_in1, col_in2 = st.columns(2)

with col_in1:
    st.subheader("📝 Geçmiş Alım Bilgileri")
    initial_date = st.date_input(
        "Son Alım Tarihi", date(2023, 4, 17), format="DD/MM/YYYY"
    )
    initial_price = st.number_input(
        "Son Alım Birim Fiyatı (₺)", min_value=0.0, value=94.0, step=1.0
    )

with col_in2:
    st.subheader("📅 Güncel Teklif Bilgileri")
    tender_date = st.date_input(
        "İhale / Güncelleme Tarihi", date.today(), format="DD/MM/YYYY"
    )
    new_offer_price = st.number_input(
        "Yeni Firma Teklif Fiyatı (₺)", min_value=0.0, value=314.0, step=1.0
    )

initial_date_str = initial_date.strftime("%Y-%m-%d")
tender_date_str = tender_date.strftime("%Y-%m-%d")

rates_initial = fetch_currency_rates(initial_date_str)
rates_tender = fetch_currency_rates(tender_date_str)

# EVDS üzerinden seçilen tarihlere göre endeksleri otomatik çek
idx_initial, idx_tender = fetch_evds_indexes(initial_date, tender_date)

st.divider()

# --- Ekonomik Göstergeler ---
st.subheader("📈 Ekonomik Göstergeler (Otomatik EVDS & Döviz)")
col_g1, col_g2, col_g3, col_g4 = st.columns(4)

with col_g1:
    st.markdown("**USD / TRY Kuru**")
    u_init = st.number_input
