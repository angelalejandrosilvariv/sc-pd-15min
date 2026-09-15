"""Pruebas del interruptor VIGENCIA_INSTRUCCION_RIO_MIN.

Una instruccion del RIO solo habilita la partida/detencion si tiene a lo mas
VIGENCIA minutos de antiguedad respecto del bloque. Con 0 no se limita.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import columnas_resumen_ciclos, filtro_vigencia_rio


def _bloques(minutos_antes):
    """Bloques a las 10:00 con instrucciones RIO ``minutos_antes`` minutos antes."""
    t = pd.Timestamp('2026-08-16 10:00')
    fecha = pd.Series([t] * len(minutos_antes))
    fuente = pd.Series([pd.NaT if m is None else t - pd.Timedelta(minutes=m) for m in minutos_antes])
    return fecha, fuente


def test_cero_no_limita_nada():
    fecha, fuente = _bloques([5, 90, 1440, None])

    np.testing.assert_array_equal(filtro_vigencia_rio(fecha, fuente, 0), [1, 1, 1, 1])


def test_treinta_minutos_acepta_hasta_treinta_y_rechaza_lo_anterior():
    fecha, fuente = _bloques([0, 30, 31, 90, 1440])

    np.testing.assert_array_equal(filtro_vigencia_rio(fecha, fuente, 30), [1, 1, 0, 0, 0])


def test_instruccion_posterior_al_bloque_es_vigente():
    # Rescatada en ventana hacia adelante: antiguedad negativa.
    fecha, fuente = _bloques([-10, -30])

    np.testing.assert_array_equal(filtro_vigencia_rio(fecha, fuente, 30), [1, 1])


def test_sin_instruccion_no_se_toca_para_respetar_la_exencion():
    fecha, fuente = _bloques([None])

    np.testing.assert_array_equal(filtro_vigencia_rio(fecha, fuente, 30), [1])


def test_vigencia_se_exporta_junto_a_los_filtros():
    columnas = columnas_resumen_ciclos(0, 1)

    assert columnas.index('Vigencia_RIO_Partida') == columnas.index('Filtro_Op_Partida') + 1
    assert columnas.index('Vigencia_RIO_Detencion') == columnas.index('Filtro_Op_Detencion') + 1
