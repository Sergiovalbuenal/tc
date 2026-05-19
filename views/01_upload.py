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


# ──────────────────────────────────────────────────────────────────────────────
# Auto-mapeo inteligente
# ──────────────────────────────────────────────────────────────────────────────

# Qué tipo de dato esperamos para cada campo estándar:
# "num" = numérico, "date" = fecha, "text" = texto/categoría
_FIELD_DATA_TYPE: dict[str, str] = {
    # Financiero
    "monto": "num", "fecha": "date", "tipo": "text", "categoria": "text",
    "subcategoria": "text", "cuenta": "text", "descripcion": "text", "moneda": "text",
    # Ventas
    "total": "num", "cantidad": "num", "precio": "num",
    "producto": "text", "cliente": "text", "vendedor": "text", "region": "text", "estado": "text",
    # RRHH
    "salario": "num", "fecha_ingreso": "date",
    "nombre": "text", "cargo": "text", "departamento": "text", "genero": "text", "sede": "text",
    # Inventario
    "stock": "num",
    "bodega": "text", "proveedor": "text",
}


def _guess_mapping_for_type(df: pd.DataFrame, dataset_type: str) -> dict[str, str | None]:
    """Auto-detecta el mapeo de columnas en dos pasadas.

    Pasada 1: coincidencia exacta / parcial por nombre de columna.
    Pasada 2: si queda un campo sin mapear, usa el tipo de dato de la columna como
              criterio de desempate (número → salario/monto, fecha → fecha_ingreso, etc.).
    """
    from src.utils.file_loader import normalize_name

    schema = DATASET_SCHEMAS.get(dataset_type, {})
    aliases_by_field = schema.get("aliases", {})
    columns = list(df.columns)
    normalized_cols = {normalize_name(col): col for col in columns}

    mapping: dict[str, str | None] = {}
    used_cols: set[str] = set()

    # ── Pasada 1: nombre ─────────────────────────────────────────────────────
    for field_key, aliases in aliases_by_field.items():
        match = None
        # Exacto
        for alias in aliases:
            if normalize_name(alias) in normalized_cols:
                match = normalized_cols[normalize_name(alias)]
                break
        # Parcial (el alias está contenido en el nombre de columna)
        if match is None:
            for col in columns:
                norm_col = normalize_name(col)
                if any(normalize_name(a) in norm_col for a in aliases):
                    match = col
                    break
        if match:
            mapping[field_key] = match
            used_cols.add(match)
        else:
            mapping[field_key] = None

    # ── Pasada 2: tipo de dato como fallback ─────────────────────────────────
    # Clasificamos las columnas no mapeadas por su dtype
    unmapped_num = [
        c for c in columns
        if c not in used_cols and pd.api.types.is_numeric_dtype(df[c])
    ]
    unmapped_date = [
        c for c in columns
        if c not in used_cols and pd.api.types.is_datetime64_any_dtype(df[c])
    ]
    # Para texto tomamos object con pocos únicos (categorías) o muchos (texto libre)
    unmapped_text = [
        c for c in columns
        if c not in used_cols
        and not pd.api.types.is_numeric_dtype(df[c])
        and not pd.api.types.is_datetime64_any_dtype(df[c])
    ]

    # También intentamos columnas object que parezcan fechas
    unmapped_datelike = [
        c for c in unmapped_text
        if df[c].dropna().astype(str).str.contains(r"[-/\.]", regex=True).mean() > 0.5
    ]

    for field_key, current_val in mapping.items():
        if current_val is not None:
            continue  # Ya tiene mapeo, no tocar
        expected_dtype = _FIELD_DATA_TYPE.get(field_key, "text")

        if expected_dtype == "num" and unmapped_num:
            mapping[field_key] = unmapped_num.pop(0)
            used_cols.add(mapping[field_key])
        elif expected_dtype == "date" and unmapped_date:
            mapping[field_key] = unmapped_date.pop(0)
            used_cols.add(mapping[field_key])
        elif expected_dtype == "date" and unmapped_datelike:
            mapping[field_key] = unmapped_datelike.pop(0)
            unmapped_text.remove(mapping[field_key])
            used_cols.add(mapping[field_key])
        elif expected_dtype == "text" and unmapped_text:
            mapping[field_key] = unmapped_text.pop(0)
            used_cols.add(mapping[field_key])

    return mapping


# ──────────────────────────────────────────────────────────────────────────────
# Componentes de UI
# ──────────────────────────────────────────────────────────────────────────────

def _render_detection_banner(detected: DetectionResult) -> str:
    """Muestra el tipo detectado y devuelve el tipo seleccionado por el usuario."""
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
                "Revisa si el tipo seleccionado es correcto."
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

    return selected_type


