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
                        
