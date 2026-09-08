"""Regresion de rendimiento para el empalme mensual vectorizado."""

from time import perf_counter

import numpy as np
import pandas as pd
import pytest

from src.fase1_integridad import empalmar_reportes


@pytest.mark.slow
def test_empalme_quinientas_mil_filas_por_archivo_en_menos_de_20_segundos():
    filas = 500_000
    fechas = pd.date_range('2026-01-01', periods=filas, freq='15min')

    def reporte(instantes):
        n = len(instantes)
        return pd.DataFrame({
            'FECHA_HORA': instantes,
            'UNIDAD GENERADORA': 'U1',
            'Central': 'C1',
            'CONFIGURACION': 'A',
            'GENERACION': np.ones(n),
            'CMg-CV': np.full(n, 2.0),
            'Dolar': np.full(n, 900.0),
        })

    # Solo 96 bloques se solapan: el caso normal es casi todo llave unica.
    pasado = reporte(fechas)
    actual = reporte(pd.date_range(fechas[-96], periods=filas, freq='15min'))
    inicio = perf_counter()
    resultado = empalmar_reportes(pasado, actual)
    duracion = perf_counter() - inicio

    assert len(resultado) == filas * 2 - 96
    assert duracion < 20, f'empalme demoro {duracion:.2f} segundos'
