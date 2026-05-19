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


def _run_etl(raw_df, mapping, dataset_type, default_currency, drop_invalid, drop_duplicates) -> None:
    """Ejecuta el pipeline y guarda los resultados en session_state."""
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
    st.session_state.auto_run_etl = False  # Resetear la bandera


def render() -> None:
    st.title("🧹 ETL y limpieza")

    if not require_raw_data():
        return

    raw_df = st.session_state.raw_data
    dataset_type = st.session_state.get("dataset_type", "financiero")
    mapping = st.session_state.get("column_mapping") or {}

    _type_banner(dataset_type)

    # Mostrar advertencias de mapeo, pero NO bloquear el flujo
    mapping_validation = validate_mapping(mapping, dataset_type)
    for warning in mapping_validation.warnings:
        st.warning(warning)
    for error in mapping_validation.errors:
        st.warning(f"⚠️ {error} — el análisis puede ser limitado sin este campo.")

    # Opciones de limpieza
    with st.container(border=True):
        st.markdown("#### Opciones de limpieza")

        if dataset_type == "financiero":
            col1, col2, col3 = st.columns(3)
            with col1:
                default_currency = st.text_input("Moneda por defecto", value="USD", max_chars=3)
            with col2:
                drop_invalid = st.checkbox(
                    "Quitar filas inválidas", value=True,
                    help="Elimina filas sin fecha o sin monto válido.",
                )
            with col3:
                drop_duplicates = st.checkbox(
                    "Quitar duplicados", value=True,
                    help="Elimina filas idénticas en fecha, monto, tipo, categoría y cuenta.",
                )
        else:
            col1, col2 = st.columns(2)
            with col1:
                drop_invalid = st.checkbox(
                    "Quitar filas con campos vacíos", value=False,
                    help="Elimina filas donde los campos requeridos estén vacíos.",
                )
            with col2:
                drop_duplicates = st.checkbox("Quitar duplicados", value=True)
            default_currency = "USD"

        run_btn = st.button("▶ Ejecutar limpieza", type="primary", use_container_width=True)

    # Auto-ejecución si viene del botón "Procesar automáticamente"
    auto_run = st.session_state.get("auto_run_etl", False)
    if auto_run and st.session_state.get("clean_data") is None:
        _run_etl(raw_df, mapping, dataset_type, default_currency, drop_invalid, drop_duplicates)
        st.rerun()

    if run_btn:
        _run_etl(raw_df, mapping, dataset_type, default_currency, drop_invalid, drop_duplicates)

    # ── Resultados ────────────────────────────────────────────────────────────
    clean_df = st.session_state.get("clean_data")
    if clean_df is None:
        st.info("Configura las opciones y ejecuta la limpieza para generar el dataset final.")
        return

    rejected = st.session_state.get("rejected_rows")
    rejected_count = 0 if rejected is None else len(rejected)
    total_raw = len(raw_df)
    pct_ok = (len(clean_df) / total_raw * 100) if total_raw > 0 else 0

    validation = st.session_state.get("last_validation")
    if validation and validation.ok:
        st.success(f"✅ {len(clean_df):,} filas listas para análisis.")
    elif validation and not validation.ok:
        st.error("La limpieza terminó con algunos problemas.")

    # Métricas
    a, b, c, d = st.columns(4)
    a.metric("Filas originales", f"{total_raw:,}")
    b.metric("Filas limpias", f"{len(clean_df):,}", delta=f"{pct_ok:.1f}% conservado")
    c.metric(
        "Rechazadas", f"{rejected_count:,}",
        delta=f"-{rejected_count}" if rejected_count else None,
        delta_color="inverse",
    )
    d.metric("Columnas útiles", f"{len([c for c in clean_df.columns if not c.startswith('_')]):,}")

    # Log de limpieza
    with st.expander("📋 Log de limpieza", expanded=True):
        for item in st.session_state.get("cleaning_log", []):
            st.write(f"- {item}")

    # Validaciones
    if validation:
        for warning in validation.warnings:
            st.warning(warning)
        for error in validation.errors:
            st.error(error)

    # Vista previa
    st.subheader("Dataset limpio")
    visible_cols = [c for c in clean_df.columns if not c.startswith("_")]
    st.dataframe(clean_df[visible_cols].head(100), use_container_width=True)

    # Filas rechazadas
    if rejected is not None and not rejected.empty:
        with st.expander(f"⚠️ Filas rechazadas ({rejected_count:,})", expanded=False):
            reason_col = "_razon_rechazo"
            if reason_col in rejected.columns:
                st.markdown("**Motivos de rechazo:**")
                for reason, count in rejected[reason_col].value_counts().items():
                    st.write(f"- {reason}: **{count}** fila(s)")
                st.divider()
            visible_rej = [c for c in rejected.columns if not c.startswith("_") or c == "_razon_rechazo"]
            st.dataframe(rejected[visible_rej], use_container_width=True)
            st.caption("Corrígelas en el archivo original y vuelve a cargar para incluirlas.")