def _mapping_form(df: pd.DataFrame, dataset_type: str) -> dict[str, str | None]:
    """Formulario de mapeo con las columnas sugeridas automáticamente."""
    schema = DATASET_SCHEMAS.get(dataset_type, DATASET_SCHEMAS["general"])
    fields = schema["fields"]

    if not fields:
        st.info(
            "Para **Datos Generales** no se requiere mapeo. "
            "El ETL procesará todas las columnas automáticamente."
        )
        return {}

    # Siempre usar el mapeo guardado en session_state (ya fue sembrado con _seed_mapping_widgets)
    guessed = st.session_state.get("column_mapping") or _guess_mapping_for_type(df, dataset_type)

    options = get_column_options(df)
    mapping: dict[str, str | None] = {}
    required_fields = schema.get("required", [])

    st.markdown("#### Mapeo de columnas")
    col_desc, col_refresh = st.columns([5, 1])
    with col_desc:
        st.caption(
            f"Sugerencia automática para **{schema['label']}**. "
            "Puedes corregir el mapeo antes de procesar."
        )
    with col_refresh:
        if st.button("↺ Re-mapear", help="Recalcula el mapeo automático", key="remap_btn"):
            if dataset_type == "financiero":
                st.session_state.column_mapping = guess_column_mapping(df)
            else:
                st.session_state.column_mapping = _guess_mapping_for_type(df, dataset_type)
            st.rerun()

    cols = st.columns(2)
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
                help="Campo obligatorio — sin esto el ETL no puede procesar los datos." if is_required else None,
            )
            mapping[field_key] = None if selected == "No usar" else selected

    st.caption("_(*) Campo obligatorio_")

    # Solo mostramos advertencias, no errores bloqueantes
    validation = validate_mapping(mapping, dataset_type)
    for warning in validation.warnings:
        st.warning(warning)
    # Los errores de campos obligatorios los mostramos como advertencia aquí
    # (el bloqueo real ocurre en ETL si el campo es crítico)
    for error in validation.errors:
        st.warning(f"⚠️ {error} — puedes continuar, pero el análisis será limitado.")

    return mapping


# ──────────────────────────────────────────────────────────────────────────────
# Gestión de estados de widgets
# ──────────────────────────────────────────────────────────────────────────────

def _clear_mapping_widgets() -> None:
    """Elimina los valores guardados de los widgets de mapeo para que se recalculen."""
    keys_to_delete = [k for k in st.session_state if k.startswith("mapping_")]
    for key in keys_to_delete:
        del st.session_state[key]


def _seed_mapping_widgets(dataset_type: str, mapping: dict[str, str | None]) -> None:
    """Pre-carga los valores correctos en los widgets de mapeo antes de renderizar."""
    for field_key, col_value in mapping.items():
        widget_key = f"mapping_{dataset_type}_{field_key}"
        st.session_state[widget_key] = col_value if col_value is not None else "No usar"


# ──────────────────────────────────────────────────────────────────────────────
# Vista principal
# ──────────────────────────────────────────────────────────────────────────────

