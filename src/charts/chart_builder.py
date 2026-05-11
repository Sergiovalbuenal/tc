# -*- coding: utf-8 -*-
"""Gráficas del dashboard.

Separamos las figuras de las páginas para que la vista se mantenga limpia.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.kpis.financial_kpis import category_summary, monthly_summary


DEFAULT_TEMPLATE = "plotly_white"


def empty_figure(message: str = "No hay datos para graficar") -> go.Figure:
    """Figura vacía con un mensaje claro."""
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, x=0.5, y=0.5)
    fig.update_layout(template=DEFAULT_TEMPLATE, height=360)
    return fig


def monthly_result_chart(df: pd.DataFrame) -> go.Figure:
    monthly = monthly_summary(df)
    if monthly.empty:
        return empty_figure()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=monthly["mes"], y=monthly["ingresos"], name="Ingresos"))
    fig.add_trace(go.Bar(x=monthly["mes"], y=monthly["egresos"], name="Egresos"))
    fig.add_trace(go.Scatter(x=monthly["mes"], y=monthly["resultado"], mode="lines+markers", name="Resultado"))

    fig.update_layout(
        title="Ingresos, egresos y resultado mensual",
        barmode="group",
        template=DEFAULT_TEMPLATE,
        hovermode="x unified",
        height=430,
        legend_title_text="",
    )
    fig.update_yaxes(title="Monto")
    fig.update_xaxes(title="")
    return fig


def cumulative_cashflow_chart(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        return empty_figure()

    daily = (
        df.groupby("fecha", as_index=False)["monto_signed"]
        .sum()
        .sort_values("fecha")
    )
    daily["flujo_acumulado"] = daily["monto_signed"].cumsum()

    fig = px.area(
        daily,
        x="fecha",
        y="flujo_acumulado",
        title="Flujo acumulado",
        template=DEFAULT_TEMPLATE,
    )
    fig.update_layout(height=420)
    fig.update_xaxes(title="")
    fig.update_yaxes(title="Resultado acumulado")
    return fig


def category_bar_chart(df: pd.DataFrame, tipo: str = "egreso", limit: int = 10) -> go.Figure:
    summary = category_summary(df, tipo=tipo, limit=limit)
    if summary.empty:
        return empty_figure("No hay categorías para mostrar")

    title_tipo = "egresos" if tipo == "egreso" else "ingresos"
    fig = px.bar(
        summary.sort_values("total"),
        x="total",
        y="categoria",
        orientation="h",
        text="movimientos",
        title=f"Top {min(limit, len(summary))} categorías por {title_tipo}",
        template=DEFAULT_TEMPLATE,
    )
    fig.update_layout(height=460)
    fig.update_xaxes(title="Total")
    fig.update_yaxes(title="")
    return fig


def type_donut_chart(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        return empty_figure()

    summary = (
        df.groupby("tipo_norm", as_index=False)["monto_abs"]
        .sum()
        .sort_values("monto_abs", ascending=False)
    )

    fig = px.pie(
        summary,
        names="tipo_norm",
        values="monto_abs",
        hole=0.55,
        title="Distribución por tipo de movimiento",
        template=DEFAULT_TEMPLATE,
    )
    fig.update_layout(height=420)
    return fig


def weekday_chart(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        return empty_figure()

    work = df.copy()
    work["dia_num"] = pd.to_datetime(work["fecha"]).dt.weekday
    work["dia"] = pd.to_datetime(work["fecha"]).dt.day_name()

    summary = (
        work.groupby(["dia_num", "dia"], as_index=False)["monto_abs"]
        .sum()
        .sort_values("dia_num")
    )

    fig = px.bar(
        summary,
        x="dia",
        y="monto_abs",
        title="Actividad por día de la semana",
        template=DEFAULT_TEMPLATE,
    )
    fig.update_layout(height=360)
    fig.update_xaxes(title="")
    fig.update_yaxes(title="Monto")
    return fig
