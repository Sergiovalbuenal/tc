# -*- coding: utf-8 -*-
"""
Desde aquí controlamos qué página se muestra y cómo se ve todo el dashboard.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import streamlit as st

# Configuración inicial: DEBE ser lo primero que Streamlit ejecute
st.set_page_config(
    page_title="Tablero de Control",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Configuramos las rutas base para que Python sepa dónde buscar nuestros archivos
ROOT_DIR = Path(__file__).resolve().parent
VIEWS_DIR = ROOT_DIR / "views"

# Agregamos la raíz al "path" para que podamos importar cosas desde la carpeta 'src'
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Importamos la lógica que maneja los datos guardados en la memoria del navegador
from src.state import init_session_state  # noqa: E402

# Aquí definimos todas las páginas que tiene nuestro sistema
# Si quieres agregar una página nueva, solo tienes que añadirla a este diccionario
PAGES = {
    "home": {
        "label": "Inicio",
        "icon": "🏠",
        "file": VIEWS_DIR / "00_home.py",
    },
    "upload": {
        "label": "Cargar datos",
        "icon": "📁",
        "file": VIEWS_DIR / "01_upload.py",
    },
    "etl": {
        "label": "ETL y limpieza",
        "icon": "🧹",
        "file": VIEWS_DIR / "02_etl.py",
    },
    "kpis": {
        "label": "KPIs",
        "icon": "📌",
        "file": VIEWS_DIR / "03_kpis.py",
    },
    "charts": {
        "label": "Gráficas",
        "icon": "📈",
        "file": VIEWS_DIR / "04_charts.py",
    },
    "export": {
        "label": "Exportar",
        "icon": "⬇️",
        "file": VIEWS_DIR / "05_export.py",
    },
    "ai": {
        "label": "Asistente IA",
        "icon": "🤖",
        "file": VIEWS_DIR / "06_ai_assistant.py",
    },
}


def load_css() -> None:
    """
    Lee nuestro archivo de estilos personalizados (CSS) y los aplica a Streamlit.
    Esto es lo que hace que el dashboard se vea profesional.
    """
    css_path = ROOT_DIR / "assets" / "styles.css"
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def load_view(view_path: Path) -> ModuleType:
    """
    Esta función es mágica: carga un archivo de Python como si fuera un módulo.
    La usamos para cargar cada página del dashboard de forma dinámica sin errores de Windows.
    """
    if not view_path.exists():
        raise FileNotFoundError(f"No encontré la vista: {view_path}")

    module_name = f"dashboard_view_{view_path.stem.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, view_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"No pude preparar la vista: {view_path.name}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_sidebar() -> str:
    """
    Dibuja el menú de la izquierda y nos dice qué página eligió el usuario.
    También muestra si ya cargamos datos o no.
    """
    # Logo y título del sidebar
    st.sidebar.markdown(
        """
        <div class="brand-box">
            <div class="brand-icon">📊</div>
            <div>
                <div class="brand-title">Tablero de Control</div>
                <div class="brand-subtitle">Análisis Financiero</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Indicadores de estado: ¿Hay datos cargados?
    raw_state = "✅ cargados" if st.session_state.get("raw_data") is not None else "pendientes"
    clean_state = "✅ listos" if st.session_state.get("clean_data") is not None else "pendientes"

    st.sidebar.caption(f"Datos crudos: {raw_state}")
    st.sidebar.caption(f"Datos limpios: {clean_state}")

    # Creamos las etiquetas para el menú de radio
    labels_by_key = {
        key: f"{page['icon']} {page['label']}"
        for key, page in PAGES.items()
    }

    # El menú de navegación principal
    selected = st.sidebar.radio(
        "Navegación",
        options=list(PAGES.keys()),
        format_func=lambda key: labels_by_key[key],
        label_visibility="collapsed",
        key="selected_page",
    )

    return selected


def main() -> None:
    """
    Función principal, donde se inicia la app
    """
    # 1. Inicio
    init_session_state()
    load_css()

    # 2. Manejamos redirecciones automáticas
    if st.session_state.get("page_to_redirect"):
        st.session_state.selected_page = st.session_state.pop("page_to_redirect")

    # 3. Dibujamos el menú y vemos qué página toca mostrar
    selected_page = render_sidebar()
    page_info = PAGES[selected_page]

    # 4. Cargamos y mostramos el contenido de la página elegida
    try:
        view = load_view(page_info["file"])
        if not hasattr(view, "render"):
            raise AttributeError(f"La vista {page_info['file'].name} no tiene función render().")
        view.render()
    except Exception as exc:
        # Si algo falla, mostramos un error pero con detalles técnicos ocultos
        st.error("Algo falló al cargar esta sección. Revisa el detalle abajo.")
        with st.expander("Detalle técnico para Sergio"):
            st.exception(exc)

    # 5. Pie de página  (siempre visible)
    st.markdown("---")
    st.markdown(
        """
        <div class="main-footer">
            <div class="visually-hidden">
                <div style="font-weight: 700; color: var(--primary);">Universidad Compensar</div>
                <div style="font-size: 0.9rem; color: var(--text-muted);">Desarrollado por <b>Sergio Valbuena</b></div>
                <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em;">Ingeniería de Sistemas</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# Si ejecutamos este archivo directamente, se inicia la app
if __name__ == "__main__":
    main()
