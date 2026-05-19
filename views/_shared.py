# -*- coding: utf-8 -*-
"""Piezas de interfaz compartidas por varias vistas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.etl.pipeline import filter_data


def require_raw_data() -> bool:
    if st.session_state.get("raw_data") is None:
        st.warning("Primero carga un archivo o usa los datos de ejemplo.")
        st.info("Ve a **Cargar datos** en la barra lateral.")
        return False
    return True


def require_clean_data() -> bool:
    if st.session_state.get("clean_data") is None:
        st.warning("Todavía no hay datos limpios para analizar.")
        st.info("Ve a **ETL y limpieza** y ejecuta la transformación.")
        return False
    return True


def filtered_dataset(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    """Filtros comunes adaptados al tipo de dataset."""
    if df is None or df.empty:
        return pd.DataFrame()

    dataset_type = st.session_state.get("dataset_type", "financiero")

    if dataset_type == "financiero":
        return _financial_filters(df, key_prefix)
    else:
        return _generic_filters(df, key_prefix)


def _financial_filters(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    """Filtros para datasets financieros (fecha, moneda, categoría, cuenta)."""
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

        selected_currencies = st.multiselect("Monedas", options=currencies, default=currencies,
                                              key=f"{key_prefix}_currencies")
        selected_categories = st.multiselect("Categorías", options=categories, default=categories,
                                              key=f"{key_prefix}_categories")
        selected_accounts = st.multiselect("Cuentas", options=accounts, default=accounts,
                                           key=f"{key_prefix}_accounts")

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


def _generic_filters(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    """Filtros genéricos: detecta columnas de fecha y categóricas disponibles."""
    date_cols = [c for c in df.columns if not c.startswith("_") and pd.api.types.is_datetime64_any_dtype(df[c])]
    cat_cols = [
        c for c in df.columns
        if not c.startswith("_")
        and c not in date_cols
        and df[c].dtype == object
        and df[c].nunique() <= 50
    ]

    filtered = df.copy()

    with st.expander("Filtros del análisis", expanded=False):
        if date_cols:
            date_col = st.selectbox("Columna de fecha para filtrar", options=date_cols,
                                    key=f"{key_prefix}_date_col")
            min_date = df[date_col].min().date()
            max_date = df[date_col].max().date()
            selected_dates = st.date_input(
                "Rango de fechas",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key=f"{key_prefix}_date_range",
            )
            if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
                start, end = pd.Timestamp(selected_dates[0]), pd.Timestamp(selected_dates[1])
                filtered = filtered[(filtered[date_col] >= start) & (filtered[date_col] <= end)]

        for col in cat_cols[:3]:  # Máximo 3 filtros categóricos
            options = sorted(filtered[col].dropna().unique().tolist())
            selected = st.multiselect(col.replace("_", " ").title(), options=options,
                                      default=options, key=f"{key_prefix}_{col}_filter")
            if selected:
                filtered = filtered[filtered[col].isin(selected)]

    return filtered.reset_index(drop=True)
