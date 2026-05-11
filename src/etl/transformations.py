# -*- coding: utf-8 -*-
"""Transformaciones del modelo financiero.

Los datos que llegan del mundo real casi nunca vienen perfectos: fechas como
texto, montos con símbolos, separadores distintos, categorías vacías, etc.
Aquí dejamos esas reglas juntas para poder revisarlas sin buscar por toda la app.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import ADJUSTMENT_WORDS, DEFAULT_CURRENCY, EXPENSE_WORDS, INCOME_WORDS, STANDARD_FIELDS


@dataclass
class ETLResult:
    data: pd.DataFrame
    rejected_rows: pd.DataFrame
    log: list[str] = field(default_factory=list)


def strip_accents(value: object) -> str:
    """Normaliza texto para comparar sin tildes ni mayúsculas."""
    text = "" if value is None else str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def parse_amount(value: object) -> float:
    """Convierte montos tipo '$1.234,56' o '1,234.56' a número."""
    if pd.isna(value):
        return np.nan

    text = str(value).strip()
    if not text:
        return np.nan

    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    text = text.replace("\u00a0", "").replace(" ", "")
    text = re.sub(r"[^0-9,.\-]", "", text)
    text = text.replace("-", "")

    if not text:
        return np.nan

    has_comma = "," in text
    has_dot = "." in text

    if has_comma and has_dot:
        # El separador decimal suele ser el último que aparece.
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        text = text.replace(thousands_sep, "")
        text = text.replace(decimal_sep, ".")
    elif has_comma:
        parts = text.split(",")
        if len(parts[-1]) in (1, 2):
            text = "".join(parts[:-1]) + "." + parts[-1]
        else:
            text = text.replace(",", "")
    elif has_dot:
        parts = text.split(".")
        if len(parts) > 2 and len(parts[-1]) in (1, 2):
            text = "".join(parts[:-1]) + "." + parts[-1]
        elif len(parts) > 1 and len(parts[-1]) == 3 and all(len(part) == 3 for part in parts[1:]):
            text = text.replace(".", "")

    try:
        number = float(text)
    except ValueError:
        return np.nan

    return -number if negative else number


def parse_date_series(series: pd.Series) -> pd.Series:
    """Parsea fechas con una pasada normal y otra pensando en formato latino."""
    parsed = pd.to_datetime(series, errors="coerce")
    missing = parsed.isna()

    if missing.any():
        parsed_latam = pd.to_datetime(series[missing], errors="coerce", dayfirst=True)
        parsed.loc[missing] = parsed_latam

    return parsed


def normalize_type(value: object, amount: float) -> str:
    """Estandariza el tipo de movimiento."""
    text = strip_accents(value)
    tokens = set(re.split(r"[^a-z0-9]+", text))

    if tokens & {strip_accents(word) for word in INCOME_WORDS}:
        return "ingreso"
    if tokens & {strip_accents(word) for word in EXPENSE_WORDS}:
        return "egreso"
    if tokens & {strip_accents(word) for word in ADJUSTMENT_WORDS}:
        return "ajuste"

    # Si el archivo no trae tipo, el signo del monto es la pista más honesta.
    if pd.notna(amount) and amount < 0:
        return "egreso"
    return "ingreso"


def _copy_mapped_columns(df: pd.DataFrame, mapping: dict[str, str | None]) -> pd.DataFrame:
    """Crea un DataFrame con los nombres internos que entiende el dashboard."""
    output = pd.DataFrame(index=df.index)

    for field in STANDARD_FIELDS:
        source_column = mapping.get(field)
        if source_column and source_column in df.columns:
            output[field] = df[source_column]
        else:
            output[field] = np.nan

    return output


def build_financial_dataset(
    raw_df: pd.DataFrame,
    mapping: dict[str, str | None],
    *,
    default_currency: str = DEFAULT_CURRENCY,
    drop_invalid_rows: bool = True,
    drop_duplicates: bool = True,
) -> ETLResult:
    """Convierte los datos cargados al modelo que usan KPIs y gráficas."""
    if raw_df is None or raw_df.empty:
        return ETLResult(data=pd.DataFrame(), rejected_rows=pd.DataFrame(), log=["No había datos para limpiar."])

    log: list[str] = []
    df = _copy_mapped_columns(raw_df, mapping)
    df["_fila_origen"] = raw_df.index + 2  # +2 porque suele haber encabezado en la fila 1.

    original_rows = len(df)

    df["fecha"] = parse_date_series(df["fecha"])
    df["monto_num"] = df["monto"].apply(parse_amount)

    df["tipo_norm"] = [
        normalize_type(tipo, monto)
        for tipo, monto in zip(df["tipo"], df["monto_num"], strict=False)
    ]

    df["monto_abs"] = df["monto_num"].abs()
    df["monto_signed"] = np.select(
        [
            df["tipo_norm"].eq("ingreso"),
            df["tipo_norm"].eq("egreso"),
            df["tipo_norm"].eq("ajuste"),
        ],
        [
            df["monto_abs"],
            -df["monto_abs"],
            df["monto_num"],
        ],
        default=df["monto_num"],
    )

    for column, fallback in {
        "categoria": "Sin categoría",
        "subcategoria": "Sin subcategoría",
        "cuenta": "Sin cuenta",
        "descripcion": "",
        "moneda": default_currency,
    }.items():
        df[column] = df[column].fillna(fallback).astype(str).str.strip()
        df[column] = df[column].replace({"": fallback, "nan": fallback, "None": fallback})

    df["moneda"] = df["moneda"].str.upper().str[:3]

    invalid_mask = df["fecha"].isna() | df["monto_num"].isna()
    rejected = df.loc[invalid_mask].copy()

    if drop_invalid_rows:
        df = df.loc[~invalid_mask].copy()
        if len(rejected):
            log.append(f"Se quitaron {len(rejected)} filas sin fecha o monto válido.")
    elif len(rejected):
        log.append(f"Hay {len(rejected)} filas con fecha o monto inválido; se dejaron marcadas.")

    if drop_duplicates and not df.empty:
        before = len(df)
        subset = ["fecha", "monto_num", "tipo_norm", "categoria", "descripcion", "cuenta"]
        df = df.drop_duplicates(subset=subset, keep="first")
        removed = before - len(df)
        if removed:
            log.append(f"Se quitaron {removed} movimientos duplicados.")

    if not df.empty:
        df["anio"] = df["fecha"].dt.year
        df["mes"] = df["fecha"].dt.to_period("M").dt.to_timestamp()
        df["mes_texto"] = df["fecha"].dt.strftime("%Y-%m")
        df["trimestre"] = df["fecha"].dt.to_period("Q").astype(str)
        df["dia_semana"] = df["fecha"].dt.day_name(locale=None)
        df = df.sort_values(["fecha", "_fila_origen"]).reset_index(drop=True)

    log.append(f"Filas recibidas: {original_rows}. Filas listas para análisis: {len(df)}.")

    return ETLResult(data=df, rejected_rows=rejected.reset_index(drop=True), log=log)
