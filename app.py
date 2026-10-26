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
        res = requests.get(url, timeout=3)
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
        res = requests.get(url_latest, timeout=3)
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


# --- TCMB EVDS API Üzerinden Akıllı Endeks Çekme ---
@st.cache_data(ttl=86400)
def fetch_evds_indexes(start_date, end_date):
    fallback_init = {"tufe": 1300.60, "yiufe": 2152.70}
    fallback_tend = {"tufe": 3510.00, "yiufe": 5020.00}

    try:
        start_str = start_date.strftime("%d-%m-%Y")
        end_str = end_date.strftime("%d-%m-%Y")
        
        url = f"https://evds2.tcmb.gov.tr/service/evds/series=TP.FG.J0,TP.WI.YI01&startDate={start_str}&endDate={end_str}&type=json"
        headers = {"key": EVDS_KEY}
        res = requests.get(url, headers=headers, timeout=5)
        
        if res.status_code == 200:
            items = res.json().get("items", [])
            if items:
                # Boş olmayan en son geçerli veriyi bulmak için tersten arayabiliriz veya ilk/son kaydı alabiliriz
                first_item = items[0]
                last_item = items[-1]
                
                # Eğer son kayıtta değer boş dönerse listedeki dolu olan son kaydı bul
                for item in reversed(items):
                    if item.get("TP_FG_J0") and item.get("TP_WI_YI01"):
                        last_item = item
                        break

                init_vals = {
                    "tufe": float(first_item.get("TP_FG_J0") or fallback_init["tufe"]),
                    "yiufe": float(first_item.get("TP_WI_YI01") or fallback_init["yiufe"])
                }
                tend_vals = {
                    "tufe": float(last_item.get("TP_FG_J0") or fallback_tend["tufe"]),
                    "yiufe": float(last_item.get("TP_WI_YI01") or fallback_tend["yiufe"])
                }
                return init_vals, tend_vals
    except Exception:
        pass
        
    return fallback_init, fallback_tend


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

idx_initial, idx_tender = fetch_evds_indexes(initial_date, tender_date)

st.divider()

# --- Ekonomik Göstergeler ---
st.subheader("📈 Ekonomik Göstergeler (Otomatik EVDS & Döviz)")
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
    st.markdown("**YI-ÜFE Endeksi (EVDS)**")
    yi_init = st.number_input(
        "Geçmiş YI-ÜFE", value=float(idx_initial["yiufe"]), format="%.2f"
    )
    yi_tend = st.number_input(
        "Güncel YI-ÜFE", value=float(idx_tender["yiufe"]), format="%.2f"
    )

with col_g4:
    st.markdown("**TÜFE Endeksi (EVDS)**")
    tu_init = st.number_input(
        "Geçmiş TÜFE", value=float(idx_initial["tufe"]), format="%.2f"
    )
    tu_tend = st.number_input(
        "Güncel TÜFE", value=float(idx_tender["tufe"]), format="%.2f"
    )

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

lower_bound = min(usd_updated, yiufei_updated if 'yiufei_updated' in locals() else yiufe_updated)
upper_bound = tufe_updated

m1, m2, m3, m4 = st.columns(4)
m1.metric("Firma Artış Oranı", f"%{firm_increase:.2f}")
m2.metric("Alt Makul Sınır (USD/Yİ-ÜFE)", f"{lower_bound:,.2f} ₺")
m3.metric("Üst Makul Sınır (TÜFE)", f"{upper_bound:,.2f} ₺")
m4.metric("Firma Teklifi", f"{new_offer_price:,.2f} ₺")

if new_offer_price <= lower_bound:
    st.success(
        "✅ **SONUÇ: UYGUN** — Firma teklifi tüm ekonomik göstergelerin ve piyasa"
        " taban fiyatının altındadır."
    )
elif new_offer_price <= upper_bound:
    st.info(
        "⚠️ **SONUÇ: SINIRDA UYGUN** — Firma teklifi tüketici enflasyonu (TÜFE)"
        " sınırları içerisindedir."
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

c_a1, c_a2, c_a3, c_a4, c_a5 = st.columns(5)
c_a1.metric("USD Artışı", f"%{usd_increase:.2f}")
c_a2.metric("EUR Artışı", f"%{eur_increase:.2f}")
c_a3.metric("Yİ-ÜFE Artışı", f"%{yiufe_increase:.2f}")
c_a4.metric("TÜFE Artışı", f"%{tufe_increase:.2f}")
c_a5.metric("Firma Teklif Artışı", f"%{firm_increase:.2f}", delta=f"{firm_increase - tufe_increase:.2f}% (TÜFE Farkı)")

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
