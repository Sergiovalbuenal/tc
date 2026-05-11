from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.etl.pipeline import filter_data
from src.charts.chart_builder import (
    category_bar_chart,
    cumulative_cashflow_chart,
    monthly_result_chart,
    type_donut_chart,
    weekday_chart,
)

FINANCIAL_FILTER_COLS = {"fecha", "moneda", "categoria", "cuenta"}


@dataclass(frozen=True)
class AiProposal:
    kind: str  # "filter" | "transform" | "chart"
    summary: str
    spec: dict[str, Any]


def is_financial_schema(df: pd.DataFrame) -> bool:
    """Dataset ya normalizado (ETL) con columnas del tablero financiero."""
    need = {"fecha", "tipo_norm", "monto_abs", "monto_signed", "categoria", "cuenta"}
    return df is not None and not df.empty and need.issubset(set(df.columns))


def _truncate_cell(val: Any, max_len: int = 240) -> Any:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return val
    s = str(val)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return val


def dataset_profile(df: pd.DataFrame, *, max_rows_preview: int = 20) -> dict[str, Any]:
    if df is None or df.empty:
        return {"empty": True}

    def _safe_value(v: Any) -> Any:
        if isinstance(v, (np.integer, np.floating)):
            if isinstance(v, np.floating) and (np.isnan(v) or np.isinf(v)):
                return None
            return v.item()
        if isinstance(v, (pd.Timestamp, pd.Timedelta)):
            return str(v)
        return v

    cols = list(df.columns)
    schema_kind = "financial" if is_financial_schema(df) else "generic"

    head_df = df.head(max_rows_preview).copy()
    for c in head_df.columns:
        if head_df[c].dtype == object:
            head_df[c] = head_df[c].map(lambda x: _truncate_cell(x))

    profile: dict[str, Any] = {
        "empty": False,
        "schema_kind": schema_kind,
        "rows": int(len(df)),
        "columns": cols,
        "column_count": len(cols),
        "dtypes": {c: str(df[c].dtype) for c in cols[:120]},
        "head": head_df.to_dict(orient="records"),
    }
    if len(cols) > 120:
        profile["dtypes_note"] = f"Solo se listan dtypes de las primeras 120 columnas (total {len(cols)})."

    if "fecha" in df.columns:
        dates = pd.to_datetime(df["fecha"], errors="coerce")
        profile["fecha_min"] = _safe_value(dates.min())
        profile["fecha_max"] = _safe_value(dates.max())

    for col in ("moneda", "categoria", "cuenta", "tipo"):
        if col in df.columns:
            vals = df[col].dropna().astype(str)
            profile[f"{col}_unique_top"] = list(vals.value_counts().head(10).index)

    for col in ("monto", "valor"):
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            profile[f"{col}_sum"] = _safe_value(s.sum())
            profile[f"{col}_mean"] = _safe_value(s.mean())

    # --- Perfil genérico (cualquier Excel sin fecha/monto estándar) ---
    numeric_cols: list[str] = []
    numeric_stats: dict[str, dict[str, Any]] = {}
    for c in cols[:80]:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().sum() == 0:
            continue
        numeric_cols.append(c)
        numeric_stats[c] = {
            "count": int(s.notna().sum()),
            "min": _safe_value(s.min()),
            "max": _safe_value(s.max()),
            "mean": _safe_value(s.mean()),
            "sum": _safe_value(s.sum()),
        }
    profile["numeric_columns"] = numeric_cols[:25]
    profile["numeric_stats"] = {k: numeric_stats[k] for k in list(numeric_stats.keys())[:25]}

    numeric_set = set(numeric_cols)
    text_summaries: dict[str, Any] = {}
    for c in cols[:40]:
        if c in numeric_set:
            continue
        if df[c].dtype not in ("object", "string", "category") and not str(df[c].dtype).startswith("str"):
            continue
        ser = df[c].dropna().astype(str)
        if ser.empty:
            continue
        vc = ser.value_counts().head(5)
        text_summaries[c] = {
            "unique_approx": int(ser.nunique()),
            "top_values": [{"value": str(i), "count": int(v)} for i, v in vc.items()],
        }
        if len(text_summaries) >= 15:
            break
    profile["text_summaries"] = text_summaries

    date_like: list[str] = []
    for c in cols[:30]:
        if c in numeric_cols:
            continue
        parsed = pd.to_datetime(df[c], errors="coerce")
        non_null = df[c].notna().sum()
        if non_null == 0:
            continue
        ok = parsed.notna().sum()
        if ok / max(non_null, 1) >= 0.5:
            date_like.append(c)
    profile["date_like_columns"] = date_like[:10]

    profile["null_counts_top"] = (
        df.isna().sum().sort_values(ascending=False).head(12).astype(int).to_dict()
    )

    return profile


