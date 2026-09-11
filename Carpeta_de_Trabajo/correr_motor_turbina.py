#!/usr/bin/env python3
"""Corre el motor SC P-D POR TURBINA (modelo alternativo, no reemplaza al v7).

Los ciclos se detectan por 'UNIDAD GENERADORA' en vez de por central relacionada.
Deja los archivos de entrada de este mes en esta misma carpeta.
"""

from __future__ import annotations

import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

import sc_pd_motor_turbina as motor  # noqa: E402

# Variables editables: solo el NOMBRE del archivo (debe estar en esta carpeta).
NOMBRE_REPORTE_15MIN = "Reporte_PD_15min_2606.csv"
NOMBRE_REPORTE_MES_PASADO = ""
NOMBRE_RIO = "RIO_06_2026.xlsx"
NOMBRE_RIO_MES_PASADO = ""
NOMBRE_COSTOS_PD = "Costos_de_P-D_Consolidado.xlsx"
NOMBRE_COSTOS_MES_PASADO = ""
NOMBRE_DICCIONARIO = "Diccionario_central_config.xlsx"
NOMBRE_DICCIONARIO_EMPRESA = "Diccionario_configuracion_empresa.xlsx"
NOMBRE_SALIDA = "Reporte_Sobrecostos_PD_Turbina.xlsx"

# Criterio de margen, igual que en el v7.
CALCULAR_MARGEN_EN_EL_MOTOR = 1
MARGEN_NETEADO_POR_CICLO = 0

# Como se reparte la tarifa cuando varias turbinas arrancan bajo la misma
# configuracion (ej. KELAR-TG1 y KELAR-TV bajo KELAR-TG1_TG1+0.5TV_DIESEL):
#   'prorrata'     -> el evento paga una vez, repartido por generacion
#   'primera'      -> el evento paga una vez, todo a la turbina que abrio
#   'cada_turbina' -> cada turbina paga la tarifa completa (multiplica el monto)
ATRIBUCION_TARIFA_TURBINA = "prorrata"


def _ruta(nombre: str) -> str:
    return str(CARPETA / nombre) if nombre else ""


def main() -> None:
    rutas = {
        "RUTA_REPORTE_15MIN": _ruta(NOMBRE_REPORTE_15MIN),
        "RUTA_REPORTE_MES_PASADO": _ruta(NOMBRE_REPORTE_MES_PASADO),
        "RUTA_RIO": _ruta(NOMBRE_RIO),
        "RUTA_RIO_MES_PASADO": _ruta(NOMBRE_RIO_MES_PASADO),
        "RUTA_COSTOS_PD": _ruta(NOMBRE_COSTOS_PD),
        "RUTA_COSTOS_MES_PASADO": _ruta(NOMBRE_COSTOS_MES_PASADO),
        "RUTA_DICCIONARIO": _ruta(NOMBRE_DICCIONARIO),
        "RUTA_DICCIONARIO_EMPRESA": _ruta(NOMBRE_DICCIONARIO_EMPRESA),
        "RUTA_SALIDA": _ruta(NOMBRE_SALIDA),
    }
    motor.main(rutas, {
        "CALCULAR_MARGEN_EN_EL_MOTOR": CALCULAR_MARGEN_EN_EL_MOTOR,
        "MARGEN_NETEADO_POR_CICLO": MARGEN_NETEADO_POR_CICLO,
        "ATRIBUCION_TARIFA_TURBINA": ATRIBUCION_TARIFA_TURBINA,
    })


if __name__ == "__main__":
    main()
