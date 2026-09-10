# Spec 22 — Interruptor para calcular el margen en el motor

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `Carpeta_de_Trabajo/correr_motor.py`, `tests/`
**⚠️ Esta spec cambia montos facturados.** Con el valor por defecto que se
pide más abajo, el `Total SC_PD` del mes baja de forma importante
(estimado en junio 2026: de ~1.066 millones a ~823 millones). El
interruptor existe precisamente para poder volver atrás en una línea.

## Contexto

Comparando nuestra salida contra el modelo horario (el sistema previo,
que sigue corriendo en paralelo) aparecieron diferencias grandes. El
dueño del proyecto pidió investigarlas. La causa dominante quedó
identificada y **no está en el cálculo del motor, está en el dato de
entrada**:

- El motor calcula hoy el margen a partir de la columna **`CMg-CV`** que
  viene precalculada en el reporte de 15 minutos:
  ```python
  reporte_sin_ceros['Margen'] = np.where(
      reporte_sin_ceros['CMg-CV'] > 0,
      reporte_sin_ceros['CMg-CV'] * reporte_sin_ceros['GENERACION'], 0)
  ```
- Esa columna **no es una resta aritmética**: viene en cero para el 100%
  de las filas con `Tipo = 'OTRO'` (645.717 filas) y `Tipo = 'SCMT'`
  (37.161 filas), y solo está poblada en el 51% de las filas
  `Tipo = 'C.Frec'`. Son 181.473 filas donde la columna dice 0 aunque
  `CMg` sí es mayor que `CV`.
- El reporte horario **ni siquiera tiene esa columna**: trae `CMg`, `CV`
  y `Dolar` crudos, y el modelo horario calcula la resta él mismo, para
  todas las filas.

Reconstruí la regla del modelo horario desde su propia salida
(`Salida_Horaria.xlsx`) más su fuente horaria (`Reporte_PD_2606.csv`) y
quedó confirmada:

> margen = Σ max(0, CMg − CV) × Dólar × Generación, sobre los bloques del
> ciclo, con las columnas crudas y **sin filtrar por `Tipo`**.

Validación de esa reconstrucción: 60 de las 80 centrales calzan dentro
del 0,1% contra la columna `Total Margen` de la salida horaria, y el
total reconstruido da 110.995 millones contra los 109.136 millones
reportados (1,7% de diferencia, explicable porque yo sumé todas las
horas del mes y el modelo horario suma solo las horas dentro de ciclos).

Con la misma generación en ambas fuentes (4.272.938 MWh exactos), el
margen resulta 148.321 millones en la fuente horaria contra 57.764
millones en la nuestra. Al amortizar menos, cobramos más.

**Decisión del dueño del proyecto:** probar el criterio del modelo
horario (calcular el margen en el motor), dejándolo como un interruptor
al inicio del código para poder controlarlo.

## Qué construir

### 1. Interruptor nuevo (sección "Logica de negocio", junto a los demás)

En `src/sc_pd_motor_v7.py`, después de `DIFERIR_CICLOS_SIN_TERMINAR`
(línea ~143):

```python
CALCULAR_MARGEN_EN_EL_MOTOR = 1  # 1 = el motor calcula el margen unitario como
                                  # (CMg - CV) * Dolar sobre TODAS las filas, igual
                                  # que el modelo horario.
                                  # 0 = usa la columna 'CMg-CV' del reporte tal como
                                  # viene (solo poblada en filas Tipo = 'C.Frec').
```

### 2. Función testeable nueva

En `src/sc_pd_motor_v7.py`, junto a las demás funciones de módulo (por
ejemplo cerca de `calcular_unidades_facturables`):

```python
def calcular_margen_bloques(reporte, calcular_en_motor=1):
    """Calcula el margen por bloque. Es cero o positivo por definicion de negocio.

    calcular_en_motor = 1: margen unitario = (CMg - CV) * Dolar, todas las filas.
    calcular_en_motor = 0: margen unitario = columna 'CMg-CV' tal como viene.
    """
    if calcular_en_motor == 1:
        faltan = [c for c in ['CMg', 'CV', 'Dolar'] if c not in reporte.columns]
        if faltan:
            sys.exit("ERROR: CALCULAR_MARGEN_EN_EL_MOTOR=1 requiere columnas "
                     f"ausentes en el reporte: {faltan}")
        margen_unitario = ((pd.to_numeric(reporte['CMg'], errors='coerce')
                            - pd.to_numeric(reporte['CV'], errors='coerce'))
                           * pd.to_numeric(reporte['Dolar'], errors='coerce'))
    else:
        margen_unitario = pd.to_numeric(reporte['CMg-CV'], errors='coerce')

    margen_unitario = margen_unitario.fillna(0)
    generacion = pd.to_numeric(reporte['GENERACION'], errors='coerce').fillna(0)
    return np.where(margen_unitario > 0, margen_unitario * generacion, 0)
```

