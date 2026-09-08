# Spec 01 — Auditoría Fase 1 (integridad de datos) y pendientes

**Para:** ChatGPT (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar — depende de `00-restaurar-motor-v7.md`
**Toca código:** sí — `src/sc_pd_motor_v7.py` y `tests/`

## Contexto

En una conversación anterior (fuera de este repo) se diagnosticaron varios
bugs de integridad de datos sobre una versión previa del motor (empalme
mensual sin recorte, cambio de hora (DST), mapeo de columnas del RIO,
doble lógica de cruce RIO, prioridad de `MOTIVO` en duplicados, comparación
de generación contra cero exacto, `Obs_Partida` con orden de causas
invertido, reconciliación final comparando ventanas distintas).

Tras leer el código real de la v7 (`src/sc_pd_motor_v7.py`, restaurado por
la spec 00), confirmo que **la mayoría de esos bugs ya están corregidos**.
Esta spec documenta qué quedó resuelto (con referencia a la sección del
propio archivo) y especifica lo que todavía falta, para que quede como
registro auditable — no como narrativa dispersa.

## 1. Ya resuelto en la v7 actual (verificado leyendo el código, no solo el docstring)

| # | Bug original | Dónde quedó resuelto | Nota |
|---|---|---|---|
| 1 | `~` sobre `shift()` de una Serie booleana (dtype `object`) fragmentaba cada ciclo en bloques de 1 | Sección 3, `calcular_ciclos_por_nivel`: `shift(1, fill_value=False).astype(bool)` | Documentado como BUG 1 en el encabezado |
| 2 | Mapeo difuso de columnas RIO enganchaba columnas vecinas (`MOTIVO`→ninguna, `ESTADO OPERACIONAL`→columna de combustible, `CONSIGNAS`→columna de limitación) | Sección 8, diccionario `MAPA_RIO` explícito + `leer_rio()` aborta si falta una columna obligatoria | Documentado como BUG 2 |
| 3 | Empalme mensual (`pd.concat`) sin recorte ni deduplicación, duplicaba energía si los archivos se traslapan | Sección 1: recorte `reporte_pasado[reporte_pasado['FECHA_HORA'] < f_min_actual]` + `drop_duplicates` | Documentado como BUG 3. Ver punto 2.1 más abajo — el `drop_duplicates` en sí tiene un caso no cubierto |
| 4 | Formato de `Llave_Concatenada` esperado (8 dígitos) no calzaba con el real (6 dígitos), waterfall completo en cero | Sección 5: `PATRONES_PO` prueba ambos formatos y detecta cuál calza | Documentado como BUG 4 |
| 5 | Con empalme activo, el ID de ciclo corrido rompía comparabilidad entre meses y la exención "primer ciclo sin RIO" | Sección 14.2 (renumeración de presentación) + `REGLA_EXENCION` parametrizada (`sin_historia` por defecto) | Documentado como BUG 5 |
| — | `reporte[suma_generacion != 0]` comparaba la suma agregada contra cero exacto, podía esconder un grupo con consumo de auxiliares que cancela la generación | Sección 2: `(s.fillna(0) != 0).any()` — evalúa bloque a bloque, no la suma agregada | Corregido pero **no está documentado como bug en el encabezado**; ver punto 3 |
| 7 | `Obs_Partida` mostraba "Sin tarifa" en un ciclo que en realidad fue rechazado por RIO, ocultando la causa real | Sección 14.7, `np.select` ahora evalúa primero `Config_RIO_Sin_Tarifa` / `Filtro_Conf` / `Filtro_Disp` / `Filtro_Op`, y "Sin tarifa" queda al final | Corregido, comentario explícito en el código lo confirma |
| 10 | Reconciliación final comparaba generación de dos meses (tras empalme) contra un `df_compacto` recortado a un mes | Sección 15: `gen_csv_mes` usa `reporte_actual` (no el `reporte` empalmado) contra `detalle_mes` (ya filtrado a `>= f_min_actual`) | Corregido |
| — | RIO cargado solo del mes actual: un ciclo que arrancó el mes pasado y sigue vivo no tenía ningún registro RIO al cual mirar hacia atrás | Sección 8/8.x: `RUTA_RIO_MES_PASADO` + `leer_rio()` reutilizable, mismo patrón de recorte/dedup que BUG 3 | Documentado como BUG 7 (nuevo desde la última revisión) |

La regla de negocio de margen (solo positivo, `TOLERANCIA_CORTES_BLOQUES = 0`,
diccionario mapea el mismo vocabulario para CSV y RIO) también coincide con
lo que confirmaste. No requieren cambio de código.

## 2. Pendiente — fixes de integridad a implementar

### 2.1 Empalme mensual: colisión de llave con datos distintos (probable causa: DST) puede borrar energía real en silencio

**Dónde:** Sección 1, bloque `if RUTA_REPORTE_MES_PASADO ...`, líneas del
`drop_duplicates(subset=llave_dedup, keep='last')` (justo después del
`pd.concat`).

**Problema:** `llave_dedup = ['FECHA_HORA', 'UNIDAD GENERADORA', 'Central',
'CONFIGURACION']`. Cuando dos filas colisionan en esa llave, el código
asume que son el mismo dato repetido (overlap entre el archivo del mes
pasado y el del mes actual) y se queda con una sola (`keep='last'`). Eso es
correcto cuando ambas filas tienen el mismo `GENERACION`. Pero si dos filas
colisionan en la llave con **`GENERACION` distinta**, no son un duplicado
real — el caso más probable es un cambio de hora (DST): Chile atrasa el
reloj en abril, y esa hora repetida produce dos bloques de 15 min físicos
distintos con la misma etiqueta de reloj. Hoy el código descarta uno de los
dos silenciosamente y pierde esa energía (y su margen, y puede alterar
`Horas_Detenida_Ciclo` si el bloque descartado era el que sostenía el ciclo
generando).

Hay un bloque más abajo (`rep = reporte.duplicated(subset=llave_ts,
keep=False)`) que **detecta** timestamps repetidos e imprime una alerta,
pero corre *después* de que el `drop_duplicates` ya actuó, y de todas
formas solo imprime — no corrige nada ni queda registrado en el Excel de
salida.

**Fix requerido:**

1. Antes de deduplicar, separar las filas colisionantes en dos grupos:
   - **Duplicado real**: incluye `GENERACION` (y si están presentes,
     `CMg-CV` y `Dolar`) idénticos entre las filas que comparten la llave.
     Se puede seguir usando `drop_duplicates(keep='last')` para este grupo.
   - **Colisión con datos distintos**: la llave se repite pero
     `GENERACION` difiere. Para este grupo, **sumar** `GENERACION` de las
     filas colisionantes en vez de descartar cualquiera (igual que ya se
     hace, por buena razón, con el `MOTIVO` no nulo al deduplicar el RIO
     empalmado — la regla general del proyecto es "no botar dato real
     porque colisiona una llave", no "quedarse con el último").
2. Registrar en `_audit_log` (vía `audit_gen` o una entrada manual) cuántas
   filas y cuántos MWh fueron afectados por cada uno de los dos casos, para
   que quede visible en la hoja `Auditoria_Pasos` del Excel de salida —
   hoy esa información solo existe como texto en la consola y se pierde.
3. El bloque de alerta existente (`rep = reporte.duplicated(...)`) debe
   quedar **después** de este fix y solo debería seguir detectando algo si
   quedó algún caso no cubierto por el punto 1 — si sigue disparando con
   frecuencia, es señal de que la lógica de arriba no está cubriendo todos
   los casos reales.

**No** se pide en esta spec resolver el problema general de DST con
zonas horarias (`tz_localize`/`tz_convert`); alcanza con no perder energía
cuando la colisión ocurre. Si en el futuro se necesita distinguir con
certeza cuál de los dos bloques es "antes" y cuál "después" del cambio de
hora (por ejemplo, para no mezclar `Horas_Detenida_Ciclo` de forma
incorrecta), eso queda fuera de alcance de Fase 1 y se abre como pendiente
separado.

### 2.2 Alerta de timestamps repetidos: agregar al log de auditoría exportado

**Dónde:** Sección 1, bloque `if rep.any(): ...`.

**Fix requerido:** además de los `print()` existentes, agregar una entrada
a `_audit_log` (mismo mecanismo que usa `audit_gen`) con el conteo de filas
y MWh involucrados, para que aparezca en la hoja `Auditoria_Pasos` del
Excel. Hoy esta alerta es invisible para alguien que solo revisa el Excel
de salida (el caso típico del negocio, que no corre el script y no ve la
consola).

### 2.3 `Config_RIO_Usada_Partida/Detencion` puede no coincidir con el registro RIO usado para los filtros Disp/Op del mismo ciclo

**Dónde:** interacción entre la Sección 10 (`merge_asof` con tolerancia de
24 horas, hacia atrás) y la Sección 14 (`ACTIVAR_BUSQUEDA_RELAJADA`,
ventana de ±30 min) cuando `USAR_TARIFA_RIO_INSTRUIDA = 1` (el default).

**Problema:** con `USAR_TARIFA_RIO_INSTRUIDA = 1`, todas las filas quedan
con `_Confiable_Partida`/`_Confiable_Detencion = False` (ese flag solo se
activa bajo `USAR_CONFIG_DOMINANTE`), así que **todos** los ciclos pasan
por la búsqueda relajada de ±30 min de la sección 14, que puede
sobrescribir `Consigna_Partida/Detencion`, `Motivo_Partida/Detencion`,
`Estado_Op_Partida/Detencion` y los tres filtros con un registro RIO
distinto al que ya se usó (vía el `merge_asof` de 24h de la sección 10)
para fijar `Configuracion RIO` / `Config_RIO_Usada_Partida` y por lo tanto
la tarifa cobrada. Es decir: la tarifa puede quedar fijada por un registro
RIO, y el filtro que decide si esa tarifa se paga o se rechaza puede quedar
fijado por **otro** registro RIO, hasta 30 minutos de distancia, sin que
quede rastro de que ocurrió.

Esto no es necesariamente incorrecto — puede ser una decisión de diseño
razonable (afinar Disp/Op con la mejor información disponible cerca del
instante) — pero hoy es invisible, y es exactamente el tipo de "dos
lógicas de cruce RIO compitiendo" que se identificó como problema en la
versión anterior del motor, solo que reformulado.

**Fix requerido (solo instrumentación, no cambia ningún costo):**

1. Antes de sobrescribir en la búsqueda relajada, guardar el
   `FECHA_HORA_RIO` (o un identificador equivalente) del registro que la
   Sección 10 usó para fijar `Configuracion RIO`, y el que la búsqueda
   relajada terminó usando para Disp/Op.
2. Agregar una columna `Diverge_Fuente_RIO_Partida` /
   `Diverge_Fuente_RIO_Detencion` (booleana) a `df_compacto` que sea `True`
   cuando ambos registros son distintos.
3. Sumar esto a la auditoría existente: imprimir cuántos ciclos y cuántos
   CLP de `Costo_Partida_Efectivo`/`Costo_Detencion_Efectivo` están en esa
   situación (mismo estilo que la sección 14.6, cascada financiera).

Con este dato medido, se decide después si hace falta unificar ambas
fuentes o si el comportamiento actual es aceptable — esa es una decisión
de negocio, no algo que se resuelva solo con código.

## 3. Documentación a corregir (no es un bug de cálculo)

El fix del punto "`reporte[suma_generacion != 0]`" (fila de la tabla de la
sección 1 marcada con `—`) ya está aplicado en el código pero no aparece en
la bitácora de bugs del encabezado del archivo (`BUG 1` a `BUG 7`). Agregar
una entrada `[BUG 8]` al docstring inicial de `src/sc_pd_motor_v7.py`
describiendo este fix, con el mismo formato que los demás (bug, causa raíz,
fix, referencia a la sección). Esto es solo documentación — no cambia
comportamiento — pero mantiene la bitácora como fuente de verdad completa,
que es justamente lo que la hace útil para una auditoría externa.

## 4. Pendiente de negocio — NO implementar en código todavía

Estos dos puntos quedaron abiertos en la conversación previa con el dueño
del proyecto y **no tienen respuesta de negocio confirmada**. No los
implementes ni los "arregles" — solo asegúrate de que sigan siendo
visibles como pendientes (ya lo son, vía comentarios en el panel de
control):

- `CODIGOS_EO_VALIDOS = ['PDO']` (línea ~192 del panel de control): el
  valor `'PDO'` no aparece en la columna `EO` de los RIO reales vistos
  hasta ahora (valores observados: `N, RO, DN, LF, DRO, PO, DF, DLF, LP,
  MM`). Es posible que el código correcto sea `'PO'`, pero eso requiere
  confirmación del CEN/negocio, no una decisión técnica.
- `Costos_de_P-D_Consolidado.xlsx` no ha sido compartido con quien hace la
  auditoría de este proyecto — sin él no se puede validar de forma
  independiente el tramo de tarifas Fría/Tibia/Caliente ni la columna
  `Costo_Cero`.

## 5. Tests a agregar (`tests/`)

El repo no tiene todavía carpeta `tests/` real (el `README.md` la describe
pero no existe — corregir eso también, ver `02-...` si aplica). Crear
`tests/test_fase1_integridad.py` con datos sintéticos mínimos (no datos de
producción) que cubran:

1. **`test_empalme_no_pierde_energia_en_colision`**: dos "archivos"
   sintéticos (mes pasado / mes actual, como DataFrames) donde una misma
   llave (`FECHA_HORA`, `UNIDAD GENERADORA`, `Central`, `CONFIGURACION`)
   aparece en ambos con `GENERACION` **distinta** (simulando DST). Verifica
   que la suma total de `GENERACION` después del empalme sea igual a la
   suma de ambas filas colisionantes (no la de una sola), y que un
   duplicado con `GENERACION` **idéntica** sí se deduplique a una sola
   fila.
2. **`test_ciclo_cruza_mes`**: una central generando de forma continua
   entre el día 30 del mes pasado y el día 2 del mes actual. Verifica que
   el ciclo no se corte en la frontera y que `Horas_Detenida_Ciclo` no
   quede `NaN` para ese ciclo.
3. **`test_micro_corte_corta_ciclo`**: una central con un solo bloque de 15
   min en cero entre dos tramos de generación. Con
   `TOLERANCIA_CORTES_BLOQUES = 0`, verifica que se detecten dos ciclos
   separados (no uno), consistente con la definición de negocio
   confirmada ("un ciclo va desde que la central parte generando hasta que
   deja de generar").
4. **`test_central_sin_registro_rio`**: una central con generación pero sin
   ningún registro en el RIO sintético del período. Verifica que el ciclo
   quede marcado para revisión manual (`Config_RIO_Sin_Tarifa` /
   `'Sin_Registro_RIO'`) y no se le cobre costo automático en 0 con una
   observación que sugiera otra causa.
5. **`test_prioridad_motivo_no_nulo_en_duplicado_rio`**: dos registros RIO
   sintéticos con la misma llave (`FECHA_HORA_RIO`, `Central_Relacionada_RIO`)
   donde solo uno trae `MOTIVO` informado. Verifica que el cruce se quede
   con el que trae `MOTIVO`, no con "el último" por orden arbitrario.
6. **`test_regresion_interruptores_apagados`**: con
   `USAR_CONFIG_DOMINANTE = 0` y `USAR_TARIFA_RIO_INSTRUIDA = 0`, sobre un
   fixture sintético pequeño con un resultado esperado calculado a mano,
   verifica que `Costo_Partida_Efectivo`/`Costo_Detencion_Efectivo` calcen
   exactamente. Este test protege contra que un cambio futuro rompa el
   comportamiento "clásico" (equivalente al v4) que los interruptores
   prometen preservar cuando están apagados.

Como el script actual corre como código de nivel de módulo (no expone
funciones separadas más allá de `calcular_ciclos_por_nivel`,
`resumen_central_relacionada_por_bloque`, `leer_reporte`, `leer_rio` y
`calcular_filtros`), los tests que no requieran el pipeline completo deben
probar esas funciones directamente. Los que sí requieren el flujo completo
(1, 2, 6) van a necesitar poder importar/ejecutar el script con rutas de
archivos temporales — si hace falta refactorizar mínimamente para que el
bloque de ejecución quede detrás de un `if __name__ == "__main__":` y una
función `main(rutas: dict, panel: dict)` para poder invocarlo desde un
test con fixtures en lugar de las rutas fijas del panel de control, hazlo
como parte de esta spec (es refactor técnico sin cambio funcional, no
requiere aprobación de negocio). Si se hace este refactor, verifica que
correr el script como antes (`python src/sc_pd_motor_v7.py`) siga
funcionando idéntico.

## 6. Qué NO hacer en esta spec

- No tocar `USAR_CONFIG_DOMINANTE`, `USAR_TARIFA_RIO_INSTRUIDA`,
  `REGLA_EXENCION` ni ningún otro interruptor de la sección 0 — son
  decisiones de negocio ya tomadas y confirmadas, no bugs.
- No agregar ninguna forma de tolerancia heurística de cortes de ciclo
  (`TOLERANCIA_CORTES_BLOQUES` debe seguir en `0`).
- No intentar resolver `CODIGOS_EO_VALIDOS` ni pedir/inventar el contenido
  de `Costos_de_P-D_Consolidado.xlsx` — son pendientes de negocio (sección
  4 de esta spec).
