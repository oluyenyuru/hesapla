import os
import ssl
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from requests.adapters import HTTPAdapter

# -------------------------------------------------
# SAYFA AYARLARI
# -------------------------------------------------
st.set_page_config(
    page_title="Kamu Alımları Fiyat Analiz Aracı",
    page_icon="⚖️",
    layout="wide",
)

# -------------------------------------------------
# EVDS (TCMB) AYARLARI
# -------------------------------------------------
# API anahtarı koda YAZILMAZ. Şu sırayla aranır:
#   1) .streamlit/secrets.toml  ->  EVDS_API_KEY = "..."
#   2) Ortam değişkeni EVDS_API_KEY
#   3) Yan menüdeki giriş kutusu
EVDS_BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"

# Seri kodlarını EVDS'deki "Veri Kategorileri" bölümünden doğrulayın.
# TÜİK endeks bazı değişirse (ör. 2025=100) yeni seri kodu gerekebilir.
SERIES_TUFE = "TP.FG.J0"  # TÜFE Genel (Aylık)
SERIES_YIUFE = "TP.TUFE1YI.T1"  # Yİ-ÜFE Genel (Aylık)
SERIES_USD = "TP.DK.USD.A.YTL"  # USD Döviz Alış (TCMB, günlük)
SERIES_EUR = "TP.DK.EUR.A.YTL"  # EUR Döviz Alış (TCMB, günlük)


def get_api_key():
    try:
        if "EVDS_API_KEY" in st.secrets:
            return st.secrets["EVDS_API_KEY"]
    except Exception:
        pass
    return os.environ.get("EVDS_API_KEY", "")


class LegacySSLAdapter(HTTPAdapter):
    """TCMB sunucusu eski SSL ayarı gerektirebilir."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        try:
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            pass
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def evds_request(api_key, series, start, end, frequency=None):
    """EVDS v3'ten seriyi çeker, DataFrame döndürür. Hata olursa açıklayıcı istisna fırlatır."""
    url = (
        f"{EVDS_BASE}series={series}"
        f"&startDate={start.strftime('%d-%m-%Y')}"
        f"&endDate={end.strftime('%d-%m-%Y')}"
        "&type=json"
    )
    if frequency:
        url += f"&frequency={frequency}"
    session = requests.Session()
    session.mount("https://", LegacySSLAdapter())
    res = session.get(
        url,
        headers={"key": api_key, "Accept": "application/json"},
        timeout=20,
    )
    ctype = res.headers.get("Content-Type", "")
    if res.status_code != 200 or "json" not in ctype.lower():
        snippet = res.text[:150].replace("\n", " ")
        raise RuntimeError(
            f"EVDS beklenmeyen yanıt verdi (HTTP {res.status_code}, {ctype or 'içerik türü yok'}): {snippet}"
        )
    data = res.json()
    items = data.get("items", []) if isinstance(data, dict) else data
    return pd.DataFrame(items)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_monthly_index(api_key, series):
    """{'2026-03': 1234.5, ...} biçiminde aylık endeks sözlüğü."""
    df = evds_request(api_key, series, date(2020, 1, 1), date.today(), frequency=5)
    col = series.replace(".", "_")
    out = {}
    for _, row in df.iterrows():
        val = row.get(col)
        if val in (None, ""):
            continue
        y, m = str(row["Tarih"]).split("-")[:2]
        out[f"{int(y)}-{int(m):02d}"] = float(val)
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fx(api_key, target_date):
    """Verilen tarihte veya ondan önceki son iş gününde USD ve EUR kuru.
    Hafta sonu / tatil için 10 gün geriye bakılır."""
    start = target_date - timedelta(days=10)
    result = {}
    for name, series in (("USD", SERIES_USD), ("EUR", SERIES_EUR)):
        df = evds_request(api_key, series, start, target_date)
        col = series.replace(".", "_")
        if df.empty or col not in df:
            return None
        df = df[df[col].notna() & (df[col] != "")]
        if df.empty:
            return None
        last = df.iloc[-1]
        result[name] = float(last[col])
        result[name + "_date"] = last["Tarih"]
    return result


def lookup_index(index_map, d):
    """(kullanılan_ay, değer, tam_eşleşme_mi). Ay yayımlanmadıysa son yayımlanan ay."""
    ym = d.strftime("%Y-%m")
    if ym in index_map:
        return ym, index_map[ym], True
    earlier = sorted(k for k in index_map if k <= ym)
    if earlier:
        return earlier[-1], index_map[earlier[-1]], False
    return None, None, False


def pct(new, old):
    return (new / old - 1) * 100 if old else 0.0


# -------------------------------------------------
# BAŞLIK
# -------------------------------------------------
st.title("⚖️ Kamu Alımları Fiyat Analiz Aracı")
st.caption(
    "TCMB EVDS verileriyle kur ve enflasyon bazlı **yaklaşık** fiyat kontrolü."
    " Resmi bir belge veya hukuki görüş yerine geçmez."
)

