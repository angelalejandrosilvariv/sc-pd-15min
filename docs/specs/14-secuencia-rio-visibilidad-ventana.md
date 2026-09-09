# Spec 14 — Mostrar la secuencia completa de instrucciones RIO dentro de la ventana (solo visibilidad)

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py` (función nueva + 2 columnas nuevas en
`Resumen_Ciclos_PD`), `tests/`

## Contexto

Investigando junto con el dueño del proyecto una comparación de junio
2026 (configuración física vs. configuración instruida por el RIO),
encontramos que en **1.796 de 2.068 límites de ciclo** (87%, contando
partida + detención de los 1.034 ciclos del mes) hay **más de una
instrucción RIO** dentro de una ventana de ±30 minutos alrededor de
`Inicio_Ciclo`/`Termino_Ciclo`.

Al revisar el documento oficial del Coordinador ("Reglas para
Establecer los Registros de Instrucciones Operacionales", junio 2023,
sección 6.1), esto tiene una explicación: `PP` (Proceso de Partida) y
`PS` (Proceso de Salida) son **estados transitorios** —

> *"PP: Unidad generadora a la cual se le instruyó iniciar su operación
> estando en estado detenida. El Proceso de Partida corresponde al
> tiempo que transcurre desde la solicitud de partida hasta la
> sincronización al sistema."*
>
> *"PS: Unidad generadora a la cual se le instruyó detenerse. El
> Proceso de Salida corresponde al tiempo transcurrido entre la
> solicitud de retirar la unidad de servicio hasta que esta se
> desconecta del sistema."*

Es decir, los pares más comunes que encontramos (`PP`→`PC`/`MT`/`CI` en
partidas, `PS`→`FS` en detenciones) casi siempre son **las etapas de un
mismo evento de arranque/parada**, no instrucciones independientes en
competencia. Con reportes de 15 minutos, es normal que una transición
que dura pocos minutos (típico en diésel) deje más de un registro RIO
dentro de la misma ventana de ±30 min.

**Decisión tomada con el dueño del proyecto:** por ahora, **no tocar**
qué instrucción determina `Config_RIO_Usada_Partida`/`Detencion` (eso
afecta directamente `Costo_Partida_Efectivo`/`Costo_Detencion_Efectivo`,
es decir, plata real facturada) — primero solo dar **visibilidad** de
toda la secuencia de instrucciones que existió dentro de la ventana,
sin cambiar ningún cálculo. Es un cambio de "qué se ve", no de "qué se
cobra". Un futuro ajuste a la lógica de selección (si se decide hacer)
será una spec aparte.

## Qué construir

### 1. Nueva función en `src/sc_pd_motor_v7.py`

Ubicarla junto a `rescatar_config_rio_en_limites` (misma sección del
archivo, mismo estilo — recibe `rio_subset` ya deduplicado por instante
exacto):

```python
def listar_secuencia_rio_ventana(momentos, rio_subset, ventana_cuartos_hora):
    """
    Para cada fila de `momentos` (columnas: Central_Relacionada, Momento),
    junta TODAS las instrucciones RIO de esa Central_Relacionada dentro de
    +/- ventana_cuartos_hora*15 minutos de Momento, ordenadas
    cronologicamente, y las devuelve como texto legible.

    Formato de salida por fila (vacio "" si no hay ninguna en la ventana):
        "{offset:+d}min {CONSIGNAS}/{MOTIVO}/{NOMBRE CONFIGURACIÓN}; ..."
    donde offset es la diferencia en minutos redondeados entre la
    instruccion y Momento (negativo = antes, positivo = despues).

    No modifica rio_subset ni momentos. Es puramente informativa: no debe
    usarse en ningun lado para decidir Config_RIO_Usada_Partida/Detencion
    ni ningun Costo_*/Filtro_*.
    """
