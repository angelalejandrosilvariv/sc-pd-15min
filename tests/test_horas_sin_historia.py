import numpy as np
import pandas as pd

from fase1_integridad import clasificar_partida, horas_cota_inferior
from sc_pd_motor_v7 import columnas_resumen_ciclos, crear_guia_lectura


def _fila(horas, cota):
    return pd.DataFrame({
        'Horas_Detenida_Ciclo': [horas], 'Horas_Cota_Inferior': [cota],
        'Fria_Num1_M': [24.0], 'Tibia_Num2_N': [12.0],
        'Caliente_Num1_P': [4.0], 'Partida_Fria': [313210.0],
        'Partida_Tibia_2': [200000.0], 'Partida_Tibia': [100000.0],
        'Partida_Caliente': [50000.0],
    })


def test_cota_mayor_que_umbral_clasifica_fria():
    resultado = clasificar_partida(
        _fila(np.nan, 48 * 24), horas_sin_historia='cota_inferior').iloc[0]
    assert resultado['Tipo_Partida'] == 'Fria'
    assert resultado['Costo_Partida'] == 313210.0
    assert bool(resultado['Horas_Detenida_Estimada'])


def test_cota_menor_que_umbral_mantiene_no_aplica():
    resultado = clasificar_partida(
        _fila(np.nan, 20.0), horas_sin_historia='cota_inferior').iloc[0]
    assert resultado['Tipo_Partida'] == 'No_Aplica'
    assert resultado['Costo_Partida'] == 0
    assert not bool(resultado['Horas_Detenida_Estimada'])


def test_nulo_es_identico_al_comportamiento_anterior():
    actual = clasificar_partida(_fila(np.nan, 100.0))
    nulo = clasificar_partida(_fila(np.nan, 100.0), horas_sin_historia='nulo')
    pd.testing.assert_frame_equal(actual, nulo)
    assert nulo.loc[0, 'Tipo_Partida'] == 'No_Aplica'


def test_ciclo_anterior_no_cambia_horas_ni_clasificacion():
    cota = horas_cota_inferior(
        pd.Timestamp('2026-08-18'), pd.Timestamp('2026-07-01'), 10.0)
    assert np.isnan(cota)
    resultado = clasificar_partida(
        _fila(10.0, np.nan), horas_sin_historia='cota_inferior').iloc[0]
    assert resultado['Tipo_Partida'] == 'Tibia'
    assert not bool(resultado['Horas_Detenida_Estimada'])


def test_columnas_y_guia_exportan_la_trazabilidad():
    columnas = columnas_resumen_ciclos(0, 1)
    assert columnas[columnas.index('Horas_Detenida_Ciclo') + 1:
                    columnas.index('Horas_Detenida_Ciclo') + 3] == [
                        'Horas_Cota_Inferior', 'Horas_Detenida_Estimada']
    assert crear_guia_lectura()['Columna'].str.contains('Horas_Cota_Inferior').any()


def test_cota_vectorizada_sobre_series_del_motor():
    # main() la llama con Series: Inicio_Ciclo_Global por bloque y Horas_Detenida_Ciclo.
    inicio = pd.Series(pd.to_datetime(['2026-08-18 06:45', '2026-08-18 06:45', '2026-08-23 20:45']))
    horas = pd.Series([np.nan, np.nan, 133.0])

    cota = horas_cota_inferior(inicio, pd.Timestamp('2026-07-01'), horas)

    assert cota.iloc[0] == cota.iloc[1] == 48 * 24 + 6.75
    assert np.isnan(cota.iloc[2])
    assert cota.index.equals(horas.index)
