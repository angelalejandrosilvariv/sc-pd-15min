import pandas as pd
import pytest

from src.sc_pd_motor_v7 import (
    asignar_observaciones_liquidacion,
    diferir_costos_ciclos_sin_terminar,
)


def _ciclo(estado):
    return pd.DataFrame({
        'Estado_Ciclo_Mes': [estado],
        'Costo_Partida_Base': [120.0],
        'Costo_Detencion_Base': [80.0],
        'Costo_Partida_Efectivo': [120.0],
        'Costo_Detencion_Efectivo': [80.0],
        'Obs_Partida': ['Aprobado'],
        'Obs_Detencion': ['Aprobado'],
    })


def _liquidar(df, activar):
    df, diferidos = diferir_costos_ciclos_sin_terminar(df, activar)
    df['Costos_Totales_PD'] = (
        df['Costo_Partida_Efectivo'] + df['Costo_Detencion_Efectivo'])
    df['Total SC_PD'] = (df['Costos_Totales_PD'] - 50.0).clip(lower=0)
    return asignar_observaciones_liquidacion(df, diferidos, activar)


@pytest.mark.parametrize('estado', ['Continua todo el mes', 'Continua proximo mes'])
def test_difiere_ciclo_que_aun_no_termina(estado):
    resultado = _liquidar(_ciclo(estado), activar=1).iloc[0]

    for columna in [
        'Costo_Partida_Base', 'Costo_Detencion_Base',
        'Costo_Partida_Efectivo', 'Costo_Detencion_Efectivo',
        'Costos_Totales_PD', 'Total SC_PD',
    ]:
        assert resultado[columna] == 0.0
    assert resultado['Obs_Partida'] == 'Diferido: ciclo aun no termina'
    assert resultado['Obs_Detencion'] == 'Diferido: ciclo aun no termina'
    assert resultado['Obs_Liquidacion_Final'].startswith('Diferido:')


@pytest.mark.parametrize('estado', ['Inicia y termina este mes', 'Viene del mes anterior'])
def test_no_modifica_ciclo_terminado(estado):
    resultado = _liquidar(_ciclo(estado), activar=1).iloc[0]

    assert resultado['Costo_Partida_Base'] == 120.0
    assert resultado['Costo_Detencion_Base'] == 80.0
    assert resultado['Costo_Partida_Efectivo'] == 120.0
    assert resultado['Costo_Detencion_Efectivo'] == 80.0
    assert resultado['Costos_Totales_PD'] == 200.0
    assert resultado['Total SC_PD'] == 150.0
    assert resultado['Obs_Partida'] == 'Aprobado'
    assert resultado['Obs_Detencion'] == 'Aprobado'
    assert resultado['Obs_Liquidacion_Final'] == 'Sobrecosto validado a pago'


def test_interruptor_apagado_conserva_comportamiento_anterior():
    resultado = _liquidar(_ciclo('Continua todo el mes'), activar=0).iloc[0]

    assert resultado['Costo_Partida_Efectivo'] == 120.0
    assert resultado['Costo_Detencion_Efectivo'] == 80.0
    assert resultado['Costos_Totales_PD'] == 200.0
    assert resultado['Total SC_PD'] == 150.0
    assert resultado['Obs_Partida'] == 'Aprobado'
    assert resultado['Obs_Detencion'] == 'Aprobado'
    assert resultado['Obs_Liquidacion_Final'] == 'Sobrecosto validado a pago'
