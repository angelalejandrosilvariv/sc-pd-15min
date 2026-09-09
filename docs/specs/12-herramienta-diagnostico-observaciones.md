# Spec 12 — Herramienta de diagnóstico para responder observaciones (central + ventana → trazado completo)

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — cambio mínimo en `src/sc_pd_motor_v7.py`, archivos nuevos
`src/diagnostico_observaciones.py` y `scripts/diagnosticar_observacion.py`,
más sus tests

## Contexto

Cada mes, después de publicar `Sobrecostos_PD_AAMM_pre/def`, el dueño del
proyecto recibe **observaciones formales** de generadoras a través de la
plataforma del Coordinador (proceso "Balance de Transferencias de
Energía", categoría "Sobrecostos"). Revisé un export real
(`Observaciones_16.xlsx`, 29 observaciones entre enero 2026 y julio 2026)
y el patrón se repite una y otra vez:

> *"Se ha identificado en la planilla 'Sobrecostos_PD_2607_pre' que no se
> están considerando todos los ciclos y pagos por partida y detención
> para TRAPEN_DIESEL [...] El día 21-07-2026 la central se activó por
> CTF(+) entre las 8:35 y 8:58, no se está contabilizando la partida ni
> la detención en la hoja PARTIDAS_DETENCIONES, ya que no aparece la
> fecha 21/07."*

> *"[...] en la fila 6689 se supone que hay un registro sobre el proceso
> de partida en Candelaria-1, sin embargo, se está contabilizando como el
> ciclo CORONEL&8."*

> *"Durante el día 23 de abril [...] la central Ujina, [...] operó en
> despacho en Isla [...] se solicita no considerar una remuneración de
> sobrecosto [...]"*

En los 29 casos revisados, cada observación cita siempre lo mismo: **una
central + una ventana de fecha/hora**, y afirma algo sobre lo que el
motor debería haber calculado ahí (un ciclo no reconocido, una
activación no pagada, un ciclo mal atribuido a otra central, generación
que no debería contar). Hoy, para responder esto, el dueño del proyecto
tiene que buscar a mano en el Excel de salida y cruzarlo con el RIO. Con
la migración a 15 minutos es menos probable que aparezcan artefactos de
frontera horaria como el de Candelaria-1/CORONEL, pero **la capacidad de
responder este tipo de observación debe existir igual**, para el día que
ocurra un caso real (por un bug, un dato de origen raro, etc.).

**Importante:** esta spec **no inventa lógica de negocio nueva**. El
motor ya calcula y exporta casi todo lo necesario para responder estas
observaciones (`Resumen_Ciclos_PD` trae, desde la spec 09,
`Estado_Op_Partida`, `Consigna_Partida`, `Motivo_Partida`,
`Filtro_Conf_Partida`, `Filtro_Disp_Partida`, `Filtro_Op_Partida`,
`Filtro_CostoCero_Partida` y sus equivalentes de detención, más
`Obs_Partida`/`Obs_Detencion`/`Obs_Liquidacion_Final` en lenguaje llano).
Lo que falta es una forma de **filtrar y presentar** todo eso por
central + ventana de tiempo, en vez de tener que revisar el Excel entero
a mano. Esta herramienta es puramente de consulta/trazado — no cambia
ningún cálculo ni interruptor de negocio.

## Alcance de la herramienta

Entrada: una **central** (nombre de `Central` o de `Central_Relacionada`
— igual que confirmó el dueño del proyecto en la spec 10, el nombre
citado en una observación puede ser cualquiera de los dos niveles) + una
**ventana de fecha/hora** (ej. `2026-07-21 08:00` a `2026-07-21 09:30`).

Salida: un Excel de evidencia que muestre, para esa central y esa
ventana, **todo lo que el motor sabe**:

1. Qué dice el RIO crudo (antes de cualquier cruce) para esa central en
   esa ventana — `CONSIGNAS`, `MOTIVO`, `NOMBRE CONFIGURACIÓN`, `ESTADO
   OPERACIONAL`, `COMENTARIO`.
2. Qué generación cruda reporta el CSV de 15 minutos para esa central en
   esa ventana (antes de cualquier filtro).
3. Qué filas de `Detalle_15Min` existen para esa central en esa ventana,
   y a qué `Etiqueta_Relacionada` (ciclo) quedó asociada cada una — esto
   es lo que expone directamente un caso como Candelaria-1/CORONEL&8: si
   la central consultada no coincide con la `Central_Relacionada` de la
   fila devuelta, salta a la vista.
4. Si la ventana no tiene ninguna fila en `Detalle_15Min` para esa
   central, decirlo explícitamente ("no aparece en Detalle_15Min: no fue
   considerada en ningún ciclo de este cálculo") — es exactamente el
   patrón "no aparece la fecha en PARTIDAS_DETENCIONES" que citan las
   observaciones.
5. Para cada ciclo (`Etiqueta_Relacionada`) que sí aparece en el punto 3,
   la fila completa de `Resumen_Ciclos_PD` — con eso ya está toda la
   explicación de si se pagó partida/detención y por qué (los filtros y
   observaciones ya existentes).

## Instrucción

### 1. Cambio mínimo en `src/sc_pd_motor_v7.py`: exponer las piezas crudas

`main(rutas, panel=None)` hoy no retorna nada — exporta directo a Excel y
listo. Agregar un parámetro nuevo con default que preserva el
comportamiento actual:

```python
def main(rutas: dict, panel: dict | None = None, devolver_diagnostico: bool = False):
    ...
    # (todo el pipeline existente, sin cambios)
    ...
    print("Listo. Proceso finalizado.")

    if devolver_diagnostico:
        return {
            'RIO': rio_subset,
            'Reporte_Crudo': reporte_actual,
            'Detalle_15Min': detalle_mes,
            'Resumen_Ciclos_PD': df_compacto,
        }
```

- Con `devolver_diagnostico=False` (default, y todos los llamados
  existentes que no pasan el parámetro), `main()` sigue retornando `None`
  exactamente igual que hoy — **cero cambio de comportamiento** para
  `correr_motor*.py` ni para nada que ya use `main()`.
- No mover ni renombrar `rio_subset`, `reporte_actual`, `detalle_mes` ni
  `df_compacto` — son las variables que ya existen en el pipeline (ver
  líneas ~506, ~1003, ~1837 y el bloque de exportación ~1854-1858 de
  `sc_pd_motor_v7.py`), solo se agrega el `return` al final.

### 2. `src/diagnostico_observaciones.py` — funciones puras y testeables

```python
def coincide_central(df, consulta, columna_central='Central',
                      columna_relacionada='Central_Relacionada'):
    """Mascara booleana: fila coincide si Central O Central_Relacionada
    igualan `consulta` (case-insensitive, trim). Si alguna de las dos
    columnas no existe en df, se ignora esa comparación."""

def filtrar_ventana(df, columna_fecha, inicio, fin, margen=pd.Timedelta('1h')):
    """Recorta df a [inicio - margen, fin + margen] sobre columna_fecha.
    El margen por defecto da contexto (ej. ver instrucciones RIO justo
    antes/despues del rango citado en la observacion)."""

def centrales_disponibles(*dfs, columnas=('Central', 'Central_Relacionada')):
    """Devuelve el conjunto de nombres de central presentes en las
    columnas dadas de los DataFrames recibidos - para sugerir opciones
    cuando una consulta no encuentra coincidencias exactas."""

def armar_trazado(rio, reporte_crudo, detalle_15min, resumen_ciclos_pd,
                   consulta, inicio, fin, margen=pd.Timedelta('1h')):
    """
    Aplica coincide_central + filtrar_ventana a cada insumo y arma:
      - 'RIO': filas de RIO que coinciden.
      - 'Reporte_Crudo': filas del CSV crudo que coinciden.
      - 'Detalle_15Min': filas de Detalle_15Min que coinciden.
      - 'Resumen_Ciclos_PD': filas de Resumen_Ciclos_PD cuyo
        Etiqueta_Relacionada aparece en el 'Detalle_15Min' filtrado
        arriba (los ciclos realmente tocados por la ventana).
      - 'Diagnostico': una fila por bloque de tiempo relevante, en
        lenguaje llano, construida SOLO a partir de columnas que el
        motor ya calcula (Obs_Partida, Obs_Detencion, Tipo_Partida,
        Filtro_*, etc.) - sin inventar ningun criterio nuevo. Si
        'Detalle_15Min' filtrado queda vacio, esta hoja debe decirlo
        explicitamente en vez de quedar vacia en silencio.
    Devuelve un dict {nombre_hoja: DataFrame}, listo para exportar.
    Lanza un error o mensaje claro (segun se decida al implementar) si
    `consulta` no coincide con ninguna central en ninguno de los
    insumos - usando centrales_disponibles() para sugerir las opciones
    mas parecidas en vez de fallar en silencio con hojas vacias.
    """
```

### 3. `scripts/diagnosticar_observacion.py` — wrapper de I/O

Mismo patrón que `scripts/prorratear_pagos_15min.py`: variables editables
arriba del archivo (sin argumentos de línea de comandos, para que sea
fácil de correr en Spyder tal como ya usa el dueño del proyecto los otros
scripts):

```python
RUTAS = { ... }  # mismo dict que usan correr_motor*.py
CENTRAL_CONSULTA = "TRAPEN_DIESEL"
FECHA_INICIO_CONSULTA = "2026-07-21 08:00"
FECHA_FIN_CONSULTA = "2026-07-21 09:30"
RUTA_SALIDA = "Diagnostico_Observacion.xlsx"
```

El script llama a `sc_pd_motor_v7.main(RUTAS, devolver_diagnostico=True)`
(corre el pipeline completo una vez), pasa el resultado a
`armar_trazado(...)`, y exporta cada hoja del dict devuelto a
`RUTA_SALIDA` con `pd.ExcelWriter` (mismo estilo de anchos de columna
automáticos que ya usa `main()` en su propia exportación).

## Criterio de aceptación

- Tests nuevos en `tests/test_diagnostico_observaciones.py`, con datos
  sintéticos, cubriendo:
  - `coincide_central`: coincide por `Central`, coincide por
    `Central_Relacionada`, no coincide si el nombre es distinto en
    ambas columnas.
  - `filtrar_ventana`: filas dentro de la ventana con margen quedan,
    filas fuera del margen no.
  - Caso "ciclo mal atribuido": un `Detalle_15Min` sintético donde
    `Central='CANDELARIA-1'` pero `Central_Relacionada='CORONEL'` /
    `Etiqueta_Relacionada='CORONEL&8'` — al consultar
    `CANDELARIA-1`, la fila debe aparecer en el trazado tal cual está
    (con su `Central_Relacionada` real visible), sin que la herramienta
    intente "corregirla" ni ocultarla.
  - Caso "sin fila en Detalle_15Min": consulta con ventana que no
    devuelve ninguna fila de `Detalle_15Min` — la hoja `Diagnostico`
    debe decirlo explícitamente, no quedar vacía sin explicación.
  - Caso "central no encontrada": `centrales_disponibles()` devuelve
    sugerencias razonables en vez de que la herramienta falle en
    silencio.
  - `armar_trazado`: con un ciclo sintético completo (con sus columnas
    `Filtro_*`/`Obs_*`), la hoja `Resumen_Ciclos_PD` del trazado
    reproduce exactamente esa fila, sin recalcular ni alterar ningún
    valor.
- `main(rutas)` sin el parámetro nuevo (o con
  `devolver_diagnostico=False`) sigue retornando `None` y el resto de
  `pytest -q -m ""` (25/25 hoy) sigue en verde sin cambios — confirma que
  el cambio en `main()` es aditivo puro.
- `python -c "import ast; ast.parse(open('scripts/diagnosticar_observacion.py', encoding='utf-8').read())"`
  sin `SyntaxError`.
- Si hay datos reales disponibles en el entorno de implementación,
  correr `scripts/diagnosticar_observacion.py` contra al menos 2 de las
  observaciones reales de `Observaciones_16.xlsx` (por ejemplo
  TENO_DIESEL, ventana 04-06-2026 ~19:38 a 19:52, o PENON_DIESEL, ventana
  05-06-2026 ~11:42 a 11:46) y reportar en la respuesta si el trazado
  exportado permite reconstruir a mano la misma conclusión que aparece
  en la columna "Respuesta" de esa observación (no hace falta que
  coincida — el objetivo es confirmar que el trazado es fiel a lo que el
  motor calculó, no verificar si el motor "tuvo la razón").

## Qué NO hacer en esta spec

- No agregar lógica de negocio nueva ni recalcular si una partida o
  detención "debería" pagarse — la herramienta solo despliega columnas
  que el motor ya calcula (`Filtro_*`, `Obs_*`, `Tipo_Partida`, etc.).
- No cambiar la firma de `main()` de forma que rompa a quien la llama sin
  el parámetro nuevo — `devolver_diagnostico` debe ser opcional con
  default `False` y comportamiento idéntico al actual en ese caso.
- No intentar redactar automáticamente una "Respuesta" para el
  Coordinador — es una herramienta de trazado/evidencia para que el
  dueño del proyecto arme su propia respuesta con los datos ya
  ordenados.
- No tocar ningún interruptor de negocio
  (`USAR_CONFIG_DOMINANTE`, `USAR_TARIFA_RIO_INSTRUIDA`,
  `REGLA_EXENCION`, `TOLERANCIA_CORTES_BLOQUES`, `CODIGOS_EO_VALIDOS`).
- No intentar resolver automáticamente ventanas que cruzan un límite de
  mes (ej. observación que cita fechas de fin de mes/inicio del
  siguiente) — fuera de alcance de esta primera versión; si aparece, se
  aborda en una spec futura.
