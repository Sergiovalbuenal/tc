# -*- coding: utf-8 -*-
"""Configuración chica y fácil de tocar.

La idea es no esconder reglas del negocio dentro de las páginas. Si mañana
cambian los nombres de columnas o los tipos de movimiento, este archivo es el
primer lugar donde mirar.
"""

from __future__ import annotations

APP_NAME = "Tablero de Control"
APP_VERSION = "2.0"

# Campos estándar que usa el modelo interno del dashboard.
STANDARD_FIELDS = {
    "fecha": "Fecha",
    "monto": "Monto",
    "tipo": "Tipo de movimiento",
    "categoria": "Categoría",
    "subcategoria": "Subcategoría",
    "cuenta": "Cuenta",
    "descripcion": "Descripción",
    "moneda": "Moneda",
}

REQUIRED_FIELDS = ("fecha", "monto")

DEFAULT_CURRENCY = "USD"

# Palabras comunes que usamos para adivinar el mapeo de columnas al cargar datos.
FIELD_ALIASES = {
    "fecha": [
        "fecha", "date", "transaction_date", "fecha_transaccion", "fecha_movimiento",
        "periodo", "created_at", "posted_date", "posting_date",
    ],
    "monto": [
        "monto", "amount", "valor", "importe", "total", "saldo", "value",
        "debe", "haber", "balance", "transaction_amount",
    ],
    "tipo": [
        "tipo", "type", "movimiento", "naturaleza", "clase", "operacion",
        "transaction_type", "ingreso_egreso",
    ],
    "categoria": [
        "categoria", "category", "rubro", "grupo", "concepto", "linea",
        "clasificacion", "cost_center",
    ],
    "subcategoria": [
        "subcategoria", "sub_category", "subcategory", "subrubro", "detalle_categoria",
    ],
    "cuenta": [
        "cuenta", "account", "banco", "wallet", "caja", "origen", "source",
    ],
    "descripcion": [
        "descripcion", "description", "detalle", "memo", "nota", "observacion",
        "glosa", "concepto_detalle",
    ],
    "moneda": [
        "moneda", "currency", "divisa", "iso_currency", "coin",
    ],
}

INCOME_WORDS = {
    "ingreso", "ingresos", "income", "revenue", "venta", "ventas", "cobro",
    "deposito", "depósito", "entrada", "abono", "credit", "credito", "crédito",
}

EXPENSE_WORDS = {
    "egreso", "egresos", "gasto", "gastos", "expense", "expenses", "pago",
    "salida", "retiro", "debit", "debito", "débito", "compra", "compras",
}

ADJUSTMENT_WORDS = {
    "ajuste", "adjustment", "transferencia", "transfer", "traslado",
}
