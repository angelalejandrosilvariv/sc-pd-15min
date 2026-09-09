# Spec 15 — Preferir, dentro de la ventana, el registro RIO cuya configuración coincide con la que físicamente generó

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `tests/`
**⚠️ Esta spec SÍ cambia montos facturados** (`Costo_Partida_Efectivo`,
`Costo_Detencion_Efectivo`, `Total SC_PD` de los ciclos afectados) — no
es aditiva como las specs 12-14. Revisar con cuidado antes de aplicar.

## Contexto

La spec 14 (ya en producción) agregó `Secuencia_RIO_Partida`/
`Secuencia_RIO_Detencion` — la lista completa de instrucciones RIO
dentro de `±VENTANA_CUARTOS_HORA` alrededor de cada límite de ciclo, sin
cambiar qué instrucción determina la tarifa. Con esa visibilidad,
cruzamos junio 2026 completo contra la configuración que **físicamente**
generó en cada bloque límite (columna `Central` de `Detalle_15Min` en
`FECHA_HORA == Inicio_Ciclo` / `== Termino_Ciclo`):

**Partida** (1.034 ciclos): 966 coinciden directo con
`Config_RIO_Usada_Partida`. De los 68 que no: 25 son `Sin_Registro_RIO`
(sin costo, no aplica) y **43 sí tienen la config física correcta en
algún punto de la ventana ±30min — 0 casos donde no aparece en
absoluto**. Monto involucrado: **426.202.388 CLP**.

**Detención**: de 21 que no coinciden directo (5 `Sin_Registro_RIO`),
**15 sí aparecen en la ventana** (33.634.340 CLP) y **1 caso genuino
donde la config física nunca aparece** (`NUEVARENCA_TG1+TV1&1`,
4.971.756 CLP — `..._GN_A` en el reporte vs. `..._GNL_C` en el RIO,
variantes de combustible distintas; no es un problema de ventana de
tiempo).

**Patrón físico identificado en los ejemplos revisados** (ej.
`KELAR-TG12&7`, `TOCOPILLA-U16&5`, `NEHUENCO-2&5`): son turbinas con dos
nombres de configuración — uno "simple" (ej. `TG1_TG1_DIESEL`) y uno
"combinado con turbina a vapor" (ej. `TG1_TG1+0.5TV_DIESEL`). El RIO
instruye el arranque de la config combinada (`PP`, generación 0
mientras arranca), pero **antes de que se una la turbina a vapor**, la
turbina a gas sola ya genera bajo el nombre simple — que es justo la
config que aparece con `PMT` (sincronizada, generación real y
creciente) unos minutos después en la ventana. El cruce actual
(`merge_asof` backward, sin límite hacia atrás) toma el `PP` viejo de la
config combinada en vez del `PMT` cercano de la config que realmente
generó.

**Decisión (confirmada con el dueño del proyecto):** agregar una regla
de preferencia por coincidencia física, con **fallback exacto al
comportamiento actual** cuando no hay ninguna coincidencia física en la
ventana (como el caso de NUEVARENCA).

## Regla a implementar

Dentro de `±VENTANA_CUARTOS_HORA` cuartos de hora alrededor de
`Inicio_Ciclo_Global` (para partida) o `Termino_Ciclo_Global` (para
detención), de todas las instrucciones RIO de esa `Central_Relacionada`:

1. Filtrar las que tengan `NOMBRE CONFIGURACIÓN` igual a la `Central`
   (física) de esa fila exacta de `resumen_relacionada`.
2. Si hay una o más: usar la más cercana en tiempo (mismo criterio que
   ya usa `rescatar_config_rio_en_limites` — `diferencias.abs().idxmin()`)
   para reemplazar `Configuracion RIO` y `Fuente_Config_RIO` de esa fila.
3. Si no hay ninguna: **no tocar nada** — se mantiene exactamente el
   valor que ya trae `Configuracion RIO` (del cruce maestro o del
   rescate de la spec 08).

## Qué construir

### 1. Nueva función en `src/sc_pd_motor_v7.py`

Ubicarla justo después de `rescatar_config_rio_en_limites` (mismo
archivo, mismo estilo de firma):

