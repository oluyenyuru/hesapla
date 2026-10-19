from datetime import date, datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(
    page_title="Kamu Doğrudan Temin & İhale Fiyat Analiz Sistemi",
    page_icon="⚖️",
    layout="wide",
)

# --- Endeks Veritabanı ---
# DİKKAT: Bu değerleri kamu alımı gerekçesinde kullanmadan önce TÜİK
# yayınlarından (data.tuik.gov.tr) doğrulayın. Özellikle yuvarlak değerli
# satırlar tahmini olabilir. Baz yılı tüm satırlarda aynı olmalıdır.
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


def get_index(date_obj):
    """Tarihin ayına eşit veya öncesindeki en yakın endeksi döndürür.

    TÜİK endeksleri ay sonrasında açıklandığından, ileriye bakmak yerine
    mevcut/önceki dönem kullanılır. Hiç önceki veri yoksa en eski kayıt alınır.
    """
    ym = date_obj.strftime("%Y-%m")
    keys = sorted(EMBEDDED_INDEXES.keys())
    previous = [k for k in keys if k <= ym]
    key = previous[-1] if previous else keys[0]
    return key, EMBEDDED_INDEXES[key]


# --- Döviz ---
def _fetch_tcmb_xml(date_obj, side):
    """TCMB gösterge kurları (anahtarsız XML). Tatil/hafta sonu için geriye gider."""
    import xml.etree.ElementTree as ET
    from datetime import timedelta

    tag = "ForexBuying" if side == "Alış" else "ForexSelling"
    last_err = "kayıt bulunamadı"
    d = min(date_obj, date.today())
    for _ in range(10):
        url = f"https://www.tcmb.gov.tr/kurlar/{d:%Y%m}/{d:%d%m%Y}.xml"
        try:
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                out = {}
                for cur in root.findall("Currency"):
                    code = cur.get("CurrencyCode")
                    if code in ("USD", "EUR"):
                        out[code] = float(cur.findtext(tag))
                if "USD" in out and "EUR" in out:
                    return out, d
            last_err = f"HTTP {res.status_code} ({d:%d.%m.%Y})"
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            break
        d -= timedelta(days=1)
    raise RuntimeError(last_err)


def _fetch_evds3(date_obj, api_key, side):
    """EVDS3 (anahtar gerekir). Eski evds2 adresi kapatıldı."""
    from datetime import timedelta

    suffix = "A" if side == "Alış" else "S"
    end = min(date_obj, date.today())
    start = end - timedelta(days=10)
    out = {}
    for cur in ("USD", "EUR"):
        url = (
            "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
            f"series=TP.DK.{cur}.{suffix}.YTL&startDate={start:%d-%m-%Y}"
            f"&endDate={end:%d-%m-%Y}&type=json"
        )
        res = requests.get(url, headers={"key": api_key}, timeout=10)
        res.raise_for_status()
        items = res.json().get("items", [])
        field = f"TP_DK_{cur}_{suffix}_YTL"
        values = [it[field] for it in items if it.get(field) not in (None, "")]
        if not values:
            raise ValueError(f"{cur} verisi yok")
        out[cur] = float(values[-1])  # aralıktaki son iş günü
    return out


def _fetch_frankfurter(date_obj):
    path = min(date_obj, date.today()).strftime("%Y-%m-%d")
    last = None
    for base in ("https://api.frankfurter.dev/v1", "https://api.frankfurter.app"):
        try:
            res = requests.get(f"{base}/{path}?base=USD&symbols=TRY,EUR", timeout=8)
            res.raise_for_status()
            rates = res.json()["rates"]
            usd_try = float(rates["TRY"])
            return {"USD": usd_try, "EUR": usd_try / float(rates["EUR"])}
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
    raise RuntimeError(last)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_currency_rates(date_str, api_key, side):
    """Başarılıysa (kurlar, kaynak) döner; hepsi başarısızsa nedenleri içeren istisna fırlatır."""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    errors = []
    try:
        rates, used = _fetch_tcmb_xml(d, side)
        return rates, f"TCMB gösterge kuru ({used:%d.%m.%Y}, {side})"
    except Exception as exc:
        errors.append(f"TCMB XML: {exc}")
    if api_key:
        try:
            return _fetch_evds3(d, api_key, side), f"TCMB EVDS3 ({side})"
        except Exception as exc:
            errors.append(f"EVDS3: {exc}")
    try:
        return _fetch_frankfurter(d), "Frankfurter (ECB)"
    except Exception as exc:
        errors.append(f"Frankfurter: {exc}")
    raise RuntimeError(" | ".join(errors))


def get_rates(date_obj, api_key, side):
    try:
        rates, source = fetch_currency_rates(date_obj.strftime("%Y-%m-%d"), api_key, side)
        return rates, source, False, ""
    except Exception as exc:
        return {"USD": 0.0, "EUR": 0.0}, "Alınamadı", True, str(exc)


