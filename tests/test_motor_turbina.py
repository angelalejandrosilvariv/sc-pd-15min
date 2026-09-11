"""Pruebas del motor por turbina (sc_pd_motor_turbina), modelo alternativo al v7.

Se prueba solo la logica propia de este motor: el agrupamiento de ciclos de
turbina en eventos de configuracion y el reparto de la tarifa entre ellos. El
resto del pipeline es identico al v7 y ya esta cubierto por sus propias pruebas.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_turbina import (agrupar_eventos_de_configuracion,
                                 atribuir_tarifa_entre_turbinas)


def _ciclos(filas):
    """filas: (turbina, config, inicio, gen, costo_partida)."""
    df = pd.DataFrame(filas, columns=['Central_Relacionada', 'Central_Partida',
                                      'Inicio_Ciclo', 'Generacion_Suma_Ciclo',
                                      'Costo_Partida_Efectivo'])
    df['Inicio_Ciclo'] = pd.to_datetime(df['Inicio_Ciclo'])
    df['Costo_Partida_Base'] = df['Costo_Partida_Efectivo']
    return df


# --- agrupamiento -------------------------------------------------------------

def test_turbinas_distintas_misma_config_dentro_de_ventana_comparten_evento():
    df = _ciclos([('TG1', 'CFG_A', '2026-06-01 02:00', 10, 100),
                  ('TV', 'CFG_A', '2026-06-01 02:15', 5, 100)])
    ev = agrupar_eventos_de_configuracion(df, 'Partida', ventana_cuartos=2)
    assert ev[0] == ev[1]


def test_configuraciones_distintas_nunca_comparten_evento():
    # KELAR-TG1 arranca bajo TG1_TG1 y KELAR-TV bajo TG1+0.5TV: son eventos
    # distintos aunque esten a 15 minutos, con cualquier ventana.
    df = _ciclos([('TG1', 'KELAR-TG1_TG1_DIESEL', '2026-06-01 02:00', 10, 100),
                  ('TV', 'KELAR-TG1_TG1+0.5TV_DIESEL', '2026-06-01 02:15', 5, 900)])
    for ventana in (2, 16, 96):
        ev = agrupar_eventos_de_configuracion(df, 'Partida', ventana)
        assert ev[0] != ev[1]


def test_fuera_de_ventana_abre_evento_nuevo():
    df = _ciclos([('TG1', 'CFG_A', '2026-06-01 02:00', 10, 100),
                  ('TV', 'CFG_A', '2026-06-01 06:00', 5, 100)])   # 4 h despues
    ev = agrupar_eventos_de_configuracion(df, 'Partida', ventana_cuartos=2)
    assert ev[0] != ev[1]


def test_la_misma_turbina_repetida_no_se_fusiona_por_transitividad():
    # Regresion del defecto encontrado en el barrido de ventana: con ventana
    # grande, arranques sucesivos de UNA sola maquina se encadenaban en un solo
    # evento (19 ciclos de TENOGAS en 202 h) y se repartian la tarifa entre si.
    df = _ciclos([('TG1', 'CFG_A', '2026-06-01 02:00', 10, 100),
                  ('TG1', 'CFG_A', '2026-06-01 04:00', 10, 100),
                  ('TG1', 'CFG_A', '2026-06-01 06:00', 10, 100)])
    ev = agrupar_eventos_de_configuracion(df, 'Partida', ventana_cuartos=16)  # 4 h
    assert len(set(ev)) == 3


def test_repeticion_de_turbina_separa_pero_conserva_el_grupo_de_las_otras():
    # [TG1, TV, TG1]: TG1 y TV comparten evento; el segundo TG1 es otro arranque.
    df = _ciclos([('TG1', 'CFG_A', '2026-06-01 02:00', 10, 100),
                  ('TV', 'CFG_A', '2026-06-01 02:15', 5, 100),
                  ('TG1', 'CFG_A', '2026-06-01 02:30', 10, 100)])
    ev = agrupar_eventos_de_configuracion(df, 'Partida', ventana_cuartos=2)
    assert ev[0] == ev[1]
    assert ev[2] != ev[0]


def test_agrupamiento_devuelve_en_el_orden_original_del_dataframe():
    df = _ciclos([('B', 'CFG_Z', '2026-06-02 00:00', 1, 1),
                  ('A', 'CFG_A', '2026-06-01 00:00', 1, 1),
                  ('C', 'CFG_A', '2026-06-01 00:15', 1, 1)])
    ev = agrupar_eventos_de_configuracion(df, 'Partida', ventana_cuartos=2)
    assert len(ev) == 3
    assert ev[1] == ev[2]        # A y C comparten
    assert ev[0] != ev[1]        # B queda aparte


# --- atribucion -----------------------------------------------------------------

@pytest.fixture
def evento_compartido():
    return _ciclos([('TG1', 'CFG_A', '2026-06-01 02:00', 30, 900),
                    ('TV', 'CFG_A', '2026-06-01 02:15', 10, 900)])


def test_cada_turbina_no_toca_los_costos(evento_compartido):
    out, aud = atribuir_tarifa_entre_turbinas(evento_compartido, 'Partida',
                                              'cada_turbina', 2)
    np.testing.assert_allclose(out['Costo_Partida_Efectivo'], [900, 900])
    assert aud['Costo_Evento_Antes'].sum() == aud['Costo_Evento_Despues'].sum() == 1800


def test_primera_cobra_una_vez_a_la_que_abrio(evento_compartido):
    out, aud = atribuir_tarifa_entre_turbinas(evento_compartido, 'Partida',
                                              'primera', 2)
    np.testing.assert_allclose(out['Costo_Partida_Efectivo'], [900, 0])
    assert aud['Costo_Evento_Despues'].sum() == 900


def test_prorrata_reparte_por_generacion_y_conserva_el_total_del_evento(evento_compartido):
    out, aud = atribuir_tarifa_entre_turbinas(evento_compartido, 'Partida',
                                              'prorrata', 2)
    # 30 y 10 MWh -> 75% y 25% de la tarifa
    np.testing.assert_allclose(out['Costo_Partida_Efectivo'], [675, 225])
    assert abs(out['Factor_Atribucion_Partida'].sum() - 1) < 1e-9
    assert aud['Costo_Evento_Despues'].sum() == 900


def test_prorrata_sin_generacion_reparte_en_partes_iguales():
    df = _ciclos([('TG1', 'CFG_A', '2026-06-01 02:00', 0, 900),
                  ('TV', 'CFG_A', '2026-06-01 02:15', 0, 900)])
    out, _ = atribuir_tarifa_entre_turbinas(df, 'Partida', 'prorrata', 2)
    np.testing.assert_allclose(out['Costo_Partida_Efectivo'], [450, 450])


def test_atribucion_escala_base_y_efectivo_juntos(evento_compartido):
    out, _ = atribuir_tarifa_entre_turbinas(evento_compartido, 'Partida',
                                            'primera', 2)
    np.testing.assert_allclose(out['Costo_Partida_Base'],
                               out['Costo_Partida_Efectivo'])


def test_evento_de_una_sola_turbina_queda_intacto_en_todos_los_modos():
    df = _ciclos([('TG1', 'CFG_A', '2026-06-01 02:00', 10, 900)])
    for modo in ('prorrata', 'primera', 'cada_turbina'):
        out, aud = atribuir_tarifa_entre_turbinas(df, 'Partida', modo, 2)
        assert out['Costo_Partida_Efectivo'].iloc[0] == 900
        assert int(aud['Turbinas_En_Evento'].iloc[0]) == 1


def test_modo_invalido_aborta(evento_compartido):
    with pytest.raises(SystemExit):
        atribuir_tarifa_entre_turbinas(evento_compartido, 'Partida', 'otro', 2)
