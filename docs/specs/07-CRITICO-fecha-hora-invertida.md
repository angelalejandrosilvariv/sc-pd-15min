# Spec 07 — CRÍTICO: `dayfirst=True` corrompe fechas del reporte de 15 min

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar — **PRIORIDAD MÁXIMA, por encima de cualquier otra spec pendiente**
**Toca código:** sí — `src/sc_pd_motor_v7.py`

## Contexto

Corrí el motor real (con todas las correcciones de las specs 00-06 ya
aplicadas) contra datos reales de junio 2026 completos
(`Reporte_PD_15min_2606.csv`, 787.820 filas; `RIO_06_2026.xlsx`;
`Diccionario_central_config.xlsx`; `Costos_de_P-D_Consolidado.xlsx`
regenerado con el fix de Tibia 2). Es la primera vez que se corre el motor
completo contra un mes real desde que empezamos a corregirlo.

Encontré un bug crítico, no relacionado con nada de lo corregido hasta
ahora, en la función `leer_reporte()` (sección "UTILIDADES", dentro de
`main()`):

```python
def leer_reporte(ruta, etiqueta):
    """Carga un CSV de 15 minutos y normaliza FECHA_HORA."""
    df = pd.read_csv(ruta, sep=",", low_memory=False)
    df['FECHA_HORA'] = pd.to_datetime(
        df['FECHA_HORA'].astype(str).str.strip(), format='mixed', dayfirst=True, errors='coerce'
    )
    ...
```

`dayfirst=True` le dice a pandas que, ante una fecha ambigua, prefiera
interpretar el primer número como día. El problema es que **también
invierte fechas que no son ambiguas en absoluto**. El CSV real usa formato
ISO sin ambigüedad (`2026-06-01 00:00:00` = año-mes-día), pero con
`dayfirst=True` pandas igual intercambia día y mes cuando el resultado
sigue siendo una fecha válida (es decir, cuando el día original es ≤12):

```
2026-06-01 10:00:00  ->  2026-01-06 10:00:00   (1 de junio se lee como 6 de enero)
2026-06-02 10:00:00  ->  2026-02-06 10:00:00   (2 de junio se lee como 6 de febrero)
2026-06-03 10:00:00  ->  2026-03-06 10:00:00
2026-06-04 10:00:00  ->  2026-04-06 10:00:00
2026-06-05 10:00:00  ->  2026-05-06 10:00:00
2026-06-06 10:00:00  ->  2026-06-06 10:00:00   (invariante: dia=mes=6)
2026-06-07 10:00:00  ->  2026-07-06 10:00:00
2026-06-08 10:00:00  ->  2026-08-06 10:00:00
2026-06-09 10:00:00  ->  2026-09-06 10:00:00
2026-06-10 10:00:00  ->  2026-10-06 10:00:00
2026-06-11 10:00:00  ->  2026-11-06 10:00:00
2026-06-12 10:00:00  ->  2026-12-06 10:00:00
2026-06-13 10:00:00  ->  2026-06-13 10:00:00   (correcto: no existe "mes 13")
```

**11 de los 30 días de junio (todos excepto el día 6, que es invariante,
y los días 13-30, donde no hay mes válido para intercambiar) quedan
esparcidos por 11 meses distintos del calendario 2026.** Esto no genera
ningún error ni `NaT` — pasa completamente en silencio. Lo confirmé
reproduciendo exactamente `leer_reporte()` contra el CSV real.

Un ciclo que cruza cualquiera de esos 11 días corruptos queda fragmentado
de forma incorrecta cuando el pipeline ordena/agrupa por `FECHA_HORA`
(detección de ciclos, `merge_asof` contra RIO, `merge_asof` contra
políticas PO) — el orden temporal real se pierde.

### Impacto medido (no es hipotético)

Corrí el motor completo dos veces contra los mismos datos de junio 2026,
una vez con el código actual y otra con un parche mínimo
(`dayfirst=False`) solo para medir el impacto:

| | Con el bug (código actual) | Con `dayfirst=False` |
|---|---|---|
| Ventana de fechas detectada | `2026-01-06` → `2026-12-06` | `2026-06-01` → `2026-06-30` |
| Ciclos detectados (`df_compacto`) | 1.044 | 1.034 |
| Costo Base Potencial | 1.633.108.314 CLP | 2.429.708.048 CLP |
| **Sobrecosto P-D final** | **691.806.794 CLP** | **1.175.418.218 CLP** |

