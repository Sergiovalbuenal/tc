# -*- coding: utf-8 -*-
"""Cálculo de indicadores financieros."""

from __future__ import annotations

import numpy as np
import pandas as pd


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Resumen mensual con ingresos, egresos y resultado."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["mes", "ingresos", "egresos", "ajustes", "resultado"])

    work = df.copy()
    work["mes"] = pd.to_datetime(work["fecha"]).dt.to_period("M").dt.to_timestamp()

    grouped = (
        work.pivot_table(
            index="mes",
            columns="tipo_norm",
            values="monto_abs",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    for column in ["ingreso", "egreso", "ajuste"]:
        if column not in grouped:
            grouped[column] = 0.0

    # Para ajustes usamos el monto firmado, porque puede sumar o restar.
    adjustments = (
        work[work["tipo_norm"].eq("ajuste")]
        .groupby("mes", as_index=False)["monto_signed"]
        .sum()
        .rename(columns={"monto_signed": "ajustes_signed"})
    )

    grouped = grouped.merge(adjustments, on="mes", how="left")
    grouped["ajustes_signed"] = grouped["ajustes_signed"].fillna(0)

    grouped = grouped.rename(columns={"ingreso": "ingresos", "egreso": "egresos", "ajuste": "ajustes_abs"})
    grouped["ajustes"] = grouped["ajustes_signed"]
    grouped["resultado"] = grouped["ingresos"] - grouped["egresos"] + grouped["ajustes"]

    return grouped[["mes", "ingresos", "egresos", "ajustes", "resultado"]].sort_values("mes")


def category_summary(df: pd.DataFrame, tipo: str = "egreso", limit: int | None = None) -> pd.DataFrame:
    """Totales por categoría para ingresos o egresos."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["categoria", "total", "movimientos", "participacion"])

    work = df[df["tipo_norm"].eq(tipo)].copy()
    if work.empty:
        return pd.DataFrame(columns=["categoria", "total", "movimientos", "participacion"])

    summary = (
        work.groupby("categoria", as_index=False)
        .agg(total=("monto_abs", "sum"), movimientos=("monto_abs", "size"))
        .sort_values("total", ascending=False)
    )
    grand_total = summary["total"].sum()
    summary["participacion"] = np.where(grand_total > 0, summary["total"] / grand_total, 0)

    if limit:
        summary = summary.head(limit)

    return summary.reset_index(drop=True)


def account_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Resultado por cuenta o banco."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["cuenta", "ingresos", "egresos", "resultado"])

    grouped = (
        df.pivot_table(
            index="cuenta",
            columns="tipo_norm",
            values="monto_abs",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    for column in ["ingreso", "egreso"]:
        if column not in grouped:
            grouped[column] = 0.0

    signed = df.groupby("cuenta", as_index=False)["monto_signed"].sum().rename(columns={"monto_signed": "resultado"})
    grouped = grouped.merge(signed, on="cuenta", how="left")
    grouped = grouped.rename(columns={"ingreso": "ingresos", "egreso": "egresos"})

    return grouped[["cuenta", "ingresos", "egresos", "resultado"]].sort_values("resultado", ascending=False)


def calculate_kpis(df: pd.DataFrame) -> dict[str, float | int | str | None]:
    """Devuelve las métricas principales del dashboard."""
    if df is None or df.empty:
        return {
            "ingresos": 0.0,
            "egresos": 0.0,
            "ajustes": 0.0,
            "resultado": 0.0,
            "margen": 0.0,
            "tasa_ahorro": 0.0,
            "movimientos": 0,
            "ticket_promedio": 0.0,
            "promedio_mensual_resultado": 0.0,
            "mejor_mes": None,
            "peor_mes": None,
            "categoria_mayor_gasto": None,
            "delta_resultado_ultimo_mes": 0.0,
        }

    ingresos = float(df.loc[df["tipo_norm"].eq("ingreso"), "monto_abs"].sum())
    egresos = float(df.loc[df["tipo_norm"].eq("egreso"), "monto_abs"].sum())
    ajustes = float(df.loc[df["tipo_norm"].eq("ajuste"), "monto_signed"].sum())
    resultado = ingresos - egresos + ajustes

    monthly = monthly_summary(df)
    promedio_mensual = float(monthly["resultado"].mean()) if not monthly.empty else 0.0

    if len(monthly) >= 2:
        delta_last = float(monthly["resultado"].iloc[-1] - monthly["resultado"].iloc[-2])
    else:
        delta_last = 0.0

    expenses = category_summary(df, tipo="egreso", limit=1)
    top_expense = None if expenses.empty else str(expenses.iloc[0]["categoria"])

    best_month = None
    worst_month = None
    if not monthly.empty:
        best_month = monthly.loc[monthly["resultado"].idxmax(), "mes"].strftime("%Y-%m")
        worst_month = monthly.loc[monthly["resultado"].idxmin(), "mes"].strftime("%Y-%m")

    return {
        "ingresos": ingresos,
        "egresos": egresos,
        "ajustes": ajustes,
        "resultado": float(resultado),
        "margen": float(resultado / ingresos) if ingresos else 0.0,
        "tasa_ahorro": float(max(resultado, 0) / ingresos) if ingresos else 0.0,
        "movimientos": int(len(df)),
        "ticket_promedio": float(df["monto_abs"].mean()) if not df.empty else 0.0,
        "promedio_mensual_resultado": promedio_mensual,
        "mejor_mes": best_month,
        "peor_mes": worst_month,
        "categoria_mayor_gasto": top_expense,
        "delta_resultado_ultimo_mes": delta_last,
    }
