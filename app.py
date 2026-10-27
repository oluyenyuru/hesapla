from datetime import date, datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------
# SAYFA AYARLARI
# ---------------------------------------------------
st.set_page_config(
    page_title="Kamu Doğrudan Temin & İhale Fiyat Analiz Sistemi",
    page_icon="⚖️",
    layout="wide",
)

# ---------------------------------------------------
# EVDS API ANAHTARI
# ---------------------------------------------------
EVDS_KEY = "J12vgkw87j"

# ---------------------------------------------------
# DÖVİZ KURLARI
# ---------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_currency_rates(date_str):
    """
    Frankfurter API üzerinden USD/TRY ve EUR/TRY kurlarını çeker.
    """

    default_rates = {
        "USD": 35.0,
        "EUR": 38.0,
    }

    try:
        url = f"https://api.frankfurter.app/{date_str}?from=USD&to=TRY,EUR"

        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            usd_try = data["rates"].get("TRY")
            usd_eur = data["rates"].get("EUR")

            if usd_try and usd_eur:
                eur_try = usd_try / usd_eur

                return {
                    "USD": usd_try,
                    "EUR": eur_try,
                }

    except Exception:
        pass

    try:
        url = "https://api.frankfurter.app/latest?from=USD&to=TRY,EUR"

        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            usd_try = data["rates"].get("TRY")
            usd_eur = data["rates"].get("EUR")

            if usd_try and usd_eur:
                eur_try = usd_try / usd_eur

                return {
                    "USD": usd_try,
                    "EUR": eur_try,
                }

    except Exception:
        pass

    return default_rates


