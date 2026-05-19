# -*- coding: utf-8 -*-
"""Pipeline y filtros reutilizables."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.etl.transformations import ETLResult, build_financial_dataset, build_generic_dataset

FINANCIAL_TYPE = "financiero"


def run_pipeline(
    raw_df: pd.DataFrame,
    mapping: dict[str, str | None],
    *,
    dataset_type: str = FINANCIAL_TYPE,
    default_currency: str = "USD",
    drop_invalid_rows: bool = True,
    drop_duplicates: bool = True,
) -> ETLResult:
    """Punto único para limpiar datos desde las vistas.

    Si el tipo es 'financiero' usa el pipeline especializado con KPIs financieros.
    Para otros tipos (ventas, rrhh, inventario, general) usa el pipeline genérico.
    """
    if dataset_type == FINANCIAL_TYPE:
        return build_financial_dataset(
            raw_df,
            mapping,
            default_currency=default_currency,
            drop_invalid_rows=drop_invalid_rows,
            drop_duplicates=drop_duplicates,
        )

    return build_generic_dataset(
        raw_df,
        mapping,
        dataset_type=dataset_type,
        drop_invalid_rows=drop_invalid_rows,
        drop_duplicates=drop_duplicates,
    )


def filter_data(
    df: pd.DataFrame,
    *,
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    currencies: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    accounts: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Aplica filtros comunes sin modificar el DataFrame original."""
    if df is None or df.empty:
        return pd.DataFrame()

    filtered = df.copy()

    if date_range and len(date_range) == 2:
        start, end = date_range
        filtered = filtered[(filtered["fecha"] >= pd.Timestamp(start)) & (filtered["fecha"] <= pd.Timestamp(end))]

    if currencies:
        currencies = list(currencies)
        if currencies:
            filtered = filtered[filtered["moneda"].isin(currencies)]

    if categories:
        categories = list(categories)
        if categories:
            filtered = filtered[filtered["categoria"].isin(categories)]

    if accounts:
        accounts = list(accounts)
        if accounts:
            filtered = filtered[filtered["cuenta"].isin(accounts)]

    return filtered.reset_index(drop=True)
