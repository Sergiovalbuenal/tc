# -*- coding: utf-8 -*-
"""
Esta es la página de bienvenida (Landing Page).
Su objetivo es dar una buena primera impresión y explicar cómo usar el sistema.
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """
    Dibuja todo el contenido de la página de inicio.
    """
    # Título principal y subtítulo amigable
    st.title("Bienvenido al Tablero de Control")
    st.markdown("#### Inteligencia financiera y análisis operativo de alta precisión.")

    # Tarjeta de bienvenida (Hero Section) con un degradado en el CSS
    st.markdown(
        """
        <div class="hero-card">
            <h1>Potencia tu gestión financiera</h1>
            <p>
                Transforma datos crudos de CSV y Excel en decisiones estratégicas. 
                Nuestra plataforma procesa, limpia y visualiza tus movimientos con 
                tecnología de punta, garantizando integridad y rapidez en cada reporte.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### El Flujo de Trabajo")
    
    # Explicamos los 3 pasos principales del dashboard en 3 columnas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(
            """
            <div style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; height: 100%;">
                <h2 style="margin:0; font-size: 2.5rem;">📁</h2>
                <h3 style="margin-top: 0.5rem;">1. Carga Inteligente</h3>
                <p style="color: #64748b; font-size: 0.9rem;">
                    Importación robusta de archivos con detección automática de columnas. 
                    Soporta múltiples formatos y encodings sin errores.
                </p>
            </div>
            """, unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; height: 100%;">
                <h2 style="margin:0; font-size: 2.5rem;">🧹</h2>
                <h3 style="margin-top: 0.5rem;">2. ETL & Limpieza</h3>
                <p style="color: #64748b; font-size: 0.9rem;">
                    Mapeo flexible, corrección de fechas, estandarización de montos y 
                    validación de integridad de datos en tiempo real.
                </p>
            </div>
            """, unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; height: 100%;">
                <h2 style="margin:0; font-size: 2.5rem;">📈</h2>
                <h3 style="margin-top: 0.5rem;">3. Análisis & KPIs</h3>
                <p style="color: #64748b; font-size: 0.9rem;">
                    Visualizaciones dinámicas con Plotly y KPIs financieros clave. 
                    Exportación profesional a múltiples formatos.
                </p>
            </div>
            """, unsafe_allow_html=True
        )

    # Espacio estético
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Sección de "Llamada a la acción" para guiar al usuario al siguiente paso
    _, c2, _ = st.columns([1, 2, 1])
    
    with c2:
        st.markdown(
            """
            <div style="background: #f1f5f9; padding: 1.5rem; border-radius: 12px; border-left: 4px solid #4f46e5;">
                <h4 style="margin-top:0; text-align: center;">¿Listo para comenzar?</h4>
                <p style="font-size: 0.85rem; color: #475569; text-align: center;">
                    Dirígete a la sección de carga para importar tus primeros movimientos.
                </p>
            </div>
            """, unsafe_allow_html=True
        )
        # Este botón usa el sistema de redirección segura que creamos para app.py
        if st.button("Ir a Cargar Datos", type="primary", use_container_width=True):
            st.session_state.page_to_redirect = "upload"
            st.rerun()


