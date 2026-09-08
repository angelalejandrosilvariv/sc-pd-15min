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
