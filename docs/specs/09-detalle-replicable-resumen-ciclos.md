# Spec 09 — `Resumen_Ciclos_PD` debe traer todo lo necesario para replicar el cálculo a mano

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`

## Contexto

El dueño del proyecto pidió: un Excel donde se pueda ver todo lo relativo
a cada ciclo — generación a nivel de 15 minutos, valor USD, margen, costo
de partida, detención, instrucciones RIO, resultado de filtros, etc. — lo
necesario para que una empresa pueda **replicar el cálculo de forma
manual**. Aclaró explícitamente que esto no debe organizarse ni separarse
por empresa — es información de ciclos, punto.

Antes de diseñar algo nuevo, revisé qué exporta el motor hoy
(`RUTA_SALIDA`, hojas `Resumen_Ciclos_PD` y `Detalle_15Min`) contra una
corrida real de junio 2026:

- **`Detalle_15Min` ya tiene 64 columnas** y es prácticamente completa a
  nivel de bloque de 15 minutos: `GENERACION`, `Margen`, `Valor_Dolar`,
  los 4 tramos de tarifa (`Partida_Fria/Tibia/Tibia_2/Caliente`,
  `Detencion`), los 4 umbrales (`Fria_Num1_M`, `Tibia_Num1_O`,
  `Tibia_Num2_N`, `Caliente_Num1_P`), las mismas columnas con sufijo
  `_RIO`, los resultados de los 3 filtros, `Tipo_Partida`/
  `Tipo_Partida_RIO`, `Costo_Partida`/`Costo_Partida_RIO`, y los campos
  crudos del RIO (`CONSIGNAS`, `MOTIVO`, `Configuracion RIO`,
  `ESTADO OPERACIONAL`, `COMENTARIO`). **No hace falta agregarle nada.**

- **`Resumen_Ciclos_PD` (la hoja a nivel de ciclo) solo tiene 30 columnas**
  y llega recortada: el motor sí calcula, para cada ciclo, los umbrales
  usados, las tarifas de cada tramo, y el resultado 0/1 de cada filtro por
  separado — pero esa información se descarta en el paso final de
  exportación (`columnas_finales`, línea ~1657) y solo queda el resultado
  ya consolidado (`Costo_Partida_Efectivo`, `Obs_Partida`). Para
  "replicar a mano" el cálculo de un ciclo específico, hoy hay que ir a
  `Detalle_15Min`, filtrar por `Etiqueta_Relacionada`, y reconstruir a
  ojo cuál fila corresponde al bloque de inicio/término — engorroso y
  propenso a error para alguien fuera del equipo técnico.

**El fix es agregar columnas que el motor ya calcula, no calcular nada
nuevo.**

## Fix requerido

### 1. Agregar campos al `.agg()` que arma `df_compacto` (línea ~1087-1110)

Agregar, dentro del mismo `.agg(...)` existente (mismo patrón `'first'`
para partida, `'last'` para detención — `resumen_relacionada` ya viene
ordenada por `FECHA_HORA` antes de este `groupby`, así que `'first'`
corresponde al bloque de `Inicio_Ciclo_Global` y `'last'` al de
`Termino_Ciclo_Global`, igual que ya hacen `Costo_Partida_Base`/
`Costo_Detencion_Base`):

```python
        Tipo_Partida=('Tipo_Partida', 'first'),
        Fria_Num1_M=('Fria_Num1_M', 'first'),
        Tibia_Num1_O=('Tibia_Num1_O', 'first'),
        Tibia_Num2_N=('Tibia_Num2_N', 'first'),
        Caliente_Num1_P=('Caliente_Num1_P', 'first'),
        Partida_Fria=('Partida_Fria', 'first'),
        Partida_Tibia=('Partida_Tibia', 'first'),
        Partida_Tibia_2=('Partida_Tibia_2', 'first'),
        Partida_Caliente=('Partida_Caliente', 'first'),
        Detencion_Tarifa=('Detencion', 'last'),
