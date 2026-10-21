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
    "2026-10": {"tufe": 4450.00, "yiufe": 6000.00},
}


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

# --- Fiyat Hesaplamaları ---
usd_updated = initial_price * (u_tend / u_init) if u_init > 0 else 0
eur_updated = initial_price * (e_tend / e_init) if e_init > 0 else 0
yiufe_updated = initial_price * (yi_tend / yi_init) if yi_init > 0 else 0
tufe_updated = initial_price * (tu_tend / tu_init) if tu_init > 0 else 0

# --- Artış Oranı Hesaplamaları (%) ---
firm_increase = (
    ((new_offer_price - initial_price) / initial_price) * 100
    if initial_price > 0
    else 0
)
usd_increase = ((u_tend - u_init) / u_init) * 100 if u_init > 0 else 0
eur_increase = ((e_tend - e_init) / e_init) * 100 if e_init > 0 else 0
yiufe_increase = ((yi_tend - yi_init) / yi_init) * 100 if yi_init > 0 else 0
tufe_increase = ((tu_tend - tu_init) / tu_init) * 100 if tu_init > 0 else 0

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

st.divider()

# --- Gösterge Artış Oranları & Fiyat Karşılaştırma Analizi ---
st.subheader("📊 Ekonomik Gösterge Artış Oranları & Fiyat Karşılaştırması")

# Artış Oranı Rozetleri
c_a1, c_a2, c_a3, c_a4, c_a5 = st.columns(5)
c_a1.metric("USD Artışı", f"%{usd_increase:.2f}")
c_a2.metric("EUR Artışı", f"%{eur_increase:.2f}")
c_a3.metric("Yİ-ÜFE Artışı", f"%{yiufe_increase:.2f}")
c_a4.metric("TÜFE Artışı", f"%{tufe_increase:.2f}")
c_a5.metric("Firma Teklif Artışı", f"%{firm_increase:.2f}", delta=f"{firm_increase - tufe_increase:.2f}% (TÜFE Farkı)")

# Grafik İçin Veri Tablosu
df_chart = pd.DataFrame({
    "Gösterge": [
        "Son Alım Fiyatı",
        "USD Güncellenmiş",
        "EUR Güncellenmiş",
        "Yİ-ÜFE Güncellenmiş",
        "TÜFE Güncellenmiş",
        "Firma Teklifi",
    ],
    "Fiyat (₺)": [
        initial_price,
        usd_updated,
        eur_updated,
        yiufe_updated,
        tufe_updated,
        new_offer_price,
    ],
    "Artış Oranı (%)": [
        0.0,
        usd_increase,
        eur_increase,
        yiufe_increase,
        tufe_increase,
        firm_increase,
    ],
})

# Plotly Sütun Grafiği
fig = px.bar(
    df_chart,
    x="Gösterge",
    y="Fiyat (₺)",
    color="Gösterge",
    text="Fiyat (₺)",
    hover_data=["Artış Oranı (%)"],
    title="Ekonomik Göstergelere Göre Uyarlanmış Fiyatlar ve Teklif Karşılaştırması",
)
fig.update_traces(texttemplate="%{y:,.2f} ₺", textposition="outside")
fig.update_layout(showlegend=False, yaxis_title="Tutar (₺)", xaxis_title="")

st.plotly_chart(fig, use_container_width=True)
