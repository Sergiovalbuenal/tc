# -*- coding: utf-8 -*-
"""Validaciones pequeñas para avisar antes de calcular KPIs."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_mapping(
    mapping: dict[str, str | None],
    dataset_type: str = "financiero",
) -> ValidationResult:
    """Revisa que el usuario haya mapeado los campos obligatorios del tipo de dataset."""
    from src.config import DATASET_SCHEMAS

    result = ValidationResult()
    schema = DATASET_SCHEMAS.get(dataset_type, DATASET_SCHEMAS["general"])
    required = schema.get("required", [])

    for req_field in required:
        if not mapping.get(req_field):
            field_label = schema["fields"].get(req_field, req_field)
            result.errors.append(f"Falta mapear el campo obligatorio: **{field_label}** (`{req_field}`).")

    if dataset_type == "financiero":
        if not mapping.get("tipo"):
            result.warnings.append(
                "No se mapeó 'Tipo de movimiento'. Se inferirá usando el signo del monto."
            )
        if not mapping.get("moneda"):
            result.warnings.append(
                "No se mapeó 'Moneda'. Se usará la moneda por defecto del proyecto."
            )

    return result


def validate_clean_data(df: pd.DataFrame, dataset_type: str = "financiero") -> ValidationResult:
    """Valida el DataFrame ya transformado según el tipo de dataset."""
    result = ValidationResult()

    if df is None or df.empty:
        result.errors.append("No hay datos limpios para analizar.")
        return result

    if dataset_type == "financiero":
        required_columns = {"fecha", "monto_abs", "monto_signed", "tipo_norm"}
        missing = required_columns - set(df.columns)
        if missing:
            result.errors.append("Faltan columnas internas: " + ", ".join(sorted(missing)))

        if "fecha" in df and df["fecha"].isna().any():
            result.warnings.append("Quedaron filas sin fecha válida.")

        if "monto_abs" in df and df["monto_abs"].isna().any():
            result.warnings.append("Quedaron filas sin monto válido.")

        if "tipo_norm" in df:
            unknown = sorted(set(df["tipo_norm"].dropna()) - {"ingreso", "egreso", "ajuste"})
            if unknown:
                result.warnings.append("Hay tipos no esperados: " + ", ".join(unknown))

        # Aviso si hay muchas filas imputadas
        if "moneda" in df:
            imputed = (df["moneda"] == "USD").sum()
            if imputed / len(df) > 0.5:
                result.warnings.append(
                    f"{imputed:,} filas usan la moneda por defecto (USD). "
                    "Verifica si el archivo trae columna de moneda."
                )
    else:
        # Validación genérica: solo avisa si hay muchos nulos
        null_pct = df.isnull().mean()
        high_null = null_pct[null_pct > 0.3]
        for col in high_null.index:
            if not col.startswith("_"):
                pct = int(high_null[col] * 100)
                result.warnings.append(f"La columna '{col}' tiene {pct}% de valores vacíos.")

    return result
