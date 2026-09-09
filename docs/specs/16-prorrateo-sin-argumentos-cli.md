# Spec 16 — `prorratear_pagos_15min.py` sin argumentos de línea de comandos (todo en Spyder)

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `scripts/prorratear_pagos_15min.py` únicamente

## Contexto

El dueño del proyecto no usa terminal/línea de comandos — todo su
flujo de trabajo es abrir un script en Spyder y correrlo con F5. Los
otros scripts del repo (`consolidar_politicas.py`,
`diagnosticar_observacion.py`) ya siguen ese patrón: rutas editables
como variables al principio del archivo, sin argumentos.
`scripts/prorratear_pagos_15min.py` (spec 11) quedó como la excepción
— usa `argparse`, lo que obliga a correrlo desde una terminal (Anaconda
Prompt) pasando rutas como argumentos, algo que ya causó fricción real
al intentar usarlo.

## Fix requerido

Reemplazar el bloque de `argparse` por variables editables al inicio
del archivo, mismo estilo que `scripts/diagnosticar_observacion.py`.
**No tocar** `leer_retiros()` ni `ejecutar()` — la lógica de negocio
(prorrateo, cuadratura, exportación) queda idéntica, solo cambia cómo
se le pasan las rutas.

```python
#!/usr/bin/env python3
"""Prorratea pagos SC P-D usando retiros de 15 minutos."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.prorrateo_15min import (  # noqa: E402
    agrupar_retiros,
    auditar_cuadratura,
    construir_membresia_ciclos,
    prorratear_retiros,
)


# Variables editables para ejecución directa desde Spyder (F5).
RUTA_EXCEL_MOTOR = r"Reporte_Sobrecostos_PD_Final.xlsx"
RUTA_RETIROS = r"Retiros_y_prorrata_por_medidor.parquet"
RUTA_SALIDA_EXCEL = r"Prorrateo_15Min.xlsx"
RUTA_SALIDA_CSV = r"Prorrateo_15Min_Detalle.csv"


def leer_retiros(ruta: Path) -> pd.DataFrame:
    """Lee retiros CSV (detectando separador) o Parquet según extensión."""
    if ruta.suffix.lower() == ".parquet":
        return pd.read_parquet(ruta)
    if ruta.suffix.lower() == ".csv":
        return pd.read_csv(ruta, sep=None, engine="python", decimal=",")
    raise ValueError("El archivo de retiros debe ser .csv o .parquet")


def ejecutar(ruta_motor: Path, ruta_retiros: Path, salida_excel: Path, salida_csv: Path) -> dict:
    # ... (sin cambios, contenido identico al actual)


def main() -> None:
    ejecutar(
        Path(RUTA_EXCEL_MOTOR), Path(RUTA_RETIROS),
        Path(RUTA_SALIDA_EXCEL), Path(RUTA_SALIDA_CSV),
    )


if __name__ == "__main__":
    main()
```

## Criterio de aceptación

- El archivo ya no importa `argparse` ni define ningún `ArgumentParser`.
- `leer_retiros()` y `ejecutar()` quedan **byte a byte idénticas** a la
  versión actual (mismo cuerpo, sin ningún cambio de lógica).
- `python -c "import ast; ast.parse(open('scripts/prorratear_pagos_15min.py', encoding='utf-8').read())"`
  no lanza `SyntaxError`.
- El script se puede correr directamente (`python
  scripts/prorratear_pagos_15min.py`, o F5 en Spyder) sin pasar ningún
  argumento — usa las 4 variables editables del inicio del archivo.
- `pytest -q -m ""` sigue en verde (no debería haber tests que dependan
  de la interfaz CLI de este script; si los hay, ajustarlos al nuevo
  patrón de variables).

## Qué NO hacer en esta spec

- No modificar `src/prorrateo_15min.py` — esta spec es solo sobre cómo
  se invoca el script, no sobre el cálculo.
- No modificar `leer_retiros()` ni `ejecutar()` más allá de lo
  estrictamente necesario para que sigan funcionando igual sin
  `argparse` (en la práctica, no deberían cambiar en absoluto).
- No tocar `scripts/diagnosticar_observacion.py` ni
  `scripts/consolidar_politicas.py` — ya siguen el patrón correcto, son
  la referencia a imitar, no el objetivo del cambio.
