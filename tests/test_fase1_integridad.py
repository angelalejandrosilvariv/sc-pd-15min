import pandas as pd

from src.fase1_integridad import (calcular_ciclos, costos_clasicos,
                                  deduplicar_rio_priorizando_motivo,
                                  empalmar_reportes, marcar_sin_tarifa_rio)


def _fila(fecha, generacion):
    return {'FECHA_HORA': pd.Timestamp(fecha), 'UNIDAD GENERADORA': 'U1',
            'Central': 'C1', 'CONFIGURACION': 'A', 'GENERACION': generacion,
            'CMg-CV': 2, 'Dolar': 900}


def test_empalme_no_pierde_energia_en_colision():
    pasado = pd.DataFrame([_fila('2026-04-05 00:00', 2), _fila('2026-04-05 00:15', 4)])
    actual = pd.DataFrame([_fila('2026-04-05 00:00', 3), _fila('2026-04-05 00:15', 4)])
    audit = []
    resultado = empalmar_reportes(pasado, actual, audit)
    assert resultado['GENERACION'].sum() == 9
    assert len(resultado) == 2
    assert audit[0]['filas'] == 2 and audit[1]['filas'] == 2


def test_ciclo_cruza_mes():
    fechas = pd.to_datetime(['2026-05-20', '2026-05-20 00:15', '2026-05-30',
                             '2026-06-01', '2026-06-02'], format='mixed')
    df = pd.DataFrame({'FECHA_HORA': fechas, 'Central': 'C1',
                       'GENERACION': [1, 0, 2, 2, 2]})
    _, ciclos = calcular_ciclos(df)
    frontera = ciclos.iloc[-1]
    assert frontera['Inicio_Ciclo'] == pd.Timestamp('2026-05-30')
    assert frontera['Termino_Ciclo'] == pd.Timestamp('2026-06-02')
    assert pd.notna(frontera['Horas_Detenida_Ciclo'])


def test_micro_corte_corta_ciclo():
    df = pd.DataFrame({'FECHA_HORA': pd.date_range('2026-06-01', periods=3, freq='15min'),
                       'Central': 'C1', 'GENERACION': [1, 0, 1]})
    _, ciclos = calcular_ciclos(df, tolerancia_cortes=0)
    assert len(ciclos) == 2


def test_central_sin_registro_rio():
    ciclo = pd.DataFrame({'Configuracion RIO': ['Sin_Registro_RIO'],
                          'Costo_Partida_Efectivo': [500]})
    resultado = marcar_sin_tarifa_rio(ciclo)
    assert resultado.loc[0, 'Config_RIO_Sin_Tarifa']
    assert resultado.loc[0, 'Costo_Partida_Efectivo'] == 0
    assert resultado.loc[0, 'Obs_Partida'].startswith('Revisar manualmente')


def test_prioridad_motivo_no_nulo_en_duplicado_rio():
    rio = pd.DataFrame({'FECHA_HORA_RIO': [pd.Timestamp('2026-06-01')] * 2,
                        'Central_Relacionada_RIO': ['C1', 'C1'],
                        'MOTIVO': ['OM', None]})
    assert deduplicar_rio_priorizando_motivo(rio).loc[0, 'MOTIVO'] == 'OM'


def test_regresion_interruptores_apagados():
    fixture = pd.DataFrame({'Costo_Partida_Base': [100], 'Filtro_Conf_Partida': [1],
                            'Filtro_Disp_Partida': [1], 'Filtro_Op_Partida': [0],
                            'Costo_Detencion_Base': [40], 'Filtro_Conf_Detencion': [1],
                            'Filtro_Disp_Detencion': [1], 'Filtro_Op_Detencion': [1]})
    resultado = costos_clasicos(fixture)
    assert resultado.loc[0, 'Costo_Partida_Efectivo'] == 0
    assert resultado.loc[0, 'Costo_Detencion_Efectivo'] == 40
