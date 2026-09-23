#!/usr/bin/env python3
"""Prorratea pagos SC P-D usando retiros de 15 minutos."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.prorrateo_15min import (  # noqa: E402,F401  (leer_retiros se reexporta)
    leer_retiros,
    prorratear_ciclos_motor,
    resumir_por_suministrador,
)


# Variables editables para ejecución directa desde Spyder (F5).
RUTA_EXCEL_MOTOR = r"Reporte_Sobrecostos_PD_Final.xlsx"
RUTA_RETIROS = r"Retiros_y_prorrata_por_medidor.parquet"
RUTA_SALIDA_EXCEL = r"Prorrateo_15Min.xlsx"
RUTA_SALIDA_CSV = r"Prorrateo_15Min_Detalle.csv"


def ejecutar(ruta_motor: Path, ruta_retiros: Path, salida_excel: Path, salida_csv: Path) -> dict:
    detalle_motor = pd.read_excel(ruta_motor, sheet_name="Detalle_15Min")
    resumen_motor = pd.read_excel(ruta_motor, sheet_name="Resumen_Ciclos_PD")
    detalle, auditoria = prorratear_ciclos_motor(
        detalle_motor, resumen_motor, leer_retiros(ruta_retiros)
    )
    resumen = resumir_por_suministrador(detalle)

    salida_excel.parent.mkdir(parents=True, exist_ok=True)
    salida_csv.parent.mkdir(parents=True, exist_ok=True)
    resumen.to_excel(salida_excel, index=False)
    detalle.to_csv(salida_csv, index=False, sep=";", decimal=",")

    print(f"Total original : {auditoria['total_original']:,.2f}")
    print(f"Total repartido: {auditoria['total_repartido']:,.2f}")
    for mensaje in auditoria["mensajes"]:
        print(mensaje)
    if not auditoria["mensajes"]:
        print("OK: todos los ciclos cuadran dentro de la tolerancia de 0,01.")
    print(f"Resumen Excel: {salida_excel}")
    print(f"Detalle CSV  : {salida_csv}")
    return auditoria


def main() -> None:
    ejecutar(
        Path(RUTA_EXCEL_MOTOR), Path(RUTA_RETIROS),
        Path(RUTA_SALIDA_EXCEL), Path(RUTA_SALIDA_CSV),
    )


if __name__ == "__main__":
    main()
