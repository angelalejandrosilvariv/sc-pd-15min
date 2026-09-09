"""Regresiones del parseo de FECHA_HORA en reportes de 15 minutos."""

import sys
from pathlib import Path

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import (leer_reporte, rescatar_config_rio_ventana,
                            validar_meses_reporte)


def test_leer_reporte_conserva_mes_en_fechas_iso_dias_1_a_12(tmp_path):
    ruta = tmp_path / 'Reporte_PD_15min_2606.csv'
    fechas = [f'2026-06-{dia:02d} 10:00:00' for dia in range(1, 13)]
    pd.DataFrame({'FECHA_HORA': fechas}).to_csv(ruta, index=False)

    reporte = leer_reporte(ruta, 'Mes actual')

    assert reporte['FECHA_HORA'].dt.year.eq(2026).all()
    assert reporte['FECHA_HORA'].dt.month.eq(6).all()
    assert reporte['FECHA_HORA'].dt.day.tolist() == list(range(1, 13))


def test_validacion_aborta_si_hay_mas_de_dos_meses(capsys):
    reporte = pd.DataFrame({
        'FECHA_HORA': pd.to_datetime([
            '2026-01-06 10:00:00',
            '2026-02-06 10:00:00',
            '2026-03-06 10:00:00',
        ])
    })

    with pytest.raises(SystemExit, match='3 meses-calendario'):
        validar_meses_reporte(reporte, 'Mes actual')

    alerta = capsys.readouterr().out
    assert 'ALERTA CRITICA' in alerta
    assert '2026-01: 1 filas' in alerta
    assert 'FECHA_HORA_original' in alerta
    assert 'FECHA_HORA_parseada' in alerta


def _caso_rescate_config_rio(desfase_minutos):
    instante = pd.Timestamp('2026-06-15 10:00:00')
    resumen = pd.DataFrame({
        'FECHA_HORA': [instante],
        'Inicio_Ciclo_Global': [instante],
        'Termino_Ciclo_Global': [instante],
        'Central_Relacionada': ['CENTRAL-1'],
        'Configuracion RIO': ['Sin_Registro_RIO'],
        'Fuente_Config_RIO': [pd.NaT],
    })
    rio = pd.DataFrame({
        'FECHA_HORA_RIO': [instante + pd.Timedelta(minutes=desfase_minutos)],
        'Central_Relacionada_RIO': ['CENTRAL-1'],
        'NOMBRE CONFIGURACIÓN': ['CENTRAL-1_GN_A'],
    })
    return resumen, rio


def test_rescata_config_rio_posterior_dentro_de_ventana():
    resumen, rio = _caso_rescate_config_rio(10)

    resultado = rescatar_config_rio_ventana(resumen, rio, activar=1,
                                             ventana_cuartos_hora=2)

    assert resultado.loc[0, 'Configuracion RIO'] == 'CENTRAL-1_GN_A'
    assert resultado.loc[0, 'Fuente_Config_RIO'] == pd.Timestamp('2026-06-15 10:10:00')
    assert bool(resultado.loc[0, 'Config_RIO_Rescatada_Ventana'])


def test_no_rescata_config_rio_fuera_de_ventana():
    resumen, rio = _caso_rescate_config_rio(45)

    resultado = rescatar_config_rio_ventana(resumen, rio, activar=1,
                                             ventana_cuartos_hora=2)

    assert resultado.loc[0, 'Configuracion RIO'] == 'Sin_Registro_RIO'
    assert not bool(resultado.loc[0, 'Config_RIO_Rescatada_Ventana'])


def test_no_rescata_config_rio_con_busqueda_relajada_desactivada():
    resumen, rio = _caso_rescate_config_rio(10)

    resultado = rescatar_config_rio_ventana(resumen, rio, activar=0,
                                             ventana_cuartos_hora=2)

    pd.testing.assert_frame_equal(
        resultado.drop(columns='Config_RIO_Rescatada_Ventana'), resumen)
    assert not bool(resultado.loc[0, 'Config_RIO_Rescatada_Ventana'])
