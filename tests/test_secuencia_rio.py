"""Regresiones para la secuencia informativa de instrucciones RIO."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import listar_secuencia_rio_ventana


def _rio(fechas, consignas):
    return pd.DataFrame({
        'FECHA_HORA_RIO': pd.to_datetime(fechas),
        'Central_Relacionada_RIO': 'CENTRAL',
        'CONSIGNAS': consignas,
        'MOTIVO': 'OM',
        'NOMBRE CONFIGURACIÓN': 'CENTRAL_DIESEL',
    })


def test_secuencia_con_una_instruccion_no_agrega_separador():
    momentos = pd.DataFrame({
        'Central_Relacionada': ['CENTRAL'],
        'Momento': pd.to_datetime(['2026-06-01 10:00']),
    })
    resultado = listar_secuencia_rio_ventana(
        momentos, _rio(['2026-06-01 09:53'], ['PP']), 2)
    assert resultado.tolist() == ['-7min PP/OM/CENTRAL_DIESEL']


def test_secuencia_multiple_esta_en_orden_cronologico_y_con_signos():
    momentos = pd.DataFrame({
        'Central_Relacionada': ['CENTRAL'],
        'Momento': pd.to_datetime(['2026-06-01 10:00']),
    })
    rio = _rio(['2026-06-01 10:05', '2026-06-01 09:53'], ['PC', 'PP'])
    resultado = listar_secuencia_rio_ventana(momentos, rio, 2)
    assert resultado.tolist() == [
        '-7min PP/OM/CENTRAL_DIESEL; +5min PC/OM/CENTRAL_DIESEL'
    ]


def test_secuencia_sin_instrucciones_es_vacia_y_no_altera_calculos():
    momentos = pd.DataFrame({
        'Central_Relacionada': ['CENTRAL'],
        'Momento': pd.to_datetime(['2026-06-01 10:00']),
        'Config_RIO_Usada_Partida': ['ORIGINAL'],
        'Config_RIO_Usada_Detencion': ['ORIGINAL'],
        'Costo_Partida_Efectivo': [100],
        'Costo_Detencion_Efectivo': [40],
        'Total SC_PD': [140],
    })
    original = momentos.copy(deep=True)
    rio = _rio(['2026-06-01 11:00'], ['PP'])

    resultado = listar_secuencia_rio_ventana(momentos, rio, 2)

    assert resultado.tolist() == ['']
    pd.testing.assert_frame_equal(momentos, original)
