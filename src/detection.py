# -*- coding: utf-8 -*-
"""Detección automática del tipo de dataset.

Analiza los nombres de columnas del archivo cargado y devuelve el tipo
de datos más probable (financiero, ventas, rrhh, inventario o general).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class DetectionResult:
    dataset_type: str
    label: str
    icon: str
    confidence: float  # 0.0 a 1.0
    description: str
    matched_fields: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def _normalize(value: object) -> str:
    text = "" if value is None else str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def detect_dataset_type(df: pd.DataFrame) -> DetectionResult:
    """Detecta el tipo de dataset analizando los nombres de columnas."""
    from src.config import DATASET_SCHEMAS

    normalized_cols = {_normalize(col) for col in df.columns}

    scores: dict[str, tuple[float, list[str]]] = {}

    for type_key, schema in DATASET_SCHEMAS.items():
        if type_key == "general":
            continue

        matched: list[str] = []
        for field_name, aliases in schema["aliases"].items():
            for alias in aliases:
                if _normalize(alias) in normalized_cols:
                    matched.append(field_name)
                    break

        required = schema["required"]
        required_matched = [r for r in required if r in matched]

        # Sin ningún campo obligatorio, el puntaje es muy bajo
        if required and not required_matched:
            scores[type_key] = (0.0, matched)
            continue

        total_fields = len(schema["fields"])
        field_score = len(matched) / total_fields if total_fields > 0 else 0
        req_score = len(required_matched) / len(required) if required else 0

        # 40% cobertura de campos + 60% campos obligatorios encontrados
        score = 0.4 * field_score + 0.6 * req_score
        scores[type_key] = (score, matched)

    best_score_val = max((s for s, _ in scores.values()), default=0.0)

    if best_score_val < 0.15:
        # Sin coincidencias suficientes: se asume financiero como default
        # (comportamiento histórico del dashboard) con confianza 0 para que
        # el usuario sepa que fue una suposición y pueda corregirla.
        schema = DATASET_SCHEMAS["financiero"]
        return DetectionResult(
            dataset_type="financiero",
            label=schema["label"],
            icon=schema["icon"],
            confidence=0.0,
            description="No se detectó el tipo automáticamente — se asume Financiero por defecto.",
            suggestions=["Revisa el tipo de datos en el selector y cámbialo si es necesario."],
        )

    best_type = max(scores, key=lambda k: scores[k][0])
    best_score, best_matched = scores[best_type]
    schema = DATASET_SCHEMAS[best_type]

    suggestions = []
    for req_field in schema["required"]:
        if req_field not in best_matched:
            suggestions.append(f"Mapea la columna '{req_field}' para activar todos los análisis.")

    return DetectionResult(
        dataset_type=best_type,
        label=schema["label"],
        icon=schema["icon"],
        confidence=min(best_score, 1.0),
        description=schema["description"],
        matched_fields=best_matched,
        suggestions=suggestions,
    )
