#!/usr/bin/env python3
"""Compara la salida del motor v7 con el Excel horario, desde esta carpeta."""
from __future__ import annotations

import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))

from comparar_con_excel_horario import comparar  # noqa: E402

# Variables editables: escribe solo nombres de archivos ubicados junto a este script.
NOMBRE_SALIDA_MOTOR = "Reporte_Sobrecostos_PD_Final.xlsx"
NOMBRE_EXCEL_HORARIO = "Sobrecostos_PD_horario.xlsm"
NOMBRE_SALIDA_COMPARACION = "Comparacion_Excel_Horario.xlsx"


def main() -> None:
    comparar(CARPETA / NOMBRE_SALIDA_MOTOR,
             CARPETA / NOMBRE_EXCEL_HORARIO,
             CARPETA / NOMBRE_SALIDA_COMPARACION)


if __name__ == "__main__":
    main()
