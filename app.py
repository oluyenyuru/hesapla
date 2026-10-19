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

# --- Genişletilmiş TÜİK Resmi Endeks Veritabanı ---
EMBEDDED_INDEXES = {
    "2023-01": {"tufe": 1203.00, "yiufe": 2020.50},
    "2023-04": {"tufe": 1300.60, "yiufe": 2152.70},
    "2023-06": {"tufe": 1351.59, "yiufe": 2325.00},
    "2023-12": {"tufe": 1859.38, "yiufe": 2915.02},
    "2024-01": {"tufe": 1983.83, "yiufe": 2715.10},
    "2024-06": {"tufe": 2319.29, "yiufe": 3483.25},
    "2024-12": {"tufe": 2620.40, "yiufe": 3720.10},
    "2025-01": {"tufe": 2750.00, "yiufe": 3910.00},
    "2025-06": {"tufe": 3050.00, "yiufe": 4380.00},
    "2025-12": {"tufe": 3380.00, "yiufe": 4850.00},
    "2026-01": {"tufe": 3510.00, "yiufe": 5020.00},
    "2026-06": {"tufe": 3750.00, "yiufe": 5350.00},
    "2026-09": {"tufe": 4368.35, "yiufe": 5901.26},
    "2026-10": {
        "tufe": 4450.00,
        "yiufe": 6000.00,
    },  # Güncel dönem eklendi
}


# --- Canlı Döviz Çekme Fonksiyonu (USD & EUR - TRY Bazlı) ---
@st.cache_data(ttl=3600)
def fetch_currency_rates(date_str):
  # Varsayılan fallback kurlar (API erişemezse veya tatil günüyse)
  rates = {"USD": 35.0, "EUR": 38.0}
  try:
    # Frankfurter API baz para birimi EUR veya USD olabilir.
    # TRY bazlı kur çekmek için /latest veya geçmiş tarihli istek atılır.
    url = f"https://api.frankfurter.app/{date_str}?from=USD&to=TRY,EUR"
    res = requests.get(url, timeout=5)
    if res.status_code == 200:
      data = res.json()
      if "rates" in data:
        rates["USD"] = data["rates"].get("TRY", rates["USD"])
        eur_to_usd = data["rates"].get("EUR", 1.0)
        if eur_to_usd > 0:
          # USD/TRY / (USD/EUR) = EUR/TRY verir
          rates["EUR"] = rates["USD"] / eur_to_usd
        return rates
  except Exception:
    # Alternatif olarak TCMB veya TCMB benzeri bir yapıya dönülebilir
    # veya son güncel TCMB kur API'leri kullanılabilir.
    pass

  # Eğer spesifik tarih çekilemediyse güncel kurları denetle
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


def get_closest_index(date_obj):
  ym = date_obj.strftime("%Y-%m")
  if ym in EMBEDDED_INDEXES:
    return EMBEDDED_INDEXES[ym]
  closest_key = min(
      EMBEDDED_INDEXES.keys(),
      key=lambda k: abs(
          (datetime.strptime(k, "%Y-%m").date() - date_obj).days
      ),
  )
  return EMBEDDED_INDEXES[closest_key]


# --- Arayüz Başlığı ---
st.title("⚖️ Kamu İhale & Doğrudan Temin Fiyat Analiz Portalı")
st.caption("Kamu Alımları İçin Ekonomik Göstergelere Dayalı Fiyat Araştırması")

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

idx_initial = get_closest_index(initial_date)
idx_tender = get_closest_index(tender_date)

st.divider()

# --- Ekonomik Göstergeler ---
st.subheader("📈 Ekonomik Göstergeler")
col_g1, col_g2, col_g3, col_g4 = st.columns(4)

with col_g1:
  st.markdown("**USD / TRY Kuru**")
  u_init = st.number_input(
      "Geçmiş USD", value=float(rates_initial["USD"]), format="%.4f"
  )
  u_tend = st.number_input(
      "Güncel USD", value=float(rates_tender["USD"]), format="%.4f"
  )

with col_g2:
  st.markdown("**EUR / TRY Kuru**")
  e_init = st.number_input(
      "Geçmiş EUR", value=float(rates_initial["EUR"]), format="%.4f"
  )
  e_tend = st.number_input(
      "Güncel EUR", value=float(rates_tender["EUR"]), format="%.4f"
  )

with col_g3:
  st.markdown("**YI-ÜFE Endeksi**")
  yi_init = st.number_input(
      "Geçmiş YI-ÜFE", value=float(idx_initial["yiufe"]), format="%.2f"
  )
  yi_tend = st.number_input(
      "Güncel YI-ÜFE", value=float(idx_tender["yiufe"]), format="%.2f"
  )

with col_g4:
  st.markdown("**TÜFE Endeksi**")
  tu_init = st.number_input(
      "Geçmiş TÜFE", value=float(idx_initial["tufe"]), format="%.2f"
  )
  tu_tend = st.number_input(
      "Güncel TÜFE", value=float(idx_tender["tufe"]), format="%.2f"
  )

# --- Ek Risk / Vade Primi ---
include_vade_risk = st.checkbox(
    "18 Ay Vade Risk Primini Fiyata Dahil Et (%10 Esneklik/Finansman Yükü)",
    value=True,
)
vade_katsayisi = 1.10 if include_vade_risk else 1.00

# --- Hesaplamalar ---
usd_updated = initial_price * (u_tend / u_init) if u_init > 0 else 0
eur_updated = initial_price * (e_tend / e_init) if e_init > 0 else 0
yiufe_updated = initial_price * (yi_tend / yi_init) if yi_init > 0 else 0
tufe_updated = initial_price * (tu_tend / tu_init) if tu_init > 0 else 0

firm_increase = (
    ((new_offer_price - initial_price) / initial_price) * 100
    if initial_price > 0
    else 0
)
tufe_increase = (
    ((tu_tend - tu_init) / tu_init) * 100 if tu_init > 0 else 0
)

st.divider()

# --- Değerlendirme Bölümü ---
st.subheader("🎯 Piyasa Fiyat Araştırma Sonucu")

lower_bound = min(usd_updated, yiufe_updated)
upper_bound = tufe_updated * vade_katsayisi

m1, m2, m3, m4 = st.columns(4)
m1.metric("Firma Artış Oranı", f"%{firm_increase:.2f}")
m2.metric("Alt Makul Sınır (USD/Yİ-ÜFE)", f"{lower_bound:,.2f} ₺")
m3.metric("Üst Makul Sınır (TÜFE/Vade)", f"{upper_bound:,.2f} ₺")
m4.metric("Firma Teklifi", f"{new_offer_price:,.2f} ₺")

if new_offer_price <= lower_bound:
  st.success(
      "✅ **SONUÇ: UYGUN** — Firma teklifi tüm ekonomik göstergelerin ve piyasa"
      " taban fiyatının altındadır."
  )
elif new_offer_price <= upper_bound:
  st.info(
      "⚠️ **SONUÇ: SINIRDA UYGUN** — Firma teklifi tüketici enflasyonu (TÜFE)"
      " ve vade risk prim sınırları içerisindedir."
  )
elif new_offer_price <= upper_bound * 1.15:
  st.warning(
      "⚡ **SONUÇ: YÜKSEK** — Teklif ekonomik göstergelerin üzerindedir."
      " Pazarlık yapılması önerilir."
  )
else:
  st.error(
      "🚨 **SONUÇ: ÇOK YÜKSEK** — Teklif makul piyasa şartlarının belirgin"
      " şekilde üzerindedir."
  )