# ---------------------------------------------------
# EVDS TÜFE / Yİ-ÜFE
# ---------------------------------------------------
@st.cache_data(ttl=86400)
def fetch_evds_indexes(start_date, end_date):

    default_vals = {
        "tufe": 3510.00,
        "yiufe": 5020.00
    }

    try:

        url = (
            "https://evds2.tcmb.gov.tr/service/evds/"
            "series=TP.FG.J0,TP.WI.YI01"
            "&startDate=01-01-2023"
            "&endDate=31-12-2030"
            "&frequency=5"
            "&type=json"
        )

        headers = {
            "key": EVDS_KEY
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:

            json_data = response.json()
            items = json_data.get("items", [])

            if items:

                index_dict = {}

                for item in items:

                    tarih = item.get("Tarih", "")

                    if len(tarih) >= 7:

                        ym = tarih[:7].replace(".", "-")

                        try:

                            tufe_value = float(item.get("TP_FG_J0") or 0)
                            yiufe_value = float(item.get("TP_WI_YI01") or 0)

                            if tufe_value > 0 and yiufe_value > 0:

                                index_dict[ym] = {
                                    "tufe": tufe_value,
                                    "yiufe": yiufe_value,
                                }

                        except Exception:
                            continue

                start_ym = start_date.strftime("%Y-%m")
                end_ym = end_date.strftime("%Y-%m")

                start_values = index_dict.get(start_ym)
                end_values = index_dict.get(end_ym)

                if not start_values and index_dict:

                    nearest_start = min(
                        index_dict.keys(),
                        key=lambda k: abs(
                            (
                                datetime.strptime(
                                    k,
                                    "%Y-%m"
                                ).date()
                                - start_date
                            ).days
                        )
                    )

                    start_values = index_dict[nearest_start]

                if not end_values and index_dict:

                    available_dates = sorted(index_dict.keys())

                    nearest_end = available_dates[-1]

                    for item in available_dates:
                        if item <= end_ym:
                            nearest_end = item

                    end_values = index_dict[nearest_end]

                return (
                    start_values or default_vals,
                    end_values or default_vals,
                )

    except Exception:
        pass

    return default_vals, default_vals


# ---------------------------------------------------
# BAŞLIK
# ---------------------------------------------------
st.title("⚖️ Kamu İhale & Doğrudan Temin Fiyat Analiz Portalı")

st.caption(
    "TCMB EVDS ve Canlı Döviz Kurları Destekli Otomatik Fiyat Araştırması"
)

st.divider()

# ---------------------------------------------------
# GİRDİ ALANLARI
# ---------------------------------------------------
with st.form("hesaplama_formu"):

    col1, col2 = st.columns(2)

    with col1:

        st.subheader("📝 Geçmiş Alım Bilgileri")

        initial_date = st.date_input(
            "Son Alım Tarihi",
            value=date.today().replace(year=date.today().year - 1),
            format="DD/MM/YYYY",
        )

        initial_price = st.number_input(
            "Son Alım Birim Fiyatı (₺)",
            min_value=0.0,
            value=15000.0,
            step=100.0,
        )

    with col2:

        st.subheader("📅 Güncel Teklif Bilgileri")

        tender_date = st.date_input(
            "İhale / Güncelleme Tarihi",
            value=date.today(),
            format="DD/MM/YYYY",
        )

        new_offer_price = st.number_input(
            "Yeni Firma Teklif Fiyatı (₺)",
            min_value=0.0,
            value=16200.0,
            step=100.0,
        )

    calculate = st.form_submit_button("📊 Analizi Hesapla")

# ---------------------------------------------------
# HESAPLAMA
# ---------------------------------------------------
if calculate:

    initial_date_str = initial_date.strftime("%Y-%m-%d")
    tender_date_str = tender_date.strftime("%Y-%m-%d")

    rates_initial = fetch_currency_rates(initial_date_str)
    rates_tender = fetch_currency_rates(tender_date_str)

    idx_initial, idx_tender = fetch_evds_indexes(
        initial_date,
        tender_date,
    )

    st.divider()

    st.subheader("📈 Ekonomik Göstergeler")

    col_g1, col_g2, col_g3, col_g4 = st.columns(4)

    with col_g1:
        u_init = rates_initial["USD"]
        u_tend = rates_tender["USD"]

        st.metric(
            "USD/TRY",
            f"{u_tend:.4f}",
            f"%{((u_tend-u_init)/u_init)*100:.2f}",
        )

    with col_g2:
        e_init = rates_initial["EUR"]
        e_tend = rates_tender["EUR"]

        st.metric(
            "EUR/TRY",
            f"{e_tend:.4f}",
            f"%{((e_tend-e_init)/e_init)*100:.2f}",
        )

    with col_g3:

        yi_init = idx_initial["yiufe"]
        yi_tend = idx_tender["yiufe"]

        st.metric(
            "Yİ-ÜFE",
            f"{yi_tend:.2f}",
            f"%{((yi_tend-yi_init)/yi_init)*100:.2f}",
        )

    with col_g4:

        tu_init = idx_initial["tufe"]
        tu_tend = idx_tender["tufe"]

        st.metric(
            "TÜFE",
            f"{tu_tend:.2f}",
            f"%{((tu_tend-tu_init)/tu_init)*100:.2f}",
        )

    # ---------------------------------------------------
    # FİYAT GÜNCELLEMELERİ
    # ---------------------------------------------------

    usd_updated = initial_price * (u_tend / u_init)
    eur_updated = initial_price * (e_tend / e_init)
    yiufe_updated = initial_price * (yi_tend / yi_init)
    tufe_updated = initial_price * (tu_tend / tu_init)

    firm_increase = (
        (new_offer_price - initial_price)
        / initial_price
        * 100
    )

    usd_increase = (u_tend - u_init) / u_init * 100
    eur_increase = (e_tend - e_init) / e_init * 100
    yiufe_increase = (yi_tend - yi_init) / yi_init * 100
    tufe_increase = (tu_tend - tu_init) / tu_init * 100

    # ---------------------------------------------------
    # MAKUL SINIRLAR
    # ---------------------------------------------------

    lower_bound = (
        usd_updated +
        eur_updated +
        yiufe_updated
    ) / 3

    upper_bound = max(
        tufe_updated,
        yiufe_updated
    )

    st.divider()

    st.subheader("🎯 Piyasa Fiyat Araştırma Sonucu")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Firma Artış Oranı",
        f"%{firm_increase:.2f}"
    )

    c2.metric(
        "Alt Makul Sınır",
        f"{lower_bound:,.2f} ₺"
    )

    c3.metric(
        "Üst Makul Sınır",
        f"{upper_bound:,.2f} ₺"
    )

    c4.metric(
        "Firma Teklifi",
        f"{new_offer_price:,.2f} ₺"
    )

    if new_offer_price <= lower_bound:

        st.success(
            "✅ SONUÇ: UYGUN"
        )

    elif new_offer_price <= upper_bound:

        st.info(
            "⚠️ SONUÇ: SINIRDA UYGUN"
        )

    elif new_offer_price <= upper_bound * 1.15:

        st.warning(
            "⚡ SONUÇ: YÜKSEK - Pazarlık önerilir."
        )

    else:

        st.error(
            "🚨 SONUÇ: ÇOK YÜKSEK"
        )

    # ---------------------------------------------------
    # GRAFİK
    # ---------------------------------------------------

    st.divider()

    df_chart = pd.DataFrame(
        {
            "Gösterge": [
                "Son Alım",
                "USD",
                "EUR",
                "Yİ-ÜFE",
                "TÜFE",
                "Firma Teklifi",
            ],
            "Fiyat": [
                initial_price,
                usd_updated,
                eur_updated,
                yiufe_updated,
                tufe_updated,
                new_offer_price,
            ],
        }
    )

    fig = px.bar(
        df_chart,
        x="Gösterge",
        y="Fiyat",
        color="Gösterge",
        text="Fiyat",
        title="Güncellenmiş Fiyat Karşılaştırması",
    )

    fig.update_traces(
        texttemplate="%{y:,.2f} ₺",
        textposition="outside",
    )

    fig.add_hline(
        y=lower_bound,
        line_dash="dot",
        annotation_text="Alt Makul Sınır",
    )

    fig.add_hline(
        y=upper_bound,
        line_dash="dash",
        annotation_text="Üst Makul Sınır",
    )

    fig.update_layout(
        showlegend=False,
        yaxis_title="Tutar (₺)",
        xaxis_title=""
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )
