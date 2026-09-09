"""Regresiones de la trazabilidad exportada por ciclo."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import (columnas_resumen_ciclos, compactar_resumen_ciclos,
                            crear_guia_lectura)


def test_resumen_ciclo_exporta_insumos_base_y_rio(tmp_path):
    tiempos = pd.to_datetime(['2026-06-01 01:00', '2026-06-01 01:15'])
    constantes = {
        'Etiqueta_Relacionada': 'CENTRAL&1', 'Central_Relacionada': 'CENTRAL',
        'Ciclo_ID_Relacionada': 1, 'Horas_Detenida_Ciclo': 12.0,
        'Flag_Exencion': False, 'Central': 'CONFIG_BASE', 'Tipo_Partida': 'Tibia_2',
        'Fria_Num1_M': 20, 'Tibia_Num1_O': 10, 'Tibia_Num2_N': 8,
        'Caliente_Num1_P': 4, 'Partida_Fria': 100, 'Partida_Tibia': 80,
        'Partida_Tibia_2': 70, 'Partida_Caliente': 50,
        'Filtro_CostoCero_Partida': 1, 'Filtro_CostoCero_Detencion': 1,
        'Conf despachada RIO': 1, 'Disponible (1) / Pruebas (0)': 1,
        'Filtro_Operacional': 1, 'CONSIGNAS': 'SSCC', 'MOTIVO': 'Operacion',
        'ESTADO OPERACIONAL': 'PDO', 'Fuente_Config_RIO': tiempos[0],
        'Config_RIO_Rescatada_Ventana': False, 'Estado_Ciclo_Mes': 'Completo',
        'Config_RIO_Corregida_Mezcla': False,
        'Tipo_Partida_RIO': 'Tibia_2', 'Fria_Num1_M_RIO': 22,
        'Tibia_Num2_N_RIO': 9, 'Caliente_Num1_P_RIO': 3,
        'Partida_Fria_RIO': 110, 'Partida_Tibia_RIO': 90,
        'Partida_Tibia_2_RIO': 75, 'Partida_Caliente_RIO': 55,
    }
    bloques = pd.DataFrame([
        dict(constantes, FECHA_HORA=tiempos[0], GENERACION=5, Margen=20,
             Detencion=15, Detencion_RIO=17, Costo_Partida_ML=70000,
             Costo_Detencion_ML=15000),
        dict(constantes, FECHA_HORA=tiempos[1], GENERACION=7, Margen=30,
             Detencion=16, Detencion_RIO=18, Costo_Partida_ML=71000,
             Costo_Detencion_ML=16000),
    ])

    resumen = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=1)
    ciclo = resumen.iloc[0]
    assert ciclo['Tipo_Partida'] == ciclo['Tipo_Partida_RIO'] == 'Tibia_2'
    assert ciclo['Partida_Tibia_2'] == 70
    assert ciclo['Partida_Tibia_2_RIO'] == 75
    assert ciclo['Detencion_Tarifa'] == 16
    assert ciclo['Detencion_Tarifa_RIO'] == 18
    assert ciclo['Costo_Partida_Base'] == 70000
    assert ciclo['Costo_Detencion_Base'] == 16000

    columnas = columnas_resumen_ciclos(0, 1)
    for columna in columnas:
        if columna not in resumen:
            resumen[columna] = 0
    ruta = tmp_path / 'resultado.xlsx'
    with pd.ExcelWriter(ruta, engine='xlsxwriter') as writer:
        crear_guia_lectura().to_excel(writer, sheet_name='Guia_Lectura', index=False)
        resumen[columnas].to_excel(writer, sheet_name='Resumen_Ciclos_PD', index=False)

    exportado = pd.read_excel(ruta, sheet_name='Resumen_Ciclos_PD')
    assert list(exportado.columns) == columnas
    assert exportado.loc[0, 'Partida_Tibia_2_RIO'] == 75
    guia = pd.read_excel(ruta, sheet_name='Guia_Lectura')
    assert guia['Que significa'].str.contains('Total SC_PD = MAX', regex=False).any()


def test_compactacion_sin_tarifa_rio_no_exige_columnas_rio():
    # La ausencia de columnas _RIO no debe afectar el interruptor apagado.
    fila = {
        origen: [0]
        for origen in {
            'FECHA_HORA', 'GENERACION', 'Margen', 'Horas_Detenida_Ciclo', 'Flag_Exencion',
            'Central', 'Tipo_Partida', 'Fria_Num1_M', 'Tibia_Num1_O', 'Tibia_Num2_N',
            'Caliente_Num1_P', 'Partida_Fria', 'Partida_Tibia', 'Partida_Tibia_2',
            'Partida_Caliente', 'Detencion', 'Costo_Partida_ML', 'Costo_Detencion_ML',
            'Filtro_CostoCero_Partida', 'Filtro_CostoCero_Detencion', 'Conf despachada RIO',
            'Disponible (1) / Pruebas (0)', 'Filtro_Operacional', 'CONSIGNAS', 'MOTIVO',
            'ESTADO OPERACIONAL', 'Fuente_Config_RIO', 'Config_RIO_Rescatada_Ventana',
            'Config_RIO_Corregida_Mezcla',
            'Estado_Ciclo_Mes',
        }
    }
    fila.update({'Etiqueta_Relacionada': ['C&1'], 'Central_Relacionada': ['C'],
                 'Ciclo_ID_Relacionada': [1]})
    resultado = compactar_resumen_ciclos(pd.DataFrame(fila), 0)
    assert 'Tipo_Partida_RIO' not in resultado.columns
