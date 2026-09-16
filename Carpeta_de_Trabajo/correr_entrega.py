#!/usr/bin/env python3
"""Genera el paquete de auditoría CEN. Edite únicamente las variables NOMBRE_*."""
from pathlib import Path
import sys

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))

from generar_entrega_cen import generar_entrega  # noqa: E402

NOMBRE_REPORTE_MOTOR = "Reporte_Sobrecostos_PD_Final.xlsx"
NOMBRE_CARPETA_SALIDA = ""  # vacío: crea Entrega_SCPD_<AAMM> junto al reporte
VERSION = "Preliminar"  # o "Definitivo"


if __name__ == "__main__":
    base = CARPETA / NOMBRE_CARPETA_SALIDA if NOMBRE_CARPETA_SALIDA else None
    print(generar_entrega(CARPETA / NOMBRE_REPORTE_MOTOR, base, version=VERSION))