### 3. Reemplazo del cálculo inline (línea ~718-723)

```python
    # El margen es cero o positivo por definicion de negocio.
    reporte_sin_ceros['Margen'] = calcular_margen_bloques(
        reporte_sin_ceros, CALCULAR_MARGEN_EN_EL_MOTOR)

    print("\n" + "=" * 78)
    print("  CRITERIO DE MARGEN")
    print("=" * 78)
    if CALCULAR_MARGEN_EN_EL_MOTOR == 1:
        print("  ACTIVO: calculado en el motor -> (CMg - CV) x Dolar, sobre todas las filas")
        print("          (mismo criterio que el modelo horario).")
    else:
        print("  ACTIVO: columna 'CMg-CV' del reporte tal como viene")
        print("          (solo poblada en filas Tipo = 'C.Frec').")
    print(f"  Margen total del mes con el criterio activo: "
          f"{reporte_sin_ceros['Margen'].sum():,.0f} CLP")
    if all(c in reporte_sin_ceros.columns for c in ['CMg', 'CV', 'Dolar', 'CMg-CV']):
        otro = calcular_margen_bloques(
            reporte_sin_ceros, 0 if CALCULAR_MARGEN_EN_EL_MOTOR == 1 else 1)
        print(f"  (Referencia: con el otro criterio seria {otro.sum():,.0f} CLP.)")
    print("  Cambia CALCULAR_MARGEN_EN_EL_MOTOR para alternar este criterio.")
```

### 4. Exponerlo en el lanzador de la carpeta de trabajo

El dueño del proyecto trabaja abriendo `Carpeta_de_Trabajo/correr_motor.py`,
no `src/sc_pd_motor_v7.py`. `main()` ya acepta un segundo parámetro
`panel` cuyo contenido sobrescribe los interruptores
(`globals().update(panel or {})`, línea ~616), así que basta usarlo.

En `Carpeta_de_Trabajo/correr_motor.py`, agregar debajo de las variables
`NOMBRE_...` existentes:

```python
# Criterio de margen: 1 = el motor calcula (CMg - CV) * Dolar sobre todas las
# filas (igual que el modelo horario). 0 = usa la columna 'CMg-CV' del reporte
# tal como viene (solo poblada en filas Tipo = 'C.Frec').
CALCULAR_MARGEN_EN_EL_MOTOR = 1
```

y cambiar la llamada dentro de `main()`:

```python
    motor.main(rutas, {"CALCULAR_MARGEN_EN_EL_MOTOR": CALCULAR_MARGEN_EN_EL_MOTOR})
```

## Criterio de aceptación

- Tests nuevos para `calcular_margen_bloques`:
  - Con `calcular_en_motor=0`, sobre un `DataFrame` sintético, devuelve
    exactamente lo mismo que la fórmula actual
    (`np.where(CMg-CV > 0, (CMg-CV) * GENERACION, 0)`), incluyendo el
    caso de margen negativo (debe quedar en 0).
  - Con `calcular_en_motor=1`, una fila con `CMg > CV` y la columna
    `CMg-CV` en 0 **sí** produce margen positivo igual a
    `(CMg - CV) * Dolar * GENERACION` — este es exactamente el caso que
    hoy se pierde.
  - Con `calcular_en_motor=1`, una fila con `CMg < CV` produce margen 0.
  - Valores no numéricos o vacíos en `CMg`/`CV`/`Dolar`/`GENERACION` no
    lanzan excepción y producen margen 0.
- Si hay datos reales disponibles en el entorno de implementación,
  correr el motor completo **con los dos valores del interruptor** y
  reportar en la respuesta, para cada uno: el margen total del mes y el
  `Total SC_PD` final. Con el interruptor en 0 el `Total SC_PD` debe ser
  **idéntico** al de antes de esta spec (es la comprobación de que no
  hubo regresión); con el interruptor en 1 debe bajar.
- `pytest -q -m ""` sigue en verde.

## Qué NO hacer en esta spec

- No tocar `src/fase1_integridad.py`. En particular, `empalmar_reportes`
  compara `['GENERACION', 'CMg-CV', 'Dolar']` para detectar colisiones de
  reloj (línea 21): eso queda igual, es un mecanismo distinto y cambiarlo
  no es parte de este pedido.
- No cambiar **qué bloques** entran en un ciclo, ni los filtros previos
  (`Costo_Cero`, grupos sin generación, ciclos de baja generación) — esta
  spec solo cambia cómo se valoriza el margen de los bloques que ya
  entran hoy.
- No tocar la fórmula final `Total SC_PD = max(0, Costos_Totales_PD -
  Margen_Suma_Ciclo)` ni ningún otro interruptor de negocio existente.
- No intentar replicar el resto de las diferencias contra el modelo
  horario (configuración/tarifa y segmentación de ciclos): están
  identificadas pero son otro tema, y la de configuración es el efecto
  deliberado de la spec 15.