```

Reutilizar el mismo patrón de agrupación por central que ya usa
`rescatar_config_rio_en_limites` (`rio_subset.groupby('Central_Relacionada_RIO')`)
para no repetir un cruce lineal costoso.

### 2. Enganchar en `main()`

Después de que `df_compacto` ya tiene `Inicio_Ciclo`/`Termino_Ciclo`
(mismo punto donde hoy se calculan `Diverge_Fuente_RIO_*` — ver
`sc_pd_motor_v7.py` ~línea 1548 en adelante), agregar:

```python
df_compacto['Secuencia_RIO_Partida'] = listar_secuencia_rio_ventana(
    df_compacto[['Central_Relacionada']].assign(Momento=df_compacto['Inicio_Ciclo']),
    rio_subset, VENTANA_CUARTOS_HORA)

df_compacto['Secuencia_RIO_Detencion'] = listar_secuencia_rio_ventana(
    df_compacto[['Central_Relacionada']].assign(Momento=df_compacto['Termino_Ciclo']),
    rio_subset, VENTANA_CUARTOS_HORA)
```

Usar `VENTANA_CUARTOS_HORA` (la misma variable global que ya existe y
que hoy usan `rescatar_config_rio_en_limites` y la búsqueda relajada —
default `2`, es decir ±30 min) para que la ventana sea consistente y
configurable en un solo lugar, tal como pidió el dueño del proyecto
("la búsqueda debe ser ±N cuartos de hora siempre").

### 3. Exportar las columnas nuevas

Agregar `'Secuencia_RIO_Partida'` y `'Secuencia_RIO_Detencion'` a
`columnas_resumen_ciclos()`, junto a `Config_RIO_Usada_Partida`/
`Config_RIO_Usada_Detencion` (mismo bloque, dentro del `if
usar_tarifa_rio_instruida == 1:`).

Agregar también una fila a `crear_guia_lectura()` explicando ambas
columnas, mismo estilo que las demás filas de esa función — dejando
explícito que son **solo informativas** y no participan del cálculo.

## Criterio de aceptación

- Tests nuevos (en `tests/test_fase1_integridad.py` o un archivo nuevo,
  el implementador decide) cubriendo:
  - Ventana con una sola instrucción: la columna trae exactamente esa
    instrucción, sin "; " de más.
  - Ventana con varias instrucciones (ej. sintético replicando el caso
    real `PP` a -7min y `PC` a +5min): la columna trae ambas, en orden
    cronológico, con el offset correcto en minutos y signo correcto.
  - Ventana sin ninguna instrucción: la columna queda `""` (no `NaN`,
    no error).
  - Confirmar que `Config_RIO_Usada_Partida`, `Config_RIO_Usada_Detencion`,
    `Costo_Partida_Efectivo`, `Costo_Detencion_Efectivo` y `Total SC_PD`
    quedan **exactamente iguales** antes/después de este cambio (mismo
    test o fixture que ya exista, agregando el aserto) — es la prueba
    central de que esto es aditivo puro.
- Si hay datos reales disponibles en el entorno de implementación,
  correr contra junio 2026 y confirmar en la respuesta que
  `AGUASBLANCAS-AGB_DIESEL&1` (`Etiqueta_Relacionada`), columna
  `Secuencia_RIO_Partida`, muestra algo equivalente a
  `"-7min PP/OM/AGUASBLANCAS-AGB_DIESEL; +5min PC/OM/AGUASBLANCAS-AGB_DIESEL"`
  (ajustar formato exacto si difiere levemente, lo importante es que
  aparezcan ambos registros en orden).
- `pytest -q -m ""` sigue en verde.

## Qué NO hacer en esta spec

- No cambiar `Config_RIO_Usada_Partida`, `Config_RIO_Usada_Detencion`,
  ni ningún `Costo_*_Efectivo`/`Filtro_*`/`Total SC_PD` — esta spec es
  estrictamente aditiva/informativa.
- No usar `Secuencia_RIO_Partida`/`Secuencia_RIO_Detencion` en ningún
  cálculo dentro de esta spec — son para lectura humana únicamente.
- No tocar `rescatar_config_rio_en_limites` ni la búsqueda relajada
  existente — es una función nueva, independiente.
- No tocar ningún interruptor de negocio.
- No decidir todavía una regla de "cuál instrucción usar para cobrar"
  cuando hay varias en la ventana — eso queda pendiente para una spec
  futura, una vez que se revisen ejemplos reales con esta nueva
  visibilidad.
