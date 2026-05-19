# -*- coding: utf-8 -*-
"""Vista de limpieza y transformación."""

from __future__ import annotations

import streamlit as st

from src.config import DATASET_SCHEMAS
from src.etl.pipeline import run_pipeline
from src.utils.validators import validate_clean_data, validate_mapping
from views._shared import require_raw_data


def _type_banner(dataset_type: str) -> None:
    schema = DATASET_SCHEMAS.get(dataset_type, DATASET_SCHEMAS["general"])
    st.info(
        f"{schema['icon']} Tipo de datos: **{schema['label']}**  \n"
        f"_{schema['description']}_"
    )


def render() -> None:
    st.title("🧹 ETL y limpieza")

    if not require_raw_data():
        return

    raw_df = st.session_state.raw_data
    dataset_type = st.session_state.get("dataset_type", "financiero")
    mapping = st.session_state.get("column_mapping") or {}

    _type_banner(dataset_type)

    mapping_validation = validate_mapping(mapping, dataset_type)
    if mapping_validation.errors:
        st.error("Revisa el mapeo de columnas en **Cargar datos** antes de continuar.")
        for error in mapping_validation.errors:
            st.write(f"- {error}")
        if st.button("Ir a Cargar datos"):
            st.session_state.page = "Cargar datos"
            st.rerun()
        return

    with st.container(border=True):
        st.markdown("#### Opciones de limpieza")

        if dataset_type == "financiero":
            col1, col2, col3 = st.columns(3)
            with col1:
                default_currency = st.text_input("Moneda por defecto", value="USD", max_chars=3)
            with col2:
                drop_invalid = st.checkbox("Quitar filas inválidas", value=True,
                                           help="Elimina filas sin fecha o sin monto válido.")
            with col3:
                drop_duplicates = st.checkbox("Quitar duplicados", value=True,
                                              help="Elimina filas idénticas en fecha, monto, tipo, categoría y cuenta.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                drop_invalid = st.checkbox("Quitar filas con campos obligatorios vacíos", value=False,
                                           help="Elimina filas donde los campos requeridos estén vacíos.")
            with col2:
                drop_duplicates = st.checkbox("Quitar duplicados", value=True)
            default_currency = "USD"

        run = st.button("▶ Ejecutar limpieza", type="primary", use_container_width=True)

    if run:
        with st.spinner("Procesando datos…"):
            result = run_pipeline(
                raw_df,
                mapping,
                dataset_type=dataset_type,
                default_currency=default_currency.upper() or "USD",
                drop_invalid_rows=drop_invalid,
                drop_duplicates=drop_duplicates,
            )

        validation = validate_clean_data(result.data, dataset_type)
        st.session_state.clean_data = result.data
        st.session_state.rejected_rows = result.rejected_rows
        st.session_state.cleaning_log = result.log
        st.session_state.last_validation = validation

        if validation.ok:
            st.success(f"✅ Limpieza terminada — {len(result.data):,} filas listas para análisis.")
        else:
            st.error("La limpieza terminó, pero hay problemas que revisar.")

    clean_df = st.session_state.get("clean_data")
    if clean_df is None:
        st.info("Configura las opciones y ejecuta la limpieza para generar el dataset final.")
        return

    rejected = st.session_state.get("rejected_rows")
    rejected_count = 0 if rejected is None else len(rejected)

    # Métricas de resultado
    total_raw = len(raw_df)
    pct_ok = (len(clean_df) / total_raw * 100) if total_raw > 0 else 0

    a, b, c, d = st.columns(4)
    a.metric("Filas originales", f"{total_raw:,}")
    b.metric("Filas limpias", f"{len(clean_df):,}", delta=f"{pct_ok:.1f}% conservado")
    c.metric("Rechazadas", f"{rejected_count:,}", delta=f"-{rejected_count}" if rejected_count else None,
             delta_color="inverse")
    d.metric("Columnas", f"{len(clean_df.columns):,}")

    # Log de limpieza
    with st.expander("📋 Log de limpieza", expanded=True):
        for item in st.session_state.get("cleaning_log", []):
            st.write(f"- {item}")

    # Advertencias y errores de validación
    validation = st.session_state.get("last_validation")
    if validation:
        for warning in validation.warnings:
            st.warning(warning)
        for error in validation.errors:
            st.error(error)

    # Vista previa del dataset limpio
    st.subheader("Vista previa del dataset limpio")
    st.dataframe(clean_df.head(100), use_container_width=True)

    # Filas rechazadas con razón
    if rejected is not None and not rejected.empty:
        with st.expander(f"⚠️ Filas rechazadas ({rejected_count:,})", expanded=rejected_count > 0):
            reason_col = "_razon_rechazo"
            if reason_col in rejected.columns:
                reason_counts = rejected[reason_col].value_counts()
                st.markdown("**Motivos de rechazo:**")
                for reason, count in reason_counts.items():
                    st.write(f"- {reason}: **{count}** fila(s)")
                st.divider()
            st.dataframe(rejected, use_container_width=True)
            st.caption("Descarga las filas rechazadas para revisarlas y corregirlas manualmente.")