# -------------------------------------------------
# YAN MENÜ
# -------------------------------------------------
with st.sidebar:
    st.header("⚙️ Denetim Ayarları")
    api_key = get_api_key()
    if not api_key:
        api_key = st.text_input("EVDS API Anahtarı", type="password")
    baz_gosterge = st.selectbox(
        "Esas Alınacak Gösterge",
        [
            "Yİ-ÜFE (Üretici Fiyat Endeksi)",
            "TÜFE (Tüketici Fiyat Endeksi)",
        ],
    )
    yasal_tolerans = st.slider(
        "Ek Tolerans (%)",
        min_value=0.0,
        max_value=20.0,
        value=5.0,
        step=0.5,
        help=(
            "Kullanıcı tanımlı bir esneklik payıdır; belirli bir mevzuat"
            " hükmüne dayanmaz. Kurumunuzun kendi kuralını girin."
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
if initial_price <= 0:
    st.error("Son alım birim fiyatı sıfırdan büyük olmalıdır.")
    st.stop()

# -------------------------------------------------
# VERİ ÇEKME (EVDS)
# -------------------------------------------------
tufe_map, yiufe_map, fx_old, fx_new = {}, {}, None, None
errors = []

if api_key:
    with st.spinner("EVDS verileri çekiliyor..."):
        try:
            tufe_map = fetch_monthly_index(api_key, SERIES_TUFE)
            yiufe_map = fetch_monthly_index(api_key, SERIES_YIUFE)
        except Exception as e:
            errors.append(f"Endeks verisi alınamadı: {e}")
        try:
            fx_old = fetch_fx(api_key, initial_date)
            fx_new = fetch_fx(api_key, tender_date)
        except Exception as e:
            errors.append(f"Kur verisi alınamadı: {e}")
else:
    errors.append("EVDS API anahtarı girilmedi; veriler elle girilmelidir.")

for msg in errors:
    st.warning("⚠️ " + msg)

# -------------------------------------------------
# MANUEL GİRİŞ / GEÇERSİZ KILMA (0 = EVDS değerini kullan)
# -------------------------------------------------
with st.expander("✍️ Verileri elle gir / EVDS değerini geçersiz kıl (0 = otomatik)"):
    st.caption("EVDS erişilemezse veya resmi bir değeri elle girmek isterseniz kullanın.")
    mc1, mc2 = st.columns(2)
    with mc1:
        man_tufe_old = st.number_input("TÜFE – geçmiş", min_value=0.0, value=0.0, format="%.4f")
        man_yiufe_old = st.number_input("Yİ-ÜFE – geçmiş", min_value=0.0, value=0.0, format="%.4f")
        man_usd_old = st.number_input("USD/TRY – geçmiş", min_value=0.0, value=0.0, format="%.4f")
        man_eur_old = st.number_input("EUR/TRY – geçmiş", min_value=0.0, value=0.0, format="%.4f")
    with mc2:
        man_tufe_new = st.number_input("TÜFE – güncel", min_value=0.0, value=0.0, format="%.4f")
        man_yiufe_new = st.number_input("Yİ-ÜFE – güncel", min_value=0.0, value=0.0, format="%.4f")
        man_usd_new = st.number_input("USD/TRY – güncel", min_value=0.0, value=0.0, format="%.4f")
        man_eur_new = st.number_input("EUR/TRY – güncel", min_value=0.0, value=0.0, format="%.4f")


def resolve_index(index_map, d, manual, label):
    if manual > 0:
        return manual
    ym, val, exact = lookup_index(index_map, d)
    if val is None:
        return None
    if not exact:
        st.warning(
            f"⚠️ {label}: {d.strftime('%m/%Y')} endeksi henüz yayımlanmamış;"
            f" son yayımlanan ay ({ym}) kullanıldı."
        )
    return val


tufe_old = resolve_index(tufe_map, initial_date, man_tufe_old, "TÜFE (geçmiş)")
tufe_new = resolve_index(tufe_map, tender_date, man_tufe_new, "TÜFE (güncel)")
yiufe_old = resolve_index(yiufe_map, initial_date, man_yiufe_old, "Yİ-ÜFE (geçmiş)")
yiufe_new = resolve_index(yiufe_map, tender_date, man_yiufe_new, "Yİ-ÜFE (güncel)")

if None in (tufe_old, tufe_new, yiufe_old, yiufe_new):
    st.error(
        "Endeks değerleri bulunamadı. API anahtarını kontrol edin veya"
        " yukarıdaki bölümden endeksleri elle girin."
    )
    st.stop()


def fx_value(fx, key, manual):
    if manual > 0:
        return manual
    return fx[key] if fx else None


usd_old = fx_value(fx_old, "USD", man_usd_old)
usd_new = fx_value(fx_new, "USD", man_usd_new)
eur_old = fx_value(fx_old, "EUR", man_eur_old)
eur_new = fx_value(fx_new, "EUR", man_eur_new)
fx_ok = None not in (usd_old, usd_new, eur_old, eur_new)
if not fx_ok:
    st.info("Kur verisi bulunamadı; kur göstergeleri ve dolar bazlı karşılaştırma gizlendi.")

# -------------------------------------------------
# GÖSTERGELER
# -------------------------------------------------
st.divider()
st.subheader("📈 Ekonomik Göstergeler (TCMB EVDS)")
g1, g2, g3, g4 = st.columns(4)


def show_metric(col, title, new, old, fmt):
    col.metric(
        title,
        f"{new:{fmt}}",
        delta=f"{pct(new, old):+.2f}% (geçmiş: {old:{fmt}})",
        delta_color="off",
    )


if fx_ok:
    show_metric(g1, "USD/TRY", usd_new, usd_old, ".4f")
    show_metric(g2, "EUR/TRY", eur_new, eur_old, ".4f")
show_metric(g3, "Yİ-ÜFE", yiufe_new, yiufe_old, ".2f")
show_metric(g4, "TÜFE", tufe_new, tufe_old, ".2f")

if fx_ok and fx_old and fx_new and not (man_usd_old or man_usd_new):
    st.caption(
        f"Kur tarihleri: geçmiş {fx_old['USD_date']}, güncel {fx_new['USD_date']}"
        " (hafta sonu/tatilde önceki iş günü kullanılır)."
    )

# -------------------------------------------------
# HESAPLAMA
# -------------------------------------------------
yiufe_price = initial_price * (yiufe_new / yiufe_old)
tufe_price = initial_price * (tufe_new / tufe_old)

if "Yİ-ÜFE" in baz_gosterge:
    aktif_baz_fiyat = yiufe_price
    resmi_artis = pct(yiufe_new, yiufe_old)
else:
    aktif_baz_fiyat = tufe_price
    resmi_artis = pct(tufe_new, tufe_old)

max_makul_sinir = aktif_baz_fiyat * (1 + yasal_tolerans / 100)
firma_artis_orani = pct(new_offer_price, initial_price)

# -------------------------------------------------
# SONUÇ KARTLARI
# -------------------------------------------------
st.divider()
st.subheader("🎯 Fiyat Kontrol Sonucu")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Firma Artış Oranı", f"%{firma_artis_orani:.2f}")
m2.metric("Endeks Artışı", f"%{resmi_artis:.2f}")
m3.metric("Tolerans Dahil Tavan Fiyat", f"{max_makul_sinir:,.2f} ₺")
m4.metric("Firma Teklifi", f"{new_offer_price:,.2f} ₺")

if fx_ok:
    d1, d2 = st.columns(2)
    d1.metric(
        "Son alım fiyatı (USD)",
        f"{initial_price / usd_old:,.2f} $",
    )
    d2.metric(
        "Firma teklifi (USD)",
        f"{new_offer_price / usd_new:,.2f} $",
        delta=f"{pct(new_offer_price / usd_new, initial_price / usd_old):+.2f}%",
        delta_color="off",
    )

if new_offer_price <= aktif_baz_fiyat:
    st.success(
        "✅ **UYGUN** — Teklif, seçilen endeksle güncellenmiş fiyatın"
        " altında veya eşittir."
    )
elif new_offer_price <= max_makul_sinir:
    st.warning(
        "⚠️ **SINIRDA** — Teklif endeksle güncellenmiş fiyatın üzerindedir"
        " ancak belirlenen tolerans içindedir. Pazarlık önerilir."
    )
else:
    st.error(
        "🚨 **YÜKSEK** — Teklif endeks ve tolerans sınırını aşmaktadır."
        " Gerekçelendirilmeli veya yeniden değerlendirilmelidir."
    )

# -------------------------------------------------
# TABLO VE GRAFİK
# -------------------------------------------------
df = pd.DataFrame(
    {
        "Kriter": [
            "Son Alım Fiyatı",
            "Yİ-ÜFE Bazlı Güncel Fiyat",
            "TÜFE Bazlı Güncel Fiyat",
            "Tavan (+Tolerans)",
            "Firma Teklifi",
        ],
        "Tutar (₺)": [
            initial_price,
            yiufe_price,
            tufe_price,
            max_makul_sinir,
            new_offer_price,
        ],
    }
)

st.divider()
st.subheader("📋 Karşılaştırma Tablosu")
st.dataframe(df.style.format({"Tutar (₺)": "{:,.2f} ₺"}), width="stretch")

fig = px.bar(
    df,
    x="Kriter",
    y="Tutar (₺)",
    color="Kriter",
    text_auto=".2f",
    title="Firma Teklifinin Endeks Bazlı Sınırlarla Karşılaştırması",
)
fig.add_hline(
    y=max_makul_sinir,
    line_color="red",
    line_dash="dash",
    annotation_text="Tavan",
)
fig.update_layout(showlegend=False, height=450)
st.plotly_chart(fig, width="stretch")

st.caption(
    "Bu araç, TCMB EVDS'den alınan kur ve TÜİK endeks verileriyle yaklaşık bir"
    " fiyat kontrolü sunar. Tolerans oranı kullanıcı tanımlıdır. Fiyat farkı"
    " ve piyasa fiyat araştırması işlemleri için ilgili mevzuat ve kurumunuzun"
    " ilgili birimi esas alınmalıdır."
)