```

Y, condicionado a que la columna exista (solo se calcula cuando
`USAR_TARIFA_RIO_INSTRUIDA == 1`, pero el `.agg()` corre siempre —
revisar si hace falta envolver esta parte en el mismo `if` que ya
protege el resto del bloque 11.1, o usar `.get`/comprobar existencia de
columna antes de agregarla al diccionario de `.agg()` para no romper
cuando el interruptor está apagado):

```python
        Tipo_Partida_RIO=('Tipo_Partida_RIO', 'first'),
        Fria_Num1_M_RIO=('Fria_Num1_M_RIO', 'first'),
        Tibia_Num2_N_RIO=('Tibia_Num2_N_RIO', 'first'),
        Caliente_Num1_P_RIO=('Caliente_Num1_P_RIO', 'first'),
        Partida_Fria_RIO=('Partida_Fria_RIO', 'first'),
        Partida_Tibia_RIO=('Partida_Tibia_RIO', 'first'),
        Partida_Tibia_2_RIO=('Partida_Tibia_2_RIO', 'first'),
        Partida_Caliente_RIO=('Partida_Caliente_RIO', 'first'),
        Detencion_Tarifa_RIO=('Detencion_RIO', 'last'),
```

(Nota: la columna `Detencion` de `resumen_relacionada` no se puede
renombrar directamente a `Detencion_Tarifa` dentro del `.agg()` con la
sintaxis `named_agg=('columna_origen', 'funcion')` — sí se puede, el
primer elemento de la tupla es el nombre de columna origen y el nombre a
la izquierda del `=` es el nombre nuevo; verificar que no choque con
ninguna columna ya existente en `df_compacto` antes de nombrarla así.)

### 2. Agregar las columnas a `columnas_finales` (línea ~1657-1670)

Agregar a la lista base (no solo las nuevas del punto 1, también las que
**ya existían en `df_compacto` pero nunca llegaban a exportarse**):

```python
        'Tipo_Partida',
        'Filtro_Conf_Partida', 'Filtro_Disp_Partida', 'Filtro_Op_Partida', 'Filtro_CostoCero_Partida',
        'Costo_Partida_Base',
        'Fria_Num1_M', 'Tibia_Num1_O', 'Tibia_Num2_N', 'Caliente_Num1_P',
        'Partida_Fria', 'Partida_Tibia', 'Partida_Tibia_2', 'Partida_Caliente',
        'Filtro_Conf_Detencion', 'Filtro_Disp_Detencion', 'Filtro_Op_Detencion', 'Filtro_CostoCero_Detencion',
        'Costo_Detencion_Base', 'Detencion_Tarifa',
```

Y, dentro del bloque `if USAR_TARIFA_RIO_INSTRUIDA == 1:` que ya agrega
`Config_RIO_Usada_Partida`/`Config_RIO_Usada_Detencion` (línea ~1668),
agregar también:

```python
        'Tipo_Partida_RIO',
        'Fria_Num1_M_RIO', 'Tibia_Num2_N_RIO', 'Caliente_Num1_P_RIO',
        'Partida_Fria_RIO', 'Partida_Tibia_RIO', 'Partida_Tibia_2_RIO', 'Partida_Caliente_RIO',
        'Detencion_Tarifa_RIO',
