"""Regresiones del diccionario mixto de relacionadas y configuraciones."""

import sys
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import asignar_empresas


def test_rescata_empresa_por_nombre_de_configuracion():
    bloques = pd.DataFrame({
        'Central': ['ANDES-1_DIESEL'],
        'Central_Relacionada': ['ANDES-1'],
    })

    resultado = asignar_empresas(bloques, {'ANDES-1_DIESEL': 'ANDES_GENERACION'})

    assert resultado.loc[0, 'Empresa'] == 'ANDES_GENERACION'
    assert resultado.loc[0, '_Empresa_Rescatada_Config'] == True


def test_prioriza_empresa_asignada_directamente_a_la_relacionada():
    bloques = pd.DataFrame({
        'Central': ['ANDES-1_DIESEL'],
        'Central_Relacionada': ['ANDES-1'],
    })
    diccionario = {
        'ANDES-1': 'EMPRESA_RELACIONADA',
        'ANDES-1_DIESEL': 'EMPRESA_CONFIGURACION',
    }

    resultado = asignar_empresas(bloques, diccionario)

    assert resultado.loc[0, 'Empresa'] == 'EMPRESA_RELACIONADA'
    assert resultado.loc[0, '_Empresa_Rescatada_Config'] == False


def test_conserva_sin_empresa_si_ningun_nombre_aparece_en_diccionario():
    bloques = pd.DataFrame({
        'Central': ['CENTRAL_DESCONOCIDA_CONFIG'],
        'Central_Relacionada': ['CENTRAL_DESCONOCIDA'],
    })

    resultado = asignar_empresas(bloques, {})

    assert pd.isna(resultado.loc[0, 'Empresa'])
    assert resultado.loc[0, '_Empresa_Rescatada_Config'] == False
