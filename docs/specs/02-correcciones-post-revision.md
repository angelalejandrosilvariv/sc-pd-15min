# Spec 02 — Correcciones tras revisión de la implementación Fase 1

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar — depende de que `docs/specs/01-fase1-integridad-datos.md` ya esté aplicada (lo está, ver `bitacora.md`)
**Toca código:** sí — `src/fase1_integridad.py`, `src/sc_pd_motor_v7.py`, `tests/`

## Contexto

Revisé la implementación de la Fase 1 (commits `009a52a` y `de040b8`).
El enfoque es correcto y quedó bien conectado al pipeline real en los
puntos que revisé: `empalmar_reportes` y `deduplicar_rio_priorizando_motivo`
sí se usan desde `src/sc_pd_motor_v7.py`, `BUG 8` quedó documentado, la
divergencia de fuente RIO quedó bien instrumentada, y ningún interruptor de
negocio fue tocado. `pytest -q` pasa (6/6).

Encontré 3 problemas al probarlo con datos de volumen realista y al
revisar qué código ejecutan realmente los tests. El detalle completo está
en la entrada de `bitacora.md` del 2026-09-08 firmada por Claude. Esta spec
los formaliza como trabajo a implementar, en orden de prioridad.

## 1. CRÍTICO — `empalmar_reportes` no escala a un mes real de datos

**Dónde:** `src/fase1_integridad.py`, función `empalmar_reportes`.

**Problema:** la función itera con un `for _, grupo in
combinado.groupby(LLAVE_REPORTE, ...)` en Python puro, sobre **todos** los
grupos del DataFrame combinado (la inmensa mayoría de tamaño 1, sin
colisión). Reproduje un dataset sintético de tamaño realista (300 centrales
× 96 bloques/día × 30 días = 864.000 filas por archivo, ~1,7M filas
combinadas) y el proceso no terminó en más de 3 minutos — tuve que matarlo
manualmente. La versión anterior (vectorizada, con `pd.concat` +
`drop_duplicates`) corría en menos de 1 segundo para el mismo volumen. Tal
como está, esta función haría impracticable correr el motor sobre un mes
completo de datos reales, que es el caso de uso central del proyecto.

**Fix requerido:** reescribir `empalmar_reportes` sin iterar en Python por
grupo. Approach sugerido (vectorizado de principio a fin):

1. Marcar con `duplicated(subset=LLAVE_REPORTE, keep=False)` qué filas
   participan en alguna colisión de llave.
2. Las filas **sin** colisión pasan tal cual al resultado (esta es la
   inmensa mayoría — debe ser una operación de indexado/booleano, sin loop).
3. Sobre el subconjunto de filas **con** colisión, usar operaciones
   vectorizadas de pandas (`groupby(...).transform(...)`,
   `groupby(...).nunique()`, `groupby(...).agg(...)`) para separar:
   - **Duplicado real**: todas las columnas de `comparar` (`GENERACION`,
     `CMg-CV`, `Dolar`, las que existan) tienen `nunique(dropna=False) == 1`
     dentro del grupo → conservar una sola fila por grupo (por ejemplo con
     `groupby(LLAVE_REPORTE, as_index=False).last()` sobre ese subconjunto,
     o `drop_duplicates(keep='last')`, ambas vectorizadas).
   - **Colisión con datos distintos**: agregar con
     `groupby(LLAVE_REPORTE, as_index=False).agg(...)`, sumando
     `GENERACION` y tomando `'last'` para el resto de columnas — mismo
     criterio que la versión actual, pero calculado con `.agg()` en vez de
     un loop.
4. Concatenar los tres resultados (sin colisión + duplicados reales
   deduplicados + colisiones agregadas) para formar el DataFrame final.
5. Mantener exactamente la misma firma (`empalmar_reportes(reporte_pasado,
   reporte_actual, audit_log=None)`), el mismo criterio de guard para
   `audit_log` mutable, y las mismas dos entradas de auditoría
   (`'1a. Duplicados reales del empalme'`, `'1b. Colisiones distintas
   agregadas'`) con los mismos conteos que hoy.

**Criterio de aceptación:**

- El test existente `test_empalme_no_pierde_energia_en_colision` debe
  seguir pasando **sin modificarlo** (verifica el resultado, no la
  implementación).
