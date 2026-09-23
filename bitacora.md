# Bitácora del proyecto

Este documento es el registro acumulativo de cambios del proyecto. Se debe
actualizar en cada *update* y no reemplazar las entradas anteriores.

Cada entrada identifica explícitamente su autor:

- **Claude**: planificación, especificaciones, revisión o decisiones de diseño.
- **Codex (OpenAI)**: implementación, pruebas y correcciones realizadas en el
  repositorio.

## Formato para próximos updates

Agregar la entrada más reciente al inicio de la sección correspondiente usando
esta estructura:

```markdown
### AAAA-MM-DD — Autor — Título breve

- **Tipo:** especificación | implementación | corrección | prueba | decisión.
- **Origen:** archivo, issue, conversación o commit que motivó el cambio.
- **Cambios:** resumen concreto de lo realizado.
- **Validación:** comandos o revisión ejecutada.
- **Pendientes:** trabajo que queda abierto, o `Ninguno`.
```

## Punto de partida para el próximo update (leer antes de tocar código)

Estado al **2026-09-14**, después del push directo a `main` de esta fecha.

**Qué hay en el repo**

| Pieza | Archivo | Estado |
|---|---|---|
| Motor de producción (ciclo por central relacionada) | `src/sc_pd_motor_v7.py` | Vigente. Specs 00–23 y 25 aplicadas. |
| Motor alternativo por turbina (ciclo por `UNIDAD GENERADORA`) | `src/sc_pd_motor_turbina.py` | Experimental, copia independiente (spec 24). No pisa al v7. |
| Motor "Reglas del Horario" (las 17 reglas del Excel sobre el dato de 15 min) | `src/sc_pd_motor_reglas_horario.py` | Funcional, **sin spec ni tests**. Solo para contrastar. |
| Reglas del Excel horario deducidas de sus fórmulas y VBA | `docs/informes/Reglas_Modelo_Horario.md` + `docs/informes/vba_modelo_horario/` | Referencia. |
| Informe de defensa del modelo 15 min | `docs/informes/Defensa_Modelo_15min.html` | Referencia. |
| Interfaz visual (tkinter) | `Carpeta_de_Trabajo/interfaz.py`, `Abrir_Interfaz.bat` | Vigente. Pestañas Configurar / Resultados / Pagos / Registro; botones Ejecutar, Prorratear y Generar entrega CEN (spec 34). |
| Runners para Spyder | `Carpeta_de_Trabajo/correr_motor*.py` | Vigentes. Editar solo las variables `NOMBRE_*`. |
| Consolidación de costos desde políticas PO | `scripts/consolidar_politicas.py` | Vigente (produce `Costos_de_P-D_Consolidado_AAMM.xlsx`). |

**Cómo correr y verificar**: `pytest -q` → 147 pruebas deben pasar. Los datos
(CSV/XLSX/XLSM/parquet) **no se versionan** (`.gitignore`); se dejan en
`Carpeta_de_Trabajo/`. Nunca escribir en la unidad `T:`; se copia a local.

**Decisiones de negocio tomadas (14-09-2026)** — no reabrir sin el dueño del proyecto:

1. **Tarifa del ciclo = la configuración más cara que generó en el ciclo**, restringida
   al combustible instruido por el RIO (`TARIFA_CONFIGURACION = 'maxima'`, spec 25).
   `'instruida'` (spec 15) queda solo para comparar.
2. **Margen truncado por bloque** (`MARGEN_NETEADO_POR_CICLO = 0`), igual que el Excel.
3. **Unidad de ciclo = central relacionada** (motor v7). El motor Turbina sigue
   disponible desde la interfaz.
4. **Vigencia de la instrucción RIO = 30 minutos** (15-09-2026): una partida o
   detención solo se justifica con una instrucción dada hasta 30 min antes (o 30
   min después, búsqueda relajada). `VIGENCIA_INSTRUCCION_RIO_MIN`, spec 27.
5. **Paradas cortas** (16-09-2026): toda interrupción de la generación es una
   detención y lo que sigue es una partida (`TOLERANCIA_CORTES_BLOQUES = 0`). Son
   paradas reales que el horario no detecta; no se tolera ninguna.
6. **Lista Pruebas** (16-09-2026): la fuente es el RIO (`CONSIGNAS = EP`). La hoja
   `Pruebas` del Excel es una copia del RIO con llave horaria; no se agrega insumo.
7. **Detención OM tras partida EP** (16-09-2026): se paga. Cada extremo del ciclo se
   evalúa por separado (GUACOLDA-1 23-ago, LOSVIENTOS &4, SANJAVIER).
8. **SSCC para aceptar OT** (16-09-2026): no hay decisión de fuente. El Excel usa el
   mismo comentario del RIO (`FIND("SSCC"|"CTF"|"CSF"|"CPF", COMENTARIO)`), pero su
   `Presta SSCC = IF(ISNUMBER(VLOOKUP(...)),1,0)` es siempre 1 → OT paga siempre.
   Es un defecto del Excel (30,0 MM en agosto), no una regla distinta.

**Decisiones abiertas** (el código las deja parametrizadas o documentadas):

- Primer ciclo sin historia: resuelto en parte por la spec 28 (cota inferior). Sigue
  la recomendación de exigir siempre el archivo del mes anterior.
- Valor exacto de la vigencia (30 min vigente). El concepto está decidido; la spec 27
  deja la sensibilidad 60/120 y la alternativa por consigna si se quiere afinar.
- Reportar al CEN los defectos del Excel horario, con celda y monto: instrucción
  asociada a la hora equivocada (R3, 48,7 MM), `Presta SSCC` con `ISNUMBER` (30,0
  MM), detenciones no marcadas por la macro (R2), PO de mitad de mes (R7), energía
  fuera de `xHyC` (ATACAMA en junio), COGEN excluido a mano.

**Cifras de referencia** (para detectar regresiones al correr con datos reales):

| Corrida | v7 `'instruida'` | v7 `'maxima'` (vigente) | Excel horario |
|---|---:|---:|---:|
| 2606 con empalme 2605 | 823.168.889 | **1.080.340.995** | 1.028.628.659 |
| 2608 sin julio | 536.027.769 | **875.313.107** | 957.823.663 (preliminar) |
| 2608 con empalme 2607 (interfaz, umbral 0,5 MWh) | — | **971.292.712** | 957.823.663 (preliminar) |
| 2606 con empalme 2605, `VIGENCIA_INSTRUCCION_RIO_MIN = 30` | — | **1.063.758.505** | 1.028.628.659 |
| 2607 con empalme 2606, `main` f820455 | — | **1.343.830.997** | (Excel de julio no comparado) |
| 2608 con empalme 2607, `RESOLUCION_MARGEN = 'hora'` (spec 30, solo para contraste) | — | 999.211.996 | 966.791.746 |
| **2608 con empalme 2607, `main` con erratum spec 25 (16-09)** | — | **939.959.962** | 966.791.746 |
| **2606 con empalme 2605, `main` con erratum spec 25 (16-09)** | — | **1.065.608.599** | 1.028.628.659 |
| 2608 con empalme 2607, `PARTIDA_EN_PRUEBAS = 'validar_orden_om_fallida'` (spec 33, apagado por defecto) | — | 1.008.974.072 | 966.791.746 |
| 2608 con empalme 2607, `PARTIDA_EN_PRUEBAS = 'validar_si_queda_disponible_om'` (spec 33, sensibilidad) | — | 1.184.861.113 | 966.791.746 |
| 2608 sin julio, `VIGENCIA_INSTRUCCION_RIO_MIN = 30` | — | **857.661.488** | 957.823.663 (preliminar) |
| 2606 con empalme 2605, vigencia 30 + cota inferior (spec 28) | — | **1.065.936.984** | 1.028.628.659 |
| 2608 sin julio, vigencia 30 + cota inferior (spec 28) | — | **910.213.848** | 957.823.663 (preliminar) |
| **2608 con empalme 2607, vigencia 30 + cota inferior (`main` f820455)** | — | **941.327.164** | 966.791.746 (corregido v2, sin traspasos; 914.259.268 en ciclos del mes) |

**Trabajo siguiente, en orden sugerido**

0. ~~Spec 33~~ — hecha y verificada (21-09). `PARTIDA_EN_PRUEBAS` sigue en `'rechazar'`;
   con `'validar_orden_om_fallida'` agosto sube a 1.008.974.072 (+69,0 MM, GUACOLDA-1).
   Falta la decisión del CEN sobre la observación de Guacolda.
0b. ~~Spec 32~~ — hecha y verificada (17-09): el libro con formato horario cierra al
   peso con el motor.
1. ~~Spec + tests para el motor Reglas del Horario~~ — hecho (spec 26, Codex).
2. ~~Conseguir julio 2026~~ — hecho; agosto corre con empalme (971,3 MM, +1,4% vs
   Excel). Queda revisar `CMg` nulo en el reporte `2608_v2` si se vuelve a usar.
3. Decidir la regla del primer ciclo sin historia (arriba) e implementarla como
   interruptor con spec, siguiendo el patrón de las specs 23 y 25.
4. Decidir los dos puntos abiertos de `docs/informes/Brechas_2608_por_empresa.md`:
   tolerancia a paradas menores a una hora (hoy toda interrupción es una partida) y
   fuente del filtro de pruebas (lista `Pruebas` del Excel vs `EP` del RIO). Ambos
   como interruptor con spec.
5. Rerun de junio con la exclusión COGEN del motor Reglas del Horario y actualizar
   `Defensa_Modelo_15min.html` con las cifras de la spec 25 y los mecanismos del
   informe de brechas de agosto.

**Convenciones**: cada cambio de regla es un interruptor en el panel del motor,
con spec en `docs/specs/NN-*.md`, tests y una entrada aquí. Nombres descriptivos
para las variantes (nada de "opción A/B"). Un modelo nuevo es un archivo nuevo,
nunca una modificación del v7.

**Reparto de verificación**: Codex no tiene ni tendrá los archivos operacionales
(reportes 15 min, RIO, costos PO, Excel horario); su entrega se valida con la suite
sintética. La verificación con datos reales de cada PR la hace Claude en la máquina
del dueño del proyecto: `pytest -q`, corrida completa de 2606 (con mayo) y 2608, y
contraste con las cifras de referencia de arriba, registrando el resultado en esta
bitácora. Un PR de Codex no se considera verificado hasta esa entrada.

## Updates

### 2026-09-23 — Claude — Verificación del PR #58 de Codex (correcciones a la spec 34)

- **Tipo:** verificación.
- **Origen:** PR #58 (`codex/corrige-tres-puntos-en-la-spec-34`), que corrige las tres
  observaciones de la revisión automática del PR #57.
- **Revisión del código:** los tres puntos están resueltos como se pidió, sin tocar los
  motores, la lógica del prorrateo ni pruebas existentes (salvo el fixture de `Ciclo_Mes`,
  como se indicó). (1) Sin retiros, la entrega borra los dos CSV de pagos de una corrida
  anterior. (2) `normalizar_etiqueta_ciclo` lleva `Etiqueta_Turbina` y la `Etiqueta` de Reglas
  del Horario a `Etiqueta_Relacionada`, y en el detalle de Reglas la reconstruye con la
  fórmula del motor. El conteo por empresa ya no depende de la etiqueta. (3) El mes sale de
  `max(Inicio_Ciclo)`.
- **Validación:** `pytest -q` → **147 passed** sobre `main` (3711438); `git diff --check`
  limpio.
- **Pendientes:** los de la spec 34 §5 (verificación con agosto y los retiros reales). Sigue
  sin haber CI: los PR con automerge entran sin correr pruebas.

### 2026-09-23 — Codex (OpenAI) — Correcciones posteriores a la revisión de la spec 34

- **Tipo:** corrección + pruebas.
- **Origen:** revisión de la spec 34 después del PR #57.
- **Cambios:** la entrega sin retiros elimina los dos CSV de pagos que pudiera haber dejado
  una corrida anterior; la interfaz normaliza las etiquetas de ciclo de las salidas v7,
  Turbina y Reglas del Horario antes de resumir o prorratear; y el mes mostrado se deriva de
  la fecha máxima de inicio de ciclo, en vez del ordinal `Ciclo_Mes`. No se modificó ningún
  motor ni la lógica del prorrateo.
- **Validación:** `pytest -q` → **147 passed**; `git diff --check` limpio.
- **Pendientes:** Ninguno.

### 2026-09-23 — Claude — Interfaz con resultados visibles y botón Prorratear: PAGA en la entrega CEN (spec 34)

- **Tipo:** implementación + pruebas.
- **Origen:** pedido del dueño del proyecto: interfaz más amigable, la salida del motor más
  visible y un botón "Prorratear" para que la entrega CEN muestre quién paga.
- **Cambios:** `generar_entrega(..., retiros=)` / `--retiros` prorratea con la lógica de la
  spec 11, solo los ciclos con monto. Agrega la hoja `Cuadro de pagos` (Prorrata = C/D,
  F = SUMIFS de `Sobrecosto_Ciclo!H` con Ciclo completo = 1, PAGA = E×F) y llena
  `RESUMEN!PAGA` con SUMIF. SALDO = RECIBE − PAGA y `G1 = SUM(SALDO)` cuadra en 0. Sin retiros
  la entrega sale igual que antes. Interfaz nueva con pestañas: **Resultados** (total, ciclos
  pagados / cubiertos / rechazados / diferidos, waterfall, empresas, top 15 ciclos, avisos),
  **Pagos** (cuadratura y monto por suministrador) y **Registro**. Barra fija con Ejecutar,
  Prorratear y Generar entrega CEN (versión Preliminar/Definitivo). La lectura de la salida
  quedó en `src/resumen_salida.py`, sin tkinter. `leer_retiros` pasó a
  `src/prorrateo_15min.py`; el script lo reexporta.
- **Validación:** `pytest -q` → **144 passed**. Interfaz manejada bajo Xvfb con una salida
  sintética de 62 ciclos y 12 suministradores: resultados, prorrateo (diferencia 0) y entrega
  con pagos de punta a punta. En este entorno no hubo motor de hojas de cálculo para
  recalcular las fórmulas nuevas. Los valores guardados salen de pandas y los prueban los tests.
- **Pendientes:** verificación con agosto y los retiros reales (spec 34 §5): cuadratura,
  `RESUMEN!G1` ≈ 0 recalculado en Excel y si los nombres de `Suministrador` calzan con los de
  `Empresa`.

### 2026-09-21 — Claude — Verificación de la spec 33 (PR #56) con agosto y junio: una corrección y cifras de sensibilidad

- **Tipo:** corrección + prueba + verificación.
- **Origen:** PR #56 de Codex (`codex/implementar-partida-en-pruebas-en-el-motor`).
- **Cambios:** la condición O (la orden no sincronizó) miraba la generación del reporte
  completo sin `Central_Relacionada` —el reporte crudo no trae esa columna, solo
  `reporte_sin_ceros`— y cualquier MWh del sistema entre la orden y el inicio la
  anulaba: `'validar_orden_om_fallida'` nunca validaba nada, y la prueba sintética no lo
  veía porque su reporte sí traía la columna. `main()` ahora mapea `Central_Relacionada`
  con el diccionario antes de llamar a `aplicar_partida_en_pruebas`, que aborta si falta
  la columna. Dos pruebas nuevas (`test_10`, `test_11`). Interfaz, runner, export y
  consola del PR quedan como vinieron.
- **Validación:** `pytest -q` → **136 passed**. Agosto con julio: `'rechazar'`
  939.959.962 (sin cambio); `'validar_orden_om_fallida'` **1.008.974.072** (+69.014.110:
  GUACOLDA-1&1 +68,58 MM, CHUYACA&3 +0,43 MM); `'validar_si_queda_disponible_om'`
  **1.184.861.113** (+244.901.151, 13 ciclos liquidados + 7 diferidos marcados). Junio con
  mayo: 1.065.608.599 / 1.065.608.599 (CMPCCORDILLERA&4 validado, Δ 0 por margen) /
  1.074.540.295 (+8,93 MM). Ningún ciclo no validado cambió. Detalle en spec 33 §9.
- **Pendientes:** decisión del CEN sobre la observación de Guacolda (el interruptor sigue
  en `'rechazar'`); la interfaz ya permite activarlo. Codex: en reglas que cruzan con el
  reporte, la spec debe decir qué DataFrame se pasa y qué columnas trae; la prueba
  sintética debe replicar las columnas reales del motor.

### 2026-09-21 — Claude — Observaciones al Excel de agosto revisadas contra el motor; spec 33 (partida en pruebas tras orden fallida)

- **Tipo:** análisis + especificación + decisión.
- **Origen:** cuatro observaciones de empresas al `Sobrecostos_PD_2608_pre` (TOCOPILLA-TG3,
  GUACOLDA-1, TRAPEN_DIESEL, PENON_DIESEL).
- **Análisis:** TRAPEN 10/08 y PENON 10/08 están cubiertos: el motor separa las activaciones
  CTF (+) en ciclos propios (TRAPEN &4–&7, PENON &6–&7) y paga partida y detención en cada
  uno; el Excel las fundió en un ciclo (R1). TOCOPILLA-TG3 **no** está cubierto por dato:
  el reporte de 15 min de agosto y la hoja `Gen` del Excel traen 0 MWh en los 2.976
  bloques de TG3 mientras el RIO registra 8 PP / 8 PS OM a mínimo técnico y julio sí trae
  1.619 MWh; hay que reponer la generación en el origen. Además `TOCOPILLA-TG3_GN_B` (y
  `_GN_C/_GN_D`) faltan en `Diccionario_central_config`, el CV de `_GN_B` en el reporte
  es 0,99 USD/MWh (placeholder) y el consolidado de costos 2608 trae 693 filas con
  `DIA = 260909`. GUACOLDA-1: el RIO trae PP OM 21/08 23:16 → FS OT DF "Falla en la
  pártida" → EP "según IF 2026004644" 23/08 00:50 → MT OM "Disponible y cancela IF" 05:00;
  el motor rechaza la partida por EP. El dueño del proyecto concuerda con la empresa: el
  EP cerró la partida ordenada por mérito, la partida es válida.
- **Decisión (21-09-2026):** la validación de la partida EP queda como característica
  **activable desde la interfaz**, apagada por defecto, con dos lecturas: solo orden OM
  fallida (grupo Guacolda: GUACOLDA-1&1 y CHUYACA&3, +69,0 MM en agosto) o toda partida
  EP que queda disponible OM en el mismo ciclo (13 ciclos, +244,9 MM; incluye salidas
  intempestivas y retornos de mantención, cronologías distintas a la de Guacolda).
  `docs/specs/33-partida-en-pruebas-tras-orden-fallida.md`.
- **Validación:** ninguna todavía (spec). Los 21 ciclos EP de agosto y sus cronologías RIO
  están en la §2 de la spec.
- **Pendientes:** Codex implementa la spec 33; Claude verifica con agosto y junio.
  Responder las observaciones de TG3 con la evidencia del dato faltante.

### 2026-09-17 — Claude — Verificación de la spec 32 (PR #55) con agosto real: el libro con formato horario cierra al peso

