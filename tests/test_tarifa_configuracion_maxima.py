"""Pruebas del interruptor TARIFA_CONFIGURACION.

'instruida' conserva el comportamiento previo (tarifa del primer/ultimo bloque,
que 14.1b reemplaza por la configuracion instruida por el RIO). 'maxima' cobra
la tarifa mas cara entre las configuraciones que generaron en el ciclo, que es
la regla del modelo horario.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import (columnas_resumen_ciclos, combustible_configuracion,
                            compactar_resumen_ciclos, tarifa_configuracion_maxima)


def _bloques(configs, partidas, detenciones=None, costo_cero=None, ciclo=1):
    """Un ciclo cuyos bloques van cambiando de configuracion y de tarifa."""
    n = len(configs)
    detenciones = detenciones or [15000] * n
    costo_cero = costo_cero or [1] * n
    tiempos = pd.date_range('2026-06-01 01:00', periods=n, freq='15min')
    filas = []
    for i in range(n):
        filas.append({
            'Etiqueta_Relacionada': f'CENTRAL&{ciclo}', 'Central_Relacionada': 'CENTRAL',
            'Ciclo_ID_Relacionada': ciclo, 'FECHA_HORA': tiempos[i], 'GENERACION': 1.0,
            'Margen': 0.0, 'Horas_Detenida_Ciclo': 12.0, 'Flag_Exencion': False,
            'Central': configs[i], 'Tipo_Partida': 'Fria',
            'Fria_Num1_M': 20 + i, 'Tibia_Num1_O': 10, 'Tibia_Num2_N': 8, 'Caliente_Num1_P': 4,
            'Partida_Fria': partidas[i] / 900, 'Partida_Tibia': 80, 'Partida_Tibia_2': 70,
            'Partida_Caliente': 50, 'Detencion': detenciones[i] / 900,
            'Costo_Partida_ML': partidas[i], 'Costo_Detencion_ML': detenciones[i],
            'Filtro_CostoCero_Partida': costo_cero[i], 'Filtro_CostoCero_Detencion': costo_cero[i],
            'Conf despachada RIO': 1, 'Disponible (1) / Pruebas (0)': 1, 'Filtro_Operacional': 1,
            'CONSIGNAS': 'SSCC', 'MOTIVO': 'OM', 'ESTADO OPERACIONAL': 'PDO',
            'Fuente_Config_RIO': tiempos[0], 'Config_RIO_Rescatada_Ventana': False,
            'Config_RIO_Corregida_Mezcla': False, 'Estado_Ciclo_Mes': 'Inicia y termina este mes',
        })
    return pd.DataFrame(filas)


# --- 'instruida' es el comportamiento previo -----------------------------------

def test_instruida_es_el_default_y_toma_primer_y_ultimo_bloque():
    bloques = _bloques(['TG', 'TG+TV', 'TG'], partidas=[70000, 250000, 70000],
                       detenciones=[15000, 40000, 15000])

    por_defecto = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0)
    explicito = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0,
                                         tarifa_configuracion='instruida')

    pd.testing.assert_frame_equal(por_defecto, explicito)
    assert por_defecto.iloc[0]['Costo_Partida_Base'] == 70000
    assert por_defecto.iloc[0]['Costo_Detencion_Base'] == 15000
    assert 'Config_Tarifa_Partida' not in por_defecto.columns


def test_instruida_no_exporta_las_columnas_de_auditoria_de_maxima():
    columnas = columnas_resumen_ciclos(0, 1)

    assert 'Config_Tarifa_Partida' not in columnas
    assert 'Configs_En_Ciclo' not in columnas
    assert 'Costo_Partida_RIO_Instruida' not in columnas


def test_valor_invalido_aborta():
    with pytest.raises(SystemExit):
        compactar_resumen_ciclos(_bloques(['TG'], [70000]), usar_tarifa_rio_instruida=0,
                                 tarifa_configuracion='dominante')


# --- 'maxima' cobra la configuracion mas cara del ciclo --------------------------

def test_maxima_elige_la_tarifa_mas_cara_aunque_dure_un_solo_bloque():
    # La turbina parte sola (barata), el vapor entra un cuarto de hora y se va.
    bloques = _bloques(['TG', 'TG+TV', 'TG'], partidas=[70000, 250000, 70000],
                       detenciones=[15000, 40000, 15000])

    ciclo = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0,
                                     tarifa_configuracion='maxima').iloc[0]

    assert ciclo['Costo_Partida_Base'] == 250000
    assert ciclo['Config_Tarifa_Partida'] == 'TG+TV'
    assert ciclo['Costo_Detencion_Base'] == 40000
    assert ciclo['Config_Tarifa_Detencion'] == 'TG+TV'
    assert ciclo['Configs_En_Ciclo'] == 2
    # Lo que habria cobrado el primer/ultimo bloque queda trazable.
    assert ciclo['Costo_Partida_Base_Original'] == 70000
    assert ciclo['Costo_Detencion_Base_Original'] == 15000


def test_maxima_arrastra_los_umbrales_de_la_configuracion_ganadora():
    # Fria_Num1_M vale 20 en el bloque 0 y 21 en el bloque 1 (ver _bloques).
    bloques = _bloques(['TG', 'TG+TV'], partidas=[70000, 250000])

    ciclo = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0,
                                     tarifa_configuracion='maxima').iloc[0]

    assert ciclo['Fria_Num1_M'] == 21
    assert ciclo['Partida_Fria'] == 250000 / 900


def test_maxima_con_una_sola_configuracion_es_identica_a_instruida():
    bloques = _bloques(['TG', 'TG', 'TG'], partidas=[70000, 70000, 70000])

    instruida = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0).iloc[0]
    maxima = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0,
                                      tarifa_configuracion='maxima').iloc[0]

    assert maxima['Costo_Partida_Base'] == instruida['Costo_Partida_Base']
    assert maxima['Costo_Detencion_Base'] == instruida['Costo_Detencion_Base']
    assert maxima['Configs_En_Ciclo'] == 1
    assert maxima['Config_Tarifa_Partida'] == 'TG'


def test_maxima_no_deja_ganar_a_una_configuracion_exenta_por_costo_cero():
    # La COGEN tiene la tarifa mas alta pero su filtro la anula: no puede ganar.
    bloques = _bloques(['TG', 'TG_COGEN'], partidas=[70000, 900000], costo_cero=[1, 0])

    ciclo = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0,
                                     tarifa_configuracion='maxima').iloc[0]

    assert ciclo['Config_Tarifa_Partida'] == 'TG'
    assert ciclo['Costo_Partida_Base'] == 70000
    assert ciclo['Filtro_CostoCero_Partida'] == 1


def test_combustible_de_la_configuracion_trata_diesel_como_un_combustible_mas():
    configs = pd.Series(['NUEVARENCA_TG1+TV1_GN_A', 'NUEVARENCA_TG1+TV1_DIESEL',
                         'TOCOPILLA-U16_TG1_GNL_C', 'QUINTERO-1', 'Sin_Registro_RIO'])

    assert combustible_configuracion(configs).tolist() == ['GN_A', 'DIESEL', 'GNL_C', '', '']


def test_maxima_solo_compite_el_combustible_instruido_por_el_rio():
    # La DIESEL es la mas cara, pero el RIO instruyo gas en la apertura: no puede
    # fijar la tarifa (columna AG del horario). Entre las de gas, gana la mas cara.
    bloques = _bloques(['TG_GN_A', 'TG_DIESEL', 'TG+TV_GN_A'], partidas=[70000, 900000, 250000])
    bloques['Configuracion RIO'] = 'TG_GN_A'

    ciclo = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0,
                                     tarifa_configuracion='maxima').iloc[0]

    assert ciclo['Config_Tarifa_Partida'] == 'TG+TV_GN_A'
    assert ciclo['Costo_Partida_Base'] == 250000
    assert not ciclo['Excluida_Combustible_Partida']


def test_maxima_sin_instruccion_rio_compiten_todas_las_configuraciones():
    bloques = _bloques(['TG_GN_A', 'TG_DIESEL'], partidas=[70000, 900000])
    bloques['Configuracion RIO'] = 'Sin_Registro_RIO'

    ciclo = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0,
                                     tarifa_configuracion='maxima').iloc[0]

    assert ciclo['Config_Tarifa_Partida'] == 'TG_DIESEL'
    assert ciclo['Costo_Partida_Base'] == 900000


def test_maxima_marca_el_ciclo_cuyo_combustible_instruido_no_aparece():
    # El RIO instruyo GNL_B y el ciclo solo genero con DIESEL: queda en 0, como
    # en el horario, pero trazable.
    bloques = _bloques(['TG_DIESEL', 'TG+TV_DIESEL'], partidas=[70000, 250000])
    bloques['Configuracion RIO'] = 'TG_GNL_B'

    ciclo = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0,
                                     tarifa_configuracion='maxima').iloc[0]

    assert ciclo['Costo_Partida_Base'] == 0
    assert ciclo['Excluida_Combustible_Partida']
    assert ciclo['Costo_Partida_Base_Original'] == 70000


def test_maxima_se_decide_ciclo_a_ciclo():
    a = _bloques(['TG', 'TG+TV'], partidas=[70000, 250000], ciclo=1)
    b = _bloques(['TG+TV', 'TG'], partidas=[250000, 70000], ciclo=2)
    b['FECHA_HORA'] = b['FECHA_HORA'] + pd.Timedelta(days=1)

    resumen = compactar_resumen_ciclos(pd.concat([a, b], ignore_index=True),
                                       usar_tarifa_rio_instruida=0,
                                       tarifa_configuracion='maxima')

    assert resumen['Costo_Partida_Base'].tolist() == [250000, 250000]
    assert resumen['Config_Tarifa_Partida'].tolist() == ['TG+TV', 'TG+TV']
    assert resumen['Costo_Partida_Base_Original'].tolist() == [70000, 250000]


def test_tarifa_configuracion_maxima_no_altera_el_resto_del_compacto():
    bloques = _bloques(['TG', 'TG+TV'], partidas=[70000, 250000])
    base = compactar_resumen_ciclos(bloques, usar_tarifa_rio_instruida=0)

    maxima = tarifa_configuracion_maxima(bloques, base)

    for columna in ('Etiqueta_Relacionada', 'Inicio_Ciclo', 'Termino_Ciclo',
                    'Generacion_Suma_Ciclo', 'Margen_Suma_Ciclo', 'Central_Partida',
                    'Central_Detencion', 'Filtro_Op_Partida', 'Estado_Ciclo_Mes'):
        assert maxima.iloc[0][columna] == base.iloc[0][columna]


# --- exportacion -----------------------------------------------------------------

def test_maxima_exporta_la_configuracion_ganadora_junto_a_la_tarifa():
    columnas = columnas_resumen_ciclos(0, 1, tarifa_configuracion='maxima')

    assert columnas.index('Excluida_Combustible_Partida') == columnas.index('Costo_Partida_Base') - 1
    assert columnas.index('Config_Tarifa_Partida') == columnas.index('Costo_Partida_Base') - 2
    assert columnas.index('Configs_En_Ciclo') == columnas.index('Costo_Partida_Base') - 3
    assert columnas.index('Config_Tarifa_Detencion') == columnas.index('Costo_Detencion_Base') - 2
    assert 'Costo_Partida_RIO_Instruida' in columnas
    assert 'Costo_Detencion_RIO_Instruida' in columnas


def test_maxima_sin_rio_no_promete_la_tarifa_instruida():
    columnas = columnas_resumen_ciclos(0, 0, tarifa_configuracion='maxima')

    assert 'Config_Tarifa_Partida' in columnas
    assert 'Costo_Partida_RIO_Instruida' not in columnas


def test_maxima_ignora_las_columnas_de_configuracion_dominante():
    columnas = columnas_resumen_ciclos(1, 0, tarifa_configuracion='maxima')

    assert 'Central_Partida_Original' not in columnas