- Agregar un test de rendimiento — puede vivir en
  `tests/test_perf_empalme.py`, marcado con `@pytest.mark.slow` si se
  quiere poder excluirlo de una corrida rápida de `pytest -q` — que
  construya un dataset sintético de al menos 500.000 filas por archivo
  (con algo de solapamiento realista en la frontera, no 100% de colisión)
  y confirme que `empalmar_reportes` corre en un tiempo acotado (sugerido:
  menos de 20 segundos; ajustar si el entorno de CI es más lento, pero
  debe quedar un número explícito, no solo "más rápido"). El objetivo de
  este test es que un futuro cambio que vuelva a introducir un loop de
  Python por fila/grupo se detecte automáticamente, no solo por inspección
  manual.

## 2. IMPORTANTE — 4 de los 6 tests no protegen el código que realmente corre

**Dónde:** `src/fase1_integridad.py` (funciones `calcular_ciclos`,
`costos_clasicos`, `marcar_sin_tarifa_rio`) y
`tests/test_fase1_integridad.py`.

**Problema:** estas tres funciones no están importadas ni usadas en ningún
punto de `src/sc_pd_motor_v7.py` — verificado con
`grep -n "costos_clasicos\|marcar_sin_tarifa_rio\|calcular_ciclos\b"
src/sc_pd_motor_v7.py`, que no devuelve nada. Son reimplementaciones
paralelas y más simples de lógica que en el motor real vive de otra forma:

- la detección de ciclos real es `calcular_ciclos_por_nivel` (sección 3 del
  motor), que agrupa por `Central_Relacionada` y usa
  `TOLERANCIA_CORTES_BLOQUES`, no el `calcular_ciclos(df, grupo=('Central',))`
  de `fase1_integridad.py`;
- el cálculo de `Costo_Partida_Efectivo`/`Costo_Detencion_Efectivo` real es
  inline en `df_compacto[...] = df_compacto['Costo_Partida_Base'] *
  df_compacto['Filtro_Conf_Partida'] * ...` (sección 11), no
  `costos_clasicos(df)`;
- la marca de "sin tarifa RIO" real es inline vía `Config_RIO_Sin_Tarifa`
  (sección 11.1) y el `np.select` de `Obs_Partida`/`Obs_Detencion` (sección
  14.7), no `marcar_sin_tarifa_rio(df)`.

Como consecuencia, `test_ciclo_cruza_mes`, `test_micro_corte_corta_ciclo`,
`test_central_sin_registro_rio` y `test_regresion_interruptores_apagados`
pasan en verde, pero no protegen contra una regresión en el código que de
verdad se ejecuta cuando alguien corre `python src/sc_pd_motor_v7.py`. Esto
va en contra del principio del propio README: "Toda modificación que pueda
alterar el monto liquidado debería acompañarse de una prueba o evidencia
reproducible" — la evidencia hoy es sobre un modelo simplificado, no sobre
el motor real.

**Fix requerido:** elegir una de estas dos rutas (documentar en la
bitácora cuál se eligió y por qué):

- **Ruta A (recomendada): hacer que el motor real use las funciones
  compartidas.** Refactorizar `src/sc_pd_motor_v7.py` para que:
  1. Todo el bloque de ejecución (desde la sección 1 en adelante) quede
     dentro de una función `main(rutas: dict, panel: dict | None = None)`,
     invocada solo bajo `if __name__ == "__main__":` con los valores del
     panel de control actual como default. Correr `python
     src/sc_pd_motor_v7.py` debe seguir comportándose exactamente igual
     que hoy.
  2. La sección 3 (`calcular_ciclos_por_nivel`) y las secciones 11/14.7
     (cálculo de costo efectivo y observaciones) se reescriben para
     **llamar** a `calcular_ciclos`, `costos_clasicos` y
     `marcar_sin_tarifa_rio` de `fase1_integridad.py` en vez de duplicar
     la lógica — ajustando esas funciones compartidas si hace falta para
     que soporten el caso real (múltiples columnas de agrupación, el
     parámetro `TOLERANCIA_CORTES_BLOQUES`, etc.), pero sin que quede
     ninguna lógica de negocio escrita dos veces.
  3. Los tests existentes de `tests/test_fase1_integridad.py` no cambian
     de aserciones, porque ahora sí están probando el código real.

