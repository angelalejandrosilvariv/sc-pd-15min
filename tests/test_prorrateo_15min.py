import pandas as pd
import pytest

from src.prorrateo_15min import (
    agrupar_retiros,
    auditar_cuadratura,
    calcular_cuarto_hora_mensual,
    construir_membresia_ciclos,
    prorratear_retiros,
)


def test_calcular_cuarto_hora_mensual_es_uno_indexado():
    fechas = pd.Series(pd.to_datetime([
        "2026-06-01 00:00", "2026-06-01 00:15", "2026-06-02 00:00"
    ]))
    assert calcular_cuarto_hora_mensual(fechas).tolist() == [1, 2, 97]


def test_membresia_deduplica_centrales_del_mismo_ciclo_y_cuarto():
    detalle = pd.DataFrame({
        "Etiqueta_Relacionada": ["C1", "C1"],
        "Central": ["A", "B"],
        "FECHA_HORA": pd.to_datetime(["2026-06-01", "2026-06-01"]),
    })
    resultado = construir_membresia_ciclos(detalle)
    assert resultado.to_dict("records") == [{"Ciclo": "C1", "Cuarto_Hora_Mensual": 1}]


def test_prorratea_ciclos_concurrentes_y_reporta_total_cero():
    membresia = pd.DataFrame({
        "Ciclo": ["C1", "C1", "C2", "C3", "SIN_DETALLE"],
        "Cuarto_Hora_Mensual": [1, 2, 2, 3, 99],
    })
    retiros = pd.DataFrame({
        "Cuarto_Hora_Mensual": [1, 1, 2, 2, 3, 3],
        "Suministrador": ["A", "B", "A", "B", "A", "B"],
        "Medida_kWh": [10.0, 30.0, 20.0, 40.0, 5.0, -5.0],
    })
    precios = pd.DataFrame({
        "Ciclo": ["C1", "C2", "C3", "AUSENTE"],
        "Precio_Ciclo": [100.0, 80.0, 50.0, 999.0],
    })
    detalle = prorratear_retiros(membresia, retiros, precios)
    por_ciclo = detalle.groupby("Ciclo")["Monetario_Cuarto"].sum()
    assert por_ciclo["C1"] == pytest.approx(100.0)
    assert por_ciclo["C2"] == pytest.approx(80.0)
    assert "C3" not in por_ciclo
    assert "AUSENTE" not in por_ciclo

    auditoria = auditar_cuadratura(detalle)
    assert auditoria["ciclos_sin_retiros"] == ["C3"]
    assert auditoria["total_repartido"] == pytest.approx(180.0)
    assert auditoria["total_original"] == pytest.approx(230.0)
    assert len(auditoria["ciclos_con_diferencia"]) == 0


def test_retiros_negativos_producen_prorratas_positivas_y_cuadran():
    membresia = pd.DataFrame({"Ciclo": ["C1"], "Cuarto_Hora_Mensual": [1]})
    retiros = agrupar_retiros(pd.DataFrame({
        "Cuarto de Hora": [1, 1],
        "Suministrador": ["A", "B"],
        "Medida_kWh": [-25.0, -75.0],
    }))
    precios = pd.DataFrame({"Ciclo": ["C1"], "Precio_Ciclo": [200.0]})
    detalle = prorratear_retiros(membresia, retiros, precios)
    assert detalle["Prorrata_Respecto_Ciclo"].tolist() == pytest.approx([0.25, 0.75])
    assert detalle["Monetario_Cuarto"].sum() == pytest.approx(200.0)