```

Ubicar estas columnas nuevas en una posición razonable dentro de la lista
(por ejemplo, agrupadas justo antes de `Costo_Partida_Efectivo`/
`Obs_Partida` y antes de `Costo_Detencion_Efectivo`/`Obs_Detencion`
respectivamente), no al final de todo — para que al abrir la hoja en
Excel las columnas relacionadas queden juntas y sea legible.

### 3. `Detalle_15Min`: no tocar

Ya tiene todo lo necesario a nivel de bloque de 15 minutos. No agregar
columnas ahí ni duplicar la información que ya trae `Resumen_Ciclos_PD`.

### 4. Agregar una hoja nueva `Guia_Lectura` con la fórmula en texto plano

Para que alguien sin contexto técnico pueda usar el archivo, agregar una
hoja nueva (antes de las demás, o al final — donde el patrón de
`hojas = {...}` del bloque de exportación lo haga más simple) con una
tabla de 2 columnas (`Columna`, `Qué significa`) explicando en una línea
cada uno de los campos nuevos de `Resumen_Ciclos_PD`, más una fila final
con la fórmula completa en texto:

```
Total SC_PD = MAX(0, (Costo_Partida_Efectivo + Costo_Detencion_Efectivo) - Margen_Suma_Ciclo)

Costo_Partida_Efectivo = Costo_Partida_Base * Filtro_Conf_Partida * Filtro_Disp_Partida
                          * Filtro_Op_Partida * Filtro_CostoCero_Partida

Costo_Partida_Base se determina por Tipo_Partida:
  Fria      si Horas_Detenida_Ciclo > Fria_Num1_M      -> tarifa Partida_Fria
  Tibia_2   si Horas_Detenida_Ciclo > Tibia_Num2_N      -> tarifa Partida_Tibia_2
  Caliente  si Horas_Detenida_Ciclo < Caliente_Num1_P   -> tarifa Partida_Caliente
  Tibia     en cualquier otro caso                      -> tarifa Partida_Tibia

(Cuando USAR_TARIFA_RIO_INSTRUIDA=1, se usan las columnas _RIO en vez de
las columnas base para fijar la tarifa realmente cobrada; Config_RIO_Usada_Partida
indica qué configuración instruyó el RIO en ese caso.)
```

Puede ser una hoja simple armada con un `pd.DataFrame` fila por fila, sin
necesidad de formato especial más allá de lo que ya hace el resto del
motor al exportar (ancho de columna automático, etc. — reusar el mismo
bloque de formato que ya se aplica a las demás hojas).

## Criterio de aceptación

- Corriendo el motor contra datos reales (si están disponibles en el
  entorno de implementación), `Resumen_Ciclos_PD` debe traer, para al
  menos un ciclo con `Tipo_Partida_RIO == 'Tibia_2'`, todos los valores
  necesarios para que alguien, a mano, multiplique
  `Partida_Tibia_2_RIO * Valor_Dolar-equivalente` (ya en `Costo_Partida_Base`,
  que viene en moneda local) `* Filtro_Conf_Partida * Filtro_Disp_Partida
  * Filtro_Op_Partida * Filtro_CostoCero_Partida` y obtenga exactamente
  `Costo_Partida_Efectivo`.
- Ningún valor de `Costo_Partida_Efectivo`, `Costo_Detencion_Efectivo`,
  `Total SC_PD` ni ninguna otra columna ya existente debe cambiar — esta
  spec solo **agrega** columnas, no debe alterar ningún cálculo.
- Agregar (o extender) un test que arme un `df_compacto` sintético
  pequeño y verifique que las columnas nuevas quedan en el Excel de
  salida con los valores esperados. Si el motor no separa fácilmente la
  construcción de `columnas_finales` de la exportación a disco, un test
  a nivel de las funciones compartidas de `fase1_integridad.py` (si
  aplica) o una prueba de humo que corra `main()` sobre un fixture
  pequeño y lea el Excel resultante es aceptable.
- `pytest -q -m ""` sigue en verde.
- Ningún interruptor de negocio se toca.

## Qué NO hacer en esta spec

- No crear hojas ni archivos separados por empresa — el dueño del
  proyecto confirmó explícitamente que esto es información de ciclos,
  sin asociarla a una empresa.
- No tocar `Detalle_15Min` — ya está completa.
- No cambiar ninguna fórmula de cálculo — esta spec es puramente de
  exportación/transparencia, no debe alterar ningún monto.