```python
def preferir_config_rio_fisica(resumen, rio_subset, activar, ventana_cuartos_hora):
    """En los limites de ciclo, si dentro de +/- ventana_cuartos_hora hay
    un registro RIO cuyo NOMBRE CONFIGURACIÓN coincide con la Central que
    fisicamente genero en ese bloque, se prefiere ese registro por sobre
    el que haya quedado asignado por el cruce maestro o el rescate de
    limites -- aunque este ultimo ya tuviera algun valor (a diferencia de
    rescatar_config_rio_en_limites, que solo actua si estaba vacio).

    Solo modifica 'Configuracion RIO' y 'Fuente_Config_RIO'. No toca
    CONSIGNAS/MOTIVO/ESTADO OPERACIONAL/COMENTARIO ni ningun Filtro_*.
    Si no hay coincidencia fisica en la ventana, la fila queda intacta.
    """
    resultado = resumen.copy()
    resultado['Config_RIO_Preferida_Fisica'] = False
    if activar != 1 or resultado.empty or rio_subset.empty:
        return resultado

    es_limite = ((resultado['FECHA_HORA'] == resultado['Inicio_Ciclo_Global'])
                 | (resultado['FECHA_HORA'] == resultado['Termino_Ciclo_Global']))
    candidatos_indices = resultado.index[es_limite]
    if candidatos_indices.empty:
        return resultado

    rio_valido = rio_subset.dropna(
        subset=['FECHA_HORA_RIO', 'Central_Relacionada_RIO', 'NOMBRE CONFIGURACIÓN'])
    por_central = {central: grupo for central, grupo in
                   rio_valido.groupby('Central_Relacionada_RIO', sort=False)}
    tolerancia = pd.Timedelta(minutes=ventana_cuartos_hora * 15)

    for indice in candidatos_indices:
        fila = resultado.loc[indice]
        candidatos = por_central.get(fila['Central_Relacionada'])
        if candidatos is None:
            continue
        mismo_fisico = candidatos[candidatos['NOMBRE CONFIGURACIÓN'] == fila['Central']]
        if mismo_fisico.empty:
            continue
        diferencias = (mismo_fisico['FECHA_HORA_RIO'] - fila['FECHA_HORA']).abs()
        dentro = diferencias <= tolerancia
        if not dentro.any():
            continue
        mejor_indice = diferencias[dentro].idxmin()
        mejor = mismo_fisico.loc[mejor_indice]
        resultado.at[indice, 'Configuracion RIO'] = mejor['NOMBRE CONFIGURACIÓN']
        resultado.at[indice, 'Fuente_Config_RIO'] = mejor['FECHA_HORA_RIO']
        resultado.at[indice, 'Config_RIO_Preferida_Fisica'] = True

    return resultado
```

### 2. Enganchar en `main()`, en el mismo punto donde corre `rescatar_config_rio_en_limites`

Justo **después** de la llamada existente a `rescatar_config_rio_en_limites`
(para que esta corrección pueda mejorar incluso lo que el rescate ya
haya llenado) y **antes** de `compactar_resumen_ciclos` (para que
`Config_RIO_Usada_Partida`/`Detencion`, y todo lo que se calcula a
partir de ellos — `Tipo_Partida_RIO`, tarifas `_RIO`,
`Costo_Partida_Base`, etc. — reflejen la corrección de forma natural,
sin tocar ningún otro punto del pipeline):

```python
resumen_relacionada = preferir_config_rio_fisica(
    resumen_relacionada, rio_subset, ACTIVAR_PREFERENCIA_CONFIG_FISICA,
    VENTANA_CUARTOS_HORA)
```

Agregar el interruptor nuevo junto a los demás, con **default `1`**
(activo, ya que es la conducta que se decidió aplicar):

```python
ACTIVAR_PREFERENCIA_CONFIG_FISICA = 1   # 1 = preferir, en la ventana +/- VENTANA_CUARTOS_HORA,
                                          # el registro RIO cuya config coincide con la que
                                          # fisicamente genero en el bloque limite del ciclo.
```

### 3. Auditoría (mismo estilo que ya existe para `Config_RIO_Rescatada_Ventana_*`)

