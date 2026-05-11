# -*- coding: utf-8 -*-
"""Exportaciones del dashboard."""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import plotly.io as pio

from src.kpis.financial_kpis import account_summary, calculate_kpis, category_summary, monthly_summary
from src.charts.chart_builder import (
    category_bar_chart,
    cumulative_cashflow_chart,
    monthly_result_chart,
    type_donut_chart,
 )


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV en UTF-8 con BOM para que Excel lo abra bien."""
    return df.to_csv(index=False).encode("utf-8-sig")


def build_excel_report(df: pd.DataFrame, cleaning_log: list[str] | None = None) -> bytes:
    """Genera un Excel con datos, KPIs y resúmenes."""
    output = io.BytesIO()
    cleaning_log = cleaning_log or []

    kpis = calculate_kpis(df)
    monthly = monthly_summary(df)
    expenses = category_summary(df, tipo="egreso")
    incomes = category_summary(df, tipo="ingreso")
    accounts = account_summary(df)

    kpi_df = pd.DataFrame(
        [
            {"indicador": key, "valor": value}
            for key, value in kpis.items()
        ]
    )

    log_df = pd.DataFrame({"paso": cleaning_log}) if cleaning_log else pd.DataFrame({"paso": ["Sin observaciones"]})

    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as writer:
        df.to_excel(writer, sheet_name="datos_limpios", index=False)
        kpi_df.to_excel(writer, sheet_name="kpis", index=False)
        monthly.to_excel(writer, sheet_name="mensual", index=False)
        expenses.to_excel(writer, sheet_name="gastos_categoria", index=False)
        incomes.to_excel(writer, sheet_name="ingresos_categoria", index=False)
        accounts.to_excel(writer, sheet_name="cuentas", index=False)
        log_df.to_excel(writer, sheet_name="log_limpieza", index=False)

        workbook = writer.book
        money_format = workbook.add_format({"num_format": "#,##0.00"})
        date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
        header_format = workbook.add_format({"bold": True, "bg_color": "#EAF2F8"})

        for sheet_name, worksheet in writer.sheets.items():
            worksheet.freeze_panes(1, 0)
            worksheet.set_row(0, None, header_format)
            worksheet.set_column(0, 0, 18)

            if sheet_name == "datos_limpios":
                worksheet.set_column("A:A", 12, date_format)
                worksheet.set_column("B:H", 18)
                worksheet.set_column("J:K", 15, money_format)
            else:
                worksheet.set_column(0, 8, 20, money_format)

    output.seek(0)
    return output.read()


def build_text_report(df: pd.DataFrame, cleaning_log: list[str] | None = None) -> str:
    """Reporte corto en texto/Markdown."""
    kpis = calculate_kpis(df)
    cleaning_log = cleaning_log or []
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# Reporte financiero",
        "",
        f"Generado: {generated_at}",
        "",
        "## Resumen",
        f"- Ingresos: {kpis['ingresos']:,.2f}",
        f"- Egresos: {kpis['egresos']:,.2f}",
        f"- Resultado: {kpis['resultado']:,.2f}",
        f"- Margen: {kpis['margen']:.2%}",
        f"- Movimientos: {kpis['movimientos']}",
        "",
        "## Limpieza aplicada",
    ]

    if cleaning_log:
        lines.extend([f"- {item}" for item in cleaning_log])
    else:
        lines.append("- Sin observaciones.")

    return "\n".join(lines).encode("utf-8").decode("utf-8")


def build_generic_markdown_report(df: pd.DataFrame, profile: dict) -> str:
    """Resumen legible para cualquier tabla (sin columnas financieras estándar)."""
    from datetime import datetime

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Resumen del archivo cargado",
        "",
        f"Generado: {stamp}",
        "",
        f"- Filas: **{profile.get('rows', 0)}**",
        f"- Columnas: **{profile.get('column_count', len(df.columns))}**",
        f"- Tipo de esquema: **{profile.get('schema_kind', 'generic')}**",
        "",
        "## Columnas",
        "",
        ", ".join(f"`{c}`" for c in (profile.get("columns") or [])[:80]),
        "",
    ]
    if profile.get("numeric_columns"):
        lines.extend(["## Columnas con valores numéricos detectados", ""])
        lines.append(", ".join(f"`{c}`" for c in profile["numeric_columns"]))
        lines.append("")
    if profile.get("numeric_stats"):
        lines.append("## Estadísticas (numéricas)")
        lines.append("")
        for col, stt in list(profile["numeric_stats"].items())[:15]:
            lines.append(f"### `{col}`")
            lines.append(
                f"- min: {stt.get('min')} | max: {stt.get('max')} | media: {stt.get('mean')} | suma: {stt.get('sum')} | n: {stt.get('count')}"
            )
            lines.append("")
    if profile.get("text_summaries"):
        lines.append("## Texto / categorías (top valores)")
        lines.append("")
        for col, info in list(profile["text_summaries"].items())[:10]:
            lines.append(f"### `{col}` (≈{info.get('unique_approx')} valores distintos)")
            for row in info.get("top_values", [])[:5]:
                lines.append(f"- `{row.get('value')}`: {row.get('count')}")
            lines.append("")
    if profile.get("date_like_columns"):
        lines.append("## Columnas con formato de fecha probable")
        lines.append("")
        lines.append(", ".join(f"`{c}`" for c in profile["date_like_columns"]))
        lines.append("")
    lines.append("## Muestra (primeras filas)")
    lines.append("")
    lines.append("Ver el archivo CSV exportado o la vista previa en la app para el detalle completo.")
    return "\n".join(lines)


def build_ai_markdown_report(df: pd.DataFrame, ai_summary: str, cleaning_log: list[str] | None = None) -> str:
    """Reporte extendido (Markdown) incorporando un resumen IA."""
    base = build_text_report(df, cleaning_log)
    extra = [
        "",
        "## Resumen IA",
        ai_summary.strip() if ai_summary else "Sin resumen adicional.",
        "",
    ]
    return base + "\n" + "\n".join(extra)


def build_dashboard_html(df: pd.DataFrame, title: str = "Dashboard financiero") -> bytes:
    """HTML auto-contenido con KPIs y gráficas Plotly."""
    kpis = calculate_kpis(df)
    figs = [
        monthly_result_chart(df),
        cumulative_cashflow_chart(df),
        category_bar_chart(df, tipo="egreso", limit=10),
        category_bar_chart(df, tipo="ingreso", limit=10),
        type_donut_chart(df),
    ]

    fig_html = "\n".join(
        [
            pio.to_html(
                fig,
                include_plotlyjs="inline" if idx == 0 else False,
                full_html=False,
                config={"displayModeBar": False},
            )
            for idx, fig in enumerate(figs)
        ]
    )

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"""
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
      .kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 16px 0 24px; }}
      .kpi {{ border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px 14px; background: #fff; }}
      .kpi .label {{ color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
      .kpi .value {{ font-weight: 800; font-size: 18px; margin-top: 6px; }}
      .section {{ margin: 18px 0; }}
      .muted {{ color: #6b7280; }}
      @media (max-width: 900px) {{ .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
    </style>
  </head>
  <body>
    <h1 style="margin:0;">{title}</h1>
    <div class="muted">Generado: {stamp}</div>

    <div class="kpis">
      <div class="kpi"><div class="label">Ingresos</div><div class="value">{kpis['ingresos']:,.2f}</div></div>
      <div class="kpi"><div class="label">Egresos</div><div class="value">{kpis['egresos']:,.2f}</div></div>
      <div class="kpi"><div class="label">Resultado</div><div class="value">{kpis['resultado']:,.2f}</div></div>
      <div class="kpi"><div class="label">Margen</div><div class="value">{kpis['margen']:.2%}</div></div>
    </div>

    <div class="section">
      {fig_html}
    </div>
  </body>
</html>
"""
    return html.encode("utf-8")