# --- Başlık ---
st.title("⚖️ Kamu İhale & Doğrudan Temin Fiyat Analiz Portalı")
st.caption("Kamu Alımları İçin Ekonomik Göstergelere Dayalı Fiyat Araştırması")

with st.sidebar:
    st.header("⚙️ Ayarlar")
    kur_side = st.radio("TCMB Döviz Kuru Türü", ["Alış", "Satış"], horizontal=True)
    evds_key = st.text_input(
        "TCMB EVDS3 API Anahtarı (isteğe bağlı)",
        type="password",
        help="Gösterge kurları anahtarsız çekilir; anahtar yalnızca ikinci yedek kaynaktır.",
    )
    vade_pct = st.slider(
        "Vade / Finansman Risk Primi (%)",
        min_value=0.0,
        max_value=30.0,
        value=10.0,
        step=0.5,
        help="Sözleşme/ödeme vadesine göre belirleyin; gerekçesini tutanağa yazın.",
    )

st.divider()

# --- Girdiler ---
c1, c2 = st.columns(2)
with c1:
    st.subheader("📝 Geçmiş Alım Bilgileri")
    initial_date = st.date_input(
        "Son Alım Tarihi", date(2023, 4, 17), format="DD/MM/YYYY"
    )
    initial_price = st.number_input(
        "Son Alım Birim Fiyatı (₺)", min_value=0.0, value=94.0, step=1.0
    )
with c2:
    st.subheader("📅 Güncel Teklif Bilgileri")
    tender_date = st.date_input(
        "İhale / Güncelleme Tarihi", date.today(), format="DD/MM/YYYY"
    )
    new_offer_price = st.number_input(
        "Yeni Firma Teklif Fiyatı (₺)", min_value=0.0, value=314.0, step=1.0
    )

if tender_date < initial_date:
    st.error("İhale tarihi, son alım tarihinden önce olamaz.")
    st.stop()
if initial_price <= 0:
    st.warning("Son alım birim fiyatı 0'dan büyük olmalıdır.")
    st.stop()

rates_i, src_i, fail_i, err_i = get_rates(initial_date, evds_key, kur_side)
rates_t, src_t, fail_t, err_t = get_rates(tender_date, evds_key, kur_side)
idx_i_key, idx_i = get_index(initial_date)
idx_t_key, idx_t = get_index(tender_date)

st.divider()

# --- Göstergeler ---
st.subheader("📈 Ekonomik Göstergeler")
if fail_i or fail_t:
    st.warning(
        "⚠️ Kur verisi otomatik çekilemedi. Lütfen aşağıdaki kur alanlarını "
        "elle girin; 0 olan alanlar hesaba katılmaz."
    )
    with st.expander("Hata ayrıntıları"):
        if fail_i:
            st.write(f"Geçmiş tarih: {err_i}")
        if fail_t:
            st.write(f"Güncel tarih: {err_t}")
st.caption(
    f"Kur kaynağı: geçmiş → {src_i}, güncel → {src_t} | "
    f"Kullanılan endeks dönemi: geçmiş → {idx_i_key}, güncel → {idx_t_key}"
)
if idx_t_key < tender_date.strftime("%Y-%m"):
    st.info(
        f"Güncel tarih için {tender_date.strftime('%Y-%m')} endeksi bulunamadı; "
        f"{idx_t_key} dönemi kullanılıyor."
    )

# key'ler tarih ve kaynağı içerir: tarih değişince alanlar yeni değerle yenilenir.
ki = initial_date.isoformat()
kt = tender_date.isoformat()

g1, g2, g3, g4 = st.columns(4)
with g1:
    st.markdown("**USD / TRY**")
    u_init = st.number_input("Geçmiş USD", value=float(rates_i["USD"]), format="%.4f", min_value=0.0, key=f"ui_{ki}_{src_i}")
    u_tend = st.number_input("Güncel USD", value=float(rates_t["USD"]), format="%.4f", min_value=0.0, key=f"ut_{kt}_{src_t}")
with g2:
    st.markdown("**EUR / TRY**")
    e_init = st.number_input("Geçmiş EUR", value=float(rates_i["EUR"]), format="%.4f", min_value=0.0, key=f"ei_{ki}_{src_i}")
    e_tend = st.number_input("Güncel EUR", value=float(rates_t["EUR"]), format="%.4f", min_value=0.0, key=f"et_{kt}_{src_t}")
