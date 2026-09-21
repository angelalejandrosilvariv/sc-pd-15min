"""Casos sinteticos de la excepcion para partidas sincronizadas en EP (spec 33)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from fase1_integridad import costos_clasicos
from sc_pd_motor_v7 import (aplicar_partida_en_pruebas, columnas_resumen_ciclos,
                            crear_guia_lectura, validar_partida_en_pruebas)


T0 = pd.Timestamp('2026-08-23 00:45')


def _compacto():
    return pd.DataFrame([{
        'Etiqueta_Relacionada': 'GUACOLDA-1&1', 'Central_Relacionada': 'GUACOLDA-1',
        'Inicio_Ciclo': T0, 'Termino_Ciclo': T0 + pd.Timedelta(hours=9),
        'Consigna_Partida': 'EP', 'Motivo_Partida': 'EP', 'Estado_Op_Partida': 'PO',
        'Comentario_Partida': 'E/S en pruebas', 'Fuente_Filtros_RIO_Partida': T0,
        'Fuente_Config_RIO_Partida': T0, 'Filtro_Conf_Partida': 1,
        'Filtro_Disp_Partida': 0, 'Filtro_Op_Partida': 1, 'Vigencia_RIO_Partida': 1,
        'Filtro_CostoCero_Partida': 1, 'Costo_Partida_Base': 1000,
        'Filtro_Conf_Detencion': 1, 'Filtro_Disp_Detencion': 1,
        'Filtro_Op_Detencion': 1, 'Filtro_CostoCero_Detencion': 1,
        'Costo_Detencion_Base': 75,
    }])


def _rio(orden_h=-25, disponible_h=4, motivo_disp='OM', comentario_disp='cancela IF'):
    filas = [
        (T0 + pd.Timedelta(hours=orden_h), 'PP', 'OM', 'DRO', ''),
        (T0, 'EP', 'EP', 'PO', 'E/S en pruebas'),
    ]
    if disponible_h is not None:
        filas.append((T0 + pd.Timedelta(hours=disponible_h), 'MT', motivo_disp, 'RO', comentario_disp))
    return pd.DataFrame(filas, columns=['FECHA_HORA_RIO', 'CONSIGNAS', 'MOTIVO',
                                        'ESTADO OPERACIONAL', 'COMENTARIO']).assign(
        Central_Relacionada_RIO='GUACOLDA-1')


def _reporte(generacion_entre=0):
    return pd.DataFrame({'FECHA_HORA': [T0 - pd.Timedelta(hours=12)],
                         'Central_Relacionada': ['GUACOLDA-1'],
                         'GENERACION': [generacion_entre]})


def _aplicar(modo, rio=None, generacion=0):
    return aplicar_partida_en_pruebas(_compacto(), rio if rio is not None else _rio(),
                                      _reporte(generacion), modo)


def test_1_valor_invalido_aborta():
    with pytest.raises(SystemExit, match='PARTIDA_EN_PRUEBAS'):
        validar_partida_en_pruebas('inventado')


def test_2_rechazar_conserva_rechazo_y_columnas_vacias():
    resultado, diagnostico = _aplicar('rechazar')
    assert resultado.loc[0, 'Filtro_Disp_Partida'] == 0
    assert diagnostico.loc[0, ['Cumple_D', 'Cumple_O']].all()
    columnas = ['Partida_En_Pruebas_Validada', 'Orden_Partida_Fallida', 'Disponible_OM_Desde',
                'Consigna_Reingreso_Pruebas', 'Fuente_Reingreso_Pruebas',
                'Comentario_Reingreso_Pruebas']
    assert resultado[columnas].replace('', pd.NA).isna().all().all()


def test_3_orden_om_fallida_valida_y_no_cambia_detencion():
    resultado, _ = _aplicar('validar_orden_om_fallida')
    assert resultado.loc[0, ['Filtro_Disp_Partida', 'Filtro_Op_Partida',
                             'Vigencia_RIO_Partida']].eq(1).all()
    assert resultado.loc[0, 'Consigna_Partida'] == 'PP'
    assert resultado.loc[0, 'Motivo_Partida'] == 'OM'
    assert resultado.loc[0, 'Consigna_Reingreso_Pruebas'] == 'EP'
    costos = costos_clasicos(resultado)
    assert costos.loc[0, 'Costo_Partida_Efectivo'] == 1000
    assert costos.loc[0, 'Costo_Detencion_Efectivo'] == 75


def test_4_generacion_previa_bloquea_orden_pero_no_variante_disponible():
    por_orden, _ = _aplicar('validar_orden_om_fallida', generacion=1)
    por_disp, _ = _aplicar('validar_si_queda_disponible_om', generacion=1)
    assert por_orden.loc[0, 'Filtro_Disp_Partida'] == 0
    assert por_disp.loc[0, 'Filtro_Disp_Partida'] == 1


def test_5_pruebas_puras_sin_disponibilidad_no_validan():
    rio = _rio(disponible_h=None)
    for modo in ('validar_orden_om_fallida', 'validar_si_queda_disponible_om'):
        resultado, _ = _aplicar(modo, rio=rio)
        assert resultado.loc[0, 'Filtro_Disp_Partida'] == 0


def test_6_orden_fuera_de_48_horas_no_valida():
    resultado, _ = _aplicar('validar_orden_om_fallida', rio=_rio(orden_h=-49))
    assert resultado.loc[0, 'Filtro_Disp_Partida'] == 0


def test_7_disponibilidad_posterior_al_ciclo_no_cuenta():
    resultado, _ = _aplicar('validar_si_queda_disponible_om', rio=_rio(disponible_h=10))
    assert resultado.loc[0, 'Filtro_Disp_Partida'] == 0


def test_8_ot_solo_cuenta_con_sscc_o_servicio_equivalente():
    valido, _ = _aplicar('validar_si_queda_disponible_om',
                         rio=_rio(motivo_disp='OT', comentario_disp='Servicio SSCC'))
    invalido, _ = _aplicar('validar_si_queda_disponible_om',
                           rio=_rio(motivo_disp='OT', comentario_disp='mantencion'))
    assert valido.loc[0, 'Filtro_Disp_Partida'] == 1
    assert invalido.loc[0, 'Filtro_Disp_Partida'] == 0


def test_9_export_ubica_y_documenta_las_seis_columnas():
    columnas = columnas_resumen_ciclos(0, 0)
    nuevas = ['Partida_En_Pruebas_Validada', 'Orden_Partida_Fallida', 'Disponible_OM_Desde',
              'Consigna_Reingreso_Pruebas', 'Fuente_Reingreso_Pruebas',
              'Comentario_Reingreso_Pruebas']
    assert columnas[columnas.index('Costo_Partida_Efectivo') - 6:
                    columnas.index('Costo_Partida_Efectivo')] == nuevas
    guia = ' '.join(crear_guia_lectura()['Columna'].astype(str))
    assert all(columna in guia for columna in nuevas)


def test_10_la_generacion_de_otras_centrales_no_bloquea_la_orden_fallida():
    # En el motor el reporte completo trae todas las centrales: solo la generacion de
    # la relacionada del ciclo puede desmentir que la orden no sincronizo.
    reporte = pd.DataFrame({'FECHA_HORA': [T0 - pd.Timedelta(hours=12)] * 2,
                            'Central_Relacionada': ['GUACOLDA-1', 'OTRA'],
                            'GENERACION': [0.0, 250.0]})
    df, diag = aplicar_partida_en_pruebas(_compacto(), _rio(), reporte, 'validar_orden_om_fallida')
    assert bool(diag['Cumple_O'].iloc[0]) and df['Partida_En_Pruebas_Validada'].iloc[0] == 'orden OM fallida'


def test_11_sin_central_relacionada_en_el_reporte_aborta_en_vez_de_callar():
    reporte = pd.DataFrame({'FECHA_HORA': [T0 - pd.Timedelta(hours=12)], 'GENERACION': [0.0]})
    with pytest.raises(SystemExit):
        aplicar_partida_en_pruebas(_compacto(), _rio(), reporte, 'validar_orden_om_fallida')
