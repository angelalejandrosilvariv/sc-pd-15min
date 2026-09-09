# Spec 17 — No cobrar ciclos que aún no terminan (diferir al mes de término)

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `tests/`
**⚠️ Esta spec SÍ cambia montos facturados** (baja `Costo_Partida_Efectivo`,
`Costo_Detencion_Efectivo` y `Total SC_PD` de los ciclos afectados a
cero). Revisar con cuidado antes de aplicar.

## Contexto

El dueño del proyecto detectó, revisando una corrida real de junio
2026 (con mayo cargado como mes anterior), que `GUACOLDA-3_CAR&1`
—un ciclo con `Estado_Ciclo_Mes = "Continua todo el mes"` (arrancó el
18-may y seguía generando al cierre del reporte, 30-jun 23:45)— tenía
`Costo_Detencion_Efectivo = 1.092.318 CLP` y `Total SC_PD =
1.092.318 CLP`, ambos con `Obs_Detencion = "Aprobado"`.

**El problema:** el motor calcula `Termino_Ciclo_Global` como el último
bloque con datos disponibles cuando el ciclo no ha terminado realmente
(`sigue_despues = Termino_Ciclo_Global >= f_max_actual`, línea ~953).
Ese "término" es artificial — no es un cese de generación real, es
solo dónde se corta el reporte. Aun así, el motor lo trata como si
fuera un evento de detención genuino: busca RIO cerca de esa fecha y
calcula una tarifa de detención con eso. Confirmado con el registro de
`GUACOLDA-3_CAR&1`: `Consigna_Detencion = PC` (Plena Carga — ¡la
central sigue generando a full carga, no se detuvo!).

Medido en la corrida real completa del dueño del proyecto: **23 ciclos**
con `Estado_Ciclo_Mes` en `{'Continua todo el mes', 'Continua proximo
mes'}`, de los cuales **21 tienen `Costo_Detencion_Efectivo > 0`**
(124.684.549 CLP en total) y el conjunto completo tiene
**209.681.737 CLP** en `Costo_Partida_Efectivo`. La mayoría queda en
`Total SC_PD = 0` porque el margen de venta lo amortigua, pero en 3
casos sí se materializó en pago real este mes (6.022.538 CLP).

`Estado_Ciclo_Mes` ya se calcula (línea ~954) pero **no se usa en
ningún otro lugar del archivo** — no hay ningún filtro que excluya
estos ciclos del cobro.

**Regla confirmada con el dueño del proyecto:** un ciclo que no ha
terminado (`Estado_Ciclo_Mes` en `{'Continua todo el mes', 'Continua
proximo mes'}`) **no se paga nada este mes — ni Partida ni Detención**.
Se difiere completo: el ciclo se vuelve a evaluar el mes en que
realmente termine, momento en el que (gracias al mecanismo de empalme
ya existente — `RUTA_REPORTE_MES_PASADO`/`RUTA_RIO_MES_PASADO`/
`RUTA_COSTOS_MES_PASADO`) se calculará con su Partida real (desde
cuando arrancó) y su Detención real (desde cuando efectivamente
paró), una sola vez. Esto es consistente con cómo ya funciona
`'Viene del mes anterior'` (un ciclo que empezó antes y termina este
mes SÍ se paga completo este mes, con su historia heredada).

## Qué construir

Dos puntos de inserción en `main()`, ambos guardados por un
interruptor nuevo.

### 1. Interruptor nuevo (junto a los demás, sección "Logica de negocio")

```python
DIFERIR_CICLOS_SIN_TERMINAR = 1   # 1 = ciclos con Estado_Ciclo_Mes = 'Continua todo
                                    # el mes' o 'Continua proximo mes' no se cobran
                                    # este mes (ni Partida ni Detencion) -- se
                                    # evaluan completos el mes en que terminen.
```

### 2. Punto A — anular costos base, justo después de `costos_clasicos`

Ubicación: inmediatamente después de la línea
`df_compacto = costos_clasicos(df_compacto)` (~línea 1681) y **antes**
de `df_compacto['Costos_Totales_PD'] = ...` (~línea 1682). Esto es
importante: debe ir antes de esa línea para que la auditoría del
"Waterfall" (que lee `Costos_Totales_PD` más abajo) ya refleje el
diferimiento.

```python
    df_compacto = costos_clasicos(df_compacto)

    ciclos_sin_terminar = df_compacto['Estado_Ciclo_Mes'].isin(
        ['Continua todo el mes', 'Continua proximo mes'])
    if DIFERIR_CICLOS_SIN_TERMINAR == 1:
        for columna in ['Costo_Partida_Base', 'Costo_Detencion_Base',
                         'Costo_Partida_Efectivo', 'Costo_Detencion_Efectivo']:
            df_compacto.loc[ciclos_sin_terminar, columna] = 0.0
        n_diferidos = int(ciclos_sin_terminar.sum())
        print(f"\n  Ciclos diferidos (aun no terminan, se evaluaran completos "
              f"el mes de termino): {n_diferidos:,}")
    else:
        ciclos_sin_terminar = pd.Series(False, index=df_compacto.index)

    df_compacto['Costos_Totales_PD'] = df_compacto['Costo_Partida_Efectivo'] + df_compacto['Costo_Detencion_Efectivo']
    df_compacto['Total SC_PD'] = np.maximum(0, df_compacto['Costos_Totales_PD'] - df_compacto['Margen_Suma_Ciclo'])
```

(la última línea de arriba ya existe hoy tal cual — solo se agrega el
bloque nuevo antes).

