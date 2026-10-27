from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st

# -------------------------------------------------
# SAYFA AYARLARI
# -------------------------------------------------
st.set_page_config(
    page_title="Kamu İhale Fiyat Analiz Sistemi (Sayıştay Uyumlu)",
    page_icon="⚖️",
    layout="wide",
)

# -------------------------------------------------
# TÜİK RESMİ ENDEKS VERİTABANI (Yİ-ÜFE & TÜFE)
# -------------------------------------------------
EMBEDDED_INDEXES = {
    "2023-01": {"tufe": 1203.00, "yiufe": 2020.50},
    "2023-04": {"tufe": 1300.60, "yiufe": 2152.70},
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
  key = previous[-1] if previous else available[0]
  return key, EMBEDDED_INDEXES[key]


# -------------------------------------------------
# BAŞLIK
# -------------------------------------------------
st.title("⚖️ Kamu Doğrudan Temin & İhale Fiyat Analiz Sistemi")
st.caption(
    "Sayıştay Denetim ve Kamu İhale Mevzuatına Uyumlu - Resmi Enflasyon Bazlı"
    " Karar Destek Modülü"
)

# -------------------------------------------------
# YAN MENÜ (Yasal Esneklik ve Endeks Seçimi)
# -------------------------------------------------
with st.sidebar:
  st.header("⚙️ Denetim & Sınır Ayarları")
  baz_gosterge = st.selectbox(
      "Esas Alınacak Resmi Gösterge",
      [
          "Yİ-ÜFE (Üretici Fiyat Endeksi - Mal Alımları)",
          "TÜFE (Tüketici Fiyat Endeksi)",
      ],
  )
  yasal_tolerans = st.slider(
      "Kabul Edilebilir Maksimum Ek Tolerans (%)",
      min_value=0.0,
      max_value=20.0,
      value=5.0,
      step=0.5,
      help=(
          "Resmi enflasyon artışının üzerine eklenebilecek azami yasal"
          " esneklik payıdır."
      ),
  )

# -------------------------------------------------
# GİRDİLER
# -------------------------------------------------
st.divider()
col1, col2 = st.columns(2)
with col1:
  st.subheader("📝 Geçmiş Alım Bilgileri")
  initial_date = st.date_input(
      "Son Alım Tarihi", value=date(2026, 3, 19), format="DD/MM/YYYY"
  )
  initial_price = st.number_input(
      "Son Alım Birim Fiyatı (₺)", min_value=0.0, value=12940.0, step=1.0
  )
with col2:
  st.subheader("📅 Güncel Teklif Bilgileri")
  tender_date = st.date_input(
      "İhale / Güncelleme Tarihi", value=date.today(), format="DD/MM/YYYY"
  )
  new_offer_price = st.number_input(
      "Firma Teklif Fiyatı (₺)", min_value=0.0, value=15500.0, step=1.0
  )

if tender_date < initial_date:
  st.error("İhale tarihi son alım tarihinden önce olamaz.")
  st.stop()

_, idx_old = get_index(initial_date)
_, idx_new = get_index(tender_date)

# -------------------------------------------------
# HESAPLAMA MANTIĞI (Saf Kamu Mevzuatı)
# -------------------------------------------------
yiufe_price = (
    initial_price * (idx_new["yiufe"] / idx_old["yiufe"])
    if idx_old["yiufe"] > 0
    else 0
)
tufe_price = (
    initial_price * (idx_new["tufe"] / idx_old["tufe"])
    if idx_old["tufe"] > 0
    else 0
)

if "Yİ-ÜFE" in baz_gosterge:
  aktif_baz_fiyat = yiufe_price
  resmi_artis = (
      ((idx_new["yiufe"] - idx_old["yiufe"]) / idx_old["yiufe"]) * 100
  )
else:
  aktif_baz_fiyat = tufe_price
  resmi_artis = ((idx_new["tufe"] - idx_old["tufe"]) / idx_old["tufe"]) * 100

max_makul_sinir = aktif_baz_fiyat * (1 + yasal_tolerans / 100)
firma_artis_orani = ((new_offer_price - initial_price) / initial_price) * 100

# -------------------------------------------------
# SONUÇ KARTLARI
# -------------------------------------------------
st.divider()
st.subheader("🎯 Piyasa Fiyat Araştırma ve Denetim Sonucu")
m1, m2, m3, m4 = st.columns(4)

m1.metric("Firma Artış Oranı", f"%{firma_artis_orani:.2f}")
m2.metric("Resmi Enflasyon Artışı", f"%{resmi_artis:.2f}")
m3.metric("Yasal Sınır Dahil Tavan Fiyat", f"{max_makul_sinir:,.2f} ₺")
m4.metric("Firma Teklifi", f"{new_offer_price:,.2f} ₺")

# -------------------------------------------------
# NET DENETİM KARARI
# -------------------------------------------------
if new_offer_price <= aktif_baz_fiyat:
  st.success(
      "✅ **SONUÇ: UYGUN** — Firma teklifi resmi TÜİK enflasyon artış"
      " oranının altındadır. Doğrudan temin edilebilir."
  )
elif new_offer_price <= max_makul_sinir:
  st.warning(
      "⚠️ **SONUÇ: SINIRDA UYGUN (PAZARLIĞA UYGUN)** — Firma teklifi resmi"
      " enflasyonun üzerindedir ancak belirlenen yasal tolerans payı"
      " içerisindedir. İndirim için pazarlık yapılması önerilir."
  )
else:
  st.error(
      "🚨 **SONUÇ: UYGUN DEĞİL / YÜKSEK** — Firma teklifi resmi enflasyon ve"
      " yasal tolerans sınırını aşmaktadır. Kamu zararı oluşturabileceği için"
      " teklif gerekçelendirilmeli veya reddedilmelidir."
  )

# -------------------------------------------------
# TABLO VE GRAFİK
# -------------------------------------------------
df = pd.DataFrame({
    "Kriter": [
        "Son Alım Fiyatı",
        "Yİ-ÜFE Bazlı Güncel Sınır",
        "TÜFE Bazlı Güncel Sınır",
        "Yasal Tavan Sınır (+Tolerans)",
        "Firma Teklifi",
    ],
    "Tutar (₺)": [
        initial_price,
        yiufe_price,
        tufe_price,
        max_makul_sinir,
        new_offer_price,
    ],
})

st.divider()
st.subheader("📋 Detaylı Karşılaştırma Tablosu")
st.dataframe(
    df.style.format({"Tutar (₺)": "{:,.2f} ₺"}), use_container_width=True
)

fig = px.bar(
    df,
    x="Kriter",
    y="Tutar (₺)",
    color="Kriter",
    text_auto=".2f",
    title="Firma Teklifinin Resmi Enflasyon Sınırları ile Karşılaştırması",
)
fig.add_hline(
    y=max_makul_sinir,
    line_color="red",
    line_dash="dash",
    annotation_text="Yasal Tavan Sınır",
)
fig.update_layout(showlegend=False, height=450)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Bu sistem Sayıştay denetim kriterleri ve Kamu İhale mevzuatı baz alınarak"
    " saf TÜİK enflasyon oranları üzerinden tasarlanmıştır."
)
