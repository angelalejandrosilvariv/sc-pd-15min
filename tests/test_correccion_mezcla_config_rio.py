import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import corregir_mezcla_configuraciones_rio


def _caso(registros, configuracion_actual='CONFIG_HERMANA'):
    instante = pd.Timestamp('2026-06-26 23:00:00')
    resumen = pd.DataFrame({
        'FECHA_HORA': [instante],
        'Inicio_Ciclo_Global': [instante],
        'Termino_Ciclo_Global': [instante + pd.Timedelta(hours=1)],
        'Central_Relacionada': ['KELAR-TG12'],
        'Central': ['KELAR-TG1_TG1_DIESEL'],
        'Configuracion RIO': [configuracion_actual],
        'Fuente_Config_RIO': [instante - pd.Timedelta(minutes=22)],
        'CONSIGNAS': ['PP'],
        'MOTIVO': ['OM'],
    })
    rio = pd.DataFrame({
        'FECHA_HORA_RIO': [instante + pd.Timedelta(minutes=minutos)
                           for minutos, _ in registros],
        'Central_Relacionada_RIO': ['KELAR-TG12'] * len(registros),
        'NOMBRE CONFIGURACIÓN': [config for _, config in registros],
    })
    return resumen, rio


def test_corrige_config_hermana_por_config_exacta_mas_cercana():
    resumen, rio = _caso([
        (-22, 'KELAR-TG1_TG1+0.5TV_DIESEL'),
        (1, 'KELAR-TG1_TG1_DIESEL'),
        (10, 'KELAR-TG1_TG1_DIESEL'),
    ])

    resultado = corregir_mezcla_configuraciones_rio(resumen, rio, 1, 2)

    assert resultado.loc[0, 'Configuracion RIO'] == 'KELAR-TG1_TG1_DIESEL'
    assert resultado.loc[0, 'Fuente_Config_RIO'] == rio.loc[1, 'FECHA_HORA_RIO']
    assert resultado.loc[0, 'Config_RIO_Corregida_Mezcla'] == True
    assert resultado.loc[0, 'CONSIGNAS'] == 'PP'
    assert resultado.loc[0, 'MOTIVO'] == 'OM'


@pytest.mark.parametrize('registros,activar', [
    ([(-10, 'CONFIG_DISTINTA')], 1),
    ([(31, 'KELAR-TG1_TG1_DIESEL')], 1),
    ([(1, 'KELAR-TG1_TG1_DIESEL')], 0),
])
def test_conserva_fila_sin_candidato_valido_o_interruptor(registros, activar):
    resumen, rio = _caso(registros)

    resultado = corregir_mezcla_configuraciones_rio(resumen, rio, activar, 2)

    pd.testing.assert_series_equal(
        resultado.drop(columns='Config_RIO_Corregida_Mezcla').loc[0],
        resumen.loc[0],
    )
    assert resultado.loc[0, 'Config_RIO_Corregida_Mezcla'] == False


def test_configuracion_ya_exacta_conserva_valor_y_actualiza_fuente_cercana():
    resumen, rio = _caso(
        [(-5, 'KELAR-TG1_TG1_DIESEL')],
        configuracion_actual='KELAR-TG1_TG1_DIESEL',
    )

    resultado = corregir_mezcla_configuraciones_rio(resumen, rio, 1, 2)

    assert resultado.loc[0, 'Configuracion RIO'] == resumen.loc[0, 'Configuracion RIO']
    assert resultado.loc[0, 'Fuente_Config_RIO'] == rio.loc[0, 'FECHA_HORA_RIO']
    assert resultado.loc[0, 'Config_RIO_Corregida_Mezcla'] == True
