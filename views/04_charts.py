# -*- coding: utf-8 -*-
"""Vista de gráficas: financieras o genéricas según el tipo de dataset."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.charts.chart_builder import (
    category_bar_chart,
    cumulative_cashflow_chart,
    monthly_result_chart,
    type_donut_chart,
    weekday_chart,
)
from views._shared import filtered_dataset, require_clean_data


def render() -> None:
    st.title("📈 Gráficas")

    if not require_clean_data():
        return

    dataset_type = st.session_state.get("dataset_type", "financiero")
    df = filtered_dataset(st.session_state.clean_data, "charts")

    if df.empty:
        st.warning("Los filtros dejaron el análisis sin datos.")
        return

    if dataset_type == "financiero":
        _render_financial_charts(df)
    else:
        _render_generic_charts(df)


def _render_financial_charts(df: pd.DataFrame) -> None:
    tab1, tab2, tab3 = st.tabs(["Tendencia", "Categorías", "Distribución"])

    with tab1:
        st.plotly_chart(monthly_result_chart(df), use_container_width=True)
        st.plotly_chart(cumulative_cashflow_chart(df), use_container_width=True)

    with tab2:
        left, right = st.columns(2)
        with left:
            st.plotly_chart(category_bar_chart(df, tipo="egreso", limit=10), use_container_width=True)
        with right:
            st.plotly_chart(category_bar_chart(df, tipo="ingreso", limit=10), use_container_width=True)

    with tab3:
        left, right = st.columns(2)
        with left:
            st.plotly_chart(type_donut_chart(df), use_container_width=True)
        with right:
            st.plotly_chart(weekday_chart(df), use_container_width=True)


def _render_generic_charts(df: pd.DataFrame) -> None:
    """Gráficas automáticas para datasets no financieros."""
    visible_cols = [c for c in df.columns if not c.startswith("_")]
    num_cols = df[visible_cols].select_dtypes(include="number").columns.tolist()
    date_cols = [c for c in visible_cols if pd.api.types.is_datetime64_any_dtype(df[c])]
    cat_cols = [
        c for c in visible_cols
        if c not in num_cols and c not in date_cols and df[c].nunique() <= 30
    ]

    if not num_cols and not date_cols:
        st.info("No se encontraron columnas numéricas o de fecha para graficar. Verifica el ETL.")
        return

    tabs = []
    if num_cols:
        tabs.append("Distribuciones")
    if date_cols and num_cols:
        tabs.append("Tendencias")
    if cat_cols and num_cols:
        tabs.append("Por categoría")

    if not tabs:
        st.info("No hay suficientes columnas para generar gráficas automáticas.")
        return

    tab_objects = st.tabs(tabs)
    tab_idx = 0

    # Tab: Distribuciones de columnas numéricas
    if "Distribuciones" in tabs:
        with tab_objects[tab_idx]:
            col_select = st.selectbox("Columna a graficar", options=num_cols, key="chart_dist_col")
            fig = px.histogram(
                df,
                x=col_select,
                nbins=30,
                title=f"Distribución de {col_select.replace('_', ' ').title()}",
                color_discrete_sequence=["#14365D"],
            )
            fig.update_layout(bargap=0.05)
            st.plotly_chart(fig, use_container_width=True)

            if cat_cols:
                color_col = st.selectbox("Color por categoría (opcional)", options=["Ninguno"] + cat_cols,
                                          key="chart_dist_color")
                if color_col != "Ninguno":
                    fig2 = px.box(df, x=color_col, y=col_select,
                                  title=f"{col_select.replace('_', ' ').title()} por {color_col.replace('_', ' ').title()}")
                    st.plotly_chart(fig2, use_container_width=True)
        tab_idx += 1

    # Tab: Tendencias en el tiempo
    if "Tendencias" in tabs:
        with tab_objects[tab_idx]:
            date_col = st.selectbox("Columna de fecha", options=date_cols, key="chart_trend_date")
            y_col = st.selectbox("Valor a graficar", options=num_cols, key="chart_trend_y")

            trend_df = df[[date_col, y_col]].dropna().sort_values(date_col)
            fig = px.line(
                trend_df,
                x=date_col,
                y=y_col,
                title=f"{y_col.replace('_', ' ').title()} en el tiempo",
                color_discrete_sequence=["#14365D"],
            )
            st.plotly_chart(fig, use_container_width=True)
        tab_idx += 1

    # Tab: Por categoría
    if "Por categoría" in tabs:
        with tab_objects[tab_idx]:
            cat_col = st.selectbox("Agrupar por", options=cat_cols, key="chart_cat_col")
            val_col = st.selectbox("Valor a sumar", options=num_cols, key="chart_cat_val")

            agg_df = df.groupby(cat_col)[val_col].sum().reset_index()
            agg_df = agg_df.sort_values(val_col, ascending=False).head(15)

            fig = px.bar(
                agg_df,
                x=val_col,
                y=cat_col,
                orientation="h",
                title=f"Top {cat_col.replace('_', ' ').title()} por {val_col.replace('_', ' ').title()}",
                color_discrete_sequence=["#14365D"],
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

            # Donut de distribución
            fig2 = px.pie(
                agg_df,
                names=cat_col,
                values=val_col,
                hole=0.4,
                title=f"Proporción por {cat_col.replace('_', ' ').title()}",
            )
            st.plotly_chart(fig2, use_container_width=True)
