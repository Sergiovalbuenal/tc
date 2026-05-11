# -*- coding: utf-8 -*-
"""Vista de gráficas."""

from __future__ import annotations

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

    df = filtered_dataset(st.session_state.clean_data, "charts")
    if df.empty:
        st.warning("Los filtros dejaron el análisis sin datos.")
        return

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
