# -*- coding: utf-8 -*-
"""Vista de limpieza y transformación."""

from __future__ import annotations

import streamlit as st

from src.etl.pipeline import run_pipeline
from src.utils.validators import validate_clean_data, validate_mapping
from views._shared import require_raw_data


def render() -> None:
    st.title("🧹 ETL y limpieza")

    if not require_raw_data():
        return

    raw_df = st.session_state.raw_data
    mapping = st.session_state.get("column_mapping") or {}

    mapping_validation = validate_mapping(mapping)
    if mapping_validation.errors:
        st.error("Antes de limpiar, revisa el mapeo de columnas en **Cargar datos**.")
        for error in mapping_validation.errors:
            st.write(f"- {error}")
        return

    with st.container(border=True):
        st.markdown("#### Opciones de limpieza")
        col1, col2, col3 = st.columns(3)
        with col1:
            default_currency = st.text_input("Moneda por defecto", value="USD", max_chars=3)
        with col2:
            drop_invalid = st.checkbox("Quitar filas inválidas", value=True)
        with col3:
            drop_duplicates = st.checkbox("Quitar duplicados", value=True)

        run = st.button("Ejecutar limpieza", type="primary", use_container_width=True)

    if run:
        result = run_pipeline(
            raw_df,
            mapping,
            default_currency=default_currency.upper() or "USD",
            drop_invalid_rows=drop_invalid,
            drop_duplicates=drop_duplicates,
        )

        validation = validate_clean_data(result.data)
        st.session_state.clean_data = result.data
        st.session_state.rejected_rows = result.rejected_rows
        st.session_state.cleaning_log = result.log
        st.session_state.last_validation = validation

        if validation.ok:
            st.success("Limpieza terminada.")
        else:
            st.error("La limpieza terminó, pero hay problemas que revisar.")

    clean_df = st.session_state.get("clean_data")
    if clean_df is None:
        st.info("Ejecuta la limpieza para generar el dataset final.")
        return

    rejected = st.session_state.get("rejected_rows")
    rejected_count = 0 if rejected is None else len(rejected)

    st.subheader("Resultado")
    a, b, c = st.columns(3)
    a.metric("Filas limpias", f"{len(clean_df):,}")
    b.metric("Columnas", f"{len(clean_df.columns):,}")
    c.metric("Rechazadas", f"{rejected_count:,}")

    with st.expander("Log de limpieza", expanded=True):
        for item in st.session_state.get("cleaning_log", []):
            st.write(f"- {item}")

    validation = st.session_state.get("last_validation")
    if validation:
        for warning in validation.warnings:
            st.warning(warning)
        for error in validation.errors:
            st.error(error)

    st.dataframe(clean_df.head(100), use_container_width=True)

    rejected = st.session_state.get("rejected_rows")
    if rejected is not None and not rejected.empty:
        with st.expander("Filas rechazadas"):
            st.dataframe(rejected, use_container_width=True)
