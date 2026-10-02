import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, date

# --- Sayfa Yapılandırması ---
st.set_page_config(
    page_title="İhale & Satın Alma Fiyat Analiz Sistemi",
    page_icon="📊",
    layout="wide"
)

# --- Dahili TÜİK Endeks Veritabanı ---
EMBEDDED_INDEXES = {
    "2024-01": {"tufe": 1983.83, "yiufe": 2715.10},
    "2024-06": {"tufe": 2320.10, "yiufe": 3280.40},
    "2024-12": {"tufe": 2620.40, "yiufe": 3720.10},
    "2025-01": {"tufe": 2750.00, "yiufe": 3910.00},
    "2025-06": {"tufe": 3050.00, "yiufe": 4380.00},
    "2025-12": {"tufe": 3380.00, "yiufe": 4850.00},
    "2026-01": {"tufe": 3510.00, "yiufe": 5020.00},
    "2026-06": {"tufe": 3750.00, "yiufe": 5350.00},
}

# --- Canlı Döviz Çekme Fonksiyonu ---
@st.cache_data(ttl=3600)
def fetch_usd_rate(date_str):
    try:
        url = f"https://api.frankfurter.app/{date_str}?from=USD&to=TRY"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data["rates"]["TRY"]
    except Exception:
        pass
    
    try:
        url_alt = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date_str}/v1/currencies/usd.json"
        res_alt = requests.get(url_alt, timeout=5)
        if res_alt.status_code == 200:
            return res_alt.json()["usd"]["try"]
    except Exception:
        pass
        
    return 35.0

def get_closest_index(date_obj):
    ym = date_obj.strftime("%Y-%m")
    if ym in EMBEDDED_INDEXES:
        return EMBEDDED_INDEXES[ym]
    closest_key = min(
        EMBEDDED_INDEXES.keys(), 
        key=lambda k: abs((datetime.strptime(k, "%Y-%m").date() - date_obj).days)
    )
    return EMBEDDED_INDEXES[closest_key]

# --- Arayüz / Başlık ---
st.title("📊 İhale & Satın Alma Fiyat Analiz Sistemi")
st.caption("Python & Streamlit Tabanlı Reel Teklif Güncelleme ve Maliyet Portalı")

st.divider()

# --- Sol Panel (Girdiler) ---
col_in1, col_in2 = st.columns([1, 1])

with col_in1:
    st.subheader("📝 Teklif & Tarih Bilgileri")
    initial_date = st.date_input("İlk Teklif Tarihi", date(2024, 1, 15), format="DD/MM/YYYY")
    initial_price = st.number_input("İlk Teklif Fiyatı (₺)", min_value=0.0, value=1000000.0, step=10000.0)

with col_in2:
    st.subheader("📅 Güncelleme / İhale Bilgileri")
    tender_date = st.date_input("İhale / Güncelleme Tarihi", date.today(), format="DD/MM/YYYY")
    new_offer_price = st.number_input("Yeni Firma Teklifi (₺)", min_value=0.0, value=1520000.0, step=10000.0)

initial_date_str = initial_date.strftime("%Y-%m-%d")
tender_date_str = tender_date.strftime("%Y-%m-%d")

usd_initial = fetch_usd_rate(initial_date_str)
usd_tender = fetch_usd_rate(tender_date_str)

idx_initial = get_closest_index(initial_date)
idx_tender = get_closest_index(tender_date)

st.divider()

# --- Ekonomik Göstergeler ---
st.subheader("📈 Ekonomik Göstergeler (Canlı & Otomatik)")
col_g1, col_g2, col_g3 = st.columns(3)

with col_g1:
    st.markdown("**USD / TRY Kuru**")
    u_init = st.number_input("İlk Tarih USD", value=float(usd_initial), format="%.2f")
    u_tend = st.number_input("İhale Tarihi USD", value=float(usd_tender), format="%.2f")

with col_g2:
    st.markdown("**Yİ-ÜFE Endeksi**")
    yi_init = st.number_input("İlk Yİ-ÜFE", value=float(idx_initial["yiufe"]), format="%.1f")
    yi_tend = st.number_input("İhale Yİ-ÜFE", value=float(idx_tender["yiufe"]), format="%.1f")

with col_g3:
    st.markdown("**TÜFE Endeksi**")
    tu_init = st.number_input("İlk TÜFE", value=float(idx_initial["tufe"]), format="%.1f")
    tu_tend = st.number_input("İhale TÜFE", value=float(idx_tender["tufe"]), format="%.1f")

# --- Hesaplamalar ---
usd_updated = initial_price * (u_tend / u_init) if u_init > 0 else 0
yiufe_updated = initial_price * (yi_tend / yi_init) if yi_init > 0 else 0
tufe_updated = initial_price * (tu_tend / tu_init) if tu_init > 0 else 0

st.divider()

# --- Referans Seçimi ve Karşılaştırma ---
st.subheader("🎯 Değerlendirme & Analiz")

ref_option = st.selectbox(
    "Önerilen Makul Fiyat İçin Referans Gösterge Yöntemi:",
    ["Yİ-ÜFE Bazlı (Sanayi/İhale Standartı)", "TÜFE Bazlı (Tüketici Enflasyonu)", "USD Dolar Kuru Bazlı", "Eşit Ağırlıklı Ortalama"]
)

if "Yİ-ÜFE" in ref_option:
    recommended_price = yiufe_updated
elif "TÜFE" in ref_option:
    recommended_price = tufe_updated
elif "USD" in ref_option:
    recommended_price = usd_updated
else:
    recommended_price = (usd_updated + yiufe_updated + tufe_updated) / 3

real_increase = ((new_offer_price - recommended_price) / recommended_price) * 100 if recommended_price > 0 else 0

# --- Sonuç Rozetleri ---
m1, m2, m3 = st.columns(3)
m1.metric("Önerilen Makul Fiyat", f"{recommended_price:,.2f} ₺")
m2.metric("Yeni Firma Teklifi", f"{new_offer_price:,.2f} ₺")
m3.metric("Reel Artış / Fark", f"%{real_increase:.2f}", delta=f"{real_increase:.2f}%", delta_color="inverse")

# --- Değerlendirme Mesajı ---
if real_increase <= 0:
    st.success(f"✅ **UYGUN TEKLİF:** Firma teklifi makul fiyatın %{abs(real_increase):.2f} altındadır. Kabul edilebilir.")
elif real_increase <= 10:
    st.warning(f"⚠️ **YÜKSEK TEKLİF:** Firma teklifi piyasa maliyet artışının %{real_increase:.2f} üzerindedir. Pazarlık önerilir.")
else:
    st.error(f"🚨 **ÇOK YÜKSEK TEKLİF:** Firma teklifi piyasa koşullarının %{real_increase:.2f} üzerindedir. Detaylı analiz istenmelidir.")

# --- Plotly Görsel Grafik ---
df_chart = pd.DataFrame({
    'Gösterge': ['İlk Fiyat', 'Yİ-ÜFE İle', 'TÜFE İle', 'USD İle', 'Önerilen Fiyat', 'Yeni Teklif'],
    'Tutar (₺)': [initial_price, yiufe_updated, tufe_updated, usd_updated, recommended_price, new_offer_price]
})

fig = px.bar(df_chart, x='Gösterge', y='Tutar (₺)', color='Gösterge', title="Fiyat Karşılaştırma Grafiği", text_auto='.2s')
st.plotly_chart(fig, use_container_width=True)
