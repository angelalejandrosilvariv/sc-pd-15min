# Spec 13 — Fix hoja `Diagnostico`: falta `Termino_Ciclo` y columnas `_RIO`

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/diagnostico_observaciones.py`, `tests/`

## Contexto

Revisé la implementación de la spec 12 (PR #27,
`src/diagnostico_observaciones.py`) corriéndola contra datos reales de
junio 2026 (el mismo insumo ya usado en revisiones anteriores). El flujo
completo funciona bien — probé la ventana citada textualmente en una
observación real (`TENO_DIESEL`, 04-06-2026 19:38–19:52) y el trazado
reproduce exactamente el patrón esperado ("No aparece en Detalle_15Min:
no fue considerada en ningún ciclo"). También probé un ciclo real que sí
se pagó (`AGUASBLANCAS-AGB_DIESEL&1`) y el trazado devuelve
correctamente sus 10 filas de `Detalle_15Min` y su fila de
`Resumen_Ciclos_PD`.

Encontré dos problemas puntuales en `_diagnostico_ciclos`, la función que
arma la hoja `Diagnostico` (el resumen "en lenguaje llano" pensado para
verse de un vistazo):

### 1. Nombre de columna equivocado: `Fin_Ciclo` no existe

```python
def _diagnostico_ciclos(resumen: pd.DataFrame) -> pd.DataFrame:
    prefijos = (
        "Etiqueta_Relacionada", "Inicio_Ciclo", "Fin_Ciclo", "Tipo_Partida",
        "Obs_Partida", "Obs_Detencion", "Obs_Liquidacion_Final",
    )
    ...
```

La columna real en `Resumen_Ciclos_PD` (ver
`columnas_resumen_ciclos()` en `sc_pd_motor_v7.py`) es
**`Termino_Ciclo`**, no `Fin_Ciclo`. Como el filtro es un simple `in`
sobre la lista de columnas del DataFrame, el nombre equivocado nunca
lanza error — solo hace que la hora de término del ciclo **nunca
aparezca** en la hoja `Diagnostico`. Lo confirmé con la corrida real:
para `AGUASBLANCAS-AGB_DIESEL&1` (ciclo real de 18:45 a 21:00 del
01-06-2026), la hoja `Diagnostico` muestra `Inicio_Ciclo` pero no trae
ninguna columna con la hora de término.

### 2. Faltan las columnas `_RIO` que determinan la tarifa realmente cobrada

Con `USAR_TARIFA_RIO_INSTRUIDA=1` (el interruptor activo en producción,
no se toca en esta spec), la tarifa que efectivamente se cobra la fija la
configuración **instruida por el RIO**, no la "clásica". Eso ya está
documentado en la fórmula completa que trae `Guia_Lectura` del propio
motor:

> *"Cuando USAR_TARIFA_RIO_INSTRUIDA=1, se usan las columnas `_RIO` para
> fijar la tarifa realmente cobrada; `Config_RIO_Usada_Partida` indica la
> configuracion instruida."*

`_diagnostico_ciclos` solo incluye `Tipo_Partida` (la clasificación
"clásica") y ningún campo `_RIO`. Para el caso más común en las
observaciones reales revisadas — donde la generadora dice "esto se
activó por instrucción X del RIO y no se está pagando/se está pagando
mal" — la hoja `Diagnostico` no muestra la evidencia RIO que explica el
monto, aunque esa evidencia sí existe en `Resumen_Ciclos_PD` (la hoja
completa, sin curar). El objetivo de `Diagnostico` es justamente evitar
tener que ir a buscarla ahí a mano.

## Fix requerido

En `src/diagnostico_observaciones.py`, dentro de `_diagnostico_ciclos`,
corregir la tupla de prefijos:

```python
def _diagnostico_ciclos(resumen: pd.DataFrame) -> pd.DataFrame:
    """Presenta exclusivamente campos explicativos ya calculados por el motor."""
    prefijos = (
        "Etiqueta_Relacionada", "Inicio_Ciclo", "Termino_Ciclo",
        "Tipo_Partida", "Tipo_Partida_RIO",
        "Config_RIO_Usada_Partida", "Config_RIO_Usada_Detencion",
        "Detencion_Tarifa", "Detencion_Tarifa_RIO",
        "Obs_Partida", "Obs_Detencion", "Obs_Liquidacion_Final",
    )
    columnas = [
        c for c in resumen.columns
        if c in prefijos or c.startswith("Filtro_")
    ]
    diagnostico = resumen.loc[:, columnas].copy()
    diagnostico.insert(0, "Diagnostico", "Ciclo encontrado en Detalle_15Min; revisar evidencia del motor.")
    return diagnostico
```

Nada más cambia: sigue siendo una selección de columnas **ya existentes**
en `Resumen_Ciclos_PD` (ninguna se calcula ni se deriva) — igual que
pedía la spec 12 originalmente, solo que ahora con el nombre correcto y
con las columnas `_RIO` que faltaban.

## Criterio de aceptación

- Test de regresión: con un `Resumen_Ciclos_PD` sintético que incluya
  `Termino_Ciclo`, `Tipo_Partida_RIO` y `Config_RIO_Usada_Partida`, la
  hoja `Diagnostico` devuelta por `armar_trazado` debe incluir esas tres
  columnas con sus valores intactos.
- Test de regresión: los 5 tests existentes en
  `tests/test_diagnostico_observaciones.py` (spec 12) siguen pasando sin
  modificarlos — en particular
  `test_armar_trazado_conserva_ciclo_mal_atribuido_y_resumen_exacto`,
  que ya verifica una columna de `Diagnostico`.
- Si hay datos reales disponibles en el entorno de implementación,
  repetir la corrida contra `AGUASBLANCAS-AGB_DIESEL&1` (ciclo real de
  junio 2026, `Inicio_Ciclo`=2026-06-01 18:45, `Termino_Ciclo`=2026-06-01
  21:00) y confirmar en la respuesta que la hoja `Diagnostico` ahora
  muestra ambas fechas y `Tipo_Partida_RIO`.
- `pytest -q -m ""` sigue en verde.

## Qué NO hacer en esta spec

- No tocar `main()` en `sc_pd_motor_v7.py` — el cambio de la spec 12 ahí
  ya quedó bien (aditivo, sin romper nada).
- No tocar `coincide_central`, `filtrar_ventana`,
  `centrales_disponibles` ni la lógica de las hojas `RIO`,
  `Reporte_Crudo`, `Detalle_15Min`, `Resumen_Ciclos_PD` del trazado — el
  problema es específico de qué columnas selecciona `_diagnostico_ciclos`
  para la hoja `Diagnostico`.
- No agregar ninguna columna que no exista ya en `Resumen_Ciclos_PD` —
  esta spec es puramente "mostrar lo que falta mostrar", no calcular
  nada nuevo.
- No tocar ningún interruptor de negocio.
