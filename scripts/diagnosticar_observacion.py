#!/usr/bin/env python3
"""Genera un Excel de evidencia para una observación sobre SC P-D."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import sc_pd_motor_v7  # noqa: E402
from diagnostico_observaciones import armar_trazado  # noqa: E402


# Variables editables para ejecución directa desde Spyder.
RUTAS = {
    "RUTA_REPORTE_15MIN": r"Reporte_PD_15min_2607.csv",
    "RUTA_REPORTE_MES_PASADO": r"Reporte_PD_15min_2606.csv",
    "RUTA_RIO": r"RIO_07_2026.xlsx",
    "RUTA_RIO_MES_PASADO": r"RIO_06_2026.xlsx",
    "RUTA_COSTOS_PD": r"Costos_de_P-D_Consolidado.xlsx",
    "RUTA_COSTOS_MES_PASADO": r"Costos_de_P-D_Consolidado_2606.xlsx",
    "RUTA_DICCIONARIO": r"Diccionario_central_config.xlsx",
    "RUTA_DICCIONARIO_EMPRESA": r"Diccionario_configuracion_empresa.xlsx",
    "RUTA_SALIDA": r"Reporte_Sobrecostos_PD_Final.xlsx",
}
CENTRAL_CONSULTA = "TRAPEN_DIESEL"
FECHA_INICIO_CONSULTA = "2026-07-21 08:00"
FECHA_FIN_CONSULTA = "2026-07-21 09:30"
RUTA_SALIDA = "Diagnostico_Observacion.xlsx"


def main() -> None:
    piezas = sc_pd_motor_v7.main(RUTAS, devolver_diagnostico=True)
    hojas = armar_trazado(
        piezas["RIO"], piezas["Reporte_Crudo"], piezas["Detalle_15Min"],
        piezas["Resumen_Ciclos_PD"], CENTRAL_CONSULTA,
        FECHA_INICIO_CONSULTA, FECHA_FIN_CONSULTA,
    )
    with pd.ExcelWriter(RUTA_SALIDA, engine="xlsxwriter") as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre, index=False)
            hoja = writer.sheets[nombre]
            for indice, columna in enumerate(df.columns):
                largo = df[columna].map(lambda valor: len(str(valor))).max() if len(df) else 0
                ancho = max(int(largo or 0), len(str(columna))) + 2
                hoja.set_column(indice, indice, min(ancho, 50))
    print(f"Diagnóstico exportado a: {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
