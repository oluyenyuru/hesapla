from datetime import date, datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# -------------------------------------------------
# SAYFA AYARLARI
# -------------------------------------------------
st.set_page_config(
    page_title="Kamu İhale Fiyat Analiz Sistemi",
    page_icon="⚖️",
    layout="wide",
)

# --- EVDS API Bilgileri ---
EVDS_KEY = "J12vgkw87j"

# -------------------------------------------------
# CANLI DÖVİZ ÇEKME FONKSİYONU (Tarih Bazlı)
# -------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_currency_rates(date_str):
    rates = {"USD": 35.0, "EUR": 38.0}
    try:
        url = f"https://api.frankfurter.app/{date_str}?from=USD&to=TRY,EUR"
        res = requests.get(url, timeout=4)
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
        res = requests.get(url_latest, timeout=4)
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

# -------------------------------------------------
# ÖRNEK ENDEKS VERİLERİ (Fallback)
# -------------------------------------------------
EMBEDDED_INDEXES = {
    "2023-01": {"tufe": 1203.00, "yiufe": 2020.50},
    "2023-06": {"tufe": 1351.59, "yiufe": 2325.00},
    "2023-12": {"tufe": 1859.38, "yiufe": 2915.02},
    "2024-06": {"tufe": 2319.29, "yiufe": 3483.25},
    "2024-12": {"tufe": 2620.40, "yiufe": 3720.10},
    "2025-06": {"tufe": 3050.00, "yiufe": 4380.00},
    "2025-12": {"tufe": 3380.00, "yiufe": 4850.00},
    "2026-03": {"tufe": 3510.00, "yiufe": 5020.00},
    "2026-06": {"tufe": 3750.00, "yiufe": 5350.00},
    "2026-10": {"tufe": 4450.00, "yiufe": 6000.00},
}

def get_index(selected_date):
    ym = selected_date.strftime("%Y-%m")
    if ym in EMBEDDED_INDEXES:
        return ym, EMBEDDED_INDEXES[ym]
    available = sorted(EMBEDDED_INDEXES.keys())
    previous = [k for k in available if k <= ym]
    if previous:
        key = previous[-1]
    else:
        key = available[0]
    return key, EMBEDDED_INDEXES[key]

# -------------------------------------------------
# BAŞLIK
# -------------------------------------------------
st.title("⚖️ Kamu İhale & Doğrudan Temin Fiyat Analiz Sistemi")
st.caption("Ekonomik göstergelere göre güncellenmiş piyasa fiyat analizi")

# -------------------------------------------------
# YAN MENÜ
# -------------------------------------------------
with st.sidebar:
    st.header("⚙️ Ayarlar")
    vade_riski = st.slider(
        "Vade / Finansman Riski (%)",
        min_value=0.0,
        max_value=30.0,
        value=10.0,
        step=0.5
    )

# -------------------------------------------------
# GİRDİLER
# -------------------------------------------------
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("📝 Geçmiş Alım")
    initial_date = st.date_input(
        "Son Alım Tarihi",
        value=date(2026, 3, 19),
        format="DD/MM/YYYY"
    )
    initial_price = st.number_input(
        "Son Alım Birim Fiyatı (₺)",
        min_value=0.0,
        value=12940.0,
        step=1.0
    )
with col2:
    st.subheader("📅 Güncel Teklif")
    tender_date = st.date_input(
        "İhale Tarihi",
        value=date.today(),
        format="DD/MM/YYYY"
    )
    new_offer_price = st.number_input(
        "Firma Teklifi (₺)",
        min_value=0.0,
        value=15500.0,
        step=1.0
    )

if tender_date < initial_date:
    st.error("İhale tarihi son alım tarihinden önce olamaz.")
    st.stop()

# -------------------------------------------------
# OTOMATİK KUR & ENDEKS ÇEKME
# -------------------------------------------------
initial_date_str = initial_date.strftime("%Y-%m-%d")
tender_date_str = tender_date.strftime("%Y-%m-%d")

rates_initial = fetch_currency_rates(initial_date_str)
rates_tender = fetch_currency_rates(tender_date_str)

idx_key_old, idx_old = get_index(initial_date)
idx_key_new, idx_new = get_index(tender_date)

# -------------------------------------------------
# GÖSTERGELER
# -------------------------------------------------
st.divider()
st.subheader("📈 Ekonomik Göstergeler (Otomatik)")
g1, g2, g3, g4 = st.columns(4)

