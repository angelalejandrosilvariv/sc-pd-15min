"""Pruebas del interruptor del criterio de margen por bloque."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import calcular_margen_bloques


def test_criterio_reporte_conserva_formula_anterior_y_anula_negativos():
    reporte = pd.DataFrame({
        'CMg-CV': [10.0, -4.0, 0.0],
        'GENERACION': [2.0, 3.0, 5.0],
    })
    esperado = np.where(
        reporte['CMg-CV'] > 0,
        reporte['CMg-CV'] * reporte['GENERACION'],
        0,
    )

    resultado = calcular_margen_bloques(reporte, calcular_en_motor=0)

    np.testing.assert_array_equal(resultado, esperado)


def test_criterio_motor_recupera_margen_que_el_reporte_deja_en_cero():
    reporte = pd.DataFrame({
        'CMg': [100.0],
        'CV': [40.0],
        'Dolar': [900.0],
        'CMg-CV': [0.0],
        'GENERACION': [2.5],
    })

    resultado = calcular_margen_bloques(reporte, calcular_en_motor=1)

    np.testing.assert_array_equal(resultado, [(100 - 40) * 900 * 2.5])


def test_criterio_motor_anula_margen_negativo():
    reporte = pd.DataFrame({
        'CMg': [30.0],
        'CV': [40.0],
        'Dolar': [900.0],
        'GENERACION': [2.5],
    })

    resultado = calcular_margen_bloques(reporte, calcular_en_motor=1)

    np.testing.assert_array_equal(resultado, [0])


def test_criterio_motor_convierte_valores_invalidos_en_margen_cero():
    reporte = pd.DataFrame({
        'CMg': ['no numerico', 100, 100, 100],
        'CV': [40, '', 40, 40],
        'Dolar': [900, 900, None, 900],
        'GENERACION': [2, 2, 2, 'vacia'],
    })

    resultado = calcular_margen_bloques(reporte, calcular_en_motor=1)

    np.testing.assert_array_equal(resultado, [0, 0, 0, 0])
