# -*- coding: utf-8 -*-
"""Vista de exportación."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.utils.exporters import build_excel_report, build_text_report, dataframe_to_csv_bytes
from views._shared import filtered_dataset, require_clean_data


def render() -> None:
    st.title("⬇️ Exportar")

    if not require_clean_data():
        return

    df = filtered_dataset(st.session_state.clean_data, "export")
    if df.empty:
        st.warning("Los filtros dejaron la exportación sin datos.")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    cleaning_log = st.session_state.get("cleaning_log", [])

    st.write("Descarga el dataset limpio o un reporte con KPIs y tablas auxiliares.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "Descargar CSV limpio",
            data=dataframe_to_csv_bytes(df),
            file_name=f"datos_limpios_{stamp}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col2:
        st.download_button(
            "Descargar Excel completo",
            data=build_excel_report(df, cleaning_log),
            file_name=f"reporte_financiero_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with col3:
        st.download_button(
            "Descargar reporte Markdown",
            data=build_text_report(df, cleaning_log).encode("utf-8"),
            file_name=f"reporte_financiero_{stamp}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.subheader("Datos incluidos")
    st.dataframe(df.head(100), use_container_width=True)
