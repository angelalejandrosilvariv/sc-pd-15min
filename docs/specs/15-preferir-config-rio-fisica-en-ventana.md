# Spec 15 — Corregir la mezcla de configuraciones hermanas en el cruce RIO

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `tests/`
**⚠️ Esta spec SÍ cambia montos facturados** (`Costo_Partida_Efectivo`,
`Costo_Detencion_Efectivo`, `Total SC_PD` de los ciclos afectados) — no
es aditiva como las specs 12-14. Revisar con cuidado antes de aplicar.

## Contexto

**Nota:** esta es una revisión de la versión anterior de esta spec. La
primera versión proponía "preferir la configuración que físicamente
generó" — el dueño del proyecto la rechazó correctamente: el criterio
regulatorio del CEN es que se cobre lo que dice el RIO, no lo que
físicamente ocurrió. Investigando más a fondo el porqué del desajuste,
encontramos que el problema real es otro, y esta versión lo corrige sin
apartarse de "cobrar lo que dice RIO".

**El problema real:** el cruce maestro (`merge_asof` en `main()`, sección
10) empareja por `Central_Relacionada` — es decir, mezcla en una sola
bolsa **todas las sub-configuraciones** de una central (ej.
`KELAR-TG1_TG1_DIESEL` la turbina sola, y `KELAR-TG1_TG1+0.5TV_DIESEL`
la turbina combinada con la de vapor son, para el cruce, la misma
entidad). Pero el propio documento del CEN ("Reglas para Establecer los
Registros de Instrucciones Operacionales") define que las instrucciones
se registran **por configuración** — cada una es una entidad separada
con su propio historial de `PP`/`PMT`/`MT`/`PS`/`FS`. Mezclarlas ya es
apartarse de cómo el RIO registra la información, no una forma de
respetarlo.

**Verificamos la alternativa "solo mirar hacia atrás, pero sin mezclar
configuraciones"** (sin ventana, exactamente la misma filosofía que usa
hoy el cruce maestro, pero restringida a la configuración exacta) contra
los 55 ciclos de junio 2026 donde `Config_RIO_Usada_Partida`/
`Detencion` no coincide con la configuración que físicamente generó:

|  | Antigüedad del registro que se usa **hoy** (mediana) | Antigüedad del registro más reciente **de la config exacta**, mirando solo hacia atrás sin ventana (mediana) |
|---|---|---|
| Partida | 60 min | 984 min (~16 h) |
| Detención | 15 min | 1.402 min (~23 h) |

Es decir: cuando una configuración arranca desde "Fuera de Servicio", no
tiene ningún registro propio reciente — el primer registro que
**confirma esa configuración exacta** normalmente lo anota el CDC unos
minutos **después** de la sincronización física, no antes. Por eso una
búsqueda estrictamente hacia atrás, incluso restringida a la
configuración correcta, casi nunca encuentra nada útil cerca (mediana de
16-23 horas de antigüedad — claramente un registro viejo e irrelevante,
de un evento anterior no relacionado).

**Conclusión:** el fallo no es "mirar hacia atrás" en sí — es cruzar
**sin distinguir configuraciones**. La corrección correcta es restringir
el cruce a la configuración exacta (leyendo el RIO tal como el CEN lo
registra, por configuración) y, dentro de esa configuración exacta,
usar el registro más cercano en el tiempo dentro de una ventana chica
(±`VENTANA_CUARTOS_HORA`, la misma que ya existe) — sin esto, no hay
forma de encontrar el registro que confirma el arranque, porque por
construcción llega después. Esto sigue siendo "cobrar lo que dice RIO"
— solo que del RIO de la configuración que corresponde, no el de una
config hermana.

**Ejemplo real** (`KELAR-TG12&7`, Inicio_Ciclo 2026-06-26 23:00):
`Secuencia_RIO_Partida` = `"-22min PP/OM/KELAR-TG1_TG1+0.5TV_DIESEL;
+1min PMT/OM/KELAR-TG1_TG1_DIESEL"`. Hoy el motor usa el registro de
-22min (`KELAR-TG1_TG1+0.5TV_DIESEL`, la config combinada) porque es el
más reciente **de cualquier config** de esa relacionada. El registro de
`KELAR-TG1_TG1_DIESEL` (la config que efectivamente generó, confirmada
en el RIO 1 minuto después) es el que corresponde según la disciplina
de "una configuración, un historial propio".

**Caso límite ya identificado** (`NUEVARENCA_TG1+TV1&1`, detención): no
existe ningún registro RIO de la configuración exacta dentro de la
ventana — ahí no hay nada que corregir, se mantiene el comportamiento
actual sin cambios.

## Regla a implementar