Después de `compactar_resumen_ciclos`, agregar impresión de auditoría
por tipo (Partida/Detención), contando cuántos ciclos usaron esta
preferencia y el monto `Costo_*_Efectivo` asociado — mismo patrón que
las líneas ya existentes de `Config_RIO_Rescatada_Ventana` y
`Diverge_Fuente_RIO`.

### 4. Exportar la columna de auditoría

Agregar `Config_RIO_Preferida_Fisica_Partida` y
`Config_RIO_Preferida_Fisica_Detencion` a `columnas_resumen_ciclos()`
(mismo bloque que `Config_RIO_Rescatada_Ventana_Partida`/`Detencion`),
agregando también, en `compactar_resumen_ciclos`, la agregación
correspondiente (primero para partida, último para detención — mismo
patrón que ya usa `Config_RIO_Rescatada_Ventana`).

## Criterio de aceptación

- Tests nuevos cubriendo:
  - Caso base (patrón real de `KELAR-TG12&7`): config combinada con
    `PP` antes del límite, config simple con `PMT` cerca — debe preferir
    la simple (la que coincide con la física) y quedar
    `Config_RIO_Preferida_Fisica=True`.
  - Caso sin coincidencia física en la ventana (patrón real de
    `NUEVARENCA_TG1+TV1&1`): la fila queda **exactamente igual** que
    antes de esta spec, `Config_RIO_Preferida_Fisica=False`.
  - Caso `ACTIVAR_PREFERENCIA_CONFIG_FISICA=0`: comportamiento idéntico
    al de antes de esta spec (interruptor apagado = sin cambios).
  - Caso donde el candidato físico está fuera de la ventana (más allá
    de `±ventana_cuartos_hora*15` min): no debe usarse, la fila queda
    intacta.
  - Regresión: un ciclo cuyo `Configuracion RIO` ya coincide con la
    física desde el cruce maestro no cambia de valor (no hay nada que
    "mejorar").
- Si hay datos reales disponibles en el entorno de implementación,
  correr contra junio 2026 completo y reportar en la respuesta:
  - Cuántos ciclos activaron `Config_RIO_Preferida_Fisica_Partida`/
    `_Detencion` (se espera algo cercano a 43 y 15 respectivamente) y el
    nuevo `Total SC_PD` del mes (se espera que suba, ya que estos
    ciclos hoy están mal tarifados — reportar el delta exacto).
  - Confirmar que `NUEVARENCA_TG1+TV1&1` queda con
    `Config_RIO_Preferida_Fisica_Detencion=False` y su
    `Costo_Detencion_Efectivo` sin cambios.
  - Confirmar que `KELAR-TG12&7` queda con
    `Config_RIO_Usada_Partida='KELAR-TG1_TG1_DIESEL'` (la config simple,
    no la combinada).
- `pytest -q -m ""` sigue en verde.

## Qué NO hacer en esta spec

- No modificar `CONSIGNAS`, `MOTIVO`, `ESTADO OPERACIONAL`,
  `COMENTARIO`, ni ningún `Filtro_Conf/Disp/Op_Partida/Detencion` — solo
  `Configuracion RIO`/`Fuente_Config_RIO` (y por herencia,
  `Config_RIO_Usada_Partida/Detencion` y lo que se calcula desde ahí).
- No tocar `rescatar_config_rio_en_limites` ni la búsqueda relajada de
  filtros existentes — son funciones separadas, este es un paso nuevo
  adicional.
- No forzar ningún resultado cuando no hay coincidencia física en la
  ventana (caso NUEVARENCA) — el fallback al comportamiento actual es
  intencional, no un caso a "resolver" en esta spec.
- No cambiar el default de `VENTANA_CUARTOS_HORA` (sigue en `2`, ±30
  min) — esta spec reutiliza el mismo valor que ya existe.
- No tocar `USAR_CONFIG_DOMINANTE`, `USAR_TARIFA_RIO_INSTRUIDA`,
  `REGLA_EXENCION`, `TOLERANCIA_CORTES_BLOQUES`, `CODIGOS_EO_VALIDOS`.
