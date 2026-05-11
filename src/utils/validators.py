# -*- coding: utf-8 -*-
"""Validaciones pequeñas para avisar antes de calcular KPIs."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.config import REQUIRED_FIELDS


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_mapping(mapping: dict[str, str | None]) -> ValidationResult:
    """Revisa que el usuario haya elegido fecha y monto."""
    result = ValidationResult()

    for field in REQUIRED_FIELDS:
        if not mapping.get(field):
            result.errors.append(f"Falta mapear el campo obligatorio: {field}.")

    if not mapping.get("tipo"):
        result.warnings.append(
            "No se mapeó tipo de movimiento. Se inferirá con el signo del monto."
        )

    if not mapping.get("moneda"):
        result.warnings.append(
            "No se mapeó moneda. Se usará la moneda por defecto del proyecto."
        )

    return result


def validate_clean_data(df: pd.DataFrame) -> ValidationResult:
    """Valida el DataFrame ya transformado."""
    result = ValidationResult()

    if df is None or df.empty:
        result.errors.append("No hay datos limpios para analizar.")
        return result

    required_columns = {"fecha", "monto_abs", "monto_signed", "tipo_norm"}
    missing = required_columns - set(df.columns)
    if missing:
        result.errors.append("Faltan columnas internas: " + ", ".join(sorted(missing)))

    if "fecha" in df and df["fecha"].isna().any():
        result.warnings.append("Quedaron filas sin fecha válida.")

    if "monto_abs" in df and df["monto_abs"].isna().any():
        result.warnings.append("Quedaron filas sin monto válido.")

    if "tipo_norm" in df:
        unknown_types = sorted(set(df["tipo_norm"].dropna()) - {"ingreso", "egreso", "ajuste"})
        if unknown_types:
            result.warnings.append("Hay tipos no esperados: " + ", ".join(unknown_types))

    return result
