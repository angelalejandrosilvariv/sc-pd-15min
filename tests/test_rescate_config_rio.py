import pandas as pd
import pytest

from src.sc_pd_motor_v7 import rescatar_config_rio_en_limites


def _caso(desfase_minutos):
    instante = pd.Timestamp('2026-06-10 08:00:00')
    resumen = pd.DataFrame({
        'FECHA_HORA': [instante],
        'Inicio_Ciclo_Global': [instante],
        'Termino_Ciclo_Global': [instante + pd.Timedelta(hours=1)],
        'Central_Relacionada': ['CENTRAL_A'],
        'Configuracion RIO': ['Sin_Registro_RIO'],
        'Fuente_Config_RIO': [pd.NaT],
    })
    rio = pd.DataFrame({
        'FECHA_HORA_RIO': [instante + pd.Timedelta(minutes=desfase_minutos)],
        'Central_Relacionada_RIO': ['CENTRAL_A'],
        'NOMBRE CONFIGURACIÓN': ['CENTRAL_A_CC'],
    })
    return resumen, rio


def test_rescata_configuracion_posterior_dentro_de_ventana():
    resumen, rio = _caso(10)

    resultado = rescatar_config_rio_en_limites(resumen, rio, activar=1,
                                                ventana_cuartos_hora=2)

    assert resultado.loc[0, 'Configuracion RIO'] == 'CENTRAL_A_CC'
    assert resultado.loc[0, 'Fuente_Config_RIO'] == rio.loc[0, 'FECHA_HORA_RIO']
    assert resultado.loc[0, 'Config_RIO_Rescatada_Ventana'] == True


@pytest.mark.parametrize('desfase,activar', [(45, 1), (10, 0)])
def test_no_rescata_fuera_de_ventana_o_con_interruptor_apagado(desfase, activar):
    resumen, rio = _caso(desfase)

    resultado = rescatar_config_rio_en_limites(resumen, rio, activar=activar,
                                                ventana_cuartos_hora=2)

    assert resultado.loc[0, 'Configuracion RIO'] == 'Sin_Registro_RIO'
    assert pd.isna(resultado.loc[0, 'Fuente_Config_RIO'])
    assert resultado.loc[0, 'Config_RIO_Rescatada_Ventana'] == False
