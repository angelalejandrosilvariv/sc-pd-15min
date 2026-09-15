#!/usr/bin/env python3
"""Corre el motor de Sobrecostos P-D. Deja los archivos de entrada de este mes en esta misma carpeta."""

from __future__ import annotations

import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

import sc_pd_motor_v7 as motor  # noqa: E402

# Variables editables: solo el NOMBRE del archivo (debe estar en esta
# carpeta, junto a este script). Deja "" en los "_MES_PASADO" si no vas
# a usar empalme con el mes anterior.
NOMBRE_REPORTE_15MIN = "Reporte_PD_15min_2606.csv"
NOMBRE_REPORTE_MES_PASADO = "Reporte_PD_15min_2605.csv"
NOMBRE_RIO = "RIO_06_2026.xlsx"
NOMBRE_RIO_MES_PASADO = "RIO_05_2026.xlsx"
NOMBRE_COSTOS_PD = "Costos_de_P-D_Consolidado_2606.xlsx"
NOMBRE_COSTOS_MES_PASADO = "Costos_de_P-D_Consolidado_2605.xlsx"   # copia local del de T:\...\2605
NOMBRE_DICCIONARIO = "Diccionario_central_config.xlsx"
NOMBRE_DICCIONARIO_EMPRESA = "Diccionario_central_empresa.xlsx"    # OJO: si el nombre no calza, el motor
                                                                    # NO da error; solo deja empresas vacias
NOMBRE_SALIDA = "Reporte_Sobrecostos_PD_Final.xlsx"

# Criterio de margen: 1 = el motor calcula (CMg - CV) * Dolar sobre todas las
# filas (igual que el modelo horario). 0 = usa la columna 'CMg-CV' del reporte
# tal como viene (solo poblada en filas Tipo = 'C.Frec').
CALCULAR_MARGEN_EN_EL_MOTOR = 1

# Cuando se descarta el margen negativo. 0 = bloque a bloque, igual que el modelo
# horario (deja esto salvo que el cambio de criterio este aprobado). 1 = deja que
# los bloques negativos compensen dentro del ciclo y trunca recien el total.
# CAMBIA EL MONTO A PAGAR. Ver docs/specs/23-margen-neteado-por-ciclo.md
MARGEN_NETEADO_POR_CICLO = 0

# Que tarifa cobra un ciclo que paso por mas de una configuracion.
#   'maxima'    = la mas cara de las que generaron en el ciclo (regla del modelo
#                 horario; decision del 14-09-2026).
#   'instruida' = la de la configuracion que instruyo el RIO (spec 15).
# CAMBIA EL MONTO A PAGAR. Ver docs/specs/25-tarifa-configuracion-maxima.md
TARIFA_CONFIGURACION = "maxima"

# Minutos de vigencia de la instruccion RIO que justifica una partida/detencion.
# 30 = solo se acepta una instruccion dada hasta 30 min antes (o 30 min despues,
# via busqueda relajada) del inicio/termino del ciclo. 0 = sin limite (hasta
# 24 h atras, comportamiento anterior). Ver docs/specs/27-vigencia-instruccion-rio.md
VIGENCIA_INSTRUCCION_RIO_MIN = 30


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
        "TARIFA_CONFIGURACION": TARIFA_CONFIGURACION,
        "VIGENCIA_INSTRUCCION_RIO_MIN": VIGENCIA_INSTRUCCION_RIO_MIN,
    })


if __name__ == "__main__":
    main()
