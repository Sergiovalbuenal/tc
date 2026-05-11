# -*- coding: utf-8 -*-
"""Piezas de interfaz compartidas por varias vistas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.etl.pipeline import filter_data


def require_raw_data() -> bool:
    """Muestra aviso si todavía no hay archivo cargado."""
    if st.session_state.get("raw_data") is None:
        st.warning("Primero carga un archivo o usa los datos de ejemplo.")
        st.info("Ve a **Cargar datos** en la barra lateral.")
        return False
    return True


def require_clean_data() -> bool:
    """Muestra aviso si todavía no se ejecutó la limpieza."""
    if st.session_state.get("clean_data") is None:
        st.warning("Todavía no hay datos limpios para analizar.")
        st.info("Ve a **ETL y limpieza** y ejecuta la transformación.")
        return False
    return True


def filtered_dataset(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    """Filtros comunes para KPIs, gráficas y exportaciones."""
    if df is None or df.empty:
        return pd.DataFrame()

    with st.expander("Filtros del análisis", expanded=False):
        min_date = pd.to_datetime(df["fecha"]).min().date()
        max_date = pd.to_datetime(df["fecha"]).max().date()

        selected_dates = st.date_input(
            "Rango de fechas",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key=f"{key_prefix}_date_range",
        )

        currencies = sorted(df["moneda"].dropna().unique())
        categories = sorted(df["categoria"].dropna().unique())
        accounts = sorted(df["cuenta"].dropna().unique())

        selected_currencies = st.multiselect(
            "Monedas",
            options=currencies,
            default=currencies,
            key=f"{key_prefix}_currencies",
        )
        selected_categories = st.multiselect(
            "Categorías",
            options=categories,
            default=categories,
            key=f"{key_prefix}_categories",
        )
        selected_accounts = st.multiselect(
            "Cuentas",
            options=accounts,
            default=accounts,
            key=f"{key_prefix}_accounts",
        )

    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        date_range = (pd.Timestamp(selected_dates[0]), pd.Timestamp(selected_dates[1]))
    else:
        date_range = None

    return filter_data(
        df,
        date_range=date_range,
        currencies=selected_currencies,
        categories=selected_categories,
        accounts=selected_accounts,
    )
