import pandas as pd

from src.fase1_integridad import (calcular_ciclos, clasificar_partida, costos_clasicos,
                                  deduplicar_rio_priorizando_motivo,
                                  empalmar_reportes, filtro_costo_cero,
                                  marcar_sin_tarifa_rio)


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


def test_costo_cero_respeta_fecha_y_mantiene_constantes():
    estados = pd.Series(['SI', 'NO', 'NO', 'SI'])
    centrales = pd.Series(['CHUYACA_DIESEL', 'CHUYACA_DIESEL', 'TERMICA', 'COGEN_X'])
    assert filtro_costo_cero(estados, centrales).tolist() == [0, 1, 1, 0]

    fixture = pd.DataFrame({
        'Costo_Partida_Base': [100, 100], 'Costo_Detencion_Base': [40, 40],
        'Filtro_CostoCero_Partida': [0, 1], 'Filtro_CostoCero_Detencion': [0, 1],
        'Filtro_Conf_Partida': 1, 'Filtro_Disp_Partida': 1, 'Filtro_Op_Partida': 1,
        'Filtro_Conf_Detencion': 1, 'Filtro_Disp_Detencion': 1, 'Filtro_Op_Detencion': 1,
        'Config_RIO_Sin_Tarifa_Partida': False, 'Config_RIO_Sin_Tarifa_Detencion': False,
    })
    resultado = marcar_sin_tarifa_rio(costos_clasicos(fixture), configuracion=None)
    assert resultado['Costo_Partida_Efectivo'].tolist() == [0, 100]
    assert resultado.loc[0, 'Obs_Partida'] == 'Exento: Costo_Cero=SI en la fecha de partida'
    assert resultado.loc[1, 'Obs_Partida'] == 'Aprobado'


def test_cuatro_tramos_partida_clasico_y_rio():
    horas = [100, 50, 200, 10]
    base = pd.DataFrame({
        'Horas_Detenida_Ciclo': horas, 'Fria_Num1_M': 144,
        'Tibia_Num2_N': 72, 'Caliente_Num1_P': 24,
        'Partida_Fria': 50050.688, 'Partida_Tibia': 30838.528,
        'Partida_Tibia_2': 31963.694, 'Partida_Caliente': 18011.61,
    })
    clasico = clasificar_partida(base)
    assert clasico['Tipo_Partida'].tolist() == ['Tibia_2', 'Tibia', 'Fria', 'Caliente']
    assert clasico['Costo_Partida'].tolist() == [31963.694, 30838.528, 50050.688, 18011.61]

    rio = base.rename(columns={c: f'{c}_RIO' for c in base if c != 'Horas_Detenida_Ciclo'})
    rio['Config_RIO_Sin_Tarifa'] = False
    resultado_rio = clasificar_partida(rio, '_RIO')
    assert resultado_rio['Tipo_Partida_RIO'].tolist() == clasico['Tipo_Partida'].tolist()
    assert resultado_rio['Costo_Partida_RIO'].tolist() == clasico['Costo_Partida'].tolist()


def test_sin_umbral_tibia_dos_conserva_clasificacion_anterior():
    base = pd.DataFrame({
        'Horas_Detenida_Ciclo': [100, 10, 200], 'Fria_Num1_M': 144,
        'Tibia_Num2_N': float('nan'), 'Caliente_Num1_P': 24,
        'Partida_Fria': 300, 'Partida_Tibia': 200,
        'Partida_Tibia_2': float('nan'), 'Partida_Caliente': 100,
    })
    resultado = clasificar_partida(base)
    assert resultado['Tipo_Partida'].tolist() == ['Tibia', 'Caliente', 'Fria']
    assert resultado['Costo_Partida'].tolist() == [200, 100, 300]


def test_empalme_sin_mes_anterior_no_pierde_energia():
    actual = pd.DataFrame([
        _fila('2026-04-05 00:00', 2),
        _fila('2026-04-05 00:00', 3),
    ])
    resultado = empalmar_reportes(actual.iloc[0:0], actual)
    assert resultado['GENERACION'].sum() == 5
    assert len(resultado) == 1
