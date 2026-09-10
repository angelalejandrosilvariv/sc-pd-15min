# Spec 19 — Carpeta de trabajo única para correr todo desde Spyder

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — solo archivos nuevos dentro de una carpeta nueva
`Carpeta_de_Trabajo/`. No modifica ningún archivo existente.

## Contexto

El dueño del proyecto no usa terminal ni Git — su flujo es descargar el
ZIP del repo desde GitHub, descomprimirlo, y correr scripts en Spyder con
F5. Hoy el código útil está repartido entre `src/` (el motor) y
`scripts/` (herramientas), y cada script espera que sus archivos de
entrada estén en rutas distintas — esto ya generó fricción real (ver
bitácora, episodios donde el dueño del proyecto no sabía en qué carpeta
dejar el Excel de salida o el parquet de retiros).

Pidió explícitamente: una sola carpeta donde poder dejar **todos** los
archivos de un mes (el reporte CSV, el RIO, los diccionarios, el
parquet de retiros, etc.) y correr **todos** los scripts desde ahí, más
un archivo de texto breve con instrucciones.

## Qué construir

Una carpeta nueva `Carpeta_de_Trabajo/` en la raíz del repo, con 4
scripts "lanzadores" cortos (ninguno duplica lógica de negocio — todos
importan las funciones reales desde `src/`/`scripts/`, solo fijan las
rutas de entrada/salida a la propia carpeta) y un archivo de
instrucciones.

**Importante:** ninguno de los 4 archivos existentes
(`src/sc_pd_motor_v7.py`, `scripts/prorratear_pagos_15min.py`,
`scripts/diagnosticar_observacion.py`, `scripts/consolidar_politicas.py`)
se modifica. Los lanzadores solo importan y llaman.

### 1. `Carpeta_de_Trabajo/correr_motor.py`

```python
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
NOMBRE_REPORTE_MES_PASADO = ""
NOMBRE_RIO = "RIO_06_2026.xlsx"
NOMBRE_RIO_MES_PASADO = ""
NOMBRE_COSTOS_PD = "Costos_de_P-D_Consolidado.xlsx"
NOMBRE_COSTOS_MES_PASADO = ""
NOMBRE_DICCIONARIO = "Diccionario_central_config.xlsx"
NOMBRE_DICCIONARIO_EMPRESA = "Diccionario_configuracion_empresa.xlsx"
NOMBRE_SALIDA = "Reporte_Sobrecostos_PD_Final.xlsx"


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
    motor.main(rutas)


if __name__ == "__main__":
    main()
```

### 2. `Carpeta_de_Trabajo/correr_prorrateo.py`

```python
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
```

### 3. `Carpeta_de_Trabajo/correr_diagnostico.py`

```python
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
```

### 4. `Carpeta_de_Trabajo/correr_consolidar_politicas.py`

```python
#!/usr/bin/env python3
"""Consolida los archivos de politicas PO. Debe existir una subcarpeta
"Politicas PO" dentro de esta misma carpeta, con los archivos PO*.xls*."""

from __future__ import annotations

import os
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))

from consolidar_politicas import consolidar_politicas  # noqa: E402


def main() -> None:
    os.chdir(CARPETA)
    consolidar_politicas()


if __name__ == "__main__":
    main()
```

### 5. `Carpeta_de_Trabajo/_LEEME.txt`

Texto plano, breve, contenido exacto (el guion bajo inicial es para que
Windows lo liste primero en la carpeta):

```
INSTRUCCIONES - Carpeta de Trabajo SC P-D
==========================================

Esta carpeta es donde corres todo. Deja aca los archivos de cada mes
(el CSV del reporte, el RIO, los diccionarios, el parquet de retiros,
etc.) y corre los scripts con F5 en Spyder, en este orden:

1. correr_motor.py
   Calcula los Sobrecostos P-D del mes. Antes de correr, edita las
   variables NOMBRE_... al inicio del archivo con los nombres exactos
   de tus archivos de este mes (deben estar en esta misma carpeta).
   Genera: Reporte_Sobrecostos_PD_Final.xlsx

2. correr_prorrateo.py (opcional)
   Reparte el costo de cada ciclo entre los suministradores, usando el
   Excel que genero el paso 1 y tu archivo de retiros de 15 minutos.
   Edita las variables NOMBRE_... al inicio del archivo.

3. correr_diagnostico.py (opcional, solo si el CEN pide una
   observacion sobre una central y horario especifico)
   Edita CENTRAL_CONSULTA, FECHA_INICIO_CONSULTA y FECHA_FIN_CONSULTA
   al inicio del archivo, ademas de las variables NOMBRE_... .

4. correr_consolidar_politicas.py (opcional)
   Junta los archivos "PO..." de una subcarpeta llamada "Politicas PO"
   en un solo consolidado. Esa subcarpeta debe existir dentro de esta
   misma carpeta antes de correrlo.

Si algo falla, revisa primero que los nombres de archivo escritos en
las variables NOMBRE_... coincidan exactamente con los archivos que
dejaste en esta carpeta (mismo nombre, misma extension).

Para bajar la version mas actualizada del proyecto: entra al
repositorio en GitHub, boton verde "Code" -> "Download ZIP",
descomprime el ZIP, y usa la carpeta "Carpeta_de_Trabajo" que viene
adentro.
```

## Criterio de aceptación

- `Carpeta_de_Trabajo/` existe en la raíz del repo con los 5 archivos de
  arriba, con el contenido especificado (los 4 `.py` pueden ajustarse
  levemente si al probarlos aparece algún detalle de import, pero deben
  conservar el mismo comportamiento: rutas resueltas contra la propia
  carpeta, cero lógica de negocio duplicada).
- Ninguno de los archivos existentes (`src/sc_pd_motor_v7.py`,
  `scripts/prorratear_pagos_15min.py`,
  `scripts/diagnosticar_observacion.py`,
  `scripts/consolidar_politicas.py`, ni ningún archivo en `tests/`) se
  modifica.
- Los 4 scripts de `Carpeta_de_Trabajo/` corren con `python
  Carpeta_de_Trabajo/correr_X.py` (o F5 en Spyder) sin pasar argumentos,
  y sin necesidad de que el usuario navegue a otra carpeta primero.
- Si hay datos reales disponibles en el entorno de implementación,
  probar al menos `correr_motor.py` copiando datos de prueba a
  `Carpeta_de_Trabajo/` con los nombres por defecto y confirmar que
  genera `Reporte_Sobrecostos_PD_Final.xlsx` ahí mismo, sin errores.
- `python -c "import ast; ast.parse(open(p, encoding='utf-8').read())"`
  sobre cada uno de los 4 `.py` nuevos no lanza `SyntaxError`.
- `pytest -q -m ""` sigue en verde (estos archivos no tienen tests
  propios ni deberían necesitarlos, al no contener lógica de negocio).

## Qué NO hacer en esta spec

- No modificar ningún archivo existente en `src/`, `scripts/` ni
  `tests/`.
- No duplicar lógica de negocio dentro de `Carpeta_de_Trabajo/` — todos
  los `.py` de ahí deben ser lanzadores delgados que importan y llaman,
  nunca una copia del código real.
- No agregar un `__init__.py` en `Carpeta_de_Trabajo/` ni convertirla en
  un paquete Python — es solo una carpeta de trabajo, no debe
  importarse desde ningún otro módulo del repo.
- No tocar ningún interruptor de negocio ni ningún spec anterior.