with g1:
    usd_old = st.number_input(
        "Geçmiş USD/TRY",
        value=float(rates_initial["USD"]),
        format="%.4f"
    )
    usd_new = st.number_input(
        "Güncel USD/TRY",
        value=float(rates_tender["USD"]),
        format="%.4f"
    )

with g2:
    eur_old = st.number_input(
        "Geçmiş EUR/TRY",
        value=float(rates_initial["EUR"]),
        format="%.4f"
    )
    eur_new = st.number_input(
        "Güncel EUR/TRY",
        value=float(rates_tender["EUR"]),
        format="%.4f"
    )

with g3:
    yiufe_old = st.number_input(
        "Geçmiş Yİ-ÜFE",
        value=float(idx_old["yiufe"])
    )
    yiufe_new = st.number_input(
        "Güncel Yİ-ÜFE",
        value=float(idx_new["yiufe"])
    )

with g4:
    tufe_old = st.number_input(
        "Geçmiş TÜFE",
        value=float(idx_old["tufe"])
    )
    tufe_new = st.number_input(
        "Güncel TÜFE",
        value=float(idx_new["tufe"])
    )

# -------------------------------------------------
# HESAPLAR
# -------------------------------------------------
def update_price(base, old, new):
    if old <= 0:
        return None
    return base * (new / old)

usd_price = update_price(initial_price, usd_old, usd_new)
eur_price = update_price(initial_price, eur_old, eur_new)
yiufe_price = update_price(initial_price, yiufe_old, yiufe_new)
tufe_price = update_price(initial_price, tufe_old, tufe_new)

economic_values = [usd_price, eur_price, yiufe_price, tufe_price]
economic_values = [x for x in economic_values if x is not None]

lower_bound = min(economic_values)
reference_price = sum(economic_values) / len(economic_values)
upper_bound = max(economic_values) * (1 + vade_riski / 100)

# -------------------------------------------------
# SONUÇ
# -------------------------------------------------
st.divider()
st.subheader("🎯 Piyasa Fiyat Araştırma Sonucu")
m1, m2, m3, m4 = st.columns(4)

firma_artisi = ((new_offer_price - initial_price) / initial_price) * 100

m1.metric("Firma Artış Oranı", f"%{firma_artisi:.2f}")
m2.metric("Alt Makul Sınır", f"{lower_bound:,.2f} ₺")
m3.metric("Referans Fiyat", f"{reference_price:,.2f} ₺")
m4.metric("Üst Makul Sınır", f"{upper_bound:,.2f} ₺")

# -------------------------------------------------
# KARAR
# -------------------------------------------------
if lower_bound <= new_offer_price <= upper_bound:
    st.success("✅ SONUÇ: UYGUN")
elif new_offer_price < lower_bound:
    st.info("ℹ️ SONUÇ: DÜŞÜK")
elif new_offer_price <= upper_bound * 1.15:
    st.warning("⚠️ SONUÇ: YÜKSEK")
else:
    st.error("🚨 SONUÇ: ÇOK YÜKSEK")

# -------------------------------------------------
# TABLO
# -------------------------------------------------
df = pd.DataFrame({
    "Gösterge": ["USD", "EUR", "Yİ-ÜFE", "TÜFE", "Referans Fiyat", "Firma Teklifi"],
    "Tutar": [usd_price, eur_price, yiufe_price, tufe_price, reference_price, new_offer_price]
})

st.divider()
st.subheader("📋 Karşılaştırma Tablosu")
st.dataframe(df.style.format({"Tutar": "{:,.2f} ₺"}), use_container_width=True)

# -------------------------------------------------
# GRAFİK
# -------------------------------------------------
fig = px.bar(df, x="Gösterge", y="Tutar", color="Gösterge", text_auto=".2f")
fig.add_hline(y=lower_bound, line_color="green", line_dash="dot", annotation_text="Alt Sınır")
fig.add_hline(y=reference_price, line_color="blue", annotation_text="Referans Fiyat")
fig.add_hline(y=upper_bound, line_color="red", line_dash="dash", annotation_text="Üst Sınır")
fig.update_layout(showlegend=False, height=500)
st.plotly_chart(fig, use_container_width=True)

st.caption("Bu sistem karar destek amaçlıdır. Nihai değerlendirme ilgili mevzuat ve piyasa araştırması tutanakları dikkate alınarak yapılmalıdır.")
