"""Pruebas de las reglas puras del motor de contraste horario (spec 26)."""

import numpy as np
import pandas as pd

from sc_pd_motor_reglas_horario import (
    es_cogen_excluida,
    factor_operacional,
    horas_detenidas_con_piso,
    marcar_partidas_detenciones,
    marcar_traspasos,
    sufijo_combustible,
    tramo_horario,
)


def test_marcar_partidas_detenciones_por_configuracion_y_sin_tolerancia():
    fechas = pd.date_range("2026-06-01", periods=8, freq="15min")
    datos = pd.DataFrame({
        "Central": ["A"] * 5 + ["B"] * 3,
        "FECHA_HORA": list(fechas[:5]) + list(fechas[:3]),
        "GENERACION": [0, 2, 3, 0, -1, 4, 0, 5],
    })

    resultado = marcar_partidas_detenciones(datos, "Central")

    assert resultado["Partida_Flag"].tolist() == [0, 1, 0, 0, 1, 0, 0, 1]
    assert resultado["Detencion_Flag"].tolist() == [0, 0, 1, 0, 0, 1, 0, 0]


def test_horas_detenidas_usa_piso_del_primer_bloque_y_luego_detencion_anterior():
    ciclos = pd.DataFrame({
        "Central_Relacionada": ["A", "A", "B"],
        "Inicio_Ciclo": pd.to_datetime(["2026-06-01 06:00", "2026-06-02 03:00", "2026-06-01 01:00"]),
        "Termino_Ciclo": pd.to_datetime(["2026-06-01 08:00", "2026-06-02 05:00", "2026-06-01 02:00"]),
        "Primer_Bloque_Central": pd.to_datetime(["2026-06-01 00:00"] * 3),
    })

    resultado = horas_detenidas_con_piso(ciclos)

    assert resultado["Horas_Detenida_Ciclo"].tolist() == [6.0, 19.0, 1.0]
    assert resultado["Historia"].tolist() == ["piso inicio mes", "detencion anterior", "piso inicio mes"]


def test_tramo_horario_tiene_bordes_inclusivos_y_solo_tres_tramos():
    resultado = tramo_horario(
        pd.Series([2, 3, 7, 8, 100]),
        pd.Series([8, 8, 8, 8, 0]),
        pd.Series([2, 2, 2, 2, 2]),
    )

    assert resultado.tolist() == ["caliente", "tibia", "tibia", "fria", "fria"]
    assert "tibia_2" not in {valor.lower() for valor in resultado}


def test_sufijo_combustible():
    assert sufijo_combustible("KELAR_TG1_GNL_B") == "GNL_B"
    assert sufijo_combustible("KELAR_TG1_DIESEL") == "DIESEL"
    assert sufijo_combustible("HIDRAULICA") == ""


def test_factor_operacional_cubre_om_pdo_ot_sscc_y_primer_ciclo_sin_instruccion():
    assert factor_operacional("OM", "", False, False) == 1
    assert factor_operacional("", "PDO", False, False) == 1
    assert factor_operacional("OT", "", True, False) == 1
    assert factor_operacional("OT", "", False, False) == 0
    assert factor_operacional(np.nan, "", False, True) == 1
    assert factor_operacional("RE", "", True, True) == 0


def test_exclusion_cogen_es_insensible_a_mayusculas():
    resultado = es_cogen_excluida(pd.Series(["SANTAFE_BL1_COGEN", "escuadron_cogen", "OTRA"])).tolist()
    assert resultado == [True, True, False]


def test_traspaso_solo_afecta_ultimo_ciclo_que_genera_al_cierre():
    ciclos = pd.DataFrame({"Central_Relacionada": ["A", "A", "B", "C"], "Ciclo_ID": [1, 2, 1, 1]})
    cierre = pd.Series({"A": 4.0, "B": 0.0, "C": -0.5})

    assert marcar_traspasos(ciclos, cierre).tolist() == [False, True, False, True]
