# -*- coding: utf-8 -*-
"""Carga y mapeo inicial de datos."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import DATASET_SCHEMAS
from src.detection import DetectionResult, detect_dataset_type
from src.state import clear_data
from src.utils.file_loader import get_column_options, guess_column_mapping, load_uploaded_file
from src.utils.sample_data import build_sample_data
from src.utils.validators import validate_mapping


def _render_detection_banner(detected: DetectionResult) -> str:
    """Muestra el tipo detectado y permite que el usuario lo cambie.

    Devuelve el tipo seleccionado (puede ser diferente al detectado si el usuario lo cambió).
    """
    type_options = {k: f"{v['icon']} {v['label']}" for k, v in DATASET_SCHEMAS.items()}
    current = st.session_state.get("dataset_type", detected.dataset_type)

    st.markdown("#### Tipo de datos detectado")
    col_info, col_select = st.columns([3, 2])

    with col_info:
        if detected.confidence >= 0.3:
            conf_pct = int(detected.confidence * 100)
            st.success(
                f"{detected.icon} **{detected.label}** — confianza {conf_pct}%  \n"
                f"_{detected.description}_"
            )
        elif detected.confidence > 0:
            conf_pct = int(detected.confidence * 100)
            st.warning(
                f"{detected.icon} **{detected.label}** — confianza baja ({conf_pct}%)  \n"
                f"Revisa si el tipo seleccionado es correcto."
            )
        else:
            st.info(
                "No se pudo identificar el tipo automáticamente.  \n"
                "Selecciona el tipo de datos manualmente."
            )

    with col_select:
        selected_type = st.selectbox(
            "Tipo de datos",
            options=list(type_options.keys()),
            format_func=lambda k: type_options[k],
            index=list(type_options.keys()).index(current) if current in type_options else 0,
            key="dataset_type_selector",
            help="Cambia el tipo si la detección automática no fue correcta.",
        )

    if detected.suggestions:
        for s in detected.suggestions:
            st.caption(f"💡 {s}")

    return selected_type


def _mapping_form(df: pd.DataFrame, dataset_type: str) -> dict[str, str | None]:
    """Formulario de mapeo de columnas adaptado al tipo de dataset seleccionado."""
    schema = DATASET_SCHEMAS.get(dataset_type, DATASET_SCHEMAS["general"])
    fields = schema["fields"]

    if not fields:
        st.info("Para el tipo 'Datos Generales' no se requiere mapeo de columnas. El ETL procesará todas las columnas automáticamente.")
        return {}

    # Para el tipo seleccionado usamos sus aliases; para financiero re-usamos guess_column_mapping
    if dataset_type == "financiero":
        guessed = st.session_state.get("column_mapping") or guess_column_mapping(df)
    else:
        guessed = _guess_mapping_for_type(df, dataset_type)

    options = get_column_options(df)
    mapping: dict[str, str | None] = {}

    st.markdown("#### Mapeo de columnas")
    st.caption(
        f"El sistema sugiere columnas para **{schema['label']}**. "
        "Corrígelas si es necesario antes de ejecutar el ETL."
    )

    cols = st.columns(2)
    required_fields = schema.get("required", [])

    for index, (field_key, field_label) in enumerate(fields.items()):
        is_required = field_key in required_fields
        label_display = f"{field_label} *" if is_required else field_label

        default_value = guessed.get(field_key) or "No usar"
        default_index = options.index(default_value) if default_value in options else 0

        with cols[index % 2]:
            selected = st.selectbox(
                label_display,
                options=options,
                index=default_index,
                key=f"mapping_{dataset_type}_{field_key}",
                help="Campo obligatorio" if is_required else None,
            )
            mapping[field_key] = None if selected == "No usar" else selected

    st.caption("_(*) Campo obligatorio_")

    validation = validate_mapping(mapping, dataset_type)
    if validation.errors:
        for error in validation.errors:
            st.error(error)
    if validation.warnings:
        for warning in validation.warnings:
            st.warning(warning)

    return mapping


def _guess_mapping_for_type(df: pd.DataFrame, dataset_type: str) -> dict[str, str | None]:
    """Auto-detecta el mapeo de columnas para tipos no financieros."""
    from src.utils.file_loader import normalize_name

    schema = DATASET_SCHEMAS.get(dataset_type, {})
    aliases_by_field = schema.get("aliases", {})
    columns = list(df.columns)
    normalized_columns = {normalize_name(col): col for col in columns}

    mapping: dict[str, str | None] = {}
    for field_key, aliases in aliases_by_field.items():
        match = None
        for alias in aliases:
            norm = normalize_name(alias)
            if norm in normalized_columns:
                match = normalized_columns[norm]
                break
        if match is None:
            for col in columns:
                if any(normalize_name(alias) in normalize_name(col) for alias in aliases):
                    match = col
                    break
        mapping[field_key] = match

    return mapping


def render() -> None:
    st.title("📁 Cargar datos")
    st.write("Sube tu archivo o usa los datos de ejemplo para explorar el flujo completo.")

    with st.container(border=True):
        uploaded_file = st.file_uploader(
            "Archivo de datos",
            type=["csv", "txt", "xlsx", "xls"],
            help="Formatos aceptados: CSV, TXT, XLSX y XLS. Tamaño máximo recomendado: 50 MB.",
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
        st.session_state.dataset_type = "financiero"
        st.success("Datos de ejemplo cargados.")
        st.rerun()

    if uploaded_file is not None:
        try:
            df = load_uploaded_file(uploaded_file)
            detected = detect_dataset_type(df)
            st.session_state.raw_data = df
            st.session_state.loaded_filename = uploaded_file.name
            st.session_state.dataset_type = detected.dataset_type
            # Guardamos el mapeo inicial basado en el tipo detectado
            if detected.dataset_type == "financiero":
                st.session_state.column_mapping = guess_column_mapping(df)
            else:
                st.session_state.column_mapping = _guess_mapping_for_type(df, detected.dataset_type)
            st.success(f"✅ Archivo cargado: **{uploaded_file.name}** — {len(df):,} filas, {len(df.columns)} columnas.")
        except Exception as exc:
            _show_upload_error(exc, uploaded_file.name)
            return

    raw_df = st.session_state.get("raw_data")
    if raw_df is None:
        st.info("Aún no hay datos cargados. Sube un archivo o usa los datos de ejemplo.")
        return

    # Banner de detección / selección de tipo
    detected_for_banner = detect_dataset_type(raw_df)
    selected_type = _render_detection_banner(detected_for_banner)

    # Si el usuario cambia el tipo, actualizamos el estado
    if selected_type != st.session_state.get("dataset_type"):
        st.session_state.dataset_type = selected_type
        if selected_type == "financiero":
            st.session_state.column_mapping = guess_column_mapping(raw_df)
        else:
            st.session_state.column_mapping = _guess_mapping_for_type(raw_df, selected_type)

    st.divider()

    # Vista previa de los datos crudos
    with st.expander("Vista previa del archivo original", expanded=True):
        st.caption(
            f"Archivo: **{st.session_state.get('loaded_filename')}** — "
            f"{len(raw_df):,} filas × {len(raw_df.columns)} columnas"
        )
        st.dataframe(raw_df.head(50), use_container_width=True)

    # Formulario de mapeo
    mapping = _mapping_form(raw_df, selected_type)

    if st.button("Guardar mapeo y continuar →", type="primary", use_container_width=True):
        st.session_state.column_mapping = mapping
        st.session_state.dataset_type = selected_type
        st.session_state.clean_data = None  # Forzar re-ejecución del ETL
        st.success("Mapeo guardado. Ve a **ETL y limpieza** para procesar los datos.")


def _show_upload_error(exc: Exception, filename: str) -> None:
    """Muestra un mensaje de error detallado y accionable al usuario."""
    msg = str(exc).lower()

    st.error(f"No se pudo leer **{filename}**.")

    if "codec" in msg or "encoding" in msg or "unicode" in msg:
        st.warning(
            "**Problema de codificación de caracteres.**  \n"
            "El archivo parece tener caracteres especiales (tildes, ñ, etc.) en un formato inesperado.  \n"
            "**Solución:** Abre el archivo en Excel → Guardar como → CSV UTF-8 (con BOM)."
        )
    elif "excel" in msg or "openpyxl" in msg or "xlrd" in msg:
        st.warning(
            "**Problema al leer el archivo Excel.**  \n"
            "Puede estar dañado, protegido con contraseña, o en un formato muy antiguo (.xls).  \n"
            "**Solución:** Ábrelo en Excel y guárdalo como **.xlsx** o **CSV**."
        )
    elif "separator" in msg or "sep" in msg or "delimiter" in msg:
        st.warning(
            "**No se detectó el separador del CSV.**  \n"
            "El archivo puede usar punto y coma (;) o tabulador como separador.  \n"
            "**Solución:** Abre el CSV en un editor de texto y verifica qué carácter separa las columnas."
        )
    elif "empty" in msg or "no columns" in msg:
        st.warning(
            "**El archivo parece estar vacío o sin columnas.**  \n"
            "**Solución:** Verifica que el archivo tenga datos y que la primera fila sea el encabezado."
        )
    else:
        st.warning(
            "**Sugerencias generales:**\n"
            "- Guarda el archivo como **CSV UTF-8** o **XLSX** e inténtalo de nuevo.\n"
            "- Verifica que el archivo no esté abierto en otro programa.\n"
            "- Asegúrate de que la primera fila tenga los nombres de columna."
        )

    with st.expander("Detalle técnico del error"):
        st.exception(exc)