- **Tipo:** corrección + prueba + verificación.
- **Origen:** PR #55 de Codex (`codex/implementar-formato-excel-para-entrega`). El PR
  trajo la estructura pero no la cadena de fórmulas: faltaban `Sobrecosto_Ciclo!F:K`,
  `Q:S` y los checks, `RESUMEN!D:G`, `PARTIDAS_DETENCIONES!V:Y`; `I` traía la etiqueta
  completa y `N` quedaba `COLMITO&COLMITO&1`; el dólar del extremo y el combustible
  instruido no se calculaban; `Presta SSCC` miraba el motivo y no el comentario; la
  columna `Empresa` del motor pisaba la del Excel y los diferidos entraban al RESUMEN.
  El libro además no abría (`<v></v>` vacíos, strings `=` como fórmulas, `MAXIFS` sin
  `_xlfn.`). Detalle en spec 32 §10.
- **Cambios:** `scripts/generar_entrega_cen.py` reescrito sobre el esqueleto del PR
  (una función por hoja, escritura fila a fila con `constant_memory`, lectura con
  `calamine`, fórmulas pesadas solo en los extremos, columnas de la detención `AQ:AY`,
  agrupación de unidades generadoras por configuración, `Central_Empresa` con el rescate
  del motor). Motor, solo export: `Resumen_Ciclos_PD` suma `Flag_Exencion`,
  `Comentario_*`, `Fuente_Config_RIO_*`, `Fuente_Filtros_RIO_*`; `Vigencia_RIO_*` pasa a
  1 cuando la búsqueda relajada aportó los filtros (antes describía la instrucción
  descartada). `tests/test_generar_entrega_cen.py` reescrito: 9 pruebas con los casos
  de la spec §9.
- **Validación:** `pytest -q` → **125 passed**. Agosto con julio (`main`): libro abre por
  COM sin reparar, recálculo 8 s; `Sobrecosto_Ciclo!T:W` = 0 en 390/390; `RESUMEN!F` = 0
  en 27/27 y `G1` = **939.959.962**; `xHyC!BE` = 0 en 41.300 bloques. `COLMITO&1`
  idéntico al peso al Excel horario v2 (207.054 / 168.434). Motor sin cambio de monto
  (939.959.962). Paquete entregado en `C:\Kpi SC_PD\5 a 6\Claude\Entrega_SCPD_2608`.
- **Pendientes:** que el dueño del proyecto lea el libro y diga si la disposición le
  sirve; cerrar PR #53 (duplicado); refrescar la Defensa v2 con el erratum (941,3 →
  940,0 MM). Para Codex: en specs con muchas fórmulas conviene exigir en §9 la prueba
  "valores en pandas = motor" desde el principio; esta vez el PR pasó su propia suite
  sin reproducir un solo monto.

### 2026-09-16 — Claude — Spec 32: el entregable al Coordinador debe tener el formato del Excel horario

- **Tipo:** especificación + decisión.
- **Origen:** revisión del paquete `Entrega_SCPD_2608` generado por la spec 31. Decisión
  del dueño del proyecto: *"el entregable debe tener un formato lo más parecido al Excel
  horario que ya existe"*. Las tablas `Ciclos`/`Bloques`/`Candidatas` con nombres del
  motor no sirven a quien audita con el libro horario en la cabeza.
- **Cambios:** `docs/specs/32-entrega-formato-excel-horario.md`. El libro se reconstruye
  con las hojas, encabezados y letras de columna del `Sobrecostos_PD_AAMM.xlsm`
  (`Menu`, `Costos_de_P-D`, `Pruebas`, `Instrucciones RIO`, `Central_Empresa`,
  `Sobrecosto_PD xHyC`, `PARTIDAS_DETENCIONES`, `Sobrecosto_Ciclo`, `RESUMEN`, `Ciclos
  inconclusos`) a resolución de 15 minutos, con la misma cadena de fórmulas
  `xHyC → PARTIDAS_DETENCIONES → Sobrecosto_Ciclo → RESUMEN` (`SUMIF`/`MAXIFS` por letra,
  rangos acotados). Las columnas del motor van a la derecha de la última del Excel.
  Cuatro diferencias de regla quedan visibles en la fórmula y declaradas en `Leeme`:
  tarifa al dólar del extremo (`USD apertura ciclo`), filtros EP/operacional en la
  instrucción del extremo (multiplican en `PARTIDAS_DETENCIONES!S/T`), vigencia ±30 y
  `Presta SSCC` desde el comentario. El motor solo gana tres hojas de export
  (`RIO_Usado`, `Costos_PD_Usados`, `Central_Empresa`). Los CSV pasan a ser el volcado
  de esas mismas hojas. La estructura del Excel horario se levantó del libro v2 de
  agosto con `openpyxl` (encabezados y fórmulas de la fila 2 de cada hoja).
- **Validación:** ninguna todavía. Codex implementa con pruebas sintéticas (§9); Claude
  verifica con agosto (§10): checks en cero en 390 ciclos, `RESUMEN!G1` = 939.959.962.
- **Pendientes:** implementación (Codex); refrescar la Defensa v2 con el erratum de la
  spec 25 (941,3 → 940,0 MM); cerrar PR #53 (duplicado de #52/#54).

### 2026-09-16 — Claude — Verificación de la spec 31 (PR #54) con datos reales: cuatro correcciones y un erratum de la spec 25

- **Tipo:** revisión + corrección + prueba.
- **Origen:** PR #54 de Codex (paquete de auditoría CEN). Suite verde (117); con la
  salida real de agosto el paquete se generaba pero el libro no abría en Excel y los
  checks no cerraban.
- **Correcciones en `scripts/generar_entrega_cen.py` y el motor:** (1) referencias
  estructuradas completas `Tabla[[#This Row],[Col]]` — con la forma corta que emite
  xlsxwriter Excel pide reparar el archivo; (2) el motor exporta `CMg`, `CV`, `Dolar`
  y `UNIDAD GENERADORA` en `Detalle_15Min` (faltaban: `Check_Margen` fallaba en 111
  ciclos); (3) hoja nueva `Detalle_Frontera` con los bloques del mes anterior de los
  ciclos vivos en el mes, que el paquete concatena (sin ella el margen de 4 ciclos de
  frontera no se reproducía); (4) candidatas con filtro de combustible por extremo y
  `MAXIFS` separado para partida y detención; `COUNTIF` en los resúmenes (el
  `COUNTIFS` de tres argumentos era inválido) y validación por rango.
- **Erratum spec 25:** el máximo se tomaba sobre `Costo_*_ML` del bloque (tarifa × dólar
  de ese bloque), premiando el día de dólar más alto del ciclo. Ahora
  `tarifa_valorizada_al_extremo()`: USD de la configuración × dólar del bloque de
  apertura/cierre. Agosto 941.327.164 → **939.959.962** (−1,37 MM, 30 ciclos, hasta
  2,7% en ciclos de julio→agosto); junio 1.065.936.984 → **1.065.608.599**.
- **Validación:** paquete de agosto abierto en Excel por COM sin reparación y
  recalculado: `Check_SC` = 0 y `Check_Margen` = 0 en 390/390 ciclos; `Candidatas`
  reproduce `Costo_Partida_Base` salvo diferidos (base 0 por regla); `Resumen_Empresa`
  y `Resumen_Central` suman 939.959.962. 120 pruebas (3 nuevas). `--tablas-dinamicas`
  no crea tablas dinámicas (solo avisa); las hojas `SUMIFS` son la salida oficial.
