"""Regresiones del parseo de FECHA_HORA en reportes de 15 minutos."""

import sys
from pathlib import Path

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sc_pd_motor_v7 import leer_reporte, validar_meses_reporte


def test_leer_reporte_conserva_mes_en_fechas_iso_dias_1_a_12(tmp_path):
    ruta = tmp_path / 'Reporte_PD_15min_2606.csv'
    fechas = [f'2026-06-{dia:02d} 10:00:00' for dia in range(1, 13)]
    pd.DataFrame({'FECHA_HORA': fechas}).to_csv(ruta, index=False)

    reporte = leer_reporte(ruta, 'Mes actual')

    assert reporte['FECHA_HORA'].dt.year.eq(2026).all()
    assert reporte['FECHA_HORA'].dt.month.eq(6).all()
    assert reporte['FECHA_HORA'].dt.day.tolist() == list(range(1, 13))


def test_validacion_aborta_si_hay_mas_de_dos_meses(capsys):
    reporte = pd.DataFrame({
        'FECHA_HORA': pd.to_datetime([
            '2026-01-06 10:00:00',
            '2026-02-06 10:00:00',
            '2026-03-06 10:00:00',
        ])
    })

    with pytest.raises(SystemExit, match='3 meses-calendario'):
        validar_meses_reporte(reporte, 'Mes actual')

    alerta = capsys.readouterr().out
    assert 'ALERTA CRITICA' in alerta
    assert '2026-01: 1 filas' in alerta
    assert 'FECHA_HORA_original' in alerta
    assert 'FECHA_HORA_parseada' in alerta
