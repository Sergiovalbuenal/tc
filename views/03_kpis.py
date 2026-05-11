# -*- coding: utf-8 -*-
"""Vista de indicadores optimizada visualmente."""

from __future__ import annotations

import streamlit as st

from src.kpis.financial_kpis import account_summary, calculate_kpis, category_summary, monthly_summary
from src.kpis.formatters import money, percent
from views._shared import filtered_dataset, require_clean_data


def render() -> None:
    st.title("📌 Indicadores Clave de Rendimiento")
    st.markdown("#### Análisis profundo de salud financiera y eficiencia operativa.")

    if not require_clean_data():
        return

    df = filtered_dataset(st.session_state.clean_data, "kpis")
    if df.empty:
        st.warning("Los filtros dejaron el análisis sin datos.")
        return

    currency = df["moneda"].mode().iloc[0] if not df["moneda"].empty else "USD"
    symbol = "$" if currency in {"USD", "COP", "MXN", "CLP", "ARS"} else currency

    kpis = calculate_kpis(df)

    # Métricas Principales (Hero Row)
    st.markdown("### Resumen Financiero")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ingresos Totales", money(kpis["ingresos"], symbol))
    col2.metric("Egresos Totales", money(kpis["egresos"], symbol))
    
    # Delta para el resultado
    delta_val = kpis["delta_resultado_ultimo_mes"]
    col3.metric("Resultado Neto", money(kpis["resultado"], symbol), delta=money(delta_val, symbol))
    col4.metric("Margen Operativo", percent(kpis["margen"]))

    # Métricas Operativas
    st.markdown("<br>", unsafe_allow_html=True)
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Volumen Movimientos", f"{kpis['movimientos']:,}")
    col6.metric("Ticket Promedio", money(kpis["ticket_promedio"], symbol))
    col7.metric("Media Mensual", money(kpis["promedio_mensual_resultado"], symbol))
    col8.metric("Tasa de Ahorro", percent(kpis["tasa_ahorro"]))

    st.divider()

    # Análisis Detallado
    left, right = st.columns([3, 2])
    
    with left:
        st.subheader("Evolución Mensual")
        st.dataframe(
            monthly_summary(df), 
            use_container_width=True, 
            hide_index=True
        )
    
    with right:
        st.subheader("Hitos del Periodo")
        st.markdown(
            f"""
            <div style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0;">
                <div style="margin-bottom: 1rem;">
                    <small style="color: #64748b; text-transform: uppercase; font-weight: 600; font-size: 0.7rem;">Mayor Gasto en Categoría</small>
                    <div style="font-size: 1.2rem; font-weight: 700; color: #1e293b;">{kpis["categoria_mayor_gasto"] or "N/A"}</div>
                </div>
                <div style="display: flex; gap: 1rem;">
                    <div style="flex: 1;">
                        <small style="color: #64748b; text-transform: uppercase; font-weight: 600; font-size: 0.7rem;">Mejor Mes</small>
                        <div style="font-weight: 600; color: #10b981;">{kpis['mejor_mes'] or 'N/A'}</div>
                    </div>
                    <div style="flex: 1;">
                        <small style="color: #64748b; text-transform: uppercase; font-weight: 600; font-size: 0.7rem;">Peor Mes</small>
                        <div style="font-weight: 600; color: #ef4444;">{kpis['peor_mes'] or 'N/A'}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Desglose por Dimensiones")
    tab1, tab2, tab3 = st.tabs(["📊 Egresos", "💰 Ingresos", "🏦 Cuentas"])
    
    with tab1:
        st.dataframe(category_summary(df, tipo="egreso"), use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(category_summary(df, tipo="ingreso"), use_container_width=True, hide_index=True)
    with tab3:
        st.dataframe(account_summary(df), use_container_width=True, hide_index=True)

