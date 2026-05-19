# -*- coding: utf-8 -*-
"""
Manejo del Estado de Sesión.

Streamlit es "olvidadizo": cada vez que haces clic en algo, vuelve a ejecutar todo el código.
Este archivo sirve para crear una "mochila" (session_state) donde guardamos los datos
importantes para que no se pierdan al navegar entre páginas.
"""

from __future__ import annotations

import streamlit as st

# Estos son los valores iniciales de nuestra "mochila"
DEFAULTS = {
    "raw_data": None,           # Los datos tal cual vienen del Excel/CSV
    "clean_data": None,         # Los datos después de pasar por la limpieza
    "loaded_filename": None,    # El nombre del archivo que subió el usuario
    "dataset_type": "financiero",  # Tipo detectado: financiero, ventas, rrhh, inventario, general
    "column_mapping": {},       # Cómo relacionamos las columnas del archivo con las del sistema
    "cleaning_log": [],         # Notas de qué se limpió o corrigió
    "rejected_rows": None,      # Filas que no pudimos procesar por errores
    "last_validation": None,    # Resultado de la última revisión de calidad
    "auto_run_etl": False,      # Si True, la página ETL ejecuta la limpieza automáticamente al cargar

    # IA (Gemini)
    "ai_chat_history": [],      # Lista de mensajes (user/assistant)
    "ai_last_proposal": None,   # Última propuesta (dict)
    "ai_preview_df": None,      # Preview del resultado propuesto (DataFrame)
    "ai_preview_chart": None,   # Spec de gráfica a renderizar (dict)
    "ai_last_compute": None,    # Último cálculo solicitado (dict)
    "ai_target": "clean",       # "raw" | "clean"
}


def init_session_state() -> None:
    """
    Inicializa la mochila con los valores por defecto si es que está vacía.
    Se llama siempre al arrancar la app.
    """
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)


def clear_data() -> None:
    """
    Vacía la mochila. Es como hacer un 'reset' de la aplicación
    sin tener que cerrar el navegador.
    """
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
