# Spec 08 — Rescatar `Configuracion RIO` cuando el registro llega después del bloque

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `tests/`

## Contexto

Corriendo el motor real contra junio 2026 completo (post spec 07), revisé
los 94 ciclos de partida marcados `"Revisar manualmente: config RIO sin
tarifa"`. Se dividen en dos causas distintas:

- ~26 son ciclos que arrancaron antes del 1 de junio (sin datos de mayo
  cargados en esta prueba) — no son un bug, se resuelven solos cuando se
  cargue el mes anterior.
- **68 tienen un `MOTIVO` real y válido en el RIO** (`OM`, `EP`, `OT`), pero
  aun así `Configuracion RIO` (la que decide qué tarifa cobrar) queda en
  `'Sin_Registro_RIO'`.

La causa: el cruce que fija `Configuracion RIO` (sección 10, línea
~806-810) usa `merge_asof(..., direction='backward', tolerance='24 hours')`
— **solo mira hacia atrás en el tiempo**. Cuando el registro del RIO que
documenta un arranque se escribe unos minutos *después* de que la central
ya estaba generando (el evento físico ocurre, el RIO lo registra un rato
después), ese registro queda invisible para este cruce, aunque exista.

La "búsqueda relajada" existente (sección 14, `ACTIVAR_BUSQUEDA_RELAJADA`,
±`VENTANA_CUARTOS_HORA` cuartos de hora = ±30 min, bidireccional) sí lo
encuentra — por eso el filtro operacional (`MOTIVO`) sale bien — pero esa
búsqueda **nunca actualiza `Configuracion RIO`** (solo toca
`Consigna`/`Motivo`/`Estado_Op`/los tres filtros), así que la tarifa queda
huérfana.

**Medí el desfase real en los 68 casos** (diferencia entre el inicio del
ciclo y el registro RIO más cercano con `MOTIVO` informado):

- 63 de 68 casos: el registro RIO llega *después* del inicio del ciclo.
- Mediana: 5,5 minutos. Percentil 90: 10 minutos. **Máximo observado: 23
  minutos** — dentro de la ventana de ±30 min que el motor ya usa en la
  búsqueda relajada (`VENTANA_CUARTOS_HORA`). No hace falta un parámetro
  nuevo.

## Fix requerido

**Alcance deliberadamente acotado**: esto NO debe tocar el cruce de la
sección 10 en sí (que sigue siendo `backward`/24h para todos los bloques,
usado también por los filtros) ni la búsqueda relajada existente
(`obtener_mejor_rio`, que sigue sin tocar `Configuracion RIO`). Se agrega
un mecanismo **nuevo y separado**, específico para rescatar
`Configuracion RIO` solo en los dos bloques que de verdad importan para el
precio: el de `Inicio_Ciclo_Global` y el de `Termino_Ciclo_Global`.

### Dónde insertarlo

Inmediatamente después de la sección 10 (después de la línea que hace
`resumen_relacionada['COMENTARIO'] = resumen_relacionada['COMENTARIO'].fillna('')`,
~línea 819) y **antes** de la sección 10.1 (que construye `Llave_FHC_RIO` a
partir de `Configuracion RIO` — el rescate debe ocurrir antes de eso, para
que el cruce de tarifa de la sección 11.1 ya vea el valor corregido, sin
necesidad de tocar nada más adelante).

### Qué debe hacer

1. Activarlo solo si `ACTIVAR_BUSQUEDA_RELAJADA == 1` (mismo interruptor
   que ya gobierna la idea de "mirar más allá del cruce exacto"; con el
   interruptor apagado, el comportamiento debe quedar idéntico al actual).
2. Identificar las filas de `resumen_relacionada` donde
   `FECHA_HORA == Inicio_Ciclo_Global` **o** `FECHA_HORA ==
   Termino_Ciclo_Global`, y que además tengan
   `Configuracion RIO == 'Sin_Registro_RIO'`. Este conjunto es pequeño
   (del orden de cientos de filas en un mes real, no cientos de miles) —
   no hace falta vectorizar de forma extrema; un bucle acotado a este
   subconjunto ya filtrado es aceptable (a diferencia de `empalmar_reportes`
   en la Fase 1, que sí iteraba sobre el dataset completo).
