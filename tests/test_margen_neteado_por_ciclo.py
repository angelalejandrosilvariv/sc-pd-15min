"""Pruebas del interruptor MARGEN_NETEADO_POR_CICLO.

El criterio 0 (default) trunca el margen bloque a bloque, igual que el modelo
horario. El criterio 1 deja que los bloques negativos compensen dentro del ciclo
y trunca recien el total agregado.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import (calcular_margen_bloques, columnas_resumen_ciclos,
                            compactar_resumen_ciclos)


def _bloques(margenes):
    """Un ciclo de N bloques con el margen ya calculado que se le indique."""
    tiempos = pd.date_range('2026-06-01 01:00', periods=len(margenes), freq='15min')
    constantes = {
        'Etiqueta_Relacionada': 'CENTRAL&1', 'Central_Relacionada': 'CENTRAL',
        'Ciclo_ID_Relacionada': 1, 'Horas_Detenida_Ciclo': 12.0,
        'Flag_Exencion': False, 'Central': 'CONFIG_BASE', 'Tipo_Partida': 'Fria',
        'Fria_Num1_M': 20, 'Tibia_Num1_O': 10, 'Tibia_Num2_N': 8,
        'Caliente_Num1_P': 4, 'Partida_Fria': 100, 'Partida_Tibia': 80,
        'Partida_Tibia_2': 70, 'Partida_Caliente': 50,
        'Filtro_CostoCero_Partida': 1, 'Filtro_CostoCero_Detencion': 1,
        'Conf despachada RIO': 1, 'Disponible (1) / Pruebas (0)': 1,
        'Filtro_Operacional': 1, 'CONSIGNAS': 'SSCC', 'MOTIVO': 'Operacion',
        'ESTADO OPERACIONAL': 'PDO', 'Fuente_Config_RIO': tiempos[0],
        'Config_RIO_Rescatada_Ventana': False, 'Estado_Ciclo_Mes': 'Completo',
        'Config_RIO_Corregida_Mezcla': False,
    }
    return pd.DataFrame([
        dict(constantes, FECHA_HORA=t, GENERACION=1, Margen=m, Detencion=15,
             Costo_Partida_ML=70000, Costo_Detencion_ML=15000)
        for t, m in zip(tiempos, margenes)
    ])


# --- criterio 0: se preserva el comportamiento actual ---------------------------

def test_por_bloque_es_el_default_y_no_deja_pasar_negativos():
    reporte = pd.DataFrame({
        'CMg': [100.0, 30.0], 'CV': [40.0, 40.0],
        'Dolar': [900.0, 900.0], 'GENERACION': [2.0, 5.0],
    })

    por_defecto = calcular_margen_bloques(reporte, calcular_en_motor=1)
    explicito = calcular_margen_bloques(reporte, calcular_en_motor=1,
                                        netear_por_ciclo=0)

    np.testing.assert_array_equal(por_defecto, explicito)
    np.testing.assert_array_equal(por_defecto, [(100 - 40) * 900 * 2, 0])


def test_por_bloque_no_expone_la_columna_de_auditoria():
    resumen = compactar_resumen_ciclos(_bloques([100.0, -40.0]),
                                       usar_tarifa_rio_instruida=0)

    assert 'Margen_Neto_Ciclo' not in resumen.columns
    assert 'Margen_Neto_Ciclo' not in columnas_resumen_ciclos(0, 1)


# --- criterio 1: el bloque negativo compensa dentro del ciclo -------------------

def test_neteado_conserva_el_signo_del_bloque():
    reporte = pd.DataFrame({
        'CMg': [100.0, 30.0], 'CV': [40.0, 40.0],
        'Dolar': [900.0, 900.0], 'GENERACION': [2.0, 5.0],
    })

    resultado = calcular_margen_bloques(reporte, calcular_en_motor=1,
                                        netear_por_ciclo=1)

    np.testing.assert_array_equal(
        resultado, [(100 - 40) * 900 * 2, (30 - 40) * 900 * 5])


def test_neteado_compensa_dentro_del_ciclo_y_no_baja_de_cero():
    # +100 y -40 se compensan: el ciclo autocubrio 60, no 100.
    resumen = compactar_resumen_ciclos(_bloques([100.0, -40.0]),
                                       usar_tarifa_rio_instruida=0,
                                       netear_por_ciclo=1)
    ciclo = resumen.iloc[0]

    assert ciclo['Margen_Neto_Ciclo'] == 60
    assert ciclo['Margen_Suma_Ciclo'] == 60


def test_ciclo_con_margen_neto_negativo_se_trunca_pero_queda_trazable():
    # Sin el MAX(0), el ciclo cobraria su costo P-D mas la perdida en energia.
    resumen = compactar_resumen_ciclos(_bloques([20.0, -90.0]),
                                       usar_tarifa_rio_instruida=0,
                                       netear_por_ciclo=1)
    ciclo = resumen.iloc[0]

    assert ciclo['Margen_Neto_Ciclo'] == -70
    assert ciclo['Margen_Suma_Ciclo'] == 0


def test_neteado_exporta_el_neto_firmado_junto_al_margen():
    columnas = columnas_resumen_ciclos(0, 1, netear_por_ciclo=1)

    assert 'Margen_Neto_Ciclo' in columnas
    assert (columnas.index('Margen_Neto_Ciclo')
            == columnas.index('Margen_Suma_Ciclo') + 1)


# --- la diferencia entre criterios es exactamente el bloque negativo ------------

def test_los_dos_criterios_solo_difieren_cuando_hay_bloques_negativos():
    solo_positivos = [30.0, 10.0]
    por_bloque = compactar_resumen_ciclos(
        _bloques(solo_positivos), usar_tarifa_rio_instruida=0).iloc[0]
    neteado = compactar_resumen_ciclos(
        _bloques(solo_positivos), usar_tarifa_rio_instruida=0,
        netear_por_ciclo=1).iloc[0]

    assert por_bloque['Margen_Suma_Ciclo'] == neteado['Margen_Suma_Ciclo'] == 40