- **Pendientes:** el PR #53 (`codex/formaliza-script-comparar-con-excel-horario-lh58m0`)
  duplica trabajo ya mezclado (#52 y #54); cerrarlo sin mezclar. Regenerar la defensa
  v2 con las cifras del erratum (diferencia < 0,2%; las conclusiones no cambian).

### 2026-09-16 — Codex (OpenAI) — Spec 31: entrega de auditoría CEN

- **Tipo:** implementación + especificación + prueba.
- **Origen:** solicitud de paquete reproducible para auditoría del Coordinador.
- **Cambios:** generador de seis CSV y libro Excel con tablas/fórmulas/checks,
  hashes e inventario del panel; función pública de candidatas de tarifa máxima;
  runner y botón sobre la última salida en la interfaz.
- **Validación:** suite `pytest -q` y compilación de los scripts.
- **Pendientes:** Claude verificará agosto real, incluidas las diferencias cero.

### 2026-09-16 — Claude — Defensa del modelo, versión 2

- **Tipo:** documentación.
- **Cambios:** `docs/informes/Defensa_Modelo_15min.html` reescrito (mismo diseño,
  contenido nuevo). Reemplaza la versión del 10-09, que defendía la tarifa instruida
  (spec 15) y los 24 ciclos contestables; esa regla ya no está vigente.
- **Contenido:** (1) veredicto: sobre los mismos ciclos agosto cierra en +0,1% con
  207 de 352 pares al peso; (2) el experimento de junio como historia (94,8% regla) y
  la adopción de la regla del horario (spec 25); (3) tabla de reglas vigentes con su
  spec; (4) agosto ciclo a ciclo, dos alcances, por empresa; (5) descomposición
  exacta por causa raíz y balance por familia (defectos del Excel +52,4 / −18,0,
  resolución −31,5, reglas propias −2,4); (6) nueve defectos del Excel con celda,
  monto y estado; (7) resolución demostrada con la spec 30 (R9 54,3 → 2,9 MM) y las
  paradas cortas; (8) cierre y límites declarados.
- **Pendientes:** actualizar el cruce ciclo a ciclo de junio con el motor actual
  (hoy solo el total: 1.065.936.984 vs 1.028.628.659).

### 2026-09-16 — Claude — Verificación de las specs 29 y 30 (PR #51 y #52) con datos reales

- **Tipo:** revisión + corrección + prueba.
- **Spec 30 (`RESOLUCION_MARGEN`)**: correcta sin cambios. Agosto con julio, `'hora'`:
  SANISIDRO-2 margen 644,2 → 587,9 MM (a mano había estimado 583,5; Excel 565,2),
  SANISIDRO-1 656,2 → 614,8, NEHUENCO-2 54,5 → 41,1; total 941,3 → 999,2 MM. En
  ciclos del mes la causa R9 pasa de −54,3 MM (bruto 54,3) a **−1,1 MM (bruto 2,9)**:
  el margen por bloque vs por hora queda demostrado como resolución pura. Con
  `'bloque'` reproduce 941.327.164 al peso.
- **Spec 29 (comparador)**: la lógica es la de los scripts de referencia y con
  fixtures pasaba, pero con el libro real fallaba tres veces: (1) `Sobrecosto_Ciclo`
  trae columnas auxiliares `Ciclo` y `Copia Ciclo` y encabezados vacíos repetidos →
  `AttributeError` al renombrar; (2) `read_only` entrega ~81.000 filas vacías bajo la
  tabla, que se contaban como ciclos; (3) el mes se tomaba del mínimo de
  `Inicio_Ciclo`, que con empalme es julio → alcance del mes vacío. Además la
  descomposición del mes completo no cerraba porque el SC publicado incluye la
  partida y el margen heredados (F y G) y las componentes no. Corregido en
  `scripts/comparar_con_excel_horario.py` (deduplicación de columnas, filtro de filas
  vacías, mes de los ciclos propios, componentes con herencia) y cubierto con dos
  pruebas sobre un libro con la forma real (116 pruebas).
- **Validación:** `comparar(Motor_2608_julio, Excel corregido v2)` reproduce la
  quinta ronda al peso: mes completo 941.327.164 vs 966.791.746 (−25,46 MM); ciclos
  del mes 914.820.834 vs 914.259.268 (+561.566); causas R3 48,7 / R6 ±47,3 / R5
  −25,3 / R1 +25,0 / R9 −54,2 / R2, R4, R7 iguales al diagnóstico manual. Tiempo:
  ~110 s. `Carpeta_de_Trabajo/correr_comparacion.py` queda operativo.
- **Pendientes:** actualizar `Defensa_Modelo_15min.html` con specs 25–30 y el
  diagnóstico de agosto; rehacer junio con `main` actual.

### 2026-09-16 — Codex (OpenAI) — Spec 30: resolución configurable del margen

- **Tipo:** especificación + implementación + prueba.
- **Origen:** causa R9 de `docs/informes/Brechas_2608_por_empresa.md` y solicitud de
  reproducir dentro del v7 el truncamiento horario del Excel.
- **Cambios:** se agregó `RESOLUCION_MARGEN = 'bloque' | 'hora'`, con `'bloque'`
  como default sin regresión; la función pura `margen_por_hora()` agrega por central
  y hora, calcula el margen y lo reparte por generación. El runner, la interfaz, la
  consola y `Guia_Lectura` exponen/documentan la selección. No se modificaron los
  motores Turbina ni Reglas del Horario.
- **Validación:** `pytest -q` y pruebas dedicadas en
  `tests/test_resolucion_margen.py`.
- **Pendientes:** Claude verificará las cifras con los datos reales.

### 2026-09-16 — Claude — Decisiones 5 a 8 cerradas; TOCOPILLA-U16 &1 aclarado

- **Tipo:** decisión + análisis con datos reales.
- **Origen:** respuestas del dueño del proyecto a las decisiones pendientes.
- **Decisiones:** paradas cortas se cobran (son paradas reales que el horario no ve);
  la vigencia de la instrucción se mantiene (no tiene sentido lejos del inicio de la
  generación); la lista Pruebas es el mismo RIO con llave horaria (no se agrega
  insumo); la detención OM tras partida EP se paga. SSCC: el Excel usa el mismo
  comentario del RIO; su `Presta SSCC` con `ISNUMBER` hace que OT pague siempre —
  defecto del Excel, no decisión (7 casos, −18,0 MM de los −25,3 de R5 en ciclos
  del mes; 30,0 MM en todo agosto).
- **TOCOPILLA-U16 &1 (50,4 MM en el Excel v2):** corrida de julio con junio
  empalmado. El motor sí cobra la partida instruida de TOCOPILLA del 29-jul
  (PMT/OM 03:53, ciclo 03:45 → 11:00, **51,07 MM en julio**). A las 11:02 la unidad
  sale por falla (FS/OT/DF, IF 2026004027), resincroniza en pruebas a las 13:42 y
  14:42 (EP, "sincronizada en pruebas según IF 2026004027") y recién a las 16:40
  pasa a operación (MT/OM). El ciclo que cruza a agosto arranca a las 14:30 en EP:
  no hay instrucción OM de partida, y el Excel lo paga porque en su hora clave
  encuentra el FS/OT de las 13:44 y OT siempre pasa por el bug de `Presta SSCC`.
  Bajo la regla que ambos modelos declaran, esa partida no se cobra; la legítima
  ya está pagada en julio. Cifra de referencia julio con junio: 1.343.830.997.
- **Pendientes:** Codex — herramienta de comparación contra el Excel y margen a
  resolución configurable; Claude — junio con `main` actual.

### 2026-09-15 — Claude — Excel corregido v2 (sin margen heredado): comparación actualizada

- **Tipo:** análisis con datos reales.
- **Cambios:** subsección "Actualización 15-09 (tarde)" en la quinta ronda de
  `docs/informes/Brechas_2608_por_empresa.md`.
- **Hallazgos:** el Excel quitó el margen heredado de julio; total sin traspasos
  897,6 → 966,8 MM. Mes completo Excel 966,8 vs motor 941,3 (−2,6%); ciclos del mes
  sin cambio (+0,1%). COLBUN queda −1% con CANDELARIA-1/2 &1 idénticas al peso. La
  brecha grande nueva es TOCOPILLA-U16 &1: el Excel cobra 50,4 MM de partida
  heredada de julio que el motor rechaza por EP (RIO 29-jul "sincronizada en pruebas
  según IF 2026004027"). Pendiente confirmar con el área si esa partida corresponde.
- **Pendientes:** los mismos.

### 2026-09-15 — Claude — Agosto definitivo: motor `main` con julio empalmado vs Excel corregido

- **Tipo:** análisis con datos reales.
- **Origen:** el dueño del proyecto entregó las rutas de julio en `T:`; se copiaron
  (solo lectura) a `Carpeta_de_Trabajo` como `Reporte_PD_15min_2607_v2.csv`,
  `RIO_07_2026.xlsx` y `Costos_de_P-D_Consolidado_2607.xlsx`.
- **Cambios:** sección "Quinta ronda" en `docs/informes/Brechas_2608_por_empresa.md`
  (reemplaza la cuarta, que corrió sin julio); scripts `correr_2608_julio.py`,
  `solo_mes2_v3.py`, `diagnostico_v3.py` en `scripts_brechas_2608/`.
- **Hallazgos:** mes completo Excel 897,6 vs motor **941,3 MM (+4,9%)**, Σ|Δ| por
  empresa 71,4 MM (14-09: 141,6). **Ciclos del mes sin herencia: 914,3 vs 914,8 MM
  (+0,1%)**, 207 de 352 pares idénticos al peso. La diferencia del mes completo es
  frontera: 26,5 MM de ciclos de julio liquidados en agosto que el Excel anula con
  margen heredado. Specs 27+28 vs corrida del 14-09: −29,97 MM (ENEL −11,7 por
  SANISIDRO-1 &1 de frontera; SGA −9,1; GMETROPOLITANA −8,6; ORAZUL +0,6), en todos
  los casos con contraparte el Excel también daba 0.
- **Pendientes:** decisiones abiertas sin cambio (SSCC, paradas cortas, Pruebas vs
  RIO, EP+OM, valor de la vigencia).

### 2026-09-15 — Claude — Agosto: motor con specs 27 y 28 vs Excel corregido

- **Tipo:** análisis con datos reales.
- **Cambios:** sección "Cuarta ronda" en `docs/informes/Brechas_2608_por_empresa.md`.
- **Hallazgos:** sin julio, mes completo Excel 897,6 vs motor 910,2 MM (+1,4%);
  Σ|Δ| por empresa 49,9 MM (era 141,6); ciclos del mes −0,4%, 210 de 353 pares
  idénticos. SGA baja de +14,1 a +5,0 (spec 27) y ORAZUL queda en −0,05 (spec 28).
  Parte del acercamiento es artefacto de correr sin julio (los ciclos de la hora 1
  no cobran partida, como el Excel; NEHUENCO-2 &1 cobra tarifa TG1 por cota).
- **Pendientes:** repetir con julio empalmado cuando los tres archivos de julio
  estén en `Carpeta_de_Trabajo`.

### 2026-09-15 — Claude — Verificación de la spec 28 (PR #50) con datos reales: corrección de un crash

- **Tipo:** revisión + corrección + prueba.
- **Origen:** PR #50 de Codex (cota inferior de horas sin historia). La suite
  pasaba (104) pero el motor abortaba con datos reales:
  `horas_cota_inferior()` hacía `(Series − Timestamp).total_seconds()` — la
  prueba solo cubría el camino escalar y `main()` la llama con Series.
- **Cambios:** `src/fase1_integridad.py` — camino vectorizado con
  `.dt.total_seconds()` y alineación de índice; `tests/test_horas_sin_historia.py`
  — prueba nueva sobre Series como las del motor (105 pruebas).
- **Validación con datos reales:** 2608 sin julio 857.661.488 → **910.213.848**
  (+52,55 MM): de 60 ciclos sin historia, 48 pasan a Fría por cota (todos "inicia
  y termina este mes"; YUNGAY-1/2 cobran 313.210 cada uno como en el Excel;
  NEHUENCO-2 &1 +16,6 MM; ATACAMA-2 &1 +14,0 MM), 8 quedan "sin historia
  suficiente" y 4 diferidos. 2606 con mayo 1.063.758.505 → **1.065.936.984**
  (+2,18 MM, 3 ciclos: LOSGUINDOS, OLIVOS, NUEVAALDEA-2). Con julio empalmado el
  efecto en agosto se limita a unidades que no generaron en julio.
- **Observación:** con `TARIFA_CONFIGURACION = 'maxima'`, si la cota no supera el
  umbral Fría de la configuración combinada pero sí el de una configuración
  simple (umbral 0), gana la simple: NEHUENCO-2 &1 cobra la tarifa TG1 (18.000
  USD) y no la TG1+TV1. Es el comportamiento pedido (cota inferior, conservador),
  pero conviene tenerlo presente al leer ciclos con historia estimada.
- **Pendientes:** ninguno de esta spec. Sigue abierto: valor de la vigencia
  (spec 27), fuente del SSCC, paradas cortas, Pruebas vs RIO, EP + OM.

### 2026-09-15 — Codex (OpenAI) — Spec 28: cota inferior sin historia

- **Tipo:** especificación, implementación y pruebas.
- **Origen:** `docs/informes/Brechas_2608_por_empresa.md`, mecanismo (10) y
  causa R8; decisión de implementar `HORAS_SIN_HISTORIA` con
  `'cota_inferior'` activo por defecto.
- **Cambios:** se agregó la función pura `horas_cota_inferior()` y la
  clasificación Fría segura del primer ciclo cuando el periodo observable ya
  supera `Fria_Num1_M`; la alternativa `'nulo'` conserva el comportamiento
  anterior. `Horas_Detenida_Ciclo` permanece nula, por lo que la exención RIO
  `'sin_historia'` sigue activa. Se exportan `Horas_Cota_Inferior` y
  `Horas_Detenida_Estimada`, se documentan en `Guia_Lectura`, y el interruptor
  quedó expuesto en runner e interfaz solo para v7.
- **Validación:** `pytest -q` (104 pruebas), `python -m py_compile src/*.py
  Carpeta_de_Trabajo/*.py tests/*.py` y `git diff --check`.
- **Pendientes:** validar con los archivos operacionales empalmados de julio y
  agosto que YUNGAY-1/YUNGAY-2 reconozcan 313.210 CLP por unidad y revisar el
  caso TENOGAS_GLP. Los datos no se versionan.

### 2026-09-15 — Claude — Spec 27: vigencia de la instrucción RIO (±30 min) implementada

- **Tipo:** decisión + implementación + prueba.
- **Origen:** al revisar el listado de filtros del motor, el dueño del proyecto
  decidió que la instrucción RIO que justifica una partida/detención solo se
  busque en ±30 minutos; el cruce maestro aceptaba la última instrucción hasta
  24 h atrás.
- **Cambios:** `VIGENCIA_INSTRUCCION_RIO_MIN = 30` en el panel del v7; función
  pura `filtro_vigencia_rio()`; `Filtro_Operacional = f_op × Vigencia_RIO` por
  bloque; columnas `Vigencia_RIO_Partida/Detencion` en el compacto y el export;
  observación "Rechazo: instruccion RIO fuera de vigencia (> N min)"; runner e
  interfaz exponen el valor (0 = sin límite). `docs/specs/27-vigencia-instruccion-rio.md`.
- **Validación:** `pytest -q` → **99 pruebas** (5 nuevas). Corridas reales:
  2608 sin julio 875.313.107 → **857.661.488** (−17,65 MM, 11 ciclos: NUEVARENCA
  &5 −8,56, siete detenciones de CORONEL −8,05, EMELDA, TENOGAS, CMPC); 2606 con
  mayo 1.080.340.995 → **1.063.758.505** (−16,58 MM). Con 0 se reproduce el
  número anterior peso a peso.
- **Pendientes:** el valor 30 rechaza NUEVARENCA &5 aunque tiene PP/OM 90 min
  antes y PMT/OM 31 min después; la spec deja la tabla de sensibilidad (60/120/240)
  y una alternativa por consigna (PP/PMT para partida, PS/FS para detención) por
  si se quiere afinar.

### 2026-09-15 — Claude — Diagnóstico de causa raíz de las diferencias en ciclos completos del mes

- **Tipo:** análisis con datos reales.
- **Origen:** pedido de un diagnóstico preciso del porqué de las diferencias.
- **Cambios:** sección "Diagnóstico de causa raíz" en
  `docs/informes/Brechas_2608_por_empresa.md`; `scripts_brechas_2608/diagnostico.py`
  (descomposición exacta del ΔSC por ciclo en efecto partida/detención/margen y
  asignación a causa raíz con los internos de `xHyC`, `PARTIDAS_DETENCIONES` y las
  `Obs_*` del motor).
- **Hallazgos:** +18,8 MM netos = 241,9 MM brutos. Causas: R3 el Excel busca la
  instrucción RIO por clave hora-reloj de la hora en que arranca la configuración del
  MAXIFS y pierde las instrucciones emitidas minutos antes (+66,4 MM, 16 ciclos;
  52 partidas y 53 detenciones con `Instrucción` vacía en agosto); R9 convexidad del
  truncamiento con CMg/CV variables dentro de la hora (−61,4 MM; verificado
  SANISIDRO-2: +60,6 MM por bloque vs hora); R6 conjunto de configuraciones que
  compite por la tarifa (±47,3, neto +0,9); R5 `Presta SSCC = 1` en 400 de 414
  partidas del Excel → OT siempre paga, motor exige SSCC en el comentario (−25,3);
  R1 paradas cortas (+25,0); R2 flags de la macro (+9,7); R4 lista Pruebas (+4,5);
  R7 PO (+0,55); R8 sin historia (−0,9). Balance: defectos del Excel +76,7;
  resolución −37,1; reglas por decisión −19,9; motor −0,9. Corrige la nota del
  14-09: NUEVARENCA &4 es R3 (hora-reloj), no lista Pruebas.
- **Pendientes:** decisiones (2) paradas cortas, (5) Pruebas vs RIO, SSCC (fuente del
  flag: lista del Excel vs comentario RIO), (9) EP+OM; spec (10)/R8.

### 2026-09-15 — Claude — Tercera ronda: solo ciclos completos del mes, sin herencia de julio

- **Tipo:** análisis con datos reales.
- **Origen:** el dueño del proyecto pidió comparar solo ciclos que inician y
  terminan en agosto, porque el margen heredado del Excel no está actualizado.
- **Cambios:** sección "Tercera ronda" en `docs/informes/Brechas_2608_por_empresa.md`;
  scripts `solo_mes.py` y `solo_mes2.py` (apareo ciclo a ciclo Excel↔motor por
  central y traslape, descomposición por causa) en `docs/informes/scripts_brechas_2608/`.
- **Hallazgos:** sobre los mismos ciclos y con el SC del Excel recalculado sin las
  columnas de ciclo inconcluso, **Excel 914,3 MM vs motor 933,1 MM (+2,1%)**; 198 de
  357 pares idénticos al peso; ENEL queda en 0% (sus +36 MM eran herencia). La
  desviación bruta (207,6 MM) se reparte en: filtro de partida 43,7 (ATACAMA-2 &4/&13
  +28,1: mecanismo nuevo (11), el Excel atribuye la instrucción PMT/OM al ciclo
  equivocado y anula dos partidas instruidas), tarifa+margen SANISIDRO-2 −27,4
  (combustible instruido, spec 25), paradas cortas +25,0, filtros de detención 20,6
  (SGA +6,6), margen por bloque vs hora −19,9.
- **Pendientes:** decisiones (2), (5), (9); spec (10); llevar (11) al CEN junto con
  (1), (3), (4), (6b), (7), (8).

### 2026-09-15 — Claude — Segunda ronda: GUACOLDA, porcentajes altos y corrección del mecanismo (6)

- **Tipo:** análisis con datos reales.
- **Origen:** pregunta del dueño del proyecto: por qué GUACOLDA tiene pago en el
  motor y por qué muchas empresas superan el 20% de diferencia.
- **Cambios:** sección "Segunda ronda" en `docs/informes/Brechas_2608_por_empresa.md`
  con la tabla completa (24 empresas, Δ en CLP y %), el caso GUACOLDA-1 paso a paso
  y cuatro mecanismos nuevos: (6b) el Excel hereda partida y **todo el margen** del
  ciclo inconcluso de julio al `&1` de agosto aunque sea otro ciclo físico (22
  ciclos, 33.795 MM de margen heredado, 21 liquidan 0); (8) el Excel paga el `&1`
  sin instrucción RIO (HUASCO-3, 5,55 MM); (9) partida EP + detención OM, el motor
  paga la detención (GUACOLDA-1, 1,29 MM); (10) sin historia con dos meses de datos,
  el motor deja la partida en 0 en vez de usar la cota inferior de horas (YUNGAY).
- **Hallazgos:** los % altos están en empresas de pocos ciclos donde un filtro
  sobre un ciclo de 1–2 MWh cambia el total en 50–200%; el 90% de la desviación en
  CLP sigue en ENEL, GMETROPOLITANA, SGA, ENGIE y TAMAKAYA, todos con mecanismo
  identificado. Se corrige la afirmación del 14-09 de que la partida de frontera
  "se pierde en ambos meses": solo cuando julio no marcó el ciclo como inconcluso.
- **Pendientes:** decisiones (2), (5), (9); spec para (10); revisar ENEL agosto
  (+29,4 MM) con el mismo método.

### 2026-09-15 — Claude — Réplica del estudio de brechas con el Excel corregido

- **Tipo:** análisis con datos reales.
- **Origen:** el área entregó `Sobrecostos_PD_2608 pre fixed.xlsm`; el dueño del
  proyecto pidió repetir el cruce por empresa contra esa versión.
- **Cambios:** sección "Réplica con el Excel corregido" en
  `docs/informes/Brechas_2608_por_empresa.md`; scripts `cmp_fixed.py`,
  `xhyc_fixed.py`, `ciclos_fixed.py` en `docs/informes/scripts_brechas_2608/`.
- **Hallazgos:** la corrección tocó solo MEJILLONES-CTM3 (agrega la configuración
  `_GNL_P` a `xHyC`: 12 → 6 ciclos, coinciden uno a uno con el motor) y
  CMPCCORDILLERA (agrega `GN_B`: margen 12,0 → 61,5 MM). Confirma los mecanismos
  (1) y (4) del informe. Excel sin traspasos 957,8 → 897,6 MM; motor 971,3 MM
  (+8,2%); Σ|Δ| por empresa 174,4 → 141,6 MM. Los mecanismos (2), (3), (5), (6)
  y (7) siguen intactos; ENEL no cambió (+29,4 MM vs motor).
- **Validación:** `Sobrecosto_Ciclo` original vs corregido comparado central a
  central: solo esas dos cambian.
- **Pendientes:** los mismos del 14-09.

### 2026-09-14 — Claude — Agosto con julio: brechas por empresa explicadas ciclo a ciclo (siete mecanismos)

- **Tipo:** análisis con datos reales + documentación.
- **Origen:** el dueño del proyecto corrió agosto desde la interfaz con empalme de
  julio (v7, tarifa máxima) y pidió explicar diez empresas con diferencias contra
  el Excel preliminar: ENGIE, GMETROPOLITANA, SGA, BE FORESTALES, ANTILHUE,
  COLMITO, ENLASA, ELEKTRAGEN, ENERGIA_SIETE, NUEVA DEGAN.
- **Cambios:** `docs/informes/Brechas_2608_por_empresa.md` con tablas ciclo a
  ciclo y `docs/informes/scripts_brechas_2608/` con los scripts del cruce (Excel
  `Sobrecosto_PD xHyC` vs `Resumen_Ciclos_PD` / `Detalle_15Min` del motor).
- **Hallazgos:** cinco defectos del Excel con caso concreto — (1) partidas
  fantasma cuando la planta generó bajo una configuración `_GNL_P` que el Excel no
  tiene (ENGIE, 61,6 MM cobrados por partidas que no ocurrieron); (3) detenciones
  reales que la macro no marca (CORONEL, 9 de 21 ciclos); (4) configuraciones fuera
  de `xHyC` cuya energía no entra al margen (CMPCCORDILLERA GN_B, 51,7 MM); (6)
  partidas de ciclos de frontera que se pierden en ambos meses; (7) política PO de
  mitad de mes no aplicada (ENLASA). Dos decisiones de regla abiertas — (2) paradas
  de 45–75 min que el horario no ve y el motor tarifica como partida caliente
  (NUEVARENCA +19,9 MM); (5) lista `Pruebas` del Excel vs `EP` del RIO (+8,6 MM).
  Único término contra el motor: la tarifa restringida al combustible instruido
  (spec 25) en NUEVARENCA del 2-ago, −9,4 MM.
- **Validación:** cada mecanismo verificado sobre las filas hora-central del Excel
  y los bloques del motor en la misma ventana de tiempo (ver informe).
- **Pendientes:** decisiones (2) y (5); llevar (1), (3), (4), (6), (7) al CEN.

### 2026-09-14 — Codex — Formalización del motor «Reglas del Horario» (spec 26)

- **Tipo:** especificación + pruebas + interfaz + documentación.
- **Origen:** tarea siguiente indicada en «Punto de partida para el próximo
  update»: formalizar el tercer motor de contraste ya existente.
- **Cambios:** `docs/specs/26-motor-reglas-horario.md` delimita las reglas 0–13
  que aplica, las aproximaciones por insumos ausentes y su carácter no productivo;
  `tests/test_motor_reglas_horario.py` cubre siete grupos de reglas puras; la
  exclusión COGEN y el traspaso quedaron expuestos como funciones testeables; la
  interfaz ofrece el tercer motor, selecciona su salida propia y deshabilita los
  interruptores ajenos; README y `_LEEME.txt` explican ambas formas de ejecución.
- **Validación:** `pytest -q` → **94 passed** (87 anteriores + 7 nuevas);
  `python -m py_compile src/sc_pd_motor_reglas_horario.py
  Carpeta_de_Trabajo/interfaz.py tests/test_motor_reglas_horario.py` → sin errores.
- **Pendientes:** reconciliar el pipeline completo con datos operacionales de
  otro mes; conseguir/formalizar las hojas `Pruebas` y `Ciclos inconclusos` si se
  exige equivalencia total con el libro. La decisión productiva sobre el primer
  ciclo sin historia permanece abierta y no fue modificada.

### 2026-09-14 — Claude — Push directo a `main`: sincroniza el repo con el estado local (specs 24, 25, motor Reglas del Horario, interfaz)

- **Tipo:** implementación + documentación.
- **Origen:** el repo tenía hasta la subida manual del 11-09 ("Add files via
  upload"); el trabajo del 11 al 14 de septiembre vivía solo en local.
- **Cambios:** 20 archivos respecto de `main` — spec 25 y sus tests, motor
  Reglas del Horario y su runner, interfaz tkinter y `Abrir_Interfaz.bat`,
  reglas del Excel deducidas (`docs/informes/`), README, `_LEEME.txt`, y la
  sección "Punto de partida" de esta bitácora.
- **Validación:** `pytest -q` → 87 pruebas; `git diff --name-status
  origin/main` revisado: solo adiciones y modificaciones, sin datos
  operacionales.
- **Pendientes:** ver "Punto de partida".

### 2026-09-14 — Claude — Decisión: la tarifa del ciclo es la de la configuración más cara (spec 25)

- **Tipo:** decisión + implementación + prueba.
- **Origen:** revisión ejecutiva del 14-09-2026. El dueño del proyecto resolvió
  las decisiones abiertas: (1) tarifa del ciclo = **la más cara presente en el
  ciclo**; (2) margen truncado **por bloque**, como el horario (se mantiene
  `MARGEN_NETEADO_POR_CICLO = 0`); (4) unidad de ciclo = central relacionada
  por ahora, con la elección visible en la interfaz (ya lo estaba: radio
  "v7 / Turbina"). Las decisiones 3 (primer ciclo sin historia) y 5 (defectos
  del Excel) quedan abiertas con explicación entregada.
- **Cambios:**
  - `src/sc_pd_motor_v7.py`: interruptor `TARIFA_CONFIGURACION` (`'maxima'` |
    `'instruida'`), **activo en `'maxima'`**. Nuevas funciones
    `combustible_configuracion()` y `tarifa_configuracion_maxima()`;
    `compactar_resumen_ciclos()` y `columnas_resumen_ciclos()` reciben el
    parámetro; 14.1b deja de reemplazar la tarifa bajo `'maxima'` y guarda
    `Costo_*_RIO_Instruida` como referencia; 14.1 (dominante) se ignora bajo
    `'maxima'`; bloque de consola `TARIFA POR CONFIGURACION`; columnas
    `Configs_En_Ciclo`, `Config_Tarifa_*`, `Excluida_Combustible_*`;
    `Guia_Lectura` actualizada.
  - Regla: compiten las configuraciones que generaron en el ciclo, tras el
    filtro de Costo_Cero y el de **combustible instruido** (columna `AG` del
    horario). Sin ese segundo filtro NUEVARENCA&1 cobraba tarifa DIESEL con el
    RIO instruyendo gas: 66,6 MM en vez de 18,1 MM.
  - `Carpeta_de_Trabajo/correr_motor.py` e `interfaz.py`: exponen el
    interruptor (radio "Tarifa del ciclo (solo motor v7)").
  - `docs/specs/25-tarifa-configuracion-maxima.md`, README.
- **Validación:** `pytest -q` → **87 pruebas** (16 nuevas en
  `tests/test_tarifa_configuracion_maxima.py`). Corridas reales con el
  interruptor (sin monkeypatch): 2606 `'instruida'` 823.168.889 (idéntico al
  previo, sin regresión); 2606 `'maxima'` **1.080.340.995** (+5,0% vs Excel
  1.028.628.659; Σ|Δ| por empresa 133,7 MM, antes 255,3 MM); 2608 `'maxima'`
  **875.313.107** (−8,6% vs Excel 957.823.663; Σ|Δ| 151,4 MM, antes 489,2 MM).
  Ningún ciclo excluido por combustible en 2606 ni 2608. El experimento previo
  por monkeypatch (1.119,8 MM / 915,8 MM) no tenía el filtro de combustible;
  queda superado por estas cifras.
- **Pendientes:** obtener julio (2607) para los 60 ciclos sin historia de
  agosto; decisión 3 (primer ciclo sin historia: piso al día 1 como el Excel o
  exención como el motor); decisión 5 (reportar al CEN los defectos del Excel);
  spec y tests del motor Reglas del Horario; subir el repo.

### 2026-09-10 — Claude — Experimento controlado: el 94,8% de la brecha contra el horario es de REGLA, no de resolución

- **Tipo:** análisis con datos reales + corrección de conclusiones previas.
- **Origen:** el dueño del proyecto propuso alimentar nuestro motor con el
  reporte horario (`Reporte_PD_2606.csv`, 190.069 filas) en vez de seguir
  infiriendo causas por comparaciones indirectas. Era el control obvio y
  debió correrse primero; se corrió al final.
- **Montaje:** el v7 corrido dos veces —con el reporte horario adaptado
  (`FECHA_HORA = Fecha + (Hora−1) h`) y con el de 15 min— ambas solo junio,
  mismo RIO, mismos costos, mismos interruptores. Validaciones previas: el
  mapeo de hora calza en **97,2% de 182.703 pares central-hora** (72,7% la
  alternativa); la generación total es idéntica en las dos fuentes
  (**4.272.938,04 MWh**). `AJUSTAR_FIN_BLOQUE = 0`, así que el motor no asume
  tamaño de bloque en ningún cálculo.
- **Resultado:**

  | Corrida | SC P-D |
  |---|---:|
  | Excel horario | 1.028.628.659 |
  | Motor sobre dato horario | 805.997.547 |
  | Motor sobre dato 15 min | 793.802.750 |

  Efecto **regla** (mismo dato, distinto motor): **−222.631.112 (94,8%)**.
  Efecto **resolución** (mismo motor, distinto dato): −12.194.797 (5,2%).
  En valor absoluto por empresa la resolución mueve 151,8 M, pero se
  compensa (ENGIE −61,0 M, ENEL +45,4 M).
- **ENEL en estado puro de regla:** sobre el mismo dato horario, los dos
  modelos detectan los mismos 27 ciclos en ATACAMA-1 y 26 en ATACAMA-2, y
  **cuatro de seis centrales calzan peso a peso** (QUINTERO-1/2,
  SANISIDRO-1/2: mismos bloques, MWh y CLP/MWh). Las dos que difieren son
  las multi-configuración, y ahí el Excel deja fuera del ciclo el 62% de la
  energía de ATACAMA-1 (28.691 de 75.255 MWh): su hoja `Sobrecosto_PD xHyC`
  no asigna clave de ciclo a todas las sub-configuraciones.
- **Correcciones a análisis previos de esta sesión:** (a) ENGIE no es
  selección de configuración, es 83% resolución (−61,0 de −73,4 M); (b)
  TAMAKAYA/KELAR es regla y más grande de lo estimado: −116,6 M incluso con
  dato horario; (c) el informe de defensa publicado presentaba la resolución
  como explicación principal de la brecha — se corrigió con recuadro de
  advertencia visible en la propia página.
- **Límites declarados:** el "efecto regla" incluye el tratamiento de ciclos
  de frontera (sin mayo vs `Ciclos inconclusos` + 28 diferidos del Excel).
  El propio libro tiene una inconsistencia interna no perseguida: 29.903 M
  de margen ENEL en `Sobrecosto_Ciclo` contra 22.017 M sumando xHyC.
- **Pendientes:** son decisiones, no código — criterio de aceptación del
  modelo si el horario no es el patrón; unidad regulatoria del ciclo
  (configuración / relacionada / turbina); los 24 ciclos contestables;
  `MARGEN_NETEADO_POR_CICLO`; qué mes liquida un ciclo de frontera; qué se
  hace con los defectos encontrados en el Excel.

### 2026-09-10 — Claude — Spec 24: modelo alternativo por turbina, implementado y medido (no reemplaza al v7)

- **Tipo:** especificación + implementación + pruebas + análisis.
- **Excepción de rol:** el dueño pidió explícitamente que se implementara,
  como copia completa e independiente, con interruptor para comparar las
  tres formas de atribuir la tarifa.
- **Origen:** regla de negocio propuesta por el dueño: abandonar el
  diccionario configuración → relacionada como entidad del ciclo y pensar en
  turbinas (`UNIDAD GENERADORA`), con comparación contra el horario a nivel
  empresa.
- **Hallazgos estructurales previos a construir:** no existe tarifa por
  turbina (3 de 275 calzan con la base de costos) ni RIO por turbina (su
  `UNIDAD GENERADORA` es la planta). Por eso el motor separa tres niveles:
  ciclo por turbina, tarifa y RIO por configuración. Solo 5 relacionadas
  agrupan más de una turbina; el diccionario fusionaba plantas distintas
  (SANISIDRO-1/2, ARICA-M1AR/M2AR).
- **Implementación:** `src/sc_pd_motor_turbina.py` (copia del v7 con cambios
  quirúrgicos comentados), `Carpeta_de_Trabajo/correr_motor_turbina.py`,
  interruptor `ATRIBUCION_TARIFA_TURBINA` ∈ {prorrata, primera,
  cada_turbina}, hoja `Atribucion_Turbinas`. Ver spec 24.
- **Defecto propio corregido:** la primera regla de agrupamiento encadenaba
  por transitividad arranques sucesivos de una sola máquina (19 ciclos de
  TENOGAS en 202,5 h con ventana de 24 h). Se agregó la regla "una turbina
  no se repite en un evento". Cambia `prorrata` en 123.370 CLP; cubierto por
  `test_la_misma_turbina_repetida_no_se_fusiona_por_transitividad`.
- **Validación:** `pytest -q` **71/71** (58 previos + 13 nuevos). Corridas
  reales: prorrata 943.149.530, primera 943.149.530, cada_turbina
  946.106.550. El factor de atribución suma exactamente 1 en los 1.063
  eventos de partida y 1.046 de detención.
- **Resultados clave:** KELAR-TV aparece con ciclos propios y su arranque
  del 27-jun cobra 61.419.507 CLP — el mismo monto del horario, pero por
  razón física. Σ|Δ| por empresa contra el horario baja de 255,3 M a 185,6 M.
  ENEL se sobre-corrige (+25,2 M): ATACAMA paga tres partidas por un
  arranque de ciclo combinado.
- **Barrido de ventana:** con la regla corregida es completamente plano de
  ±0,5 h a ±24 h. Las turbinas de una planta arrancan bajo configuraciones
  distintas por construcción, así que nunca comparten llave. Medido offline
  con validación de 0 CLP contra las corridas reales. El primer barrido
  (antes de corregir la regla) mostraba una curva con mínimo en 3 h que era
  íntegramente el artefacto de encadenamiento — no se usó.
- **Decisión abierta:** llave de evento por planta en vez de configuración.
  Medido: ENEL cruza el horario a ±1,5–2 h; la Σ|Δ| agregada empeora, pero
  ese indicador está sesgado hacia parecerse al horario. Requiere definir
  llave, ventana y regla de pago (`mayor_tarifa` aparece como tercera
  opción). No implementado.
- **Reencuadre posterior:** el experimento controlado (entrada de arriba)
  mostró que la brecha es 94,8% regla. Este motor se construyó como
  herramienta de convergencia; su adopción debe decidirse por sus méritos.

### 2026-09-10 — Claude — Spec 23 escrita e implementada: netear el margen dentro del ciclo (`MARGEN_NETEADO_POR_CICLO`)

- **Tipo:** análisis con datos reales + especificación + implementación + pruebas.
- **Excepción de rol:** el dueño del proyecto pidió explícitamente que además
  de la spec escribiera el código. Se hizo en esta ocasión; el reparto
  habitual (Claude especifica, Codex implementa) no cambia.
- **Origen:** el dueño preguntó si el margen alguna vez es negativo en vez de
  cero. Respuesta: **no, nunca** — hay dos truncamientos, uno por bloque en
  `calcular_margen_bloques()` y otro por ciclo en `Total SC_PD`.
- **El modelo horario hace exactamente lo mismo** (verificado leyendo las
  fórmulas de `Copia de Sobrecostos_PD_2606 def.xlsm`):
  `Sobrecosto_PD xHyC!Y = IF(X-W<0,0,X-W)` trunca **por fila hora-central**
  antes del `SUMIF` del ciclo, y `Sobrecosto_Ciclo!H` aplica el segundo
  clamp. El motor es un calco. Magnitudes coherentes: el horario trunca
  8.276 de 19.510 filas (42,4%); el motor 309.326 de 787.820 (39,3%).
  **Conclusión: no es un bug, es la regla vigente.** Cambiarla requiere
  aprobación de negocio.
- **Caso que motiva el cambio:** TOCOPILLA-U16, ciclo del 23-jun. Margen neto
  real del ciclo −20.601.044 CLP (vendió a pérdida), pero el truncamiento por
  bloque le acredita +76.923.870, que cubre sus 50.594.150 de costo P-D y lo
  deja pagando **0**. MEJILLONES-CTM3 igual: neto −59,9 M, acreditado +88,8 M.
- **Variante sin truncar descartada:** el pago subiría a 11.565.686.567 CLP
  contra un costo efectivo validado de 1.694.803.967 (~7x los costos P-D). No
  es defendible y no se implementó.
- **Implementación:** interruptor `MARGEN_NETEADO_POR_CICLO`, **default 0**.
  Cuatro seams: `calcular_margen_bloques(..., netear_por_ciclo)` conserva el
  signo; `compactar_resumen_ciclos(...)` guarda `Margen_Neto_Ciclo` y aplica
  `MAX(0, ...)` al total ya neteado; `columnas_resumen_ciclos(...)` inserta
  esa columna en la lista blanca del export (sin esto el criterio quedaba sin
  trazabilidad); la consola declara el criterio activo y advierte cuando no es
  el del horario. Expuesto en `Carpeta_de_Trabajo/correr_motor.py`.
- **Validación ejecutada** (junio 2026 con empalme de mayo, ambos RIO y
  costos de mayo desde `T:`):
  1. `pytest -q`: **58/58 OK** (51 anteriores + 7 nuevos).
  2. **Interruptor en 0:** `Total SC_PD` = **823.168.889,26**, idéntico peso a
     peso al baseline previo. 0 ciclos con SC_PD distinto, `Costos_Totales_PD`
     idéntico, y `Margen_Neto_Ciclo` correctamente ausente. Sin regresión.
  3. **Interruptor en 1:** `Total SC_PD` = **1.099.088.305,85**, que
     **reproduce exactamente** la medición independiente por monkeypatch hecha
     antes de escribir la spec.
  4. **Cambio quirúrgico:** `Costo_Partida_Efectivo`, `Costo_Detencion_Efectivo`,
     `Costos_Totales_PD`, las bases y `Generacion_Suma_Ciclo` son idénticos en
     ambos modos. (`Horas_Detenida_Ciclo` aparecía distinto en una primera
     comparación: era artefacto de comparar `NaN` con `NaN` en los 5 ciclos
     `sin_historia`; `Series.equals()` confirma que es idéntico.)
  5. De 1.035 ciclos, **337 cambian y todos suben** — correcto por definición:
     netear solo puede reducir el margen acreditado, nunca aumentarlo. 667
     ciclos quedan con margen neto negativo, todos truncados a 0, y ninguno
     con `Margen_Suma_Ciclo` negativo. Ningún `Total SC_PD` supera su costo.
  6. Los 23 ciclos diferidos de la spec 17 siguen diferidos en ambos modos.
  7. 139.165 bloques con margen negativo pasan a compensar
     (−74.567.817.152 CLP).
- **Comparación por empresa contra el horario** (total horario
  **1.028.628.659 CLP**, 987 ciclos con empresa más 28 traspasados; extracción
  validada peso a peso contra la hoja `RESUMEN` del propio Excel):

  | | Total | Δ neto | Suma \|Δ\| por empresa |
  |---|---:|---:|---:|
  | Horario | 1.028.628.659 | — | — |
  | Interruptor 0 | 823.168.889 | −205.459.770 (−20,0%) | 255.292.186 |
  | Interruptor 1 | 1.099.088.306 | +70.459.647 (+6,8%) | **275.118.686** |

  **Advertencia:** el criterio 1 acerca el *total* pero **desalinea más la
  plata por empresa**. ENEL pasa de −14,2 M a **+84,9 M** sobre el horario. No
  se puede justificar como "se parece más al horario"; hay que defenderlo por
  su lectura de la regla.
- **Corrección a un análisis previo de esta misma sesión:** la brecha de
  TAMAKAYA/KELAR-TG12 (−97.815.745 CLP, 48% del total bajo el criterio 0) se
  reportó primero como un pendiente abierto que "merece su propia spec". Es
  incorrecto: ya está documentado en esta bitácora como el **efecto
  deliberado de la spec 15**, y es inmune a ambos criterios de margen (su
  margen es 0 en los dos modelos). Converger con el horario ahí significaría
  revertir la spec 15. También se verificó empíricamente que
  `USAR_CONFIG_DOMINANTE` no aplica bajo `USAR_TARIFA_RIO_INSTRUIDA = 1`:
  correr con el interruptor en 1 da cifras idénticas peso a peso, tal como
  anticipa el comentario del panel (líneas 194-197).
- **Pendientes:** decisión de negocio sobre encender el interruptor. Queda
  anotada en la spec una fragilidad latente: con `netear_por_ciclo=0` el
  truncamiento evalúa el signo del margen **unitario** antes de multiplicar
  por la generación, así que una `GENERACION` negativa (bombeo/consumo)
  colaría un margen negativo. Verificado: **0 filas con generación negativa en
  2606**, inerte hoy. No se corrigió acá para no mezclar robustez con cambio
  de regla.

### 2026-09-10 — Claude — Interruptor de margen (spec 22, PR #46) verificado con datos reales

- **Tipo:** revisión de implementación + validación con datos reales.
- **Origen:** `docs/specs/22-interruptor-criterio-de-margen.md`,
  implementada por Codex en PR #46, ya fusionada en `main`.
- **Revisión del diff:** implementación exacta a lo especificado —
  interruptor `CALCULAR_MARGEN_EN_EL_MOTOR` en la sección de lógica de
  negocio, función `calcular_margen_bloques`, reemplazo del cálculo
  inline, bloque de impresión del criterio activo con la referencia al
  otro criterio, y el interruptor expuesto en
  `Carpeta_de_Trabajo/correr_motor.py` vía el parámetro `panel`. Sin
  desviaciones y sin tocar `src/fase1_integridad.py`.
- **Validación ejecutada** (junio 2026, sin mes pasado en este entorno):
  1. `pytest -q -m ""`: **51/51 OK** (47 anteriores + 4 nuevos).
  2. **Interruptor en 0:** margen 45.589.554.833 CLP, `Total SC_PD` =
     **1.035.077.837,13** — idéntico peso a peso al baseline previo a
     esta spec. Sin regresión.
  3. **Interruptor en 1:** margen 112.842.764.244 CLP, `Total SC_PD` =
     **793.802.749,56**. Baja 241.275.088 CLP (−23,3%).
  4. **El margen del modo 1 coincide exactamente con la estimación
     independiente** que había calculado antes de escribir la spec
     (112.842.764.244), lo que confirma que la implementación hace lo
     que se analizó.
  5. **Prueba de que el cambio es quirúrgico:** `Costos_Totales_PD` da
     exactamente 1.595.732.666 CLP en **ambos** modos — el interruptor
     solo mueve el margen, no toca ningún costo de partida ni detención.
  6. De 1.034 ciclos, 418 cambian de pago y **ninguno sube** — correcto
     por definición: más margen solo puede amortizar más, nunca menos.
  7. Los 23 ciclos diferidos de la spec 17 siguen diferidos y en cero en
     ambos modos; el mecanismo no se vio afectado.
- **Observación para la comparación con el modelo horario:** con el
  interruptor en 1 **no convergemos** al horario, lo pasamos por debajo
  (793,8 millones contra 1.029,5 del horario, aunque no son
  directamente comparables porque esta corrida no tiene mayo cargado).
  Es lo esperado: la causa 2 (configuración/tarifa, efecto deliberado de
  la spec 15) nos hace cobrar menos que el horario, y empuja en sentido
  contrario al margen.
- **Pendientes:** que el dueño del proyecto corra con sus datos reales
  (con mayo) y decida si el criterio nuevo es el correcto. Siguen
  abiertas las causas 2 y 3 de la comparación, que requieren el detalle
  por ciclo del modelo horario.

### 2026-09-10 — Claude — Diferencias contra el modelo horario: causa dominante identificada — spec 22 escrita

- **Tipo:** análisis comparativo con datos reales + especificación.
- **Origen:** el dueño del proyecto entregó la salida del modelo horario
  (`Salida_Horaria.xlsx`, 1.015 ciclos), su fuente horaria
  (`Reporte_PD_2606.csv`, 190.069 filas) y nuestra salida de junio 2026
  (1.035 ciclos), y pidió investigar las diferencias.
- **Punto de partida:** horario 1.029.455.882 CLP vs nuestro
  1.065.910.132 CLP (+36 millones, +3,5%). Ese +3,5% esconde diferencias
  mucho mayores que se compensan: 59 de 82 centrales difieren en más de
  1.000 CLP, con casos como KELAR-TG12 (−97,8 millones) y CORONEL
  (+34,0 millones) apuntando en direcciones opuestas.
- **Causa 1 — el margen (dominante, y está en el dato de entrada, no en
  el motor):** la columna `CMg-CV` del reporte de 15 minutos no es una
  resta aritmética. Viene en cero en el 100% de las filas
  `Tipo = 'OTRO'` (645.717) y `Tipo = 'SCMT'` (37.161), y poblada solo
  en el 51% de las `Tipo = 'C.Frec'`. Son 181.473 filas donde la columna
  dice 0 aunque `CMg > CV`. El reporte horario ni siquiera tiene esa
  columna: trae `CMg`, `CV` y `Dolar` crudos. Con **la misma generación
  en ambas fuentes** (4.272.938 MWh exactos), el margen da 148.321
  millones en la horaria contra 57.764 millones en la nuestra. Ejemplos
  extremos: GUACOLDA-3_CAR y ALFALFAL tienen margen 0 en nuestro
  cálculo y 3.779 y 2.755 millones en el horario.
- **Regla del modelo horario, reconstruida y confirmada sin necesidad de
  su código** (pesa 74 MB comprimido y no se pudo enviar): margen =
  Σ max(0, CMg − CV) × Dólar × Generación sobre los bloques del ciclo,
  con las columnas crudas y sin filtrar por `Tipo`. Validación: 60 de
  las 80 centrales calzan dentro del 0,1% contra la columna
  `Total Margen` de la salida horaria; total reconstruido 110.995
  millones contra 109.136 reportados (1,7%, explicable porque yo sumé
  todas las horas del mes y el horario suma solo las horas en ciclos).
  Detalle a cuidar: `Total Margen` y `Margen ciclo inconcluso` son
  columnas distintas y **no** deben sumarse.
- **Impacto estimado del criterio de margen:** recalculando el margen
  crudo por ciclo sobre nuestra propia salida, el `Total SC_PD` bajaría
  de 1.065.910.132 a **~823 millones**, con 415 ciclos de 1.035
  cambiando de pago.
- **Causa 2 — configuración/tarifa:** KELAR-TG12 (−97,8 M) y
  MEJILLONES-CTM3 (−29,0 M) son el efecto **deliberado** de la spec 15.
  El horario mezcla configuraciones hermanas y termina aplicando
  tarifas de ciclo combinado; en KELAR cobra 60 millones de partida
  donde nosotros cobramos 7,4 millones con la configuración exacta.
- **Causa 3 — segmentación de ciclos:** a 15 minutos vemos detenciones
  que la resolución horaria no puede ver (CORONEL 35 ciclos vs 30,
  KELAR 7 vs 6). Más ciclos implica más partidas y detenciones
  cobradas, y además mueve `Horas_Detenida`, que puede cambiar la
  tarifa entre fría/tibia/caliente.
- **Decisión del dueño del proyecto:** probar el criterio del modelo
  horario, con un interruptor al inicio del código para controlarlo.
- **Spec escrita:** `docs/specs/22-interruptor-criterio-de-margen.md`
  (`CALCULAR_MARGEN_EN_EL_MOTOR`, por defecto en 1, expuesto también en
  `Carpeta_de_Trabajo/correr_motor.py` vía el parámetro `panel` que
  `main()` ya acepta).
- **Pendientes:** implementación por Codex. Quedan abiertas las causas 2
  y 3, que requieren el detalle por ciclo del modelo horario (fechas de
  inicio/término, horas detenida, tarifa y configuración aplicada).

### 2026-09-10 — Claude — Spec 21 descartada: era un nombre de archivo mal escrito, no un bug

- **Tipo:** corrección de un diagnóstico propio equivocado.
- **Origen:** tras reportar el dueño del proyecto que "no está
  funcionando el cruce para saber la empresa", diagnostiqué que el
  nombre por defecto de `RUTA_DICCIONARIO_EMPRESA`
  (`Diccionario_configuracion_empresa.xlsx`) estaba mal y debía ser
  `Diccionario_central_empresa.xlsx`, y escribí la spec 21 (PR #45).
- **Corrección:** el dueño del proyecto aclaró que **él tenía mal
  escrito el nombre de su archivo local**. El nombre por defecto del
  código es el correcto y no hay ningún bug.
- **Mi error:** tomé como evidencia el nombre del archivo en mi entorno
  de pruebas y una mención en la spec 10, y no verifiqué con el dueño
  del proyecto antes de escribir la spec. El diagnóstico correcto era
  preguntar primero.
- **Estado:** la spec 21 queda anulada y **su archivo se eliminó de la
  rama antes de fusionar**, para que nunca entre al repo: si el archivo
  quedara en `docs/specs/`, Codex podría implementarlo y rompería el
  nombre por defecto para todos. Solo queda este registro.
- **Lo único aprovechable del episodio:** cuando no encuentra el
  diccionario, el motor deja todo el reporte en `Empresa = 'Sin_Empresa'`
  avisando con una sola línea fácil de pasar por alto. Si eso vuelve a
  confundir, se puede especificar un aviso más visible — pero no se hace
  ahora, no fue pedido.

### 2026-09-10 — Claude — Bug real reportado: nombre incorrecto del diccionario de empresas — spec 21 escrita

- **Tipo:** diagnóstico de bug reportado por el usuario + especificación
  de corrección.
- **Origen:** el dueño del proyecto reportó "no esta funcionando el
  cruce para saber la empresa, eso antes estaba funcionando".
- **Causa raíz:** el nombre de archivo por defecto de
  `RUTA_DICCIONARIO_EMPRESA` quedó mal desde la spec 00 (la que
  restauró el motor) — `Diccionario_configuracion_empresa.xlsx` en el
  código, cuando el archivo real que usa el dueño del proyecto se llama
  `Diccionario_central_empresa.xlsx` (esto lo documenta correctamente la
  propia spec 10, y es el nombre que usé yo mismo en todas las corridas
  reales de esta sesión — de hecho, al validar la spec 19 tuve que
  **renombrar** el archivo real a mano para que calzara con el nombre
  por defecto incorrecto, sin notar en ese momento que ese era el
  síntoma de un bug). Si el archivo no se encuentra bajo ese nombre, la
  sección de carga (línea ~818) cae en su rama de "sin diccionario" y
  deja **todo el reporte en `Empresa = 'Sin_Empresa'`**, con solo una
  línea de aviso fácil de pasar por alto. Con `Carpeta_de_Trabajo/`
  (spec 19) el problema se volvió más visible, porque el dueño del
  proyecto ahora deja su archivo (ya correctamente nombrado
  `Diccionario_central_empresa.xlsx`) en esa carpeta sin razón para
  renombrarlo.
- **Spec escrita:** `docs/specs/21-fix-nombre-diccionario-empresa.md`.
  Corregía el nombre por defecto en los 5 lugares donde aparecía
  (`src/sc_pd_motor_v7.py`, `scripts/diagnosticar_observacion.py`, los
  dos lanzadores de `Carpeta_de_Trabajo/`, y `README.md`).
  **⚠️ ANULADA:** el diagnóstico era equivocado (ver la entrada
  "Spec 21 descartada" más arriba). El archivo de la spec se eliminó
  antes de fusionar y nunca llegó al repo.
- **Pendientes:** implementación por Codex, luego pedir al dueño del
  proyecto que confirme con una corrida real que el cruce de empresa
  vuelve a funcionar.

### 2026-09-10 — Claude — Fix de spec 20 (PR #43) verificado — spec 20 cerrada

- **Tipo:** revisión de implementación + validación.
- **Origen:** `docs/specs/20-fix-crash-unidad-vacia-filtro-costo-cero.md`,
  implementada por Codex en PR #43, ya fusionada en `main`.
- **Revisión del diff:** el fix extrae `calcular_unidades_facturables(df_externo)`
  como función propia y testeable (opción que la spec permitía
  explícitamente), excluye las filas con `UNIDAD` nula antes del
  `groupby`, e imprime el aviso `[!] N fila(s) ... sin UNIDAD` cuando
  corresponde. Coincide con lo pedido.
- **Validación ejecutada:**
  1. `pytest -q -m ""`: **47/47 OK** (los 45 anteriores + los 2 tests
     nuevos de `tests/test_unidades_facturables.py`).
  2. **Reproducción directa del crash reportado:** armé un `DataFrame`
     sintético con filas de `UNIDAD` vacía mezcladas con válidas
     (replicando la forma del archivo real que hizo fallar al dueño del
     proyecto) y llamé a `calcular_unidades_facturables` directamente —
     ya no lanza `ValueError`, excluye correctamente las filas sin
     `UNIDAD` y calcula bien las unidades facturables restantes.
  3. Corrida completa del motor real contra los datos de junio 2026 (sin
     filas `UNIDAD` vacías, como antes): mismo resultado de siempre
     (1.034 ciclos) — sin regresión para el caso sin datos faltantes.
- **Conclusión:** el crash reportado por el dueño del proyecto queda
  resuelto. Falta que él vuelva a correr `correr_motor.py` con sus datos
  reales de producción para la confirmación final end-to-end (no se pudo
  reproducir con los datos de prueba de este entorno, que no tienen
  `UNIDAD` vacía).
- **Pendientes:** ninguno de mi parte. Avisar al dueño del proyecto para
  que reintente su corrida real.

### 2026-09-10 — Claude — Bug real reportado por el dueño del proyecto: crash por `UNIDAD` vacía en Costos Consolidados — spec 20 escrita

- **Tipo:** diagnóstico de bug reportado por el usuario + especificación
  de corrección.
- **Origen:** el dueño del proyecto corrió `correr_motor.py` (de
  `Carpeta_de_Trabajo/`) con sus datos reales de producción (con mes
  pasado acoplado) y compartió el traceback completo. El motor se cae
  antes de generar cualquier reporte:
  ```
  ValueError: Cannot mask with non-boolean array containing NA / NaN values
    File "src/sc_pd_motor_v7.py", line 754, in main
      unidades_facturables = set(df_externo.loc[tiene_costo, 'UNIDAD'])
  ```
- **Causa raíz** (leída directamente del código, sección "4. COSTOS
  CONSOLIDADOS Y DICCIONARIOS", código preexistente sin relación con
  las specs 16-19): el filtro `Costo_Cero` agrupa `df_externo` por la
  columna `UNIDAD`. Si esa columna trae `NaN` en alguna fila (filas en
  blanco o incompletas en el Excel real de Costos Consolidados o en su
  archivo de mes pasado — algo que no aparecía en los datos de prueba
  usados hasta ahora), pandas excluye esas filas del `groupby` por
  defecto y `.transform('any')` les devuelve `NaN` en vez de un
  booleano, produciendo una máscara con huecos que `.loc[]` rechaza.
- **Spec escrita:** `docs/specs/20-fix-crash-unidad-vacia-filtro-costo-cero.md`.
  Fix: excluir explícitamente del filtro las filas con `UNIDAD` vacía
  antes del `groupby`, e imprimir un aviso con el conteo de filas
  excluidas (para que el dueño del proyecto pueda revisar su archivo de
  origen si el número no le hace sentido). No cambia la definición de
  negocio del filtro.
- **Estado:** no pude reproducir el crash con los datos de prueba en
  este entorno (no tienen filas con `UNIDAD` vacía) — la spec queda
  redactada a partir de la lectura del código y del traceback exacto
  compartido por el dueño del proyecto. Pedí en la spec un test
  sintético que sí reproduzca el caso.
- **Pendientes:** implementación por Codex, luego pedir al dueño del
  proyecto que vuelva a correr `correr_motor.py` con sus datos reales
  para confirmar que ya no se cae.

### 2026-09-10 — Claude — Revisión de `Carpeta_de_Trabajo` (spec 19, PR #40) — verificada con datos reales

- **Tipo:** revisión de implementación + validación con datos reales.
- **Origen:** `docs/specs/19-carpeta-de-trabajo-unica-para-spyder.md`,
  implementada por Codex en PR #40, ya fusionada en `main`.
- **Revisión del diff:** los 5 archivos (`_LEEME.txt`,
  `correr_motor.py`, `correr_prorrateo.py`, `correr_diagnostico.py`,
  `correr_consolidar_politicas.py`) quedaron copia exacta de lo pedido
  en la spec, sin desviaciones. Ningún archivo existente en `src/` ni
  `scripts/` fue tocado — confirmado con el diff completo del PR.
- **Validación ejecutada:**
  1. `pytest -q -m ""`: **45/45 OK**.
  2. `ast.parse` sobre los 4 `.py` nuevos: sin errores de sintaxis.
  3. **Prueba de extremo a extremo real:** copié `Carpeta_de_Trabajo/`
     completa a un entorno de prueba aislado, dejé ahí los datos reales
     de junio 2026 (reporte, RIO, costos, diccionarios) usando
     exactamente los nombres de archivo que ya vienen por defecto en
     `correr_motor.py`, y lo corrí sin editar ninguna variable ni pasar
     ningún argumento (`python correr_motor.py`, equivalente a F5 en
     Spyder). Generó `Reporte_Sobrecostos_PD_Final.xlsx` en la misma
     carpeta, con **1.034 ciclos** y **Total SC_PD = 1.035.077.837 CLP**
     — idéntico al resultado de la corrida de verificación de la spec 18
     (PR #38), confirmando cero drift respecto al motor real.
- **Conclusión:** la carpeta queda lista para usar. El dueño del
  proyecto puede descargar el ZIP actualizado del repo y usar
  `Carpeta_de_Trabajo/` como su único espacio de trabajo en Spyder.
- **Pendientes:** ninguno sobre esta spec.

### 2026-09-10 — Claude — Especificación de carpeta de trabajo única para Spyder

- **Tipo:** especificación.
- **Origen:** pedido explícito del dueño del proyecto — quiere una sola
  carpeta donde dejar todos los archivos de entrada de cada mes y correr
  todos los scripts desde ahí, más un `.txt` breve con instrucciones. Es
  continuación directa de la molestia ya documentada en la spec 16
  ("no me gusta que el ambiente de trabajo sea de esta manera").
- **Spec escrita:** `docs/specs/19-carpeta-de-trabajo-unica-para-spyder.md`.
  Propone una carpeta nueva `Carpeta_de_Trabajo/` con 4 scripts
  "lanzadores" cortos (para el motor, el prorrateo, el diagnóstico de
  observaciones y la consolidación de políticas PO) que importan la
  lógica real desde `src/`/`scripts/` sin duplicarla — solo resuelven
  las rutas de entrada/salida contra la propia carpeta, usando nombres
  de archivo en vez de rutas largas de Windows. Incluye el texto exacto
  de `_LEEME.txt` con instrucciones breves y el orden de uso. Ningún
  archivo existente se modifica.
- **Pendientes:** implementación por Codex, luego revisión con una
  corrida real (copiar datos de prueba a `Carpeta_de_Trabajo/` y
  confirmar que `correr_motor.py` genera el reporte sin errores).

### 2026-09-10 — Claude — Fix de spec 18 (PR #37) verificado con datos reales — spec 17 cerrada

- **Tipo:** revisión de implementación + validación con datos reales.
- **Origen:** `docs/specs/18-fix-crash-diferir-ciclos-indice-desalineado.md`,
  implementada por Codex en PR #37 (commit `afd3ebc`), ya fusionada en
  `main` (merge `06a5dd0`).
- **Revisión del diff:** el fix aplicado es exactamente el propuesto en la
  spec — `asignar_observaciones_liquidacion` recalcula
  `ciclos_sin_terminar` desde `df['Estado_Ciclo_Mes']` en el momento de
  uso, en vez de confiar en el parámetro recibido (potencialmente
  desalineado por el reordenamiento de `RENUMERAR_CICLOS_DEL_MES`). Firma
  de la función y call site en `main()` sin cambios, como se pedía.
  Agregaron además `test_observaciones_siguen_al_ciclo_despues_de_reordenar_y_reindexar`,
  que reproduce fielmente el escenario real: índice con huecos
  (`[0, 2, 4, 7, 9]`, imitando el filtrado previo del motor) seguido de un
  `sort_values(...).reset_index(drop=True)` a mitad de camino — exactamente
  el patrón que causaba el crash — y confirma que cada ciclo conserva su
  observación y costo correctos por identidad, no por posición.
- **Validación ejecutada:**
  1. `pytest -q -m ""`: **45/45 OK** (los 44 anteriores + el test nuevo).
  2. Corrida completa del motor real (`sc_pd_motor_v7.main()`) contra los
     mismos datos reales de junio 2026 usados en la revisión anterior
     (1.034 ciclos) — **terminó sin excepciones**, generó el reporte
     completo (antes se caía en `asignar_observaciones_liquidacion`).
  3. Verificado en el Excel de salida: los **23 ciclos** con
     `Estado_Ciclo_Mes` en `{'Continua todo el mes', 'Continua proximo
     mes'}` quedan **todos** con `Total SC_PD = 0` y
     `Obs_Liquidacion_Final` empezando con "Diferido..." — incluyendo
     `GUACOLDA-3_CAR&1`, el caso original que motivó la spec 17. Ningún
     ciclo quedó con datos cruzados ni desalineados.
  4. `Total SC_PD` del mes completo: **1.035.077.837 CLP** — coherente con
     la auditoría financiera impresa por el propio motor durante la
     corrida (cascada "PAGO FINAL DE SOBRECOSTO P-D").
- **Conclusión:** el bug de la spec 17 queda cerrado y verificado de
  extremo a extremo con datos reales. `main` ya no se cae — el dueño del
  proyecto puede volver a correr el motor completo con normalidad.
- **Pendientes:** ninguno sobre esta spec. Siguen abiertos los pendientes
  de negocio ya documentados en entradas anteriores (audit message
  engañoso de `Config_RIO_Corregida_Mezcla`, casos residuales
  `Sin_Registro_RIO`, posible ampliación de `VENTANA_CUARTOS_HORA`).

### 2026-09-10 — Claude — 🔴 Bug crítico encontrado en spec 17 (PR #35): motor se cae con datos reales — spec 18 escrita

- **Tipo:** revisión post-merge + hallazgo de bug crítico + especificación
  de corrección.
- **Origen:** revisión de rutina (iniciativa propia, como parte de la
  responsabilidad de revisar cada implementación) de la spec 16 (PR #34,
  commit `603837e`) y la spec 17 (PR #35, commit `b43a460`), ambas ya
  fusionadas en `main` (confirmado con `git log`: merges `578a82f` y
  `6989052` respectivamente).
- **Spec 16 (prorrateo sin CLI):** revisión limpia. `leer_retiros()` y
  `ejecutar()` quedaron byte a byte idénticas (confirmado por diff), ya no
  se importa `argparse`, las 4 variables editables quedaron al inicio del
  archivo igual que `diagnosticar_observacion.py`. Sin hallazgos.
- **Spec 17 (diferir ciclos sin terminar):** la lógica de negocio quedó
  bien implementada — los 4 tests nuevos en
  `tests/test_diferir_ciclos_sin_terminar.py` pasan y cubren los 4
  escenarios pedidos. `pytest -q -m ""` completo: **44/44 OK**. Pero al
  correr el **motor completo contra datos reales** de junio 2026 (1.034
  ciclos, mismo dataset de corridas anteriores) para validar el
  comportamiento end-to-end, **el motor se cae**:
  ```
  TypeError: unhashable type: 'Series'
    File "src/sc_pd_motor_v7.py", line 1964, in main
      df_compacto = asignar_observaciones_liquidacion(...)
    File "src/sc_pd_motor_v7.py", line 578, in asignar_observaciones_liquidacion
      df.loc[ciclos_sin_terminar, 'Obs_Partida'] = mensaje
  ```
  Los tests unitarios no lo detectan porque usan un DataFrame sintético de
  una sola fila, donde este tipo de desalineación no puede ocurrir.
- **Causa raíz** (confirmada instrumentando una copia descartable del
  motor en `/tmp` con prints de diagnóstico, nunca el archivo real del
  repo): `ciclos_sin_terminar` se calcula en la línea ~1716 y se usa recién
  en la línea ~1947. **Entre medio**, la sección preexistente
  "RENUMERACION DE CICLOS PARA EL REPORTE" (línea ~1753, nada que ver con
  la spec 17) hace `df_compacto.sort_values(...).reset_index(drop=True)`
  — reordena las filas y les asigna un índice nuevo. La variable
  `ciclos_sin_terminar`, calculada antes de ese reordenamiento, queda con
  el índice viejo. Verificado elemento a elemento (no solo una muestra):
  mismo largo (1.034 en ambos), pero valores de índice distintos desde la
  posición 4 en adelante — exactamente el patrón esperado al comparar un
  índice con huecos (heredado de un filtrado anterior sin
  `reset_index`, línea ~1627) contra un `RangeIndex` limpio posterior.
- **Riesgo adicional detectado, más allá del crash:** si pandas no hubiera
  lanzado la excepción, la línea `np.select([ciclos_sin_terminar, ...])`
  de la misma función no falla (opera por posición, no por índice) — habría
  asignado el mensaje "Diferido..." a **filas equivocadas** en
  `Obs_Liquidacion_Final`, en silencio. El fix propuesto en la spec 18
  elimina ambos problemas de raíz.
- **Spec escrita:** `docs/specs/18-fix-crash-diferir-ciclos-indice-desalineado.md`.
  Fix quirúrgico: `asignar_observaciones_liquidacion` recalcula
  `ciclos_sin_terminar` internamente desde la columna `Estado_Ciclo_Mes`
  del propio `df` recibido (en vez de confiar en el parámetro, que puede
  quedar obsoleto), garantizando alineación por construcción sin importar
  cuántas veces se haya reordenado el DataFrame antes. No cambia la firma
  de la función ni el call site en `main()`. Pide un test nuevo que
  reproduzca el reordenamiento intermedio explícitamente, para que este
  tipo de bug no pueda volver a colarse sin que un test lo detecte.
- **Validación de mi parte:** reproducido el crash de forma aislada y
  confirmado el fix propuesto contra el mecanismo real (no se modificó el
  archivo del repo, todo en una copia en `/tmp`, descartada al terminar).
- **Estado:** `main` queda con un bug de producción activo hasta que la
  spec 18 se implemente — el dueño del proyecto no debería volver a correr
  el motor completo con `DIFERIR_CICLOS_SIN_TERMINAR=1` (valor por
  defecto) hasta entonces.
- **Pendientes:** implementación de la spec 18 (Codex). Después de
  implementada, repetir la validación con datos reales antes de dar por
  cerrada la spec 17.

### 2026-09-09 — Claude — Investigación de casos "Sin_Registro_RIO" y corrección sobre NUEVARENCA

- **Tipo:** análisis ad-hoc con datos reales, a pedido del dueño del
  proyecto, más una corrección a una conclusión propia anterior.
- **Origen:** continuación de la revisión de la spec 15 — se pidió
  investigar los 30 ciclos (25 partida + 5 detención) de junio 2026
  marcados `Obs_Partida`/`Obs_Detencion = "Revisar manualmente: config
  RIO sin tarifa"` con `Config_RIO_Usada = Sin_Registro_RIO`.
- **Resultado de la categorización** (ver
  `Analisis_Sin_Registro_RIO_202606.xlsx`, entregado al dueño del
  proyecto, no versionado en el repo):
  - **16 casos**: ciclo arranca exactamente el 01-jun 00:00:00 —
    consistente con un ciclo que empezó en mayo, artefacto de que este
    entorno de prueba no tiene `RUTA_REPORTE_MES_PASADO`/
    `RUTA_RIO_MES_PASADO` cargados. No aplica a producción.
  - **4 casos** ("cerca hacia adelante", ≤60min): `CHUYACA_DIESEL&1`
    (registro real a 34 min de `Inicio_Ciclo`, confirmado con el RIO
    crudo — el dueño del proyecto señaló correctamente que sí existía
    RIO para esa central/fecha) y `UJINA-2/3/4&1` (38 min cada una,
    mismo instante). Caso límite real: el registro correcto existe,
    pero cae fuera de `±VENTANA_CUARTOS_HORA` (30 min) por poco.
  - **8 casos** ("lejos en ambas direcciones", >60min):
    `CONSTITUCION_DIESEL&9`, `CORONEL&1`, `EMELDA-1_DIESEL&1`,
    `TRINCAO_DIESEL&16`, `TOCOPILLA-TG3&19` — sin nada cercano en el
    RIO real, posible vacío genuino de reporte, sin patrón técnico
    común identificado.
  - **NEHUENCO-9B** (partida y detención): **cero registros RIO en
    todo el mes**, confirmado revisando las 10 configuraciones
    posibles que el diccionario le asocia (`_GN_A`, `_GNL_A` a `_G`,
    `_GNL_INFLEX`, `_GN_B`) — ninguna aparece en `RIO_06_2026.xlsx`. No
    es un problema de mapeo de nombres; es un vacío real de datos que
    valdría la pena consultar directamente con el CEN/CDC.
- **Corrección importante:** al investigar por qué
  `NUEVARENCA_TG1+TV1&1` (el residual de detención de la spec 15)
  nunca coincidía, encontramos que la caracterización original en la
  spec 15 ("no existe ningún registro de la configuración exacta en la
  ventana") **estaba mal**. Sí existe: `NUEVARENCA_TG1+TV1_GN_A` (la
  config física correcta) tiene un registro `EP` a **36 minutos** de
  `Termino_Ciclo` — apenas 6 minutos fuera de la ventana `±30min`. Es
  el mismo patrón que `CHUYACA_DIESEL&1` y las 3 `UJINA` — no un
  "vacío genuino" como se dijo. Corregido el texto de
  `docs/specs/15-preferir-config-rio-fisica-en-ventana.md`.
- **Conclusión con implicancia concreta:** 5 casos reales
  (`CHUYACA_DIESEL&1`, `UJINA-2/3/4&1`, `NUEVARENCA_TG1+TV1&1`
  detención) comparten el mismo patrón — el registro RIO correcto
  existe, a 34-38 minutos del límite del ciclo, justo fuera de
  `VENTANA_CUARTOS_HORA=2` (±30min). Ampliar a `VENTANA_CUARTOS_HORA=3`
  (±45min) resolvería los 5 en una sola pasada. No se implementó nada
  todavía — queda como candidato a spec futura, pendiente de que el
  dueño del proyecto decida si quiere ese cambio (afecta el mismo
  interruptor que usan `rescatar_config_rio_en_limites` y la búsqueda
  relajada, así que ampliar el valor tiene alcance más amplio que solo
  estos 5 casos — hay que evaluarlo con cuidado, no es un cambio
  aislado).
- **Pendientes:** ninguna acción de código todavía — el dueño del
  proyecto pasa a hacer pruebas reales en su propio computador; queda
  pendiente si en algún momento quiere una spec para ampliar la
  ventana.

### 2026-09-09 — Claude — Revisión spec 15 con datos reales (PR #32): baja el Total SC_PD, no sube

- **Tipo:** prueba de integración end-to-end con datos reales + revisión,
  con 1 hallazgo de calidad de auditoría (no bloqueante) y una
  corrección importante a mi propia predicción de la spec.
- **Origen:** implementación de Codex en `45c3773` (PR #32,
  `codex/implementar-configuracion-rio-fisica-en-ventana`) de
  `docs/specs/15-preferir-config-rio-fisica-en-ventana.md` (nota: el PR
  de la spec en sí, #31, no se había mergeado todavía cuando Codex
  implementó — el código llegó a `main` antes que el documento).
- **Revisión del código:** `corregir_mezcla_configuraciones_rio` sigue
  exactamente el diseño de la spec — restringe el RIO de los límites de
  ciclo a la configuración exacta de la fila, dentro de
  `±VENTANA_CUARTOS_HORA`, con fallback intacto si no hay coincidencia.
  `pytest -q -m ""`: 39/39 OK (incluye `test_correccion_mezcla_config_rio.py`,
  4 tests cubriendo el caso base real de `KELAR-TG12&7`, casos sin
  candidato válido, interruptor apagado, y el caso "ya coincidía").
- **Validación con datos reales (junio 2026):**
  - **Re-corrí la comparación completa** (config física vs.
    `Config_RIO_Usada_Partida/Detencion`) contra el resultado real: la
    spec cerró **los 43 casos de partida a 0 mismatches**, y dejó
    **1 solo residual en detención** — exactamente
    `NUEVARENCA_TG1+TV1&1`, el caso genuino sin coincidencia en la
    ventana ya identificado antes de implementar. Confirma que el
    mecanismo funciona tal como se diseñó.
  - **Corrección a mi propia predicción:** la spec decía "se espera que
    suba" el `Total SC_PD` — estaba equivocado, fue una suposición sin
    verificar. El resultado real es una **baja** de
    **1.180.652.296 → 1.037.795.695 CLP (-142.856.600 CLP, -12,1%)**.
    31 ciclos de partida (-228.517.940 CLP) y 14 de detención
    (-25.107.594 CLP) tuvieron cambio real de costo — la razón: varias
    configuraciones "combinadas" (turbina+vapor) que se usaban por
    error tenían tarifas más altas que las configuraciones "simples"
    correctas, así que corregir bajó el costo en más casos de los que
    subió. Verificado puntualmente: `KELAR-TG12&7` ahora usa
    `KELAR-TG1_TG1_DIESEL` (config correcta) y
    `NUEVARENCA_TG1+TV1&1` quedó intacto.
- **Hallazgo (calidad de auditoría, no bloqueante):** el mensaje
  impreso ("Mezcla de configuraciones RIO corregida partida: 976
  ciclos, 780.931.028 CLP efectivos") es engañoso — de los 976 ciclos
  marcados `Config_RIO_Corregida_Mezcla_Partida=True`, solo **31
  tuvieron cambio real de costo**. El resto son ciclos donde la
  configuración ya coincidía y la función encontró un registro RIO
  duplicado (mismo nombre) dentro de la ventana, marcándolo como
  "corregido" sin que cambiara ningún valor. El monto de 780M CLP que
  imprime es la suma de `Costo_Partida_Efectivo` de TODOS los marcados,
  no el impacto real. Pendiente: decidir si vale la pena una spec
  chica para que la auditoría cuente/sume solo los casos con cambio
  real (el dueño del proyecto no se ha pronunciado aún sobre si
  aplicarlo).
- **Entregable adicional (fuera de specs, análisis ad-hoc a pedido del
  dueño del proyecto):** `Partidas_Detenciones_Negadas_202606.xlsx` —
  detalle completo de partidas/detenciones negadas por filtro o falta
  de tarifa, usando las clasificaciones `Obs_Partida`/`Obs_Detencion`
  que el motor ya calcula (sin lógica nueva). Total no cobrado por
  negación: ~386M CLP (302,1M partida + 84,0M detención), concentrado
  en "Máquina en Pruebas (EP)" (294,7M CLP, partida) y "Sin Motivo ni
  SSCC en RIO" (79,1M CLP, detención).
- **Pendientes:**
  1. Mergear PR #31 (el documento de la spec 15 en sí — el código ya
     está en `main` pero el `.md` todavía no).
  2. Decidir si se ajusta el mensaje de auditoría de
     `Config_RIO_Corregida_Mezcla_*` para no sobrestimar el impacto.
  3. Investigar el caso residual `NUEVARENCA_TG1+TV1&1` (GN_A vs GNL_C)
     si el dueño del proyecto lo considera prioritario.
  4. Revisar los 40 ciclos "Revisar manualmente: config RIO sin
     tarifa" (33 partida + 7 detención) — podría ser un vacío en
     `Costos_de_P-D_Consolidado.xlsx`, no evaluado todavía.

### 2026-09-09 — Claude — Confirmación specs 13 y 14 con datos reales (PR #29) — ambas cerradas

- **Tipo:** prueba de integración end-to-end con datos reales + revisión.
- **Origen:** implementación de Codex en `aaeaaa9` (PR #29,
  `codex/implementar-especificaciones-del-diagnostico-y-visibilidad`) de
  `docs/specs/13-fix-diagnostico-observaciones-termino-ciclo-rio.md` y
  `docs/specs/14-secuencia-rio-visibilidad-ventana.md`.
- **Revisión del código:**
  - Spec 13: `_diagnostico_ciclos` corrige el nombre de columna
    (`Termino_Ciclo` en vez de `Fin_Ciclo`) y agrega
    `Tipo_Partida_RIO`, `Config_RIO_Usada_Partida`,
    `Config_RIO_Usada_Detencion`, `Detencion_Tarifa`,
    `Detencion_Tarifa_RIO` a la hoja `Diagnostico`, exactamente como
    pedía la spec.
  - Spec 14: `listar_secuencia_rio_ventana` (nueva, junto a
    `rescatar_config_rio_en_limites`) arma la secuencia cronológica de
    instrucciones RIO dentro de `± VENTANA_CUARTOS_HORA` alrededor de
    `Inicio_Ciclo`/`Termino_Ciclo`, formato `"{offset:+d}min
    CONSIGNAS/MOTIVO/NOMBRE_CONFIGURACION; ..."`. Se agregó como
    `Secuencia_RIO_Partida`/`Secuencia_RIO_Detencion` junto a
    `Config_RIO_Usada_Partida`/`Detencion` en
    `columnas_resumen_ciclos()`, y una fila nueva en `Guia_Lectura`
    aclarando que es solo informativa.
- **Validación con datos reales (junio 2026, mismo insumo de
  revisiones anteriores):**
  - `pytest -q -m ""`: 34/34 OK (incluye `tests/test_secuencia_rio.py`,
    nuevo, y el test de regresión agregado a
    `test_diagnostico_observaciones.py`).
  - **`Total SC_PD` idéntico al de antes de este cambio:**
    1.180.652.295,52 CLP — confirma que la spec 14 es aditiva pura, no
    tocó ningún cálculo.
  - Confirmé en el ciclo real `AGUASBLANCAS-AGB_DIESEL&1` exactamente
    el patrón que motivó la spec 14:
    - `Secuencia_RIO_Partida` = `"-7min PP/OM/AGUASBLANCAS-AGB_DIESEL;
      +5min PC/OM/AGUASBLANCAS-AGB_DIESEL"` (coincide con el ejemplo
      de la spec).
    - `Secuencia_RIO_Detencion` = `"-2min PS/OM/AGUASBLANCAS-AGB_DIESEL;
      +10min FS/OM/AGUASBLANCAS-AGB_DIESEL"` — confirma también el
      patrón simétrico de detención (PS→FS) que se había hipotetizado
      pero no verificado explícitamente en el mismo ciclo.
  - Confirmé con el diagnóstico de ese mismo ciclo (vía
    `armar_trazado`, spec 12/13) que la hoja `Diagnostico` ahora sí
    muestra `Termino_Ciclo` (`2026-06-01 21:00:00`) y las columnas
    `_RIO` (`Tipo_Partida_RIO`, `Config_RIO_Usada_Partida`,
    `Config_RIO_Usada_Detencion`, `Detencion_Tarifa_RIO`) — el hallazgo
    de la spec 13 queda resuelto.
- **Conclusión:** ambas specs cierran limpio, sin hallazgos nuevos.
- **Pendientes:** ninguno de estas dos specs. Queda abierta la decisión
  de negocio (no de esta spec) de si algún día se cambia la regla de
  selección de qué instrucción RIO determina la tarifa cuando hay
  varias en la ventana — por ahora la visibilidad de la spec 14 es
  puramente informativa, según lo decidido explícitamente con el dueño
  del proyecto.

### 2026-09-09 — Claude — Revisión de la herramienta de diagnóstico de observaciones (spec 12, PR #27)

- **Tipo:** prueba de integración end-to-end con datos reales + revisión,
  con 2 hallazgos que requieren corrección.
- **Origen:** implementación de Codex en `6f82224` (PR #27,
  `codex/implementar-herramienta-diagnostico-observaciones`) de
  `docs/specs/12-herramienta-diagnostico-observaciones.md`.
- **Revisión del código:** el cambio en `main()` es exactamente aditivo
  (parámetro `devolver_diagnostico=False` por defecto, sin tocar el
  `return` implícito existente cuando no se usa) — confirmado además
  porque `pytest -q -m ""` (30/30, incluidos los 5 tests nuevos de
  `test_diagnostico_observaciones.py`) sigue en verde sin cambios de
  comportamiento. `coincide_central`/`filtrar_ventana`/`armar_trazado`
  siguen el diseño de la spec: no agregan lógica de negocio nueva, solo
  filtran y despliegan columnas que el motor ya calcula.
- **Validación con datos reales:** corrí `main(rutas,
  devolver_diagnostico=True)` contra el mismo insumo real de junio 2026
  ya usado en revisiones anteriores, y probé `armar_trazado` con dos
  casos:
  1. **TENO_DIESEL, 04-06-2026 19:38–19:52** (la ventana citada
     textualmente en una observación real de `Observaciones_16.xlsx`):
     el trazado devuelve `Detalle_15Min` y `Resumen_Ciclos_PD` vacíos, y
     la hoja `Diagnostico` dice explícitamente "No aparece en
     Detalle_15Min: no fue considerada en ningún ciclo de este cálculo"
     — reproduce exactamente el patrón que describe la observación
     ("no se está pagando la partida ni la detención [...] ya que no
     aparece la activación en la hoja PARTIDAS_DETENCIONES"). El RIO
     real (`RIO_06_2026.xlsx`) tampoco trae registros de esta central en
     esa ventana — consistente con que muchos de estos sub-puntos, en
     las respuestas reales del Coordinador, terminan "No Acogido" por no
     encontrarse en el RIO oficial.
  2. Un ciclo real que sí se pagó (`AGUASBLANCAS-AGB_DIESEL&1`,
     5.890,71 CLP): el trazado devuelve 10 filas de `Detalle_15Min` y la
     fila completa de `Resumen_Ciclos_PD`, confirmando que el caso
     "encontrado" también funciona de punta a punta.
- **Hallazgos (a corregir):**
  1. **Bug de nombre de columna:** `_diagnostico_ciclos` (en
     `src/diagnostico_observaciones.py`) filtra por el nombre literal
     `'Fin_Ciclo'`, pero la columna real en `Resumen_Ciclos_PD` es
     `Termino_Ciclo` — confirmado con `columnas_resumen_ciclos()` y con
     la corrida real de arriba: la hoja `Diagnostico` muestra
     `Inicio_Ciclo` pero nunca la hora de término del ciclo. No hace
     `raise` (el nombre simplemente nunca calza), así que pasó
     silenciosamente los tests y la corrida real.
  2. **Campos RIO faltantes en la hoja `Diagnostico`:** con
     `USAR_TARIFA_RIO_INSTRUIDA=1` (el interruptor activo en producción),
     la tarifa realmente cobrada la determinan las columnas `_RIO`
     (`Tipo_Partida_RIO`, `Config_RIO_Usada_Partida`,
     `Config_RIO_Usada_Detencion`, `Detencion_Tarifa_RIO`), no
     `Tipo_Partida` a secas. Ninguna de esas columnas `_RIO` quedó en la
     lista de prefijos de `_diagnostico_ciclos`, así que la hoja
     resumen "en lenguaje llano" —el punto central de esta herramienta—
     no muestra la razón RIO real detrás del monto. La hoja completa
     `Resumen_Ciclos_PD` del mismo Excel sí trae estas columnas, así que
     no se pierde información, pero la hoja pensada para verse "de un
     vistazo" queda incompleta para el caso más común de las
     observaciones reales revisadas.
- **Conclusión:** el diseño y el flujo end-to-end funcionan
  correctamente y ya se verificaron contra un caso real citado
  textualmente en una observación. Los dos hallazgos de arriba se
  documentan en la spec 13 para que Codex los corrija antes de dar por
  cerrada esta herramienta.
- **Pendientes:** aplicar spec 13 (fix de `Termino_Ciclo` + columnas
  `_RIO` en la hoja `Diagnostico`).

### 2026-09-09 — Claude — Convención de `Cuarto de Hora` confirmada contra el mes completo — spec 11 cerrada

- **Tipo:** validación final con datos reales, cierre de spec.
- **Origen:** el dueño del proyecto corrió la primera parte del script de
  validación (`validar_retiros_15min.py`) contra su parquet completo de
  retiros de 15 minutos (~1GB, junio 2026) y compartió el diagnóstico
  impreso por consola.
- **Resultado:**
  ```
  Clave_Anio_Mes=2606 (30 dias) -> min=1, max=2880, esperado max=2880  [OK]
  ```
  El máximo real de `Cuarto de Hora` (2.880) coincide exacto con
  `días_del_mes * 96` (30 × 96 = 2.880) para junio 2026. Confirma, contra
  el mes completo (no solo la muestra parcial de 20 cuartos usada antes),
  que `calcular_cuarto_hora_mensual` — 1-indexado, día 1 cuarto 1 =
  `[00:00,00:15)` — es la convención correcta del archivo real de
  producción. **No se requiere ningún ajuste a la fórmula.**
- **Conclusión:** con esto se cierra el único pendiente que quedaba
  abierto de la spec 11 (`docs/specs/11-prorrateo-pagos-15min.md`). Junto
  con la cuadratura perfecta ya verificada en las dos corridas reales
  anteriores (muestra de 1 suministrador y muestra de 79
  suministradores), la implementación del prorrateo de pagos a 15
  minutos queda completamente validada de punta a punta.
- **Pendientes:** ninguno de esta spec. Cuando el dueño del proyecto
  tenga el archivo de retiros completo listo para producción, puede
  correr `scripts/prorratear_pagos_15min.py` directo contra él (acepta
  `.parquet` sin conversión previa).

### 2026-09-09 — Claude — Segunda corrida real del prorrateo, muestra más rica (79 suministradores)

- **Tipo:** prueba de integración end-to-end adicional con datos reales.
- **Origen:** continuación de la revisión de la spec 11 (entrada
  siguiente) — el dueño del proyecto no pudo subir el parquet completo de
  retiros (~1GB), así que le pasé un script para extraer, desde su propio
  archivo, solo una muestra chica (columnas mínimas + primeros 20 cuartos
  de hora del mes, comprimida en `.csv.gz`).
- **Cambios:** ninguno en el repositorio — es una corrida de verificación
  adicional, no una implementación.
- **Validación:** la muestra recibida trae **79 suministradores reales**
  distintos (vs. 1 en la muestra original de la spec 11), en los primeros
  20 cuartos de hora del mes (`Cuarto de Hora` entre 1 y 20). Corrí
  `scripts/prorratear_pagos_15min.py` de punta a punta contra esta
  muestra y el mismo Excel real de junio 2026 ya usado:
  - 25 de 1.034 ciclos cruzaron con retiros (coherente con que la muestra
    solo cubre 20 de ~2.976 cuartos de hora del mes).
  - **Cuadratura perfecta** de nuevo: delta máximo `2,3e-10` en los 25
    ciclos, incluido un ciclo con 1.553 filas de detalle (79
    suministradores x hasta 20 cuartos), confirmando que el reparto entre
    múltiples suministradores concurrentes funciona igual de bien que con
    un solo suministrador.
  - Nota de robustez: a nivel de medidor individual (no de
    `Suministrador` agregado) hay un 0,5% de filas con `Medida_kWh`
    positivo (inyección) mezcladas con retiros negativos — no afecta el
    resultado, la cuadratura sigue exacta, porque el prorrateo opera
    sobre la suma agregada por `Suministrador`+cuarto, no por medidor.
- **Pendiente sin cambios:** la validación de la convención exacta de
  `Cuarto de Hora` contra el mes completo (`max == días_mes * 96`) sigue
  abierta — esta muestra solo llega hasta el cuarto 20, insuficiente para
  probar el cruce de día (ej. cuarto 96 -> 97). Falta que el dueño del
  proyecto comparta el diagnóstico que imprime la primera parte del
  script de validación (corrido contra el parquet completo).

### 2026-09-09 — Claude — Revisión del prorrateo de pagos a 15 minutos (spec 11, PR #24)

- **Tipo:** prueba de integración end-to-end con datos reales + revisión.
- **Origen:** implementación de Codex en `67362cd` (PR #24,
  `codex/implementar-prorrateo-de-pagos`) de
  `docs/specs/11-prorrateo-pagos-15min.md`.
- **Revisión del código:** `src/prorrateo_15min.py` implementa las 4
  funciones puras pedidas (`calcular_cuarto_hora_mensual`,
  `construir_membresia_ciclos`, `agrupar_retiros`/`prorratear_retiros`,
  `auditar_cuadratura`), separadas del wrapper de I/O
  (`scripts/prorratear_pagos_15min.py`), igual que el patrón
  `fase1_integridad.py`/`sc_pd_motor_v7.py`. La fórmula de
  `Cuarto_Hora_Mensual` es exactamente la propuesta en la spec. El cruce
  con retiros usa `merge` por `Cuarto_Hora_Mensual` solamente (no por
  central), replicando fielmente que un mismo retiro del sistema se
  reparte entre todos los ciclos concurrentes activos en ese cuarto de
  hora — igual que el script horario original. El caso de ciclo con
  `Total_kWh_Ciclo == 0` (sin retiros, o retiros que se cancelan) se
  excluye del reparto sin lanzar excepción y queda listado explícitamente
  en la auditoría, tal como pedía la spec.
- **Validación con datos reales — corrida completa:**
  1. Reconstruí el Excel del motor con datos reales de junio 2026 (mismo
     insumo usado para confirmar la spec 10), usando el `src/` actual del
     repo (`main` ya con specs 00-10 aplicadas). El `Total SC_PD` agregado
     coincidió con el total ya confirmado antes: **1.180.652.295,52 CLP**
     (vs. 1.180.652.296 CLP reportado en la revisión de la spec 10 —
     diferencia de redondeo de centavos, no un cambio real).
  2. Corrí `scripts/prorratear_pagos_15min.py` de punta a punta contra ese
     Excel y la única muestra de retiros 15-minutales disponible
     (`prueba_de_retiros_15min.csv`, ~100 filas, un solo
     `Suministrador`/`nombre_barra`, cubre solo cuartos de hora 1 a 147 —
     es decir, apenas los 2 primeros días del mes de un único
     suministrador). Con esa muestra tan acotada, **894 de 1.034 ciclos**
     del mes quedaron marcados `sin retiros para prorratear` (esperado:
     casi ningún ciclo del mes cae dentro de esa ventana de 2 días de un
     solo suministrador) y solo se repartieron 77,6M de los 1.180,6M CLP
     totales — comportamiento correcto dado el tamaño de la muestra, no
     un bug.
  3. **Cuadratura, verificada de forma independiente:** de los 140 ciclos
     que sí tuvieron al menos un retiro cruzado, recalculé
     `Monetario_Repartido` por ciclo desde el CSV de detalle exportado y
     lo comparé contra `Precio_Ciclo` — la diferencia máxima encontrada
     fue `9,3e-10` (ruido de punto flotante), es decir, cuadratura
     perfecta en los 140/140 ciclos.
  4. **Convención de `Cuarto de Hora` — validación parcial:** los valores
     de la muestra van de 1 a 147, consistentes con la hipótesis de
     índice 1-indexado del script (día 1 = 1-96, día 2 = 97-192). No pude
     confirmar el límite superior real de un mes completo (`días_mes *
     96`) porque no hay un archivo de retiros de 15 minutos con el mes
     completo disponible en este entorno — la muestra entregada por el
     dueño del proyecto solo cubre ~2 días. **Queda pendiente confirmar
     esto contra el archivo real de producción cuando esté disponible**,
     tal como ya advertía la spec.
- **Tests:** `pytest -q -m ""` — 25/25 OK (los 4 nuevos de
  `tests/test_prorrateo_15min.py` cubren exactamente los casos de
  aceptación de la spec: fórmula del cuarto de hora, deduplicación de
  membresía, ciclos concurrentes + ciclo sin retiros, y robustez de
  signo). `ast.parse` sobre `scripts/prorratear_pagos_15min.py` sin
  error.
- **Conclusión:** la implementación es correcta y fiel a la spec; la
  cuadratura cierra exactamente contra datos reales para todo ciclo que
  tuvo retiros que cruzar. No se encontraron hallazgos que bloqueen el
  cierre de esta spec.
- **Pendientes:** validar la convención exacta de `Cuarto de Hora` (punto
  4 de arriba) en cuanto el dueño del proyecto tenga el archivo de
  retiros de 15 minutos de un mes completo — si el índice real no calzara
  con la hipótesis 1-indexada, ajustar `calcular_cuarto_hora_mensual` en
  consecuencia.

### 2026-09-09 — Claude — Revisión del fallback de empresa por configuración (spec 10, PR #21)

- **Tipo:** prueba de integración end-to-end con datos reales + revisión.
- **Origen:** implementación de Codex en `0273610` (PR #21,
  `codex/aplicar-diccionario-empresa-fallback`) de
  `docs/specs/10-diccionario-empresa-fallback-configuracion.md`.
- **Revisión del código — hallazgo importante detectado por el propio
  implementador:** el código original tenía **dos asignaciones
  independientes de `Empresa`** — una a nivel de bloque
  (`reporte_sin_ceros['Empresa']`) y otra a nivel de ciclo
  (`df_compacto['Empresa']`, con su propio `.map()` directo contra
  `Central_Relacionada`, ignorando por completo la resolución a nivel de
  bloque). Si solo se corregía la primera (como pedía la spec
  literalmente), el rescate por nombre de configuración nunca se habría
  reflejado en `SC_por_Empresa`, porque esa hoja depende de la segunda.
  Codex corrigió ambas: `asignar_empresas()` (nueva función de módulo,
  testeable) resuelve por relacionada y rescata por configuración a nivel
  de bloque; `df_compacto['Empresa']` ahora se calcula agregando la
  `Empresa` ya resuelta por bloque, tomando la dominante por energía
  dentro de cada ciclo (antes decía hacerlo en un comentario, pero el
  código no lo hacía). Tests nuevos
  (`tests/test_diccionario_empresa.py`) cubren el rescate, la prioridad
  de la relacionada directa sobre el rescate, y el caso genuinamente sin
  empresa. `pytest -q -m ""`: 21/21 OK.
- **Verificación con datos reales (junio 2026, sexta corrida completa,
  con `RUTA_DICCIONARIO_EMPRESA` real conectado):** el log confirma
  `"1 centrales relacionadas resueltas por nombre de configuracion
  (217.03 MWh): NEHUENCO-9B"` y `"OK: todas las centrales relacionadas
  vigentes tienen empresa asignada"`. En `Resumen_Ciclos_PD`, el ciclo
  `NEHUENCO-9B&1` quedó con `Empresa = COLBUN` (antes `Sin_Empresa`). El
  total de `SC_por_Empresa` no cambió (1.180.652.296 CLP).
- **Nota:** la funcionalidad de desglose por empresa
  (`RUTA_DICCIONARIO_EMPRESA`) ya existía en el motor desde antes de este
  proyecto de correcciones — se probó por primera vez con el diccionario
  real del dueño del proyecto en esta ronda (specs 10), no hubo que
  construirla desde cero.
- **Pendientes:** ninguno de esta spec. Sigue pendiente conseguir
  RIO/reporte/costos de mayo 2026 para el empalme de frontera mensual.

### 2026-09-09 — Claude — Revisión de la trazabilidad exportada por ciclo (spec 09, PR #18)

- **Tipo:** prueba de integración end-to-end con datos reales + revisión.
- **Origen:** implementación de Codex en `c9e10c3` (PR #18,
  `codex/aplicar-detalles-de-documento-de-ciclos`) de
  `docs/specs/09-detalle-replicable-resumen-ciclos.md`.
- **Revisión del código:** extrajo `compactar_resumen_ciclos()`,
  `columnas_resumen_ciclos()` y `crear_guia_lectura()` como funciones de
  módulo (testeables). Las columnas RIO quedaron insertadas junto a
  `Costo_Partida_Efectivo`/`Costo_Detencion_Efectivo` (no al final), más
  legible de lo que pedía la spec literalmente. Tests nuevos
  (`tests/test_resumen_ciclos_exportacion.py`) cubren un ciclo sintético
  con Tibia_2 base y RIO, la exportación real a Excel, y que el
  interruptor `USAR_TARIFA_RIO_INSTRUIDA=0` no exige columnas `_RIO`.
  `pytest -q -m ""`: 18/18 OK.
- **Verificación con datos reales (junio 2026, cuarta corrida completa):**
  `Resumen_Ciclos_PD` pasó de 30 a 59 columnas. El sobrecosto final no
  cambió (1.180.652.296 CLP, idéntico a la corrida anterior) — confirma
  que la spec solo agregó columnas, sin alterar ningún cálculo. Tomé un
  ciclo real aprobado (`AGUASBLANCAS-AGB_DIESEL&2`) y repliqué a mano
  `Costo_Partida_Base_RIO × Filtro_Conf × Filtro_Disp × Filtro_Op ×
  Filtro_CostoCero` usando solo las columnas nuevas: coincide exacto con
  `Costo_Partida_Efectivo` (5.890,71 CLP). También confirmé que
  `Partida_Tibia_2_RIO` para `GUACOLDA-3_CAR` (31.963,694) coincide con el
  valor que se había verificado a mano semanas atrás contra el archivo PO
  original.
- **Nota:** ningún ciclo de junio quedó clasificado en `Tibia_2` con
  `Horas_Detenida_Ciclo` calculada — las centrales GUACOLDA generan casi
  todo el mes sin parar, y sin datos de mayo no se puede calcular cuántas
  horas llevaban detenidas antes de junio (mismo problema de frontera
  mensual ya conocido). No es un bug de esta spec.
- **Pendientes:** ninguno de esta spec. Sigue pendiente conseguir
  RIO/reporte/costos de mayo 2026 para el empalme de frontera.

### 2026-09-09 — Claude — Revisión del rescate de Configuracion RIO (spec 08, PR #15)

- **Tipo:** prueba de integración end-to-end con datos reales + revisión.
- **Origen:** implementación de Codex en `873cae2` (PR #15,
  `codex/revisar-y-aplicar-especificaciones-de-rescate`) de
  `docs/specs/08-rescate-config-rio-ventana.md`.
- **Revisión del código:** `rescatar_config_rio_en_limites()` quedó
  extraída como función de módulo (testeable sin correr `main()`),
  respeta exactamente el alcance pedido (solo bloques de
  `Inicio_Ciclo_Global`/`Termino_Ciclo_Global`, solo cuando
  `Configuracion RIO == 'Sin_Registro_RIO'`, guardada por
  `ACTIVAR_BUSQUEDA_RELAJADA`), actualiza `Fuente_Config_RIO` en
  consistencia, y agrega su propia columna de auditoría
  (`Config_RIO_Rescatada_Ventana_Partida/Detencion`) exportada en
  `Resumen_Ciclos_PD`. Tests nuevos (`tests/test_rescate_config_rio.py`)
  cubren los 3 casos pedidos: dentro de ventana, fuera de ventana,
  interruptor apagado. `pytest -q -m ""`: 16/16 OK.
- **Verificación con datos reales (junio 2026, tercera corrida completa):**
  64 de los 68 casos identificados quedaron rescatados automáticamente
  (`Configuracion RIO rescatada partida: 64 ciclos, 5.190.351 CLP
  efectivos`; `detencion: 6 ciclos, 43.727 CLP`). "Revisar manualmente:
  config RIO sin tarifa" en partida bajó de 94 a 33; ciclos aprobados
  subieron de 875 a 920. Sobrecosto P-D final: de 1.175.418.218 CLP a
  **1.180.652.296 CLP** (+5.234.078 CLP, coincide exactamente con el
  monto rescatado reportado por el propio motor).
- **Corrección a mi propio reporte anterior:** inicialmente atribuí a esta
  spec el salto en la métrica amplia "Cobertura de Instrucción RIO"
  (57,5%→94,0%), pero verifiqué contra la corrida intermedia (solo con
  spec 07, sin spec 08) y esa métrica ya estaba en 94,0% antes de esta
  spec — el salto fue enteramente del fix de fechas (spec 07). Lo corregí
  con el usuario antes de reportarlo como definitivo.
- **Pendientes:** los ~30 casos restantes de "revisar manualmente"/"sin
  tarifa de partida" tras el rescate son mayormente cobertura de datos
  (la configuración que instruyó el RIO no tiene precio en
  `Costos_de_P-D_Consolidado.xlsx`), no un problema de lógica del motor.

### 2026-09-09 — Claude — Primera corrida real del motor completo (junio 2026) + revisión del fix crítico

- **Tipo:** prueba de integración end-to-end con datos de producción.
- **Origen:** primera vez que se corre `main()` contra archivos reales
  completos (`Reporte_PD_15min_2606.csv` 787.820 filas,
  `RIO_06_2026.xlsx`, `Diccionario_central_config.xlsx`,
  `Costos_de_P-D_Consolidado.xlsx` regenerado con el fix de Tibia 2 a
  partir de las 116 políticas PO reales de junio). Sin archivos de mes
  anterior (mayo 2026 no disponible en esta sesión).
- **Hallazgo crítico encontrado y corregido (spec 07, PR #11,
  commit `f06e2d9`):** `leer_reporte()` usaba `dayfirst=True`, que invertía
  día/mes incluso en fechas ISO no ambiguas para los días 1-12 de cada mes.
  Medido con dos corridas completas del motor sobre los mismos datos:
  - Con el bug: ventana `2026-01-06` → `2026-12-06`, SC P-D final =
    691.806.794 CLP.
  - Corregido: ventana `2026-06-01` → `2026-06-30`, SC P-D final =
    **1.175.418.218 CLP**.
  - Subestimación del bug: **483.611.424 CLP (70%) en un solo mes.**
- **Revisión del fix de Codex:** confirmé que `dayfirst=False` más la
  función `validar_meses_reporte()` (aborta si aparecen fechas en más de
  2 meses-calendario, con muestra de valores original/parseado) quedaron
  bien implementados. Volví a correr el motor real (sin ningún parche mío)
  con el código ya corregido: reproduce exactamente
  **1.175.418.218 CLP**, igual que mi verificación independiente.
  `pytest -q -m ""`: 13/13 OK.
- **Otros hallazgos de esta corrida real, registrados para seguimiento
  (no bloquean, no son de la prioridad de la spec 07):**
  - Cruce `Llave_FHC` vs. tabla de costos: solo 83,2% de los bloques
    encuentran tarifa.
  - Cobertura de instrucción RIO: 42,0% de la generación analizada
    (1.257.132 MWh) queda "No instruida" (sin `MOTIVO` directo ni por
    ventana/mismo bloque) — probablemente se reduce bastante al agregar
    RIO y reporte del mes anterior (mayo 2026), no disponibles en esta
    prueba.
  - 5 de 85 centrales relacionadas no tienen ningún registro en el RIO
    del mes.
  - 2 filas del diccionario con prefijo de configuración distinto al de
    la relacionada (`UJINA-6_HFO`→`UJINA-4`, `TENOGAS-1a26_GLP`→`TENOGAS_GLP`)
    — a revisar si son agrupaciones legítimas.
  - `CODIGOS_EO_VALIDOS=['PDO']` sigue sin aparecer en el RIO de junio
    (consistente con lo ya confirmado: es un estado poco frecuente, no un
    error de mapeo).
- **Pendientes:** conseguir RIO/reporte/costos de mayo 2026 para probar el
  empalme de frontera mensual con datos reales; investigar la cobertura
  RIO del 42% "no instruida" una vez que exista ese empalme.

### 2026-09-09 — Claude — Revisión de specs 04-06 (PR #8)

- **Tipo:** prueba y revisión.
- **Origen:** cambios de Codex en `60c1f63` (PR #8,
  `codex/revisar-y-aplicar-especificaciones-en-orden`), revisados contra
  `docs/specs/04-costo-cero-por-fecha.md`,
  `docs/specs/05-script-consolidacion-tibia2.md` y
  `docs/specs/06-motor-cuarto-tramo-tibia2.md`.
- **Cambios verificados (con prueba propia, no solo lectura de código):**
  1. **`scripts/consolidar_politicas.py`**: coincide con la spec 05. Lo
     corrí contra el archivo PO real (`PO260609_20.xlsx`): `GUACOLDA-3_CAR`
     produce `Partida_Tibia_2 = 31.963,694` (valor correcto), y la
     auditoría de consistencia nueva detectó automáticamente el caso
     `GUACOLDA-5_CAR` (precio de Tibia 2 sin rango de horas informado) tal
     como se esperaba.
  2. **`Costo_Cero` por fecha**: el pre-filtro temprano ahora usa "¿alguna
     vez `NO`?" (vectorizado, sin loop) en vez de "última fila", y el
     `Costo_Cero` real se resuelve por `Llave_FHC_Inicio`/`Llave_FHC_Fin`,
     igual que las tarifas. Reproduce correctamente el caso
     `CHUYACA_DIESEL` en el test nuevo. Observación distinguible
     (`"Exento: Costo_Cero=SI en la fecha de partida"`) agregada en
     `Obs_Partida`/`Obs_Detencion`.
  3. **4 tramos de partida**: implementado con una función compartida
     `clasificar_partida()` reutilizada por la rama clásica y la rama
     `_RIO` (mejor que la duplicación que pedía la spec). Confirmado con
     el caso real `GUACOLDA-3_CAR` (100h → Tibia_2 a 31.963,694; 50h →
     Tibia a 30.838,528; 200h → Fría; 10h → Caliente) y con la regresión
     obligatoria: unidades sin `Tibia_Num2_N` (la mayoría) dan resultado
     idéntico al de antes de esta spec.
  - `pytest -q -m ""`: 11/11 OK (incluye el test de rendimiento). Ningún
    interruptor de negocio fue tocado.
- **Nota de proceso:** esta implementación no agregó su propia entrada a
  esta bitácora — la agrego yo para no perder la trazabilidad del cambio.
- **Pendientes:** validar con datos operacionales reales de un mes
  completo cuando estén disponibles. Sigue abierto confirmar si el patrón
  "Tibia 2" existe en otras centrales/meses más allá de las `GUACOLDA`
  encontradas hasta ahora (no bloquea nada, es solo cobertura de muestra).

### 2026-09-09 — Codex (OpenAI) — Costo_Cero por fecha y tramo "Tibia 2"

- **Tipo:** implementación, refactor y pruebas.
- **Origen:** `docs/specs/04-costo-cero-por-fecha.md`,
  `docs/specs/05-script-consolidacion-tibia2.md`,
  `docs/specs/06-motor-cuarto-tramo-tibia2.md`.
- **Cambios:** agregado `scripts/consolidar_politicas.py` (con captura de
  `Partida_Tibia_2`/`Tiempo_Partida_Tibia_2` y auditoría de consistencia
  contra `Tibia_Num2_N`/`Fria_Num1_M`); `Costo_Cero` resuelto por fecha vía
  `Llave_FHC` en vez de un valor único por central; clasificación de
  partida extendida a 4 tramos (`clasificar_partida()` en
  `fase1_integridad.py`, reutilizada por la rama clásica y la rama RIO
  instruida); `[BUG 9]` documentado en el encabezado del motor.
- **Validación declarada:** `pytest -q` en verde.
- **Commit:** `60c1f63` (`Implementar costo cero por fecha y tramo Tibia 2`).
- **Nota:** entrada reconstruida por Claude en la revisión posterior — esta
  implementación no dejó su propia entrada en la bitácora (ver entrada de
  arriba).

### 2026-09-08 — Claude — `CODIGOS_EO_VALIDOS` confirmado, cierra pendiente de negocio

- **Tipo:** decisión (documentación, sin cambio de comportamiento).
- **Origen:** `docs/specs/03-confirmar-codigos-eo-validos.md`, a partir de
  la fórmula de Excel original que compartió el dueño del proyecto.
- **Cambios:** se verificó celda por celda la fórmula de Excel que este
  motor reemplaza (`P2`=`MOTIVO`, `Z2`=chequeo SSCC/CTF/CSF/CPF,
  `N2`=`Etiqueta_Relacionada`, `Q2`=`BUSCARV` directo contra la columna
  `ESTADO OPERACIONAL` del RIO comparado contra `"PDO"`). Coincide
  exactamente con `CODIGOS_EO_VALIDOS = ['PDO']` del motor — no hay bug de
  mapeo de columnas. El dueño del proyecto confirmó además, revisando un
  RIO real, que la columna `ESTADO OPERACIONAL` sí contiene el valor
  `"PDO"` (no aparecía en la muestra de julio 2026 usada en la auditoría
  original por ser un estado poco frecuente). README actualizado para
  quitar este ítem de la lista de pendientes.
- **Validación:** revisión manual de la fórmula de Excel contra
  `calcular_filtros` en `src/sc_pd_motor_v7.py`, confirmación del dueño del
  proyecto sobre datos reales de RIO.
- **Pendientes:** que Codex actualice el comentario junto a
  `CODIGOS_EO_VALIDOS` en `src/sc_pd_motor_v7.py` (spec 03) — el valor
  `['PDO']` no cambia, solo el comentario que lo marcaba como pendiente.
  Sigue abierto compartir `Costos_de_P-D_Consolidado.xlsx`.

### 2026-09-08 — Claude — Revisión de la implementación Fase 1 (PR #2)

- **Tipo:** prueba y revisión.
- **Origen:** cambios de Codex en `de040b8`/`009a52a` (PR #2, `codex/aplicar-cambios-de-documentacion-especificada`), revisados contra `docs/specs/01-fase1-integridad-datos.md`.
- **Cambios revisados:** confirmé que `empalmar_reportes` y
  `deduplicar_rio_priorizando_motivo` quedaron correctamente conectados al
  pipeline real (`src/sc_pd_motor_v7.py`), que el `BUG 8` quedó documentado
  en el encabezado, que la divergencia de fuente RIO
  (`Diverge_Fuente_RIO_Partida/Detencion`) quedó bien instrumentada, y que
  ningún interruptor de negocio fue tocado. `pytest -q` pasa (6/6) y el
  archivo sigue siendo sintácticamente válido.
- **Hallazgos (ver `docs/specs/02-correcciones-post-revision.md` para el detalle):**
  1. **Crítico — rendimiento:** `empalmar_reportes` itera en Python puro
     sobre `groupby()`. Probé con un dataset sintético de ~1,7M filas
     combinadas (tamaño realista de un mes de datos) y el proceso no
     terminó en más de 3 minutos (tuve que matarlo manualmente); el
     `drop_duplicates` vectorizado que reemplazó corría en menos de 1
     segundo para el mismo volumen. Tal como está, esta función haría
     impracticable correr el motor sobre un mes completo de datos reales.
  2. **Importante — pruebas desconectadas del código real:** `calcular_ciclos`,
     `costos_clasicos` y `marcar_sin_tarifa_rio` en `src/fase1_integridad.py`
     no están importadas ni usadas en ningún punto de
     `src/sc_pd_motor_v7.py` — son reimplementaciones paralelas que solo
     ejercitan los tests. De los 6 tests, 4
     (`test_ciclo_cruza_mes`, `test_micro_corte_corta_ciclo`,
     `test_central_sin_registro_rio`, `test_regresion_interruptores_apagados`)
     pasan en verde pero no protegen la lógica que de verdad corre en el
     motor (`calcular_ciclos_por_nivel` y el cálculo inline de
     `Costo_*_Efectivo`/`Obs_Partida`). Solo 2 tests
     (`test_empalme_no_pierde_energia_en_colision`,
     `test_prioridad_motivo_no_nulo_en_duplicado_rio`) cubren código
     realmente ejecutado por el script.
  3. **Menor:** cuando no hay archivo de mes anterior
     (`RUTA_REPORTE_MES_PASADO` vacío/inexistente), `reporte` se asigna
     directo desde `reporte_actual` sin pasar por `empalmar_reportes`, así
     que una colisión de llave dentro del propio mes actual (el mismo caso
     de DST que se pidió corregir) seguiría perdiendo generación en
     silencio en ese escenario específico.
- **Validación:** `pytest -q` (6/6 OK), `ast.parse`, `py_compile`, prueba de
  estrés manual con datos sintéticos (no incluida en el repo).
- **Pendientes:** aplicar `docs/specs/02-correcciones-post-revision.md`.

### 2026-09-08 — Codex (OpenAI) — Bitácora acumulativa

- **Tipo:** documentación.
- **Origen:** solicitud del propietario del proyecto.
- **Cambios:** creación de `bitacora.md` como registro compartido para los
  updates de Claude y Codex. Se documentó un formato común y se incorporó el
  historial conocido hasta esta fecha.
- **Validación:** revisión Markdown y `git diff --check`.
- **Pendientes:** mantener esta bitácora actualizada en cada cambio futuro.

### 2026-09-08 — Codex (OpenAI) — Implementación de integridad de datos, Fase 1

- **Tipo:** implementación y pruebas.
- **Origen:** `docs/specs/01-fase1-integridad-datos.md`.
- **Cambios:**
  - se añadió la entrada documental `BUG 8` al motor;
  - se implementó un empalme que deduplica solapamientos reales y suma la
    generación de colisiones con datos distintos;
  - se incorporaron al log exportable los duplicados, las colisiones y las
    alertas residuales de timestamps repetidos;
  - se conservaron las fuentes temporales RIO usadas para tarifa y filtros, y
    se añadieron indicadores de divergencia para partida y detención;
  - se extrajeron utilidades puras en `src/fase1_integridad.py`;
  - se agregaron seis pruebas sintéticas en `tests/test_fase1_integridad.py`.
- **Validación:** `pytest -q`, `python -m py_compile src/*.py tests/*.py`, parseo
  con `ast` y `git diff --check`.
- **Pendientes:** validar el pipeline completo con archivos reales cuando estén
  disponibles; no se modificaron las decisiones de negocio pendientes.
- **Commit:** `de040b8` (`implement phase one data integrity safeguards`).

### 2026-09-08 — Codex (OpenAI) — Restauración del motor v7

- **Tipo:** implementación.
- **Origen:** `docs/specs/00-restaurar-motor-v7.md`.
- **Cambios:** reemplazo del esqueleto de `src/sc_pd_motor_v7.py` por el código
  completo del motor v7 entregado en la especificación, antes de aplicar la
  Fase 1.
- **Validación:** parseo con `ast`, comprobación del tamaño del archivo y
  verificación de su primera y última línea.
- **Pendientes:** Ninguno para la restauración.
- **Commit:** `009a52a` (`restore v7 cost engine`).

### 2026-09-08 — Claude — Especificación de integridad de datos, Fase 1

- **Tipo:** especificación y auditoría.
- **Origen:** `docs/specs/01-fase1-integridad-datos.md`.
- **Cambios:** documentación de correcciones ya presentes en v7 y definición de
  los fixes pendientes: colisiones del empalme, auditoría exportable de
  timestamps repetidos, trazabilidad de fuentes RIO, documentación de `BUG 8`
  y seis escenarios de prueba sintéticos.
- **Validación:** revisión del código v7 descrita en la propia especificación.
- **Pendientes de negocio:** confirmar `CODIGOS_EO_VALIDOS` y validar las
  tarifas con `Costos_de_P-D_Consolidado.xlsx`; no deben resolverse por una
  decisión exclusivamente técnica.
- **Commit de la especificación:** `a6bcc37`.

### 2026-09-08 — Claude — Especificación para restaurar el motor v7

- **Tipo:** especificación.
- **Origen:** `docs/specs/00-restaurar-motor-v7.md`.
- **Cambios:** entrega literal del código fuente completo del motor v7 y de las
  verificaciones necesarias para restaurarlo sin reformatear ni alterar sus
  interruptores o rutas de ejemplo.
- **Validación solicitada:** parseo con `ast`, conteo aproximado de líneas y
  comprobación del inicio y final del archivo.
- **Pendientes:** ejecutar la Fase 1 únicamente después de restaurar v7.
- **Commit de la especificación:** `a6bcc37`.

### 2026-09-08 — Claude — Revisión de las correcciones post-revisión (PR #4)

- **Tipo:** prueba y revisión.
- **Origen:** cambios de Codex en `6163f47` (PR #4,
  `codex/confirmar-archivo-y-aplicar-cambios`), revisados contra
  `docs/specs/02-correcciones-post-revision.md`.
- **Cambios verificados (los 3 puntos de la spec 02, cada uno con prueba
  independiente, no solo lectura de código):**
  1. **Rendimiento:** confirmé con `ast`/`grep` que `empalmar_reportes`
     quedó reescrito de forma vectorizada (sin loop de Python por grupo).
     Repetí mi prueba de estrés original del caso más adverso (864.000
     filas por archivo, **100% de colisión de llave** — peor caso posible,
     más duro que el test de volumen incluido en el repo, que usa
     solapamiento realista de 96 filas): terminó en **5,74 segundos**
     conservando el total de `GENERACION` esperado. Antes de este fix, el
     mismo caso no terminaba en más de 3 minutos.
  2. **Cobertura de pruebas:** confirmé con `ast.walk` que todo el pipeline
     (secciones 1 a 15) quedó anidado dentro de una función `main(rutas,
     panel=None)`, con `if __name__ == "__main__": main({})` al final
     (comportamiento idéntico al de antes al correr el script). Confirmé
     con `grep` que `calcular_ciclos_por_nivel` ahora delega en
     `calcular_ciclos`, y que `costos_clasicos`/`marcar_sin_tarifa_rio` se
     invocan directamente sobre `df_compacto` en el lugar exacto donde
     antes vivía la lógica duplicada — no quedó lógica inline duplicada
     (verificado que el bloque `Costo_Partida_Efectivo] = (df_compacto...`
     original ya no existe). Los 8 tests ahora sí ejercitan código
     realmente conectado al motor.
  3. **Caso sin mes anterior:** confirmé que la rama `else` (sin
     `RUTA_REPORTE_MES_PASADO`) ahora llama a
     `empalmar_reportes(reporte_actual.iloc[0:0].copy(), reporte_actual,
     _audit_log)`, aplicando la misma protección contra colisión de llave
     también en ese escenario. Cubierto por el nuevo test
     `test_empalme_sin_mes_anterior_no_pierde_energia`.
  - Reconfirmé que ningún interruptor de negocio fue tocado
    (`USAR_CONFIG_DOMINANTE=0`, `USAR_TARIFA_RIO_INSTRUIDA=1`,
    `REGLA_EXENCION='sin_historia'`, `TOLERANCIA_CORTES_BLOQUES=0`,
    `CODIGOS_EO_VALIDOS=['PDO']` sin cambios).
- **Nota menor, no bloqueante:** `main()` usa `globals().update(rutas or
  {}, panel or {})` para inyectar configuración — funciona bien para el
  uso actual (un solo `main()` por proceso), pero si en el futuro se llama
  `main()` más de una vez en el mismo proceso con overrides parciales, los
  valores de una llamada anterior podrían quedar pegados. No requiere
  acción ahora.
- **Validación:** `pytest -q -m ""` (8/8 OK, incluye el test de
  rendimiento marcado `slow`), `ast.parse`, `py_compile`, prueba de estrés
  propia con datos sintéticos (peor caso, no incluida en el repo).
- **Conclusión:** Fase 1 (integridad de datos) queda cerrada. Los 3
  hallazgos de la revisión anterior están resueltos y verificados de forma
  independiente.
- **Pendientes:** ninguno de integridad de datos. Siguen abiertos los
  pendientes de negocio ya documentados (`CODIGOS_EO_VALIDOS`,
  `Costos_de_P-D_Consolidado.xlsx`) y la validación con datos operacionales
  reales cuando estén disponibles.

### 2026-09-08 — Codex (OpenAI) — Correcciones posteriores a revisión

- **Tipo:** implementación, refactor y pruebas.
- **Origen:** `docs/specs/02-correcciones-post-revision.md`.
- **Cambios:** se eligió la **Ruta A** para evitar que las pruebas validen
  implementaciones paralelas: el motor ahora tiene un punto de entrada `main`,
  es importable sin ejecutar archivos, y reutiliza las funciones compartidas
  para ciclos, costos efectivos y observaciones RIO. El empalme quedó
  vectorizado, incluida la agregación del mes actual cuando no existe archivo
  anterior, y se añadieron regresiones funcionales y de volumen.
- **Validación:** `pytest -q --durations=5` (8/8 OK) sobre 500.000 filas por
  archivo; la prueba de rendimiento completó el empalme de 1.000.000 de filas
  de entrada en **2,71 segundos**, con límite explícito de 20 segundos.
- **Pendientes:** validar el pipeline completo con los archivos operacionales
  reales cuando estén disponibles.
### 2026-09-16 — Codex (OpenAI) — Comparador oficial con Excel horario (spec 29)

- **Tipo:** implementación, documentación y pruebas.
- **Origen:** scripts manuales de `docs/informes/scripts_brechas_2608` y diagnóstico
  de las rondas tercera a quinta de `Brechas_2608_por_empresa.md`.
- **Cambios:** herramienta importable/CLI que lee el `.xlsm` horario en modo
  `read_only`/`data_only`, deriva fechas desde xHyC, calcula los alcances mes completo
  y ciclos propios sin herencia, aparea por central/traslape, descompone exactamente
  el delta SC y asigna causas R1–R9. Exporta las siete hojas de auditoría y ofrece un
  runner con archivos locales en `Carpeta_de_Trabajo`.
- **Validación:** suite `pytest -q`, compilación Python y `git diff --check`.
- **Pendientes:** Claude debe ejecutar y contrastar la herramienta con los libros
  reales; esos datos no se versionan.

### 2026-09-16 — Codex (OpenAI) — Entrega con formato Excel horario (spec 32)

- **Tipo:** implementación, exportación, documentación y pruebas sintéticas.
- **Cambios:** la entrega de la spec 31 fue reemplazada por las trece hojas del
  Excel horario, fórmulas por letra y rangos acotados, y CSV de valores. El motor
  expone sin alterar el cálculo `RIO_Usado`, `Costos_PD_Usados` y
  `Central_Empresa`. Se agregó la versión Preliminar/Definitivo y se retiró la
  opción de tablas dinámicas.
- **Pendiente:** Claude verificará agosto de 2026 con los archivos reales.

### 2026-09-21 — Codex (OpenAI) — Partida en pruebas tras orden fallida (spec 33)

- **Tipo:** regla de negocio opcional, auditoría, interfaz y pruebas sintéticas.
- **Cambios:** se agregó `PARTIDA_EN_PRUEBAS`, apagado por defecto, con las
  variantes que exigen orden OM fallida más disponibilidad o solamente
  disponibilidad con motivo válido. El motor conserva la instrucción EP original,
  expone seis columnas de auditoría, muestra en consola la sensibilidad D/O aun al
  rechazar y ofrece el selector únicamente para v7 en runner e interfaz.
- **Validación:** nueve escenarios sintéticos de la spec 33 y suite completa de
  regresión. Con `rechazar` no se alteran filtros ni montos existentes.
- **Pendiente:** Claude verificará agosto de 2026 con los archivos reales, según la
  sección 9 de la especificación.
### 2026-09-23 — Codex (OpenAI) — Rendimiento sin cambiar resultados (spec 35)

- **Tipo:** instrumentación, optimización opcional y pruebas de regresión.
- **Cambios:** generador reproducible de 892.800 bloques y 80 suministradores;
  perfil por etapa con reloj, RSS y cProfile; caché Parquet opcional y con
  invalidación por antigüedad para que prorrateo y entrega eviten releer las
  hojas grandes del XLSX. El XLSX y todos los formatos contractuales permanecen
  sin cambios; sin `pyarrow`, o ante cualquier hoja incompatible, se usa Excel.
- **Medición rápida (misma máquina):** motor 13,01→12,21 s; prorrateo
  3,56→3,02 s; entrega 26,25→26,93 s (ruido dominante en esta muestra pequeña).
  La tabla, limitaciones y comando del volumen mensual están en la spec 35.
- **Descartado:** vectorizar desempates RIO y cambiar el escritor contractual
  sin evidencia golden suficiente; ambas opciones arriesgaban resultados.
- **Validación:** suite completa de pytest, prueba dedicada de vigencia/fallback
  del caché, compilación Python y `git diff --check`.
- **Compatibilidad del PR:** la referencia golden se conserva como JSON de
  texto sin compresión para que el revisor pueda mostrar el diff; se eliminó el
  `.json.gz` que la plataforma rechazaba como archivo binario.
