"""Regresiones del filtro Costo_Cero ante unidades vacias."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import calcular_unidades_facturables


def test_excluye_unidad_nula_sin_afectar_unidades_validas():
    costos = pd.DataFrame({
        'UNIDAD': ['FACTURABLE', 'NO_FACTURABLE', np.nan],
        'Costo_Cero': ['NO', 'SI', 'NO'],
    })

    resultado = calcular_unidades_facturables(costos)

    assert resultado == {'FACTURABLE'}


def test_conserva_resultado_anterior_si_no_hay_unidades_nulas():
    costos = pd.DataFrame({
        'UNIDAD': ['UNIDAD_A', 'UNIDAD_A', 'UNIDAD_B', 'UNIDAD_C'],
        'Costo_Cero': ['SI', ' no ', 'SI', 'NO'],
    })
    tiene_costo_anterior = (
        costos['Costo_Cero'].astype(str).str.strip().str.upper().eq('NO')
        .groupby(costos['UNIDAD']).transform('any')
    )
    resultado_anterior = set(costos.loc[tiene_costo_anterior, 'UNIDAD'])

    assert calcular_unidades_facturables(costos) == resultado_anterior