with g3:
    st.markdown("**Yİ-ÜFE**")
    yi_init = st.number_input("Geçmiş Yİ-ÜFE", value=float(idx_i["yiufe"]), format="%.2f", min_value=0.0, key=f"yi_{ki}")
    yi_tend = st.number_input("Güncel Yİ-ÜFE", value=float(idx_t["yiufe"]), format="%.2f", min_value=0.0, key=f"yt_{kt}")
with g4:
    st.markdown("**TÜFE**")
    tu_init = st.number_input("Geçmiş TÜFE", value=float(idx_i["tufe"]), format="%.2f", min_value=0.0, key=f"ti_{ki}")
    tu_tend = st.number_input("Güncel TÜFE", value=float(idx_t["tufe"]), format="%.2f", min_value=0.0, key=f"tt_{kt}")

# --- Hesaplamalar (geçersiz/0 girdi olan gösterge hesaba katılmaz) ---
def updated(price, new, old):
    return price * (new / old) if old > 0 and new > 0 else None


updated_prices = {
    "USD": updated(initial_price, u_tend, u_init),
    "EUR": updated(initial_price, e_tend, e_init),
    "Yİ-ÜFE": updated(initial_price, yi_tend, yi_init),
    "TÜFE": updated(initial_price, tu_tend, tu_init),
}
valid = {k: v for k, v in updated_prices.items() if v is not None}

if not valid:
    st.error("Hesaplama için geçerli en az bir gösterge girilmelidir.")
    st.stop()

vade_katsayisi = 1 + vade_pct / 100
lower_bound = min(valid.values())
upper_bound = max(valid.values()) * vade_katsayisi

firm_increase = (new_offer_price - initial_price) / initial_price * 100
tufe_increase = (tu_tend - tu_init) / tu_init * 100 if tu_init > 0 else None
usd_increase = (u_tend - u_init) / u_init * 100 if u_init > 0 else None
yiufe_increase = (yi_tend - yi_init) / yi_init * 100 if yi_init > 0 else None

st.divider()

# --- Sonuç ---
st.subheader("🎯 Piyasa Fiyat Araştırma Sonucu")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Firma Artış Oranı", f"%{firm_increase:.2f}")
m2.metric("Alt Sınır (en düşük gösterge)", f"{lower_bound:,.2f} ₺")
m3.metric(f"Üst Sınır (en yüksek gösterge + %{vade_pct:g})", f"{upper_bound:,.2f} ₺")
m4.metric("Firma Teklifi", f"{new_offer_price:,.2f} ₺")

used = ", ".join(valid.keys())
if new_offer_price <= lower_bound:
    st.success(
        f"✅ **UYGUN** — Teklif, hesaba katılan tüm göstergelerin ({used}) "
        "altında veya eşittir."
    )
elif new_offer_price <= upper_bound:
    st.info(
        "⚠️ **SINIRDA UYGUN** — Teklif, göstergeler aralığı ve vade risk primi "
        "sınırları içerisindedir."
    )
elif new_offer_price <= upper_bound * 1.15:
    st.warning(
        "⚡ **YÜKSEK** — Teklif üst sınırın üzerindedir. Pazarlık yapılması önerilir."
    )
else:
    st.error(
        "🚨 **ÇOK YÜKSEK** — Teklif makul piyasa şartlarının belirgin şekilde "
        "üzerindedir."
    )

# --- Karşılaştırma tablosu ve grafik ---
rows = []
inc = {"USD": usd_increase, "EUR": None, "Yİ-ÜFE": yiufe_increase, "TÜFE": tufe_increase}
if e_init > 0 and e_tend > 0:
    inc["EUR"] = (e_tend - e_init) / e_init * 100
for k, v in updated_prices.items():
    rows.append(
        {
            "Gösterge": k,
            "Güncellenmiş Fiyat (₺)": v,
            "Değişim (%)": inc.get(k),
        }
    )
rows.append({"Gösterge": "Firma Teklifi", "Güncellenmiş Fiyat (₺)": new_offer_price, "Değişim (%)": firm_increase})
df = pd.DataFrame(rows)

tcol, gcol = st.columns([1, 1])
with tcol:
    st.dataframe(
        df.style.format(
            {"Güncellenmiş Fiyat (₺)": "{:,.2f}", "Değişim (%)": "{:.2f}"},
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )
with gcol:
    chart_df = df.dropna(subset=["Güncellenmiş Fiyat (₺)"])
    fig = px.bar(
        chart_df,
        x="Gösterge",
        y="Güncellenmiş Fiyat (₺)",
        color="Gösterge",
        text_auto=",.2f",
    )
    fig.add_hline(y=upper_bound, line_dash="dash", annotation_text="Üst sınır")
    fig.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Bu araç karar destek amaçlıdır. Kur ve endeks değerlerini resmi kaynaklardan "
    "(TCMB, TÜİK) doğrulayıp, sonucu ilgili mevzuat çerçevesinde değerlendiriniz."
)