**El motor está subestimando el sobrecosto de junio en 483.611.424 CLP** —
un 70% del valor que debería reportarse. Este es, por lejos, el hallazgo
de mayor impacto financiero de todo el proyecto hasta ahora.

## Fix requerido

### 1. Corregir el parseo en `leer_reporte()`

Todos los valores de `FECHA_HORA` observados en datos reales siguen el
patrón ISO `AAAA-MM-DD HH:MM:SS`, que no necesita (y no debe usar)
`dayfirst=True`. Cambiar:

```python
    df['FECHA_HORA'] = pd.to_datetime(
        df['FECHA_HORA'].astype(str).str.strip(), format='mixed', dayfirst=True, errors='coerce'
    )
```

por:

```python
    df['FECHA_HORA'] = pd.to_datetime(
        df['FECHA_HORA'].astype(str).str.strip(), format='mixed', dayfirst=False, errors='coerce'
    )
```

(mantener `format='mixed'` por si en algún archivo real hay variación de
formato dentro del mismo CSV — pero sin forzar la interpretación día-primero,
que es la que causa la inversión silenciosa sobre fechas ISO).

### 2. Agregar una validación que aborte ruidosamente si esto vuelve a pasar

Este bug no generó ningún error, ninguna alerta, nada — corrió "exitosamente"
con el mes mal. Eso es justamente lo que hay que evitar. Después de parsear
`FECHA_HORA` en `leer_reporte()`, agregar una verificación: el archivo
representa nominalmente un solo mes calendario (así lo trata el resto del
pipeline — `f_min_actual`/`f_max_actual` se usan como si fueran una ventana
mensual). Si tras el parseo aparecen fechas en más de 2 meses-calendario
distintos (dando algo de margen para el propio empalme de frontera, que
concatena mes actual + mes pasado en otra función, no en `leer_reporte()`
misma — pero `leer_reporte()` se llama una vez por archivo, y cada archivo
individual debería caer dentro de 1 solo mes), se debe:

- Imprimir una alerta con el detalle: cuántos meses distintos se
  encontraron, cuántas filas caen en cada uno, y una muestra de las
  filas problemáticas (valor original de `FECHA_HORA` vs. valor parseado).
- Abortar la ejecución (`sys.exit(...)`) — igual que ya hace el motor en
  otros puntos (ej. columnas faltantes del RIO, formato de
  `Llave_Concatenada` no reconocido). Es preferible que el proceso truene
  y alguien lo revise, a que seep produzca un número equivocado que se use
  para facturar.

## Criterio de aceptación

- Con `Reporte_PD_15min_2606.csv` real, `leer_reporte()` debe devolver
  `FECHA_HORA` con ventana `2026-06-01 00:00:00` → `2026-06-30 23:45:00`,
  sin ninguna fecha fuera de junio 2026.
- Agregar un test sintético en `tests/` que reproduzca este caso: un CSV
  con fechas ISO para varios días del 1 al 12 de un mes (los días
  vulnerables al bug) y confirme que, tras `leer_reporte()`, todas quedan
  en el mes correcto — no en 11 meses distintos.
- Agregar un test que confirme que la validación nueva del punto 2 aborta
  (levanta `SystemExit` o excepción equivalente) cuando se le da un
  DataFrame con fechas ya parseadas que caen en más de 2 meses distintos
  (simulando el bug re-introducido), en vez de continuar en silencio.
- `pytest -q -m ""` sigue en verde.
- Ningún interruptor de negocio se toca.

## Qué NO hacer en esta spec

- No tocar `leer_rio()` ni el parseo de `Fecha_PO` (sección 5) — no usan
  `dayfirst`, no están afectados por este bug (verificado).
- No agregar `dayfirst=True` en ningún otro punto del código para
  "compensar" — el problema es exactamente que `dayfirst=True` se aplicó
  donde no correspondía.
- No intentar adivinar ni soportar automáticamente un formato DD/MM/AAAA
  además del ISO en esta spec — si en el futuro aparece un archivo con
  formato realmente ambiguo, eso se resuelve como un caso nuevo, con
  evidencia real, no especulando ahora.
