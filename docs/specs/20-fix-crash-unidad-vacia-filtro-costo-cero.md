# Spec 20 — Fix del crash cuando `UNIDAD` viene vacía en Costos Consolidados (PO)

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `tests/`
**⚠️ Bloqueante:** el dueño del proyecto corrió el motor con sus datos
reales de producción (usando `Carpeta_de_Trabajo/`, con mes pasado
acoplado) y el motor se cae antes de generar cualquier reporte.

## Contexto

El dueño del proyecto reportó este error corriendo `correr_motor.py`
con sus datos reales:

```
ValueError: Cannot mask with non-boolean array containing NA / NaN values
  File "src/sc_pd_motor_v7.py", line 754, in main
    unidades_facturables = set(df_externo.loc[tiene_costo, 'UNIDAD'])
```

**Causa raíz:** en la sección "4. COSTOS CONSOLIDADOS Y DICCIONARIOS"
(línea ~741), justo después de cargar y acoplar `RUTA_COSTOS_PD` (+
`RUTA_COSTOS_MES_PASADO` si existe) en `df_externo`, el filtro
`Costo_Cero` hace:

```python
tiene_costo = (df_externo['Costo_Cero'].astype(str).str.strip().str.upper().eq('NO')
               .groupby(df_externo['UNIDAD']).transform('any'))
unidades_facturables = set(df_externo.loc[tiene_costo, 'UNIDAD'])
```

`df_externo['UNIDAD']` se usa como llave de `groupby`. Si esa columna
trae valores vacíos/`NaN` en alguna fila (algo que puede pasar con
archivos reales de Excel — filas en blanco al final, filas de
subtotal, una fila de "Politicas PO" a la que se le olvidó llenar la
`UNIDAD`), pandas **excluye esas filas de cualquier grupo** por
defecto (`groupby(dropna=True)`), y `.transform('any')` les devuelve
`NaN` en vez de `True`/`False`. El resultado es una Serie booleana con
huecos, que `.loc[]` rechaza como indexador con la excepción de arriba.

Esta sección de código es anterior a todas las specs de esta sesión (no
tiene relación con las specs 16-19) — es la primera vez que se corre el
motor contra un archivo real de `Costos_de_P-D_Consolidado.xlsx` +
mes pasado que trae este tipo de fila incompleta.

Además del crash, hay un problema de fondo: **ninguna fila con `UNIDAD`
vacía se audita ni se avisa** — si de verdad falta la `UNIDAD` en una
fila de costos real (no una fila basura), hoy esa fila desaparecería en
silencio del análisis. Vale la pena que el dueño del proyecto se entere
cuántas filas así hay, por si corresponde revisar el archivo de origen.

## Qué construir

En `src/sc_pd_motor_v7.py`, reemplazar el bloque `--- Filtro Costo_Cero
---` (línea ~753) por:

```python
    # --- Filtro Costo_Cero ---
    df_costos_validos = df_externo[df_externo['UNIDAD'].notna()]
    filas_sin_unidad = len(df_externo) - len(df_costos_validos)
    if filas_sin_unidad > 0:
        print(f"  [!] {filas_sin_unidad:,} fila(s) de Costos Consolidados (PO) sin "
              f"UNIDAD (vacio/NaN) -- excluidas del filtro Costo_Cero. Revisa el "
              f"archivo de origen si no lo esperabas.")
    tiene_costo = (df_costos_validos['Costo_Cero'].astype(str).str.strip().str.upper().eq('NO')
                   .groupby(df_costos_validos['UNIDAD']).transform('any'))
    unidades_facturables = set(df_costos_validos.loc[tiene_costo, 'UNIDAD'])
```

Todo lo que viene después de este bloque (`resultado_buscarx =
reporte_sin_ceros['Central'].isin(unidades_facturables)` en adelante) no
cambia — sigue usando `unidades_facturables` igual que antes, ahora
garantizado sin `NaN` adentro.

## Criterio de aceptación

- Test nuevo en `tests/` que reproduzca el escenario exacto: un
  `df_externo` sintético con al menos 2 filas de `UNIDAD` válida (una
  con `Costo_Cero = 'NO'`, otra con `Costo_Cero` distinto de `'NO'`) más
  al menos 1 fila con `UNIDAD = NaN`. Confirmar que el cálculo de
  `unidades_facturables` (o el resultado equivalente que exponga la
  función/sección bajo prueba) ya no lanza `ValueError` y que la fila
  con `UNIDAD` vacía queda excluida del resultado sin afectar a las
  demás. Si la lógica no está aislada en una función propia, extraerla
  a una función pequeña y testeable (p. ej. `calcular_unidades_facturables(df_externo)`)
  es válido, siempre que el comportamiento del resto de `main()` quede
  idéntico.
- Regresión: con un `df_externo` sin ninguna fila de `UNIDAD` vacía, el
  resultado de `unidades_facturables` debe ser idéntico al que se
  obtenía antes de este fix (mismo conjunto de unidades).
- Si hay datos reales disponibles en el entorno de implementación,
  correr el motor completo y confirmar en la respuesta que ya no se cae
  en este punto.
- `pytest -q -m ""` sigue en verde.

## Qué NO hacer en esta spec

- No cambiar la definición de negocio del filtro `Costo_Cero` (qué
  hace que una `UNIDAD` sea "facturable") — solo se excluyen del
  cálculo las filas sin `UNIDAD`, el resto de la lógica queda igual.
- No tocar cómo se cargan o acoplan `RUTA_COSTOS_PD`/`RUTA_COSTOS_MES_PASADO`
  (líneas ~730-745) — el problema no está en la carga, está en el
  filtro posterior.
- No agregar `'UNIDAD'` a la validación `faltan = [c for c in cols_costos
  if c not in df_externo.columns]` de más arriba — esa validación
  chequea que la *columna* exista, lo cual ya es cierto; el problema
  acá es que algunas *filas* de una columna que sí existe vienen vacías.
- No tocar ningún otro interruptor de negocio ni ninguna spec anterior.