def render() -> None:
    st.title("📁 Cargar datos")
    st.write("Sube tu archivo. El sistema detecta el tipo, mapea las columnas y procesa automáticamente.")

    with st.container(border=True):
        uploaded_file = st.file_uploader(
            "Archivo de datos",
            type=["csv", "txt", "xlsx", "xls"],
            help="Formatos aceptados: CSV, TXT, XLSX y XLS.",
        )
        left, right = st.columns(2)
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
        mapping = guess_column_mapping(df)
        st.session_state.raw_data = df
        st.session_state.loaded_filename = "datos_ejemplo.csv"
        st.session_state.column_mapping = mapping
        st.session_state.dataset_type = "financiero"
        st.session_state["dataset_type_selector"] = "financiero"
        st.session_state.auto_run_etl = True
        st.session_state.clean_data = None
        _clear_mapping_widgets()
        _seed_mapping_widgets("financiero", mapping)
        st.rerun()

    if uploaded_file is not None:
        try:
            df = load_uploaded_file(uploaded_file)
            detected = detect_dataset_type(df)
            dtype = detected.dataset_type
            mapping = (
                guess_column_mapping(df)
                if dtype == "financiero"
                else _guess_mapping_for_type(df, dtype)
            )
            st.session_state.raw_data = df
            st.session_state.loaded_filename = uploaded_file.name
            st.session_state.dataset_type = dtype
            st.session_state.column_mapping = mapping
            st.session_state.clean_data = None
            # Sincronizar el widget del selectbox de tipo
            st.session_state["dataset_type_selector"] = dtype
            # Limpiar los widgets de mapeo anteriores para que tomen los nuevos valores
            _clear_mapping_widgets()
            # Pre-cargar los valores correctos en los widgets de mapeo
            _seed_mapping_widgets(dtype, mapping)
            st.success(
                f"✅ **{uploaded_file.name}** cargado — "
                f"{len(df):,} filas, {len(df.columns)} columnas."
            )
        except Exception as exc:
            _show_upload_error(exc, uploaded_file.name)
            return

    raw_df = st.session_state.get("raw_data")
    if raw_df is None:
        st.info("Aún no hay datos cargados. Sube un archivo o usa los datos de ejemplo.")
        return

    # Banner de detección
    detected_for_banner = detect_dataset_type(raw_df)
    selected_type = _render_detection_banner(detected_for_banner)

    # Si el usuario cambia el tipo manualmente, recalcular el mapeo y limpiar widgets
    if selected_type != st.session_state.get("dataset_type"):
        new_mapping = (
            guess_column_mapping(raw_df)
            if selected_type == "financiero"
            else _guess_mapping_for_type(raw_df, selected_type)
        )
        st.session_state.dataset_type = selected_type
        st.session_state.column_mapping = new_mapping
        st.session_state.clean_data = None
        _clear_mapping_widgets()
        _seed_mapping_widgets(selected_type, new_mapping)
        st.rerun()

    st.divider()

    # Vista previa
    with st.expander("Vista previa del archivo", expanded=False):
        st.caption(
            f"**{st.session_state.get('loaded_filename')}** — "
            f"{len(raw_df):,} filas × {len(raw_df.columns)} columnas"
        )
        st.dataframe(raw_df.head(30), use_container_width=True)

    # Mapeo de columnas
    mapping = _mapping_form(raw_df, selected_type)

    st.divider()

    # Botones de acción
    col_auto, col_manual = st.columns(2)

    with col_auto:
        if st.button(
            "▶ Procesar automáticamente",
            type="primary",
            use_container_width=True,
            help="Guarda el mapeo y ejecuta el ETL en un solo paso.",
            key="btn_auto_process",
        ):
            st.session_state.column_mapping = mapping
            st.session_state.dataset_type = selected_type
            st.session_state.auto_run_etl = True
            st.session_state.clean_data = None
            # Navegar a ETL usando el sistema de redirección de app.py
            st.session_state.page_to_redirect = "etl"
            st.rerun()

    with col_manual:
        if st.button(
            "Guardar mapeo →",
            use_container_width=True,
            help="Solo guarda el mapeo. Ve a ETL y limpieza para ejecutar después.",
            key="btn_save_mapping",
        ):
            st.session_state.column_mapping = mapping
            st.session_state.dataset_type = selected_type
            st.session_state.clean_data = None
            st.success("Mapeo guardado. Ve a **ETL y limpieza** en la barra lateral.")


# ──────────────────────────────────────────────────────────────────────────────
# Errores de carga
# ──────────────────────────────────────────────────────────────────────────────

def _show_upload_error(exc: Exception, filename: str) -> None:
    msg = str(exc).lower()
    st.error(f"No se pudo leer **{filename}**.")

    if "codec" in msg or "encoding" in msg or "unicode" in msg:
        st.warning(
            "**Problema de codificación.**  \n"
            "El archivo tiene caracteres especiales (tildes, ñ) en un formato inesperado.  \n"
            "**Solución:** Excel → Guardar como → CSV UTF-8 (con BOM)."
        )
    elif "excel" in msg or "openpyxl" in msg or "xlrd" in msg:
        st.warning(
            "**Problema con el archivo Excel.**  \n"
            "Puede estar dañado o protegido con contraseña.  \n"
            "**Solución:** Ábrelo en Excel y guárdalo como **.xlsx** o **CSV**."
        )
    elif "separator" in msg or "sep" in msg or "delimiter" in msg:
        st.warning(
            "**Separador no detectado.**  \n"
            "El CSV puede usar punto y coma (;) o tabulador.  \n"
            "**Solución:** Verifica el separador abriendo el CSV en un editor de texto."
        )
    elif "empty" in msg or "no columns" in msg:
        st.warning(
            "**Archivo vacío o sin columnas.**  \n"
            "**Solución:** Verifica que la primera fila tenga los nombres de columna."
        )
    else:
        st.warning(
            "**Sugerencias:**\n"
            "- Guarda como **CSV UTF-8** o **XLSX** e inténtalo de nuevo.\n"
            "- Verifica que el archivo no esté abierto en otro programa.\n"
            "- Asegúrate de que la primera fila tenga los encabezados."
        )
    with st.expander("Detalle técnico"):
        st.exception(exc)