def apply_generic_filters(df: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    """Filtros simples sobre columnas arbitrarias."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    for rule in filters or []:
        col = rule.get("column")
        op = rule.get("op")
        val = rule.get("value")
        if not col or col not in out.columns or not op:
            continue
        ser = out[col]
        if op == "eq":
            out = out[ser.astype(str) == str(val)]
        elif op == "ne":
            out = out[ser.astype(str) != str(val)]
        elif op == "contains":
            out = out[ser.astype(str).str.contains(str(val), case=False, na=False)]
        elif op == "in" and isinstance(val, list):
            out = out[ser.astype(str).isin([str(x) for x in val])]
        elif op == "gte":
            num = pd.to_numeric(ser, errors="coerce")
            out = out[num >= float(val)]
        elif op == "lte":
            num = pd.to_numeric(ser, errors="coerce")
            out = out[num <= float(val)]
        elif op == "notna":
            out = out[ser.notna()]
    return out.reset_index(drop=True)


def apply_filter_spec(df: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    """Aplica filtros: financieros (ETL) o genéricos (`generic_filters`)."""
    if df is None or df.empty:
        return pd.DataFrame()

    if spec.get("generic_filters"):
        return apply_generic_filters(df, spec["generic_filters"])

    if FINANCIAL_FILTER_COLS.issubset(set(df.columns)):
        date_range = None
        if spec.get("date_range"):
            start, end = spec["date_range"]
            date_range = (pd.Timestamp(start), pd.Timestamp(end))

        currencies = spec.get("currencies")
        categories = spec.get("categories")
        accounts = spec.get("accounts")

        return filter_data(
            df,
            date_range=date_range,
            currencies=_as_list(currencies),
            categories=_as_list(categories),
            accounts=_as_list(accounts),
        )

    # Sin columnas financieras: no-op (evita KeyError)
    return df.copy()


def propose_filter(df: pd.DataFrame, *, date_range=None, currencies=None, categories=None, accounts=None) -> AiProposal:
    spec: dict[str, Any] = {
        "date_range": date_range,
        "currencies": _as_list(currencies),
        "categories": _as_list(categories),
        "accounts": _as_list(accounts),
    }
    spec = {k: v for k, v in spec.items() if v not in (None, [], {})}
    summary = "Propuesta de filtros preparada."
    return AiProposal(kind="filter", summary=summary, spec=spec)


def apply_transform_spec(df: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    """Aplica transformaciones acotadas a partir de un spec JSON."""
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    if spec.get("drop_duplicates"):
        out = out.drop_duplicates()

    if rename_cols := spec.get("rename_columns"):
        out = out.rename(columns=rename_cols)

    if category_map := spec.get("map_categoria"):
        if "categoria" in out.columns:
            out["categoria"] = out["categoria"].replace(category_map)

    if fillna := spec.get("fillna"):
        for col, val in fillna.items():
            if col in out.columns:
                out[col] = out[col].fillna(val)

    return out.reset_index(drop=True)


def build_chart(df: pd.DataFrame, spec: dict[str, Any]) -> go.Figure:
    """Construye una figura Plotly a partir de un spec acotado."""
    chart = (spec or {}).get("chart")
    if df is None or df.empty:
        return go.Figure()

    if chart == "monthly_result":
        return monthly_result_chart(df)
    if chart == "cashflow_cumulative":
        return cumulative_cashflow_chart(df)
    if chart == "donut_tipo":
        return type_donut_chart(df)
    if chart == "weekday":
        return weekday_chart(df)
    if chart == "bar_categoria_egresos":
        return category_bar_chart(df, tipo="egreso", limit=int(spec.get("limit", 10)))
    if chart == "bar_categoria_ingresos":
        return category_bar_chart(df, tipo="ingreso", limit=int(spec.get("limit", 10)))

    # Genérico: barras/linea por columnas existentes
    kind = spec.get("kind")
    x = spec.get("x")
    y = spec.get("y")
    agg = spec.get("agg", "sum")
    if kind in {"bar", "line"} and x in df.columns and y in df.columns:
        work = df.copy()
        work[y] = pd.to_numeric(work[y], errors="coerce")
        grouped = work.groupby(x, as_index=False)[y].agg(agg)
        if kind == "bar":
            return px.bar(grouped, x=x, y=y, title=spec.get("title") or "Gráfica")
        return px.line(grouped, x=x, y=y, markers=True, title=spec.get("title") or "Gráfica")

    return go.Figure()


def run_compute(df: pd.DataFrame, spec: dict[str, Any]) -> dict[str, Any]:
    """Cálculos acotados (sin ejecutar código arbitrario)."""
    if df is None or df.empty:
        return {"empty": True}

    op = (spec or {}).get("op")
    column = spec.get("column")
    group_by = spec.get("group_by")
    limit = int(spec.get("limit", 15))

    if op == "value_counts" and column and column in df.columns:
        vc = df[column].dropna().astype(str).value_counts().head(limit)
        return {
            "op": "value_counts",
            "column": column,
            "top": [{"value": str(i), "count": int(v)} for i, v in vc.items()],
        }

    if op == "nunique" and column and column in df.columns:
        return {"op": "nunique", "column": column, "value": int(df[column].nunique(dropna=True))}

    if op == "count_rows":
        return {"op": "count_rows", "value": int(len(df))}

    if column and column in df.columns:
        s = pd.to_numeric(df[column], errors="coerce")
    else:
        s = None

    if op == "max" and s is not None and s.notna().any():
        idx = s.idxmax()
        row = df.loc[idx].to_dict() if idx is not None and idx == idx else {}
        return {"op": "max", "column": column, "value": float(s.max()), "row": _json_safe_row(row)}
    if op == "min" and s is not None and s.notna().any():
        idx = s.idxmin()
        row = df.loc[idx].to_dict() if idx is not None and idx == idx else {}
        return {"op": "min", "column": column, "value": float(s.min()), "row": _json_safe_row(row)}
    if op == "sum" and s is not None:
        return {"op": "sum", "column": column, "value": float(s.sum()) if s.notna().any() else 0.0}
    if op == "mean" and s is not None and s.notna().any():
        return {"op": "mean", "column": column, "value": float(s.mean())}

    if op == "groupby_sum" and group_by in df.columns and column in df.columns:
        work = df[[group_by, column]].copy()
        work[column] = pd.to_numeric(work[column], errors="coerce")
        out = (
            work.groupby(group_by, as_index=False)[column]
            .sum()
            .sort_values(column, ascending=False)
            .head(int(spec.get("limit", 20)))
        )
        return {"op": "groupby_sum", "group_by": group_by, "column": column, "top": out.to_dict(orient="records")}

    if op == "groupby_count" and group_by in df.columns:
        out = (
            df.groupby(group_by, as_index=False)
            .size()
            .rename(columns={"size": "count"})
            .sort_values("count", ascending=False)
            .head(limit)
        )
        return {"op": "groupby_count", "group_by": group_by, "top": out.to_dict(orient="records")}

    return {"op": op, "error": "spec no soportado o columnas inválidas"}


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, (pd.Timestamp, pd.Timedelta)):
            safe[k] = str(v)
        elif isinstance(v, (np.integer, np.floating)):
            safe[k] = v.item()
        else:
            safe[k] = v
    return safe


def propose_transform(
    *,
    drop_duplicates: bool | None = None,
    rename_columns: dict[str, str] | None = None,
    map_categoria: dict[str, str] | None = None,
    fillna: dict[str, Any] | None = None,
) -> AiProposal:
    spec: dict[str, Any] = {
        "drop_duplicates": bool(drop_duplicates) if drop_duplicates is not None else None,
        "rename_columns": rename_columns,
        "map_categoria": map_categoria,
        "fillna": fillna,
    }
    spec = {k: v for k, v in spec.items() if v not in (None, [], {})}
    return AiProposal(kind="transform", summary="Propuesta de transformación preparada.", spec=spec)


def _as_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(v) for v in value if v is not None]
    return None