3. Para cada una de esas filas, buscar en `rio_subset` (la tabla ya
   deduplicada de la sección 10, agrupable por `Central_Relacionada_RIO`)
   el registro más cercano en el tiempo — **en cualquier dirección**, no
   solo hacia atrás — para la misma `Central_Relacionada`, dentro de
   `pd.Timedelta(minutes=VENTANA_CUARTOS_HORA * 15)`.
4. Si se encuentra uno: actualizar, para esa fila específica,
   `Configuracion RIO` con su `NOMBRE CONFIGURACIÓN`, y `Fuente_Config_RIO`
   con su `FECHA_HORA_RIO` (para que la auditoría de divergencia de fuente
   RIO, ya existente, siga siendo consistente con de dónde salió el dato).
   Si no se encuentra nada dentro de la ventana, dejar la fila como está
   (`'Sin_Registro_RIO'`, sigue yendo a revisión manual — eso es correcto,
   no todos los casos tienen que resolverse).
5. Agregar una columna booleana nueva, por ejemplo
   `Config_RIO_Rescatada_Ventana`, en `True` para las filas donde este
   mecanismo efectivamente encontró y aplicó un reemplazo. Debe propagarse
   hasta `df_compacto` (mismo patrón que otras columnas de auditoría:
   `first` para partida, `last` para detención, o el mecanismo que ya use
   el código para llevar campos de `resumen_relacionada` a `df_compacto`).
6. Imprimir un resumen (mismo estilo que el resto del motor): cuántos
   bloques de partida y cuántos de detención se rescataron, y el CLP
   efectivo involucrado — mismo patrón que ya existe para
   `Diverge_Fuente_RIO_Partida/Detencion`.

### No modificar

- El `merge_asof` de la sección 10 (sigue `backward`, 24h, para todos los
  bloques).
- `obtener_mejor_rio()` / la búsqueda relajada existente de la sección 14
  (sigue sin tocar `Configuracion RIO`, tal como está documentado en el
  comentario de esa sección — sigue aplicando solo a
  Consigna/Motivo/Estado_Op/filtros).
- Ningún interruptor de negocio.

## Criterio de aceptación

- Test sintético: una central con generación empezando en un bloque
  `FECHA_HORA=T`, y un registro RIO para esa misma central con `MOTIVO`
  informado en `T + 10 minutos` (dentro de la ventana) pero **ningún**
  registro RIO en las 24 horas anteriores a `T`. Verificar que, con
  `ACTIVAR_BUSQUEDA_RELAJADA=1`, `Configuracion RIO` en el bloque `T` deja
  de ser `'Sin_Registro_RIO'` y pasa a ser la configuración del registro
  de `T+10min`, y que el ciclo correspondiente en `df_compacto` ya no cae
  en `Config_RIO_Sin_Tarifa_Partida`.
- Test de regresión: el mismo caso, pero con el registro RIO a
  `T + 45 minutos` (fuera de la ventana de 30 min) — debe seguir en
  `'Sin_Registro_RIO'`, sin cambios.
- Test de regresión: con `ACTIVAR_BUSQUEDA_RELAJADA=0`, el comportamiento
  debe ser idéntico al actual (sin el mecanismo nuevo).
- Correr el motor real contra junio 2026 (si el archivo de datos está
  disponible en el entorno donde se implementa; si no, dejarlo señalado
  como pendiente de validar) y confirmar que el número de ciclos con
  `Config_RIO_Sin_Tarifa_Partida` baja de 89 y que la mayoría de los 68
  casos identificados en esta spec quedan resueltos.
- `pytest -q -m ""` sigue en verde.

## Qué NO hacer en esta spec

- No ampliar la tolerancia del `merge_asof` de la sección 10 de 24h a más
  (no es el problema — el problema es la dirección, no el rango).
- No hacer que la búsqueda relajada existente (`obtener_mejor_rio`)
  también actualice `Configuracion RIO` — mantenerlas como dos mecanismos
  separados, cada uno con su propósito, para no repetir el patrón de "dos
  lógicas de cruce RIO compitiendo" que ya causó problemas antes en este
  proyecto.
- No tocar `CODIGOS_EO_VALIDOS`, `REGLA_EXENCION`, `USAR_CONFIG_DOMINANTE`,
  `USAR_TARIFA_RIO_INSTRUIDA`, `TOLERANCIA_CORTES_BLOQUES`.
