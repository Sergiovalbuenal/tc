# -*- coding: utf-8 -*-
"""Carga y mapeo inicial de datos."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import STANDARD_FIELDS
from src.state import clear_data
from src.utils.file_loader import get_column_options, guess_column_mapping, load_uploaded_file
from src.utils.sample_data import build_sample_data
from src.utils.validators import validate_mapping


def _mapping_form(df: pd.DataFrame) -> dict[str, str | None]:
    """Formulario para decirle al dashboard qué significa cada columna."""
    guessed = st.session_state.get("column_mapping") or guess_column_mapping(df)
    options = get_column_options(df)

    mapping: dict[str, str | None] = {}

    st.markdown("#### Mapeo de columnas")
    st.caption("El sistema sugiere columnas, pero tú puedes corregirlas antes de limpiar.")

    cols = st.columns(2)
    for index, (field, label) in enumerate(STANDARD_FIELDS.items()):
        default_value = guessed.get(field) or "No usar"
        default_index = options.index(default_value) if default_value in options else 0

        with cols[index % 2]:
            selected = st.selectbox(
                label,
                options=options,
                index=default_index,
                key=f"mapping_{field}",
            )
            mapping[field] = None if selected == "No usar" else selected

    validation = validate_mapping(mapping)
    if validation.errors:
        for error in validation.errors:
            st.error(error)
    if validation.warnings:
        for warning in validation.warnings:
            st.warning(warning)

    return mapping


def render() -> None:
    st.title("📁 Cargar datos")
    st.write("Sube tu archivo financiero o usa una muestra para revisar el flujo completo.")

    with st.container(border=True):
        uploaded_file = st.file_uploader(
            "Archivo financiero",
            type=["csv", "txt", "xlsx", "xls"],
            help="Formatos permitidos: CSV, TXT, XLSX y XLS.",
        )

        left, right = st.columns([1, 1])
        with left:
            use_sample = st.button("Usar datos de ejemplo", use_container_width=True)
        with right:
            reset = st.button("Limpiar sesión", use_container_width=True)

    if reset:
        clear_data()
        st.success("Sesión limpiada.")
        st.rerun()

    if use_sample:
        df = build_sample_data()
        st.session_state.raw_data = df
        st.session_state.loaded_filename = "datos_ejemplo.csv"
        st.session_state.column_mapping = guess_column_mapping(df)
        st.success("Datos de ejemplo cargados.")
        st.rerun()

    if uploaded_file is not None:
        try:
            df = load_uploaded_file(uploaded_file)
            st.session_state.raw_data = df
            st.session_state.loaded_filename = uploaded_file.name
            st.session_state.column_mapping = guess_column_mapping(df)
            st.success(f"Archivo cargado: {uploaded_file.name}")
        except Exception as exc:  # noqa: BLE001
            st.error("No pude leer el archivo. Revisa el formato o prueba guardarlo como UTF-8/XLSX.")
            with st.expander("Detalle técnico"):
                st.exception(exc)
            return

    raw_df = st.session_state.get("raw_data")
    if raw_df is None:
        st.info("Aún no hay datos cargados.")
        return

    st.subheader("Vista previa")
    st.caption(f"Archivo actual: {st.session_state.get('loaded_filename')}")
    st.dataframe(raw_df.head(50), use_container_width=True)

    mapping = _mapping_form(raw_df)

    if st.button("Guardar mapeo", type="primary", use_container_width=True):
        st.session_state.column_mapping = mapping
        st.success("Mapeo guardado. Continúa con **ETL y limpieza**.")
