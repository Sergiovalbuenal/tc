# -*- coding: utf-8 -*-
"""Formatos de números para que todo se vea parejo."""

from __future__ import annotations

import math


def spanish_number(value: float, decimals: int = 2) -> str:
    """Formatea 1234.5 como 1.234,50."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = 0

    formatted = f"{abs(float(value)):,.{decimals}f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{formatted}" if float(value) < 0 else formatted


def money(value: float, currency: str = "$") -> str:
    """Formatea dinero con estilo latino."""
    sign = "- " if value is not None and float(value) < 0 else ""
    return f"{sign}{currency} {spanish_number(abs(float(value or 0)), 2)}"


def percent(value: float) -> str:
    """Formatea porcentajes sin explotar con None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = 0
    return f"{spanish_number(float(value) * 100, 1)}%"


def compact(value: float) -> str:
    """Número corto para tarjetas."""
    value = float(value or 0)
    abs_value = abs(value)

    if abs_value >= 1_000_000:
        return f"{spanish_number(value / 1_000_000, 1)} M"
    if abs_value >= 1_000:
        return f"{spanish_number(value / 1_000, 1)} K"
    return spanish_number(value, 0)