Dentro de `±VENTANA_CUARTOS_HORA` cuartos de hora alrededor de
`Inicio_Ciclo_Global` (para partida) o `Termino_Ciclo_Global` (para
detención):

1. De las instrucciones RIO de esa `Central_Relacionada`, filtrar las
   que tengan `NOMBRE CONFIGURACIÓN` **exactamente igual** a la
   configuración de la fila (columna `Central` de esa fila exacta de
   `resumen_relacionada` — es el identificador de configuración que ya
   usa el resto del pipeline, no un dato "físico" ajeno al RIO: es
   simplemente cómo se sabe a qué configuración pertenece cada fila).
2. Si hay una o más: usar la más cercana en tiempo (mismo criterio que
   ya usa `rescatar_config_rio_en_limites` — `diferencias.abs().idxmin()`)
   para reemplazar `Configuracion RIO` y `Fuente_Config_RIO` de esa fila.
3. Si no hay ninguna dentro de la ventana: **no tocar nada** — se
   mantiene exactamente el valor que ya trae `Configuracion RIO` (del
   cruce maestro o del rescate de la spec 08), como en el caso de
   NUEVARENCA.

## Qué construir

### 1. Nueva función en `src/sc_pd_motor_v7.py`

Ubicarla justo después de `rescatar_config_rio_en_limites` (mismo
archivo, mismo estilo de firma):

```python
def corregir_mezcla_configuraciones_rio(resumen, rio_subset, activar, ventana_cuartos_hora):
    """En los limites de ciclo, restringe el registro RIO a la
    configuracion exacta de la fila (columna 'Central'), en vez del
    registro mas reciente de CUALQUIER configuracion de la
    Central_Relacionada (que es lo que hace el cruce maestro, y mezcla
    configuraciones hermanas entre si).

    Dentro de +/- ventana_cuartos_hora, si hay un registro RIO cuyo
    NOMBRE CONFIGURACIÓN coincide exactamente con la configuracion de la
    fila, se usa el mas cercano en tiempo -- aunque el cruce maestro ya
    tuviera algun valor asignado (a diferencia de
    rescatar_config_rio_en_limites, que solo actua si estaba vacio: acá
    puede corregir un valor existente pero mezclado con otra config).

    Solo modifica 'Configuracion RIO' y 'Fuente_Config_RIO'. No toca
    CONSIGNAS/MOTIVO/ESTADO OPERACIONAL/COMENTARIO ni ningun Filtro_*.
    Si no hay ningun registro de la configuracion exacta en la ventana,
    la fila queda intacta (ej. NUEVARENCA_TG1+TV1&1 en junio 2026).
    """
    resultado = resumen.copy()
    resultado['Config_RIO_Corregida_Mezcla'] = False
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
        misma_config = candidatos[candidatos['NOMBRE CONFIGURACIÓN'] == fila['Central']]
        if misma_config.empty:
            continue
        diferencias = (misma_config['FECHA_HORA_RIO'] - fila['FECHA_HORA']).abs()
        dentro = diferencias <= tolerancia
        if not dentro.any():
            continue
        mejor_indice = diferencias[dentro].idxmin()
        mejor = misma_config.loc[mejor_indice]
        resultado.at[indice, 'Configuracion RIO'] = mejor['NOMBRE CONFIGURACIÓN']
        resultado.at[indice, 'Fuente_Config_RIO'] = mejor['FECHA_HORA_RIO']
        resultado.at[indice, 'Config_RIO_Corregida_Mezcla'] = True

    return resultado
```

### 2. Enganchar en `main()`, en el mismo punto donde corre `rescatar_config_rio_en_limites`

Justo **después** de la llamada existente a `rescatar_config_rio_en_limites`
(para que esta corrección pueda operar incluso sobre lo que el rescate
ya haya llenado) y **antes** de `compactar_resumen_ciclos` (para que
`Config_RIO_Usada_Partida`/`Detencion`, y todo lo que se calcula a
partir de ellos — `Tipo_Partida_RIO`, tarifas `_RIO`,
`Costo_Partida_Base`, etc. — reflejen la corrección de forma natural,
sin tocar ningún otro punto del pipeline):

```python
resumen_relacionada = corregir_mezcla_configuraciones_rio(
    resumen_relacionada, rio_subset, ACTIVAR_CORRECCION_MEZCLA_CONFIG_RIO,
    VENTANA_CUARTOS_HORA)
```

Agregar el interruptor nuevo junto a los demás, con **default `1`**
(activo, ya que es la conducta que se decidió aplicar):

```python
ACTIVAR_CORRECCION_MEZCLA_CONFIG_RIO = 1   # 1 = en los limites de ciclo, restringir el
                                             # registro RIO a la configuracion exacta de la
                                             # fila (en vez de mezclarla con configs
                                             # hermanas de la misma Central_Relacionada),
                                             # buscando en +/- VENTANA_CUARTOS_HORA.
```

