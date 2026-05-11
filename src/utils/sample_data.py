# -*- coding: utf-8 -*-
"""Datos de ejemplo para probar el dashboard sin subir archivos reales."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


def build_sample_data(months: int = 12, seed: int = 42) -> pd.DataFrame:
    """Genera movimientos financieros realistas para demo."""
    rng = np.random.default_rng(seed)

    today = pd.Timestamp(datetime.today().date())
    start = (today - pd.DateOffset(months=months - 1)).replace(day=1)
    dates = pd.date_range(start=start, end=today, freq="D")

    rows: list[dict[str, object]] = []

    income_categories = [
        ("Ventas", "Producto"),
        ("Ventas", "Servicios"),
        ("Otros ingresos", "Intereses"),
    ]
    expense_categories = [
        ("Marketing", "Publicidad"),
        ("Operaciones", "Software"),
        ("Operaciones", "Logística"),
        ("Nómina", "Salarios"),
        ("Administración", "Oficina"),
        ("Finanzas", "Comisiones"),
    ]

    accounts = ["Banco principal", "Cuenta ahorro", "Pasarela pagos"]
    currencies = ["USD"]

    for date in dates:
        # Ingresos: más probables entre lunes y viernes.
        if date.weekday() < 5 and rng.random() < 0.55:
            category, subcategory = income_categories[rng.integers(0, len(income_categories))]
            amount = round(float(rng.normal(1850, 520)), 2)
            rows.append(
                {
                    "fecha": date,
                    "categoria": category,
                    "subcategoria": subcategory,
                    "cuenta": accounts[rng.integers(0, len(accounts))],
                    "descripcion": f"Ingreso {subcategory.lower()}",
                    "tipo": "Ingreso",
                    "monto": max(amount, 120),
                    "moneda": currencies[0],
                }
            )

        # Egresos: varios gastos chicos durante el mes.
        if rng.random() < 0.75:
            category, subcategory = expense_categories[rng.integers(0, len(expense_categories))]
            base = 420 if category != "Nómina" else 2100
            spread = 160 if category != "Nómina" else 350
            amount = round(float(rng.normal(base, spread)), 2)
            rows.append(
                {
                    "fecha": date,
                    "categoria": category,
                    "subcategoria": subcategory,
                    "cuenta": accounts[rng.integers(0, len(accounts))],
                    "descripcion": f"Pago {subcategory.lower()}",
                    "tipo": "Egreso",
                    "monto": max(amount, 35),
                    "moneda": currencies[0],
                }
            )

    return pd.DataFrame(rows).sort_values("fecha").reset_index(drop=True)
