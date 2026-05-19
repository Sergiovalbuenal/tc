# -*- coding: utf-8 -*-
"""Vista de indicadores: KPIs financieros o perfil de datos según el tipo cargado."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import DATASET_SCHEMAS
from src.kpis.financial_kpis import account_summary, calculate_kpis, category_summary, monthly_summary
from src.kpis.formatters import money, percent
from views._shared import filtered_dataset, require_clean_data


def render() -> None:
    dataset_type = st.session_state.get("dataset_type", "financiero")

    if not require_clean_data():
        return

    if dataset_type == "financiero":
        _render_financial_kpis()
    else:
        _render_data_profile()


# ──────────────────────────────────────────────────────────────────────────────
# KPIs financieros (comportamiento original)
# ──────────────────────────────────────────────────────────────────────────────

def _render_financial_kpis() -> None:
    st.title("📌 Indicadores Clave de Rendimiento")
    st.markdown("#### Análisis profundo de salud financiera y eficiencia operativa.")

    df = filtered_dataset(st.session_state.clean_data, "kpis")
    if df.empty:
        st.warning("Los filtros dejaron el análisis sin datos.")
        return

    currency = df["moneda"].mode().iloc[0] if not df["moneda"].empty else "USD"
    symbol = "$" if currency in {"USD", "COP", "MXN", "CLP", "ARS"} else currency

    kpis = calculate_kpis(df)

    st.markdown("### Resumen Financiero")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ingresos Totales", money(kpis["ingresos"], symbol))
    col2.metric("Egresos Totales", money(kpis["egresos"], symbol))
    delta_val = kpis["delta_resultado_ultimo_mes"]
    col3.metric("Resultado Neto", money(kpis["resultado"], symbol), delta=money(delta_val, symbol))
    col4.metric("Margen Operativo", percent(kpis["margen"]))

    st.markdown("<br>", unsafe_allow_html=True)
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Volumen Movimientos", f"{kpis['movimientos']:,}")
    col6.metric("Ticket Promedio", money(kpis["ticket_promedio"], symbol))
    col7.metric("Media Mensual", money(kpis["promedio_mensual_resultado"], symbol))
    col8.metric("Tasa de Ahorro", percent(kpis["tasa_ahorro"]))

    st.divider()

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Evolución Mensual")
        st.dataframe(monthly_summary(df), use_container_width=True, hide_index=True)
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


# ──────────────────────────────────────────────────────────────────────────────
# Perfil de datos para tipos no financieros
# ──────────────────────────────────────────────────────────────────────────────

def _render_data_profile() -> None:
    dataset_type = st.session_state.get("dataset_type", "general")
    schema = DATASET_SCHEMAS.get(dataset_type, DATASET_SCHEMAS["general"])

    st.title(f"{schema['icon']} Perfil de Datos — {schema['label']}")
    st.markdown(f"_{schema['description']}_")

    df = filtered_dataset(st.session_state.clean_data, "kpis")
    if df.empty:
        st.warning("Los filtros dejaron el análisis sin datos.")
        return

    # Métricas generales
    visible_cols = [c for c in df.columns if not c.startswith("_")]
    num_cols = df[visible_cols].select_dtypes(include="number").columns.tolist()
    date_cols = [c for c in visible_cols if pd.api.types.is_datetime64_any_dtype(df[c])]
    cat_cols = [c for c in visible_cols if c not in num_cols and c not in date_cols]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de filas", f"{len(df):,}")
    c2.metric("Columnas", f"{len(visible_cols):,}")
    c3.metric("Cols. numéricas", f"{len(num_cols):,}")
    c4.metric("Cols. de fecha", f"{len(date_cols):,}")

    st.divider()

    # Estadísticas numéricas
    if num_cols:
        st.subheader("📊 Estadísticas de columnas numéricas")
        stats = df[num_cols].describe().T.reset_index()
        stats.columns = ["Columna", "Conteo", "Media", "Desv. Est.", "Mínimo", "Q25%", "Mediana", "Q75%", "Máximo"]
        st.dataframe(stats.round(2), use_container_width=True, hide_index=True)

    # Resumen de columnas de texto / categoría
    if cat_cols:
        st.subheader("🏷️ Valores más frecuentes por columna")
        cols_per_row = 3
        rows = [cat_cols[i:i + cols_per_row] for i in range(0, len(cat_cols), cols_per_row)]
        for row in rows:
            display_cols = st.columns(len(row))
            for col_widget, col_name in zip(display_cols, row):
                with col_widget:
                    top = df[col_name].value_counts().head(5)
                    st.markdown(f"**{col_name.replace('_', ' ').title()}**")
                    for val, cnt in top.items():
                        pct = cnt / len(df) * 100
                        st.write(f"- {val}: {cnt:,} ({pct:.1f}%)")

    # Calidad de datos
    st.subheader("🔍 Calidad de datos")
    null_info = []
    for col in visible_cols:
        nulls = df[col].isna().sum()
        if nulls > 0:
            null_info.append({
                "Columna": col,
                "Valores vacíos": nulls,
                "% vacío": f"{nulls / len(df) * 100:.1f}%",
            })

    if null_info:
        st.dataframe(pd.DataFrame(null_info), use_container_width=True, hide_index=True)
    else:
        st.success("✅ No hay valores vacíos en el dataset limpio.")

    # Rango de fechas
    if date_cols:
        st.subheader("📅 Rango de fechas")
        for dcol in date_cols:
            min_d = df[dcol].min()
            max_d = df[dcol].max()
            span = (max_d - min_d).days if pd.notna(min_d) and pd.notna(max_d) else 0
            st.write(f"**{dcol}**: {min_d.date()} → {max_d.date()} ({span} días)")
