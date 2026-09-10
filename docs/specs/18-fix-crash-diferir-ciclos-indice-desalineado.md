# Spec 18 — 🔴 CRÍTICO: fix del crash en `asignar_observaciones_liquidacion` (spec 17 / PR #35)

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar — **urgente**
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `tests/test_diferir_ciclos_sin_terminar.py`
**⚠️ `main` está roto ahora mismo:** el motor se cae con una excepción sin
llegar a generar el reporte cuando corre contra datos reales con más de un
puñado de filas. Este fix debe aplicarse antes de que el dueño del proyecto
vuelva a correr el motor localmente.

## Contexto

La spec 17 (PR #35, commit `b43a460`) quedó bien implementada en su lógica
de negocio — los tests unitarios (`tests/test_diferir_ciclos_sin_terminar.py`,
4/4 OK) la validan correctamente. El problema **no es la lógica de
diferimiento**, es que la variable `ciclos_sin_terminar` queda **obsoleta**
entre el punto donde se calcula y el punto donde se usa.

Reproducido corriendo el motor completo contra datos reales de junio 2026
(1.034 ciclos). Excepción:

```
TypeError: unhashable type: 'Series'
  File "src/sc_pd_motor_v7.py", line 1964, in main
    df_compacto = asignar_observaciones_liquidacion(
  File "src/sc_pd_motor_v7.py", line 578, in asignar_observaciones_liquidacion
    df.loc[ciclos_sin_terminar, 'Obs_Partida'] = mensaje
```

**Causa raíz confirmada** (instrumentando el código con prints de
diagnóstico y comparando índices elemento a elemento):

1. En `main()`, `ciclos_sin_terminar` se calcula en la línea ~1716, dentro
   de `diferir_costos_ciclos_sin_terminar(df_compacto, ...)`. En ese
   momento `df_compacto` ya viene con huecos en su índice (quedaron de un
   filtrado anterior con `df_compacto = df_compacto[~mask_baja].copy()`,
   línea ~1627, que no resetea el índice). `ciclos_sin_terminar` hereda
   ese índice con huecos — es coherente con `df_compacto` en ese instante.
2. Más abajo, la sección "RENUMERACION DE CICLOS PARA EL REPORTE" (línea
   ~1753, preexistente, nada que ver con la spec 17) hace:
   ```python
   df_compacto = df_compacto.sort_values(['Central_Relacionada', 'Inicio_Ciclo']).reset_index(drop=True)
   ```
   Esto **reordena las filas y reasigna un índice nuevo y limpio
   (0..N-1)**. `df_compacto` cambia de índice; `ciclos_sin_terminar` (que
   quedó "congelada" con el índice viejo y con huecos) no se actualiza.
3. En la línea ~1947, dentro de `asignar_observaciones_liquidacion`, se usa
   la `ciclos_sin_terminar` obsoleta contra el `df_compacto` ya reordenado.
   Confirmado con un chequeo posicional completo (no solo una muestra):
   mismo largo (1.034), pero valores de índice distintos a partir de la
   posición 4 (`df` trae `4`, la máscara trae `5`; en la posición 7 la
   máscara ya salta a `9`, etc.) — es exactamente el patrón esperado
   cuando un índice con huecos "vieja" se compara contra un
   `RangeIndex` limpio "nueva". Pandas no logra tratar la Serie como
   indexador booleano alineado y termina lanzando `TypeError: unhashable
   type: 'Series'` al intentar interpretarla como una lista de etiquetas.

**Importante — esto no es solo un crash, es un riesgo de corrupción
silenciosa:** si por azar pandas no lanzara la excepción (p. ej. con otro
tamaño de datos donde la conversión interna tome otro camino), la línea
`np.select([ciclos_sin_terminar, ...])` de la misma función **no habría
fallado** — `np.select` convierte a array por posición, ignorando el
índice. Con `ciclos_sin_terminar` calculada sobre el orden **anterior** al
reordenamiento de la línea ~1753, el mensaje "Diferido..." se habría
asignado a **las filas equivocadas** (por posición, no por identidad de
ciclo) en `Obs_Liquidacion_Final`, sin ningún error visible. El fix de
abajo elimina ambos problemas de raíz, no solo el crash.

Los tests actuales no lo detectan porque usan DataFrames sintéticos de una
sola fila — con una sola fila no hay reordenamiento posible que produzca
una desalineación.

## Qué construir

Un único cambio, quirúrgico, en `asignar_observaciones_liquidacion`
(`src/sc_pd_motor_v7.py`, línea ~574). En vez de confiar en el parámetro
`ciclos_sin_terminar` recibido (que puede haber quedado desalineado por
cualquier reordenamiento intermedio, presente o futuro), la función debe
**recalcularlo en el momento**, a partir de la columna
`Estado_Ciclo_Mes` del propio `df` que recibe — esa columna viaja con cada
fila sin importar cuántas veces se haya reordenado u re-indexado el
DataFrame, así que el resultado queda garantizado alineado con `df` por
construcción.

```python
def asignar_observaciones_liquidacion(df, ciclos_sin_terminar, activar=1):
    """Explica el diferimiento y el resultado financiero de cada ciclo."""
    # Se recalcula aqui en vez de confiar en el parametro recibido: entre
    # diferir_costos_ciclos_sin_terminar() y este punto, main() reordena y
    # reindexa df_compacto (ver "RENUMERACION DE CICLOS PARA EL REPORTE"),
    # lo que desalinea cualquier Serie booleana calculada antes de eso.
    # Estado_Ciclo_Mes viaja con cada fila sin importar el orden, asi que
    # recalcular aqui es inmune a ese (o cualquier futuro) reordenamiento.
    if activar == 1:
        ciclos_sin_terminar = df['Estado_Ciclo_Mes'].isin(
            ['Continua todo el mes', 'Continua proximo mes'])
        mensaje = 'Diferido: ciclo aun no termina'
        df.loc[ciclos_sin_terminar, 'Obs_Partida'] = mensaje
        df.loc[ciclos_sin_terminar, 'Obs_Detencion'] = mensaje
    else:
        ciclos_sin_terminar = pd.Series(False, index=df.index)

    df['Obs_Liquidacion_Final'] = np.select(
        [ciclos_sin_terminar,
         (df['Costos_Totales_PD'] > 0) & (df['Total SC_PD'] == 0),
         df['Costos_Totales_PD'] == 0,
         df['Total SC_PD'] > 0],
        ['Diferido: ciclo aun no termina, se evaluara completo el mes de termino',
         'Costo amortizado: Margen supero el costo P-D',
         'Costo nulo o anulado por filtros RIO/EP',
         'Sobrecosto validado a pago'], default='Sin Pago')
    return df
```

Notas sobre este cambio:

- La firma de la función **no cambia** (sigue recibiendo
  `ciclos_sin_terminar` como parámetro) para no tocar el call site en
  `main()` (línea ~1946-1947) ni forzar cambios innecesarios en los tests
  existentes — el parámetro simplemente deja de usarse tal cual llega
  cuando `activar == 1`, y se recalcula localmente.
- `Estado_Ciclo_Mes` está garantizado presente en `df_compacto` en el
  punto donde se llama esta función (línea ~1947): se usa más abajo
  también en la auditoría de frontera, línea ~1853, y recién se elimina
  del reporte final (si correspondiera) en la selección de columnas de la
  línea ~1951, que ocurre **después** de esta llamada.
- El bloque en `main()` que imprime `n_diferidos` (línea ~1719, justo
  después de `diferir_costos_ciclos_sin_terminar`) **no se toca** — ese uso
  de `ciclos_sin_terminar` ocurre antes de cualquier reordenamiento, es
  coherente en ese punto y no participa del bug.
- `diferir_costos_ciclos_sin_terminar` (línea ~561) **no se toca** — el
  bug no está ahí, ya calcula todo correctamente en el momento en que se
  invoca.

## Criterio de aceptación

- Los 4 tests existentes en `tests/test_diferir_ciclos_sin_terminar.py`
  siguen pasando sin modificarlos (deberían seguir pasando tal cual, ya
  que recalcular desde `Estado_Ciclo_Mes` produce el mismo resultado que
  el parámetro que recibían antes, en esos casos de una sola fila).
- **Test nuevo** que reproduzca exactamente el escenario del bug: un
  DataFrame de varias filas (mínimo 4-5) con `Estado_Ciclo_Mes` mixto
  (algunas `'Continua todo el mes'`, otras `'Inicia y termina este mes'`),
  donde **entre** el llamado a `diferir_costos_ciclos_sin_terminar` y el
  llamado a `asignar_observaciones_liquidacion` el test aplique
  deliberadamente un `sort_values(...).reset_index(drop=True)` (o
  equivalente que cambie el índice) sobre el DataFrame — replicando lo que
  hace `RENUMERAR_CICLOS_DEL_MES` en `main()`. Confirmar que, después del
  reordenamiento, cada fila conserva el mensaje "Diferido..." y el costo en
  cero que le corresponde **según su propio `Estado_Ciclo_Mes`**, sin
  importar su nueva posición ni su nuevo valor de índice.
- Correr el motor completo contra datos reales de un mes con varios
  cientos de ciclos (si hay datos reales disponibles en el entorno de
  implementación) y confirmar en la respuesta que:
  - El motor ya **no lanza `TypeError: unhashable type: 'Series'`** ni
    ninguna otra excepción en `asignar_observaciones_liquidacion`.
  - Se genera el reporte final completo.
  - Los ciclos con `Estado_Ciclo_Mes` en `{'Continua todo el mes',
    'Continua proximo mes'}` (verificar con al menos un caso conocido, por
    ejemplo un ciclo `_CAR&1` que siga generando al cierre del reporte)
    quedan con `Total SC_PD = 0` y `Obs_Liquidacion_Final` empezando con
    "Diferido", igual que se pedía en la spec 17 original.
- `pytest -q -m ""` sigue en verde.

## Qué NO hacer en esta spec

- No tocar la lógica de negocio de la spec 17 (qué se difiere, qué
  mensajes se muestran, el orden de las condiciones en `Obs_Liquidacion_Final`)
  — eso ya quedó bien y no es lo que falló.
- No tocar `diferir_costos_ciclos_sin_terminar` — el bug no está ahí.
- No tocar ni reordenar la sección "RENUMERACION DE CICLOS PARA EL
  REPORTE" (línea ~1753) — es un mecanismo preexistente que funciona bien
  para su propósito (numerar ciclos por central para el reporte); el fix
  correcto es que `asignar_observaciones_liquidacion` sea inmune a
  cualquier reordenamiento posterior, no impedir que el reordenamiento
  ocurra.
- No modificar `src/fase1_integridad.py`.
- No tocar ningún interruptor de negocio existente (`DIFERIR_CICLOS_SIN_TERMINAR`
  incluido — su valor por defecto y su semántica quedan iguales).
