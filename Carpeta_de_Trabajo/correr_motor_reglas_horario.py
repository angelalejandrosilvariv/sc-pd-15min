#!/usr/bin/env python3
"""Corre el motor 'REGLAS DEL HORARIO' sobre el reporte de 15 minutos.

Tercer modelo, independiente del v7 y del turbina. Aplica las reglas del Excel
horario tal como se leyeron en sus formulas y macros (ver
docs/informes/Reglas_Modelo_Horario.md). Sirve para contrastar, no para liquidar.

Deja los archivos de entrada en esta misma carpeta. NO usa mes anterior: el
horario no empalma el mes anterior en ningun nivel, y este motor tampoco.
"""

from __future__ import annotations

import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

import sc_pd_motor_reglas_horario as motor  # noqa: E402

# Variables editables: solo el NOMBRE del archivo (debe estar en esta carpeta).
NOMBRE_REPORTE_15MIN = "Reporte_PD_15min_2608_v2.csv"
NOMBRE_RIO = "RIO_08_2026.xlsx"
NOMBRE_COSTOS_PD = "Costos_de_P-D_Consolidado_2608.xlsx"
NOMBRE_DICCIONARIO = "Diccionario_central_config.xlsx"
NOMBRE_DICCIONARIO_EMPRESA = "Diccionario_central_empresa.xlsx"    # OJO: si el nombre no calza, no da error
NOMBRE_SALIDA = "Reporte_Sobrecostos_PD_ReglasHorario.xlsx"

# Criterio de margen. El horario calcula (CMg - CV) x Dolar y trunca por bloque.
CALCULAR_MARGEN_EN_EL_MOTOR = 1


def _ruta(nombre: str) -> str:
    return str(CARPETA / nombre) if nombre else ""


def main() -> None:
    rutas = {
        "RUTA_REPORTE_15MIN": _ruta(NOMBRE_REPORTE_15MIN),
        "RUTA_RIO": _ruta(NOMBRE_RIO),
        "RUTA_COSTOS_PD": _ruta(NOMBRE_COSTOS_PD),
        "RUTA_DICCIONARIO": _ruta(NOMBRE_DICCIONARIO),
        "RUTA_DICCIONARIO_EMPRESA": _ruta(NOMBRE_DICCIONARIO_EMPRESA),
        "RUTA_SALIDA": _ruta(NOMBRE_SALIDA),
    }
    motor.main(rutas, {"CALCULAR_MARGEN_EN_EL_MOTOR": CALCULAR_MARGEN_EN_EL_MOTOR})


if __name__ == "__main__":
    main()
