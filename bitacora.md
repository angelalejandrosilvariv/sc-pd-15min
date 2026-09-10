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

## Updates

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