- **Ruta B (alternativa, si A resulta demasiado invasiva para este
  momento): dejar el motor como está y reescribir los tests** para que
  importen y ejerciten directamente las funciones reales del motor
  (`calcular_ciclos_por_nivel`, y fragmentos equivalentes para el cálculo
  de costo/observaciones), usando el refactor a `main()`/funciones
  importables del punto A.1 de todas formas — es la única forma de que un
  test pueda invocar esas piezas con datos sintéticos sin depender de
  archivos reales en disco. En este caso, `calcular_ciclos`,
  `costos_clasicos` y `marcar_sin_tarifa_rio` deberían eliminarse de
  `fase1_integridad.py` si quedan sin ningún uso (ni en el motor ni en los
  tests), para no dejar código muerto que alguien podría confundir con la
  lógica real.

**Criterio de aceptación (aplica a cualquiera de las dos rutas):** después
del fix, cada test de `tests/` debe ejercitar, directa o indirectamente,
una función que efectivamente se invoca durante una corrida normal de
`src/sc_pd_motor_v7.py`. Antes de dar por cerrada esta spec, correr de
nuevo el mismo chequeo (`grep` de los nombres de función usados por los
tests contra el motor) y confirmar que ya no hay funciones "huérfanas"
usadas solo por tests.

## 3. MENOR — el fix del empalme no cubre el caso sin mes anterior

**Dónde:** `src/sc_pd_motor_v7.py`, sección 1, rama `else` del
`if RUTA_REPORTE_MES_PASADO and os.path.exists(...)`.

**Problema:** cuando no hay archivo de mes anterior, el código hace
`reporte = reporte_actual.copy()` directamente, sin pasar por
`empalmar_reportes`. Si dentro del propio `reporte_actual` hay una
colisión de llave con datos distintos (el mismo caso de DST que motivó el
fix de la sección 1), esa energía se sigue perdiendo en silencio en este
escenario específico — solo queda la alerta informativa de más abajo
(`rep.any()`), que ya se corrigió para loguearse en `_audit_log`, pero que
no corrige el dato.

**Fix requerido:** aplicar la misma lógica de deduplicación/agregación
también en la rama `else`, por ejemplo llamando a `empalmar_reportes` con
un DataFrame vacío como `reporte_pasado` (mismas columnas que
`reporte_actual`, cero filas), o extrayendo esa parte a una función que se
aplique siempre sobre `reporte_actual` independientemente de si hay o no
archivo de mes anterior. El resultado debe ser que, con o sin
`RUTA_REPORTE_MES_PASADO`, una colisión de llave con `GENERACION` distinta
dentro de `reporte_actual` nunca se resuelva con un `drop`/`keep='last'`
silencioso.

**Test a agregar:** una variante de
`test_empalme_no_pierde_energia_en_colision` que solo pase `reporte_actual`
(sin mes pasado) con una colisión interna, y confirme que la energía
tampoco se pierde en ese caso.

## 4. Qué NO hacer en esta spec

- No tocar `USAR_CONFIG_DOMINANTE`, `USAR_TARIFA_RIO_INSTRUIDA`,
  `REGLA_EXENCION`, `TOLERANCIA_CORTES_BLOQUES` ni `CODIGOS_EO_VALIDOS`.
- No cambiar el resultado numérico de `test_empalme_no_pierde_energia_en_colision`
  ni de `test_prioridad_motivo_no_nulo_en_duplicado_rio` — el fix del punto
  1 debe ser un cambio de implementación (más rápido), no de comportamiento.
- Si se elige la Ruta A del punto 2, no cambiar el comportamiento de
  `calcular_ciclos_por_nivel` frente a los datos reales — el objetivo es
  que quede probada, no que cambie.

## 5. Actualizar `bitacora.md`

Al terminar, agregar una entrada nueva (no reemplazar las anteriores) con
el formato ya establecido, indicando qué ruta se eligió en el punto 2 y
los resultados de la prueba de rendimiento del punto 1 (tiempo medido en
segundos, tamaño del dataset usado).