### 3. Auditoría (mismo estilo que ya existe para `Config_RIO_Rescatada_Ventana_*`)

Después de `compactar_resumen_ciclos`, agregar impresión de auditoría
por tipo (Partida/Detención), contando cuántos ciclos se corrigieron y
el monto `Costo_*_Efectivo` asociado — mismo patrón que las líneas ya
existentes de `Config_RIO_Rescatada_Ventana` y `Diverge_Fuente_RIO`.

### 4. Exportar la columna de auditoría

Agregar `Config_RIO_Corregida_Mezcla_Partida` y
`Config_RIO_Corregida_Mezcla_Detencion` a `columnas_resumen_ciclos()`
(mismo bloque que `Config_RIO_Rescatada_Ventana_Partida`/`Detencion`),
agregando también, en `compactar_resumen_ciclos`, la agregación
correspondiente (primero para partida, último para detención — mismo
patrón que ya usa `Config_RIO_Rescatada_Ventana`).

## Criterio de aceptación

- Tests nuevos cubriendo:
  - Caso base (patrón real de `KELAR-TG12&7`): config combinada con
    `PP` a -22min, config exacta (la de la fila) con `PMT` a +1min —
    debe corregir a la config exacta y quedar
    `Config_RIO_Corregida_Mezcla=True`.
  - Caso sin coincidencia de la configuración exacta en la ventana
    (patrón real de `NUEVARENCA_TG1+TV1&1`): la fila queda
    **exactamente igual** que antes de esta spec,
    `Config_RIO_Corregida_Mezcla=False`.
  - Caso `ACTIVAR_CORRECCION_MEZCLA_CONFIG_RIO=0`: comportamiento
    idéntico al de antes de esta spec (interruptor apagado = sin
    cambios).
  - Caso donde el candidato de la config exacta está fuera de la
    ventana (más allá de `±ventana_cuartos_hora*15` min): no debe
    usarse, la fila queda intacta.
  - Regresión: un ciclo cuyo `Configuracion RIO` ya coincide con la
    configuración exacta desde el cruce maestro no cambia de valor.
- Si hay datos reales disponibles en el entorno de implementación,
  correr contra junio 2026 completo y reportar en la respuesta:
  - Cuántos ciclos activaron `Config_RIO_Corregida_Mezcla_Partida`/
    `_Detencion` (se espera algo cercano a 43 y 15 respectivamente) y el
    nuevo `Total SC_PD` del mes (se espera que suba, ya que estos
    ciclos hoy están tarifados con una configuración hermana en vez de
    la que corresponde — reportar el delta exacto).
  - Confirmar que `NUEVARENCA_TG1+TV1&1` queda con
    `Config_RIO_Corregida_Mezcla_Detencion=False` y su
    `Costo_Detencion_Efectivo` sin cambios.
  - Confirmar que `KELAR-TG12&7` queda con
    `Config_RIO_Usada_Partida='KELAR-TG1_TG1_DIESEL'`.
- `pytest -q -m ""` sigue en verde.

## Qué NO hacer en esta spec

- No modificar `CONSIGNAS`, `MOTIVO`, `ESTADO OPERACIONAL`,
  `COMENTARIO`, ni ningún `Filtro_Conf/Disp/Op_Partida/Detencion` — solo
  `Configuracion RIO`/`Fuente_Config_RIO` (y por herencia,
  `Config_RIO_Usada_Partida/Detencion` y lo que se calcula desde ahí).
- No tocar `rescatar_config_rio_en_limites` ni la búsqueda relajada de
  filtros existentes — son funciones separadas, este es un paso nuevo
  adicional.
- No forzar ningún resultado cuando no hay registro de la configuración
  exacta en la ventana (caso NUEVARENCA) — el fallback al comportamiento
  actual es intencional, no un caso a "resolver" en esta spec.
- No cambiar el default de `VENTANA_CUARTOS_HORA` (sigue en `2`, ±30
  min) — esta spec reutiliza el mismo valor que ya existe.
- No aplicar este cambio al cruce maestro completo (los bloques que no
  son límite de ciclo) — el alcance es específico a
  `Inicio_Ciclo_Global`/`Termino_Ciclo_Global`, igual que
  `rescatar_config_rio_en_limites`. Ampliarlo a todo el pipeline (todos
  los bloques, `Filtro_Conf/Disp/Op` incluidos) es un cambio de alcance
  mucho mayor, fuera de esta spec.
- No tocar `USAR_CONFIG_DOMINANTE`, `USAR_TARIFA_RIO_INSTRUIDA`,
  `REGLA_EXENCION`, `TOLERANCIA_CORTES_BLOQUES`, `CODIGOS_EO_VALIDOS`.
