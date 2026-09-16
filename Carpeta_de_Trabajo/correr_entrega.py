#!/usr/bin/env python3
"""Genera la entrega de auditoria CEN usando archivos de esta carpeta."""
from pathlib import Path
import sys

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from generar_entrega_cen import generar_entrega  # noqa: E402

NOMBRE_SALIDA_MOTOR = "Reporte_Sobrecostos_PD_Final.xlsx"
NOMBRE_CARPETA_ENTREGA = ""  # vacio = Entrega_SCPD_<AAMM>
TABLAS_DINAMICAS = False

# Nombres de los insumos usados en la corrida; vacio si no correspondia.
NOMBRE_REPORTE_15MIN = "Reporte_PD_15min_2606.csv"
NOMBRE_REPORTE_MES_PASADO = "Reporte_PD_15min_2605.csv"
NOMBRE_RIO = "RIO_06_2026.xlsx"
NOMBRE_RIO_MES_PASADO = "RIO_05_2026.xlsx"
NOMBRE_COSTOS_PD = "Costos_de_P-D_Consolidado_2606.xlsx"
NOMBRE_COSTOS_MES_PASADO = "Costos_de_P-D_Consolidado_2605.xlsx"
NOMBRE_DICCIONARIO = "Diccionario_central_config.xlsx"
NOMBRE_DICCIONARIO_EMPRESA = "Diccionario_central_empresa.xlsx"


def _ruta(nombre): return str(CARPETA / nombre) if nombre else ""


def main():
    rutas = {k.replace("NOMBRE_", "RUTA_"): _ruta(v) for k, v in globals().items()
             if k.startswith("NOMBRE_") and k not in {"NOMBRE_SALIDA_MOTOR", "NOMBRE_CARPETA_ENTREGA"}}
    generar_entrega(_ruta(NOMBRE_SALIDA_MOTOR), rutas,
                    _ruta(NOMBRE_CARPETA_ENTREGA) or None, TABLAS_DINAMICAS)


if __name__ == "__main__": main()
