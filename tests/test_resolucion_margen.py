"""Pruebas de la resolucion temporal configurable del margen (spec 30)."""

import numpy as np
import pandas as pd
import pytest

import sc_pd_motor_v7 as motor
from sc_pd_motor_v7 import calcular_margen_bloques, margen_por_hora


def _reporte(cmg, gen=None, inicio='2026-08-01 01:00'):
    n = len(cmg)
    return pd.DataFrame({
        'Central': ['CENTRAL'] * n,
        'FECHA_HORA': pd.date_range(inicio, periods=n, freq='15min'),
        'CMg': cmg,
        'CV': [50.0] * n,
        'Dolar': [900.0] * n,
        'GENERACION': gen or [1.0] * n,
    })


def test_default_bloque_es_identico_al_calculo_actual():
    assert motor.RESOLUCION_MARGEN == 'bloque'
    reporte = _reporte([80.0, 30.0, 60.0, 40.0])
    np.testing.assert_array_equal(
        calcular_margen_bloques(reporte),
        calcular_margen_bloques(reporte, calcular_en_motor=1,
                                netear_por_ciclo=0))


def test_cmg_constante_da_el_mismo_margen_en_bloque_y_hora():
    reporte = _reporte([75.0] * 4, gen=[1.0, 2.0, 3.0, 4.0])
    np.testing.assert_allclose(
        margen_por_hora(reporte), calcular_margen_bloques(reporte))


def test_cruce_del_cv_cumple_convexidad_y_reparto_suma_margen_horario():
    reporte = _reporte([100.0, 0.0, 100.0, 40.0], gen=[1.0, 1.0, 3.0, 3.0])
    bloque = calcular_margen_bloques(reporte)
    hora = margen_por_hora(reporte)
    gen_h = reporte['GENERACION'].sum()
    cmg_h = np.average(reporte['CMg'], weights=reporte['GENERACION'])
    esperado = max(0, cmg_h - 50.0) * 900.0 * gen_h

    assert bloque.sum() >= hora.sum()
    assert hora.sum() == pytest.approx(esperado)
    np.testing.assert_allclose(hora / esperado,
                               reporte['GENERACION'] / gen_h)


def test_hora_incompleta_de_dos_bloques_se_agrega_igual():
    reporte = _reporte([80.0, 40.0], gen=[2.0, 1.0], inicio='2026-08-01 02:00')
    resultado = margen_por_hora(reporte)
    esperado = max(0, (80 * 2 + 40) / 3 - 50) * 900 * 3
    assert resultado.sum() == pytest.approx(esperado)


def test_neteado_mas_hora_conserva_el_signo():
    reporte = _reporte([10.0, 20.0, 30.0, 40.0])
    resultado = margen_por_hora(reporte, netear_por_ciclo=1)
    assert resultado.sum() < 0
    assert np.all(resultado < 0)


def test_valor_invalido_aborta_antes_de_cargar_archivos(monkeypatch):
    monkeypatch.setattr(motor, 'RESOLUCION_MARGEN', 'diaria')
    with pytest.raises(SystemExit, match="RESOLUCION_MARGEN='diaria'.*no es valido"):
        motor.main({}, {})
