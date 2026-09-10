#!/usr/bin/env python3
"""Genera un Excel de evidencia para una observación sobre SC P-D. Deja los archivos de entrada en esta misma carpeta."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

import sc_pd_motor_v7  # noqa: E402
from diagnostico_observaciones import armar_trazado  # noqa: E402

# Variables editables: solo el NOMBRE del archivo (debe estar en esta carpeta).
NOMBRE_REPORTE_15MIN = "Reporte_PD_15min_2607.csv"
NOMBRE_REPORTE_MES_PASADO = "Reporte_PD_15min_2606.csv"
NOMBRE_RIO = "RIO_07_2026.xlsx"
NOMBRE_RIO_MES_PASADO = "RIO_06_2026.xlsx"
NOMBRE_COSTOS_PD = "Costos_de_P-D_Consolidado.xlsx"
NOMBRE_COSTOS_MES_PASADO = "Costos_de_P-D_Consolidado_2606.xlsx"
NOMBRE_DICCIONARIO = "Diccionario_central_config.xlsx"
NOMBRE_DICCIONARIO_EMPRESA = "Diccionario_configuracion_empresa.xlsx"

CENTRAL_CONSULTA = "TRAPEN_DIESEL"
FECHA_INICIO_CONSULTA = "2026-07-21 08:00"
FECHA_FIN_CONSULTA = "2026-07-21 09:30"
NOMBRE_SALIDA = "Diagnostico_Observacion.xlsx"


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
    }
    piezas = sc_pd_motor_v7.main(rutas, devolver_diagnostico=True)
    hojas = armar_trazado(
        piezas["RIO"], piezas["Reporte_Crudo"], piezas["Detalle_15Min"],
        piezas["Resumen_Ciclos_PD"], CENTRAL_CONSULTA,
        FECHA_INICIO_CONSULTA, FECHA_FIN_CONSULTA,
    )
    salida = CARPETA / NOMBRE_SALIDA
    with pd.ExcelWriter(salida, engine="xlsxwriter") as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre, index=False)
            hoja = writer.sheets[nombre]
            for indice, columna in enumerate(df.columns):
                largo = df[columna].map(lambda valor: len(str(valor))).max() if len(df) else 0
                ancho = max(int(largo or 0), len(str(columna))) + 2
                hoja.set_column(indice, indice, min(ancho, 50))
    print(f"Diagnóstico exportado a: {salida}")


if __name__ == "__main__":
    main()
