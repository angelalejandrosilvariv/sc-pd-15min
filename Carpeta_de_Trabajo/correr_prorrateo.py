#!/usr/bin/env python3
"""Prorratea pagos SC P-D a 15 minutos. Deja los archivos de entrada en esta misma carpeta."""

from __future__ import annotations

import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts.prorratear_pagos_15min import ejecutar  # noqa: E402

# Variables editables: solo el NOMBRE del archivo (debe estar en esta carpeta).
NOMBRE_EXCEL_MOTOR = "Reporte_Sobrecostos_PD_Final.xlsx"
NOMBRE_RETIROS = "Retiros_y_prorrata_por_medidor.parquet"
NOMBRE_SALIDA_EXCEL = "Prorrateo_15Min.xlsx"
NOMBRE_SALIDA_CSV = "Prorrateo_15Min_Detalle.csv"


def main() -> None:
    ejecutar(
        CARPETA / NOMBRE_EXCEL_MOTOR, CARPETA / NOMBRE_RETIROS,
        CARPETA / NOMBRE_SALIDA_EXCEL, CARPETA / NOMBRE_SALIDA_CSV,
    )


if __name__ == "__main__":
    main()