### 3. Punto B — mensaje correcto en `Obs_Partida`/`Obs_Detencion`/`Obs_Liquidacion_Final`

`marcar_sin_tarifa_rio(df_compacto, configuracion=None)` (~línea 1905)
recalcula `Obs_Partida`/`Obs_Detencion` desde cero usando
`Costo_{tipo}_Base == 0` como una de sus condiciones — como ya
zombificamos `Costo_Partida_Base`/`Costo_Detencion_Base` en el punto A,
esa llamada va a etiquetar estos ciclos como `"Sin tarifa de
partida/detencion"`, lo cual es engañoso (no es que falte tarifa, es
que el ciclo no ha terminado). Justo después de esa llamada, sobrescribir:

```python
    df_compacto = marcar_sin_tarifa_rio(df_compacto, configuracion=None)

    if DIFERIR_CICLOS_SIN_TERMINAR == 1:
        df_compacto.loc[ciclos_sin_terminar, 'Obs_Partida'] = 'Diferido: ciclo aun no termina'
        df_compacto.loc[ciclos_sin_terminar, 'Obs_Detencion'] = 'Diferido: ciclo aun no termina'

    df_compacto['Obs_Liquidacion_Final'] = np.select(
        [ciclos_sin_terminar,
         (df_compacto['Costos_Totales_PD'] > 0) & (df_compacto['Total SC_PD'] == 0),
         df_compacto['Costos_Totales_PD'] == 0,
         df_compacto['Total SC_PD'] > 0],
        ['Diferido: ciclo aun no termina, se evaluara completo el mes de termino',
         'Costo amortizado: Margen supero el costo P-D',
         'Costo nulo o anulado por filtros RIO/EP',
         'Sobrecosto validado a pago'], default='Sin Pago')
```

(el `np.select` de `Obs_Liquidacion_Final` ya existe hoy — solo se
agrega la condición `ciclos_sin_terminar` al principio de la lista,
con prioridad sobre las demás).

`ciclos_sin_terminar` debe seguir siendo la misma variable calculada en
el punto A (no recalcularla) — así, con el interruptor apagado,
queda `pd.Series(False, ...)` y este bloque no cambia nada.

## Criterio de aceptación

- Tests nuevos cubriendo:
  - Ciclo con `Estado_Ciclo_Mes = 'Continua todo el mes'` y costos base
    reales (como `GUACOLDA-3_CAR&1`): `Costo_Partida_Efectivo`,
    `Costo_Detencion_Efectivo`, `Costos_Totales_PD` y `Total SC_PD`
    quedan en 0; `Obs_Partida`, `Obs_Detencion` y
    `Obs_Liquidacion_Final` muestran el mensaje "Diferido...".
  - Mismo caso con `Estado_Ciclo_Mes = 'Continua proximo mes'`.
  - Regresión: un ciclo con `Estado_Ciclo_Mes = 'Inicia y termina este
    mes'` o `'Viene del mes anterior'` no cambia en absoluto (mismos
    montos y observaciones que sin esta spec).
  - `DIFERIR_CICLOS_SIN_TERMINAR=0`: comportamiento idéntico al actual
    (sin diferir nada).
- Si hay datos reales disponibles en el entorno de implementación,
  correr contra un mes con mes anterior cargado y confirmar en la
  respuesta:
  - Que `GUACOLDA-3_CAR&1` (o el ciclo equivalente de ese mes) queda
    con `Total SC_PD = 0` y `Obs_Liquidacion_Final` empieza con
    "Diferido".
  - El nuevo `Total SC_PD` del mes completo (debería bajar respecto a
    antes de esta spec, en la magnitud de lo que antes se cobraba de
    ciclos sin terminar).
  - Que un ciclo `'Viene del mes anterior'` que sí termina este mes
    sigue cobrando su Partida + Detención completas, sin cambios.
- `pytest -q -m ""` sigue en verde.

## Qué NO hacer en esta spec

- No tocar `Estado_Ciclo_Mes` ni su cálculo (línea ~954) — ya está
  bien, solo faltaba usarlo.
- No tocar cómo se calcula `Termino_Ciclo_Global`/`Inicio_Ciclo_Global`
  ni el mecanismo de empalme entre meses (`empalmar_reportes`,
  `RUTA_REPORTE_MES_PASADO`, etc.) — ese mecanismo ya funciona bien
  para los ciclos `'Viene del mes anterior'`, que sí deben seguir
  cobrando completo el mes en que terminan.
- No modificar `marcar_sin_tarifa_rio` en `src/fase1_integridad.py` —
  el fix vive enteramente en `sc_pd_motor_v7.py`, sobrescribiendo su
  resultado después, para no afectar otros posibles usos de esa
  función compartida.
- No tocar `Waterfall_Costos` más allá de que sus números reflejen el
  diferimiento automáticamente (por estar el punto A antes de que se
  calcule) — no hace falta agregar una fila nueva explicando "diferido"
  ahí; eso puede ser una spec futura si se quiere más detalle en esa
  hoja.
- No tocar ningún otro interruptor de negocio existente
  (`USAR_CONFIG_DOMINANTE`, `USAR_TARIFA_RIO_INSTRUIDA`,
  `REGLA_EXENCION`, `TOLERANCIA_CORTES_BLOQUES`, `CODIGOS_EO_VALIDOS`,
  `ACTIVAR_BUSQUEDA_RELAJADA`, `ACTIVAR_CORRECCION_MEZCLA_CONFIG_RIO`).
