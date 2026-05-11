# -*- coding: utf-8 -*-

from src.etl.pipeline import run_pipeline
from src.kpis.financial_kpis import calculate_kpis
from src.utils.sample_data import build_sample_data


def test_pipeline_and_kpis_with_sample_data():
    df = build_sample_data(months=3)
    mapping = {
        "fecha": "fecha",
        "monto": "monto",
        "tipo": "tipo",
        "categoria": "categoria",
        "subcategoria": "subcategoria",
        "cuenta": "cuenta",
        "descripcion": "descripcion",
        "moneda": "moneda",
    }

    result = run_pipeline(df, mapping)
    kpis = calculate_kpis(result.data)

    assert not result.data.empty
    assert kpis["movimientos"] == len(result.data)
    assert kpis["ingresos"] >= 0
    assert kpis["egresos"] >= 0
