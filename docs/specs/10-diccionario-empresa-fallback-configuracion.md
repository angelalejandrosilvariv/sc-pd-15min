# Spec 10 — Diccionario de empresas: aceptar entradas a nivel de configuración

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `tests/`

## Contexto

El motor ya tiene soporte completo para el desglose de sobrecosto por
empresa (`RUTA_DICCIONARIO_EMPRESA`, sección "Diccionario
Central_Relacionada -> Empresa", ~línea 638-673) — no hace falta
construir nada desde cero. El dueño del proyecto compartió
`Diccionario_central_empresa.xlsx` (columna A = central relacionada,
columna B = empresa) y lo probé conectándolo directamente: corriendo el
motor real contra junio 2026 completo, la hoja `SC_por_Empresa` sale
correcta — 31 empresas, total exacto de 1.180.652.296 CLP, coincide con
la corrida sin desglose por empresa.

**Hallazgo:** el diccionario mezcla dos niveles de nombre. La mayoría de
las filas usan el nombre de central **relacionada** (ej. `ABANICO`), pero
18 de 122 relacionadas reales de junio no aparecen así — en cambio,
aparecen sus **configuraciones** sin consolidar (`ANDES-1_DIESEL`,
`ANDES-1_FO6`, `ANDES-1+2_DIESEL` en vez de la relacionada `ANDES-1`, que
las agrupa a las tres según `Diccionario_central_config.xlsx`). Confirmé
que esas 18 configuraciones sí están, como filas separadas, en el
diccionario de empresas — solo que con el nombre equivocado para el cruce
que usa el motor (`Central_Relacionada`, no `Central`).

**Impacto medido en junio:** mínimo — solo `NEHUENCO-9B` cae en
`'Sin_Empresa'` (205,51 MWh a nivel de ciclo, **0 CLP** de sobrecosto, esa
central no tuvo ciclos facturables este mes). El propio motor ya audita
esto correctamente hoy (`[!] 1 centrales relacionadas sin empresa (217.03
MWh)...`) — el problema no es que falte auditoría, es que el motor no
tiene ninguna forma de recuperar el dato cuando el diccionario usa el
nombre de configuración en vez del de relacionada. En otro mes con más
actividad de esas 18 centrales, el impacto podría ser mayor.

## Fix requerido

Agregar un **segundo intento** de resolución cuando el cruce por
`Central_Relacionada` no encuentra empresa: probar con el nombre de
`Central` (la configuración cruda, antes de consolidar) contra el mismo
diccionario. Esto no requiere que el dueño del proyecto reordene su
Excel — el diccionario puede seguir mezclando ambos niveles de nombre.

En la sección ~638-673, después de la línea:

```python
        reporte_sin_ceros['Empresa'] = (reporte_sin_ceros['Central_Relacionada'].astype(str).str.strip()
                                        .map(empresa_por_relacionada))
```

agregar, antes del cálculo de `sin_emp`:

```python
        # Algunas centrales aparecen en el diccionario con el nombre de la
        # configuracion sin consolidar (ej. 'ANDES-1_DIESEL') en vez del
        # nombre de la relacionada que las agrupa (ej. 'ANDES-1'). Cuando el
        # cruce por Central_Relacionada no encuentra empresa, se reintenta
        # por Central (la configuracion cruda) contra el mismo diccionario,
        # antes de caer a 'Sin_Empresa'.
        sin_empresa_mask = reporte_sin_ceros['Empresa'].isna()
        rescate_config = (reporte_sin_ceros.loc[sin_empresa_mask, 'Central'].astype(str).str.strip()
                          .map(empresa_por_relacionada))
        reporte_sin_ceros.loc[sin_empresa_mask, 'Empresa'] = rescate_config
```

Y actualizar el audit existente (el bloque `sin_emp`/`[!] ... centrales
relacionadas sin empresa`) para que:

1. Siga reportando, sin cambios, las centrales que **de verdad** quedan
   sin empresa después de ambos intentos.
2. Agregue una línea nueva indicando cuántas centrales relacionadas (y
   cuántos MWh) se resolvieron gracias al rescate por `Central` — mismo
   estilo que las demás auditorías del motor (ej. "X centrales
   relacionadas resueltas por nombre de configuracion (Y MWh):" con la
   lista de nombres, igual formato que la lista existente).

## Criterio de aceptación

- Test sintético: un diccionario de empresa con una fila para una
  configuración cruda (ej. `'ANDES-1_DIESEL': 'ANDES_GENERACION'`) y
  **sin** fila para la relacionada `'ANDES-1'`. Un bloque con
  `Central='ANDES-1_DIESEL'` y `Central_Relacionada='ANDES-1'` debe
  terminar con `Empresa == 'ANDES_GENERACION'`, no `'Sin_Empresa'`.
- Test de regresión: el caso ya cubierto (relacionada presente
  directamente en el diccionario) sigue funcionando exactamente igual.
- Test de regresión: una central que genuinamente no tiene empresa ni por
  relacionada ni por configuración sigue cayendo en `'Sin_Empresa'`, sin
  quedar oculta por el nuevo mecanismo.
- Si hay datos reales disponibles en el entorno de implementación, correr
  el motor contra junio 2026 con `RUTA_DICCIONARIO_EMPRESA` apuntando al
  diccionario real y confirmar que `NEHUENCO-9B` deja de aparecer en
  `'Sin_Empresa'` en la hoja `SC_por_Empresa`, y que el total de
  `Total SC_PD` no cambia.
- `pytest -q -m ""` sigue en verde.
- Ningún interruptor de negocio se toca.

## Qué NO hacer en esta spec

- No pedirle al dueño del proyecto que edite su Excel — el fix es que el
  motor tolere ambos niveles de nombre, no que la fuente de datos cambie.
- No tocar el mecanismo de duplicados por `Central_Relacionada`
  (`drop_duplicates(keep='last')`) — ya se verificó que las 54 filas
  duplicadas del diccionario real son inofensivas (misma empresa en todas
  sus apariciones), no hace falta una regla de prioridad distinta.
- No aplicar este mismo mecanismo de rescate a `diccionario_central`
  (`Central -> Central_Relacionada`) ni a ningún otro cruce del motor —
  esta spec es específica del diccionario de empresas.
