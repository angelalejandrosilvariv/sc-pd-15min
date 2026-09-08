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
