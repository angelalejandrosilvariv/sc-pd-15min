# Spec 06 — El motor debe cobrar el 4º tramo: "Tibia 2"

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar — depende de `docs/specs/05-script-consolidacion-tibia2.md`
  (necesita que `Costos_de_P-D_Consolidado.xlsx` ya traiga `Partida_Tibia_2`)
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `tests/`

## Contexto

El dueño del proyecto confirmó la regla de negocio completa (ver spec 05
para la evidencia en datos reales de `GUACOLDA-3_CAR`):

```
Caliente (< Caliente_Num1_P)
  -> Tibia        (Caliente_Num1_P a Tibia_Num2_N)
  -> Tibia 2      (Tibia_Num2_N a Fria_Num1_M)     <- tramo nuevo, tarifa Partida_Tibia_2
  -> Fria (> Fria_Num1_M)
```

Hoy el motor solo conoce 3 tramos (`Fria`/`Tibia`/`Caliente`), usando
únicamente `Fria_Num1_M` y `Caliente_Num1_P`. Todo lo que cae entre
`Tibia_Num2_N` y `Fria_Num1_M` se cobra hoy a la tarifa de "Tibia" normal
(`Partida_Tibia`), cuando debería cobrarse a `Partida_Tibia_2` — casi
siempre más cara. Para unidades sin un tramo "Tibia 2" real (la inmensa
mayoría, donde `Tibia_Num2_N` es `NaN`), el comportamiento debe quedar
**exactamente igual** que hoy.

## Fix requerido

### 1. Sección 4 (~línea 368): agregar `Partida_Tibia_2` a `cols_costos`

```python
cols_costos = ['Llave_Concatenada', 'Fria_Num1_M', 'Tibia_Num1_O', 'Tibia_Num2_N',
               'Caliente_Num1_P', 'Partida_Fria', 'Partida_Tibia', 'Partida_Tibia_2',
               'Partida_Caliente', 'Detencion']
```

(agrega `'Partida_Tibia_2'` a la lista existente; el resto de la sección 4
no cambia).

### 2. Sección 11 (~línea 921-934): clasificación de 4 tramos, rama clásica

Reemplazar:

```python
    resumen_relacionada['Tipo_Partida'] = np.select(
        [resumen_relacionada['Horas_Detenida_Ciclo'].isna(),
         resumen_relacionada['Horas_Detenida_Ciclo'] > resumen_relacionada['Fria_Num1_M'],
         resumen_relacionada['Horas_Detenida_Ciclo'] < resumen_relacionada['Caliente_Num1_P']],
        ['No_Aplica', 'Fria', 'Caliente'], default='Tibia')

    resumen_relacionada['Costo_Partida'] = pd.to_numeric(pd.Series(np.select(
        [resumen_relacionada['Tipo_Partida'] == 'Fria',
         resumen_relacionada['Tipo_Partida'] == 'Caliente',
         resumen_relacionada['Tipo_Partida'] == 'Tibia'],
        [resumen_relacionada['Partida_Fria'],
         resumen_relacionada['Partida_Caliente'],
         resumen_relacionada['Partida_Tibia']], default=0
    ), index=resumen_relacionada.index), errors='coerce').fillna(0)
```

por:

```python
    # [BUG 9] "Tibia 2": entre Tibia_Num2_N y Fria_Num1_M hay un tramo con
    # tarifa propia (Partida_Tibia_2), no la misma que "Tibia" normal. Para
    # unidades sin ese tramo (Tibia_Num2_N es NaN), la comparacion
    # 'Horas_Detenida_Ciclo > NaN' es siempre False y el comportamiento
    # queda identico al de antes (3 tramos).
    resumen_relacionada['Tipo_Partida'] = np.select(
        [resumen_relacionada['Horas_Detenida_Ciclo'].isna(),
         resumen_relacionada['Horas_Detenida_Ciclo'] > resumen_relacionada['Fria_Num1_M'],
         resumen_relacionada['Horas_Detenida_Ciclo'] > resumen_relacionada['Tibia_Num2_N'],
         resumen_relacionada['Horas_Detenida_Ciclo'] < resumen_relacionada['Caliente_Num1_P']],
        ['No_Aplica', 'Fria', 'Tibia_2', 'Caliente'], default='Tibia')

    resumen_relacionada['Costo_Partida'] = pd.to_numeric(pd.Series(np.select(
        [resumen_relacionada['Tipo_Partida'] == 'Fria',
         resumen_relacionada['Tipo_Partida'] == 'Tibia_2',
         resumen_relacionada['Tipo_Partida'] == 'Caliente',
         resumen_relacionada['Tipo_Partida'] == 'Tibia'],
        [resumen_relacionada['Partida_Fria'],
         resumen_relacionada['Partida_Tibia_2'],
         resumen_relacionada['Partida_Caliente'],
         resumen_relacionada['Partida_Tibia']], default=0
    ), index=resumen_relacionada.index), errors='coerce').fillna(0)
```

Nota el orden de las condiciones en `np.select`: `np.select` usa la
**primera** condición verdadera. Por eso "Fria" va antes que "Tibia_2" —
si ya pasó el umbral de Fria, no debe caer en Tibia_2 aunque también sea
`> Tibia_Num2_N`.

### 3. Sección 11.1 (~línea 959-986): mismo fix para la rama `USAR_TARIFA_RIO_INSTRUIDA`

Este interruptor está **activo por defecto** (`USAR_TARIFA_RIO_INSTRUIDA = 1`),
así que en la práctica es esta rama la que fija el cobro real. Reemplazar:

```python
        cols_tarifa_rio = {'Fria_Num1_M': 'Fria_Num1_M_RIO', 'Caliente_Num1_P': 'Caliente_Num1_P_RIO',
                           'Partida_Fria': 'Partida_Fria_RIO', 'Partida_Tibia': 'Partida_Tibia_RIO',
                           'Partida_Caliente': 'Partida_Caliente_RIO', 'Detencion': 'Detencion_RIO'}
```

por:

```python
        cols_tarifa_rio = {'Fria_Num1_M': 'Fria_Num1_M_RIO', 'Tibia_Num2_N': 'Tibia_Num2_N_RIO',
                           'Caliente_Num1_P': 'Caliente_Num1_P_RIO',
                           'Partida_Fria': 'Partida_Fria_RIO', 'Partida_Tibia': 'Partida_Tibia_RIO',
                           'Partida_Tibia_2': 'Partida_Tibia_2_RIO',
                           'Partida_Caliente': 'Partida_Caliente_RIO', 'Detencion': 'Detencion_RIO'}
```

Y reemplazar:

```python
        resumen_relacionada['Tipo_Partida_RIO'] = np.select(
            [resumen_relacionada['Horas_Detenida_Ciclo'].isna() | resumen_relacionada['Config_RIO_Sin_Tarifa'],
             resumen_relacionada['Horas_Detenida_Ciclo'] > resumen_relacionada['Fria_Num1_M_RIO'],
             resumen_relacionada['Horas_Detenida_Ciclo'] < resumen_relacionada['Caliente_Num1_P_RIO']],
            ['No_Aplica', 'Fria', 'Caliente'], default='Tibia')

        resumen_relacionada['Costo_Partida_RIO'] = pd.to_numeric(pd.Series(np.select(
            [resumen_relacionada['Tipo_Partida_RIO'] == 'Fria',
             resumen_relacionada['Tipo_Partida_RIO'] == 'Caliente',
             resumen_relacionada['Tipo_Partida_RIO'] == 'Tibia'],
            [resumen_relacionada['Partida_Fria_RIO'], resumen_relacionada['Partida_Caliente_RIO'],
             resumen_relacionada['Partida_Tibia_RIO']], default=0
        ), index=resumen_relacionada.index), errors='coerce').fillna(0)
```

por:

```python
        resumen_relacionada['Tipo_Partida_RIO'] = np.select(
            [resumen_relacionada['Horas_Detenida_Ciclo'].isna() | resumen_relacionada['Config_RIO_Sin_Tarifa'],
             resumen_relacionada['Horas_Detenida_Ciclo'] > resumen_relacionada['Fria_Num1_M_RIO'],
             resumen_relacionada['Horas_Detenida_Ciclo'] > resumen_relacionada['Tibia_Num2_N_RIO'],
             resumen_relacionada['Horas_Detenida_Ciclo'] < resumen_relacionada['Caliente_Num1_P_RIO']],
            ['No_Aplica', 'Fria', 'Tibia_2', 'Caliente'], default='Tibia')

        resumen_relacionada['Costo_Partida_RIO'] = pd.to_numeric(pd.Series(np.select(
            [resumen_relacionada['Tipo_Partida_RIO'] == 'Fria',
             resumen_relacionada['Tipo_Partida_RIO'] == 'Tibia_2',
             resumen_relacionada['Tipo_Partida_RIO'] == 'Caliente',
             resumen_relacionada['Tipo_Partida_RIO'] == 'Tibia'],
            [resumen_relacionada['Partida_Fria_RIO'], resumen_relacionada['Partida_Tibia_2_RIO'],
             resumen_relacionada['Partida_Caliente_RIO'], resumen_relacionada['Partida_Tibia_RIO']], default=0
        ), index=resumen_relacionada.index), errors='coerce').fillna(0)
```

`Config_RIO_Sin_Tarifa` (basado en `Fria_Num1_M_RIO.isna()`) no cambia —
sigue siendo un proxy válido de "no hubo cruce con la tabla de tarifas",
sin importar cuántas columnas nuevas se agreguen al merge.

## Documentar en el encabezado del motor

Agregar una entrada `[BUG 9]` al docstring inicial de
`src/sc_pd_motor_v7.py` (mismo formato que BUG 1-8), describiendo: la
columna "Partida Tibia 2" del archivo de políticas PO nunca llegaba al
motor porque el script de consolidación no la leía (spec 05), y el motor
solo clasificaba en 3 tramos en vez de 4, subcobrando el tramo entre
`Tibia_Num2_N` y `Fria_Num1_M`.

## Criterio de aceptación

- **Regresión obligatoria**: para cualquier ciclo donde `Tibia_Num2_N` sea
  `NaN` (la inmensa mayoría de las unidades hoy), `Tipo_Partida` y
  `Costo_Partida` deben dar exactamente igual que antes de este cambio.
  Agregar un test que lo verifique explícitamente.
- Test nuevo que reproduzca el caso `GUACOLDA-3_CAR`: fixture sintético
  con `Fria_Num1_M=144`, `Tibia_Num2_N=72`, `Caliente_Num1_P=24`,
  `Partida_Tibia=30838.528`, `Partida_Tibia_2=31963.694`,
  `Partida_Fria=50050.688`, `Partida_Caliente=18011.61`. Verificar:
  - `Horas_Detenida_Ciclo=100` -> `Tipo_Partida='Tibia_2'`,
    `Costo_Partida=31963.694`.
  - `Horas_Detenida_Ciclo=50` -> `Tipo_Partida='Tibia'`,
    `Costo_Partida=30838.528`.
  - `Horas_Detenida_Ciclo=200` -> `Tipo_Partida='Fria'`.
  - `Horas_Detenida_Ciclo=10` -> `Tipo_Partida='Caliente'`.
- Repetir el mismo test para la rama `Tipo_Partida_RIO`/`Costo_Partida_RIO`
  (con las columnas `_RIO` correspondientes).
- `pytest -q -m ""` sigue en verde.
- Ningún interruptor de negocio (`USAR_CONFIG_DOMINANTE`,
  `USAR_TARIFA_RIO_INSTRUIDA`, `REGLA_EXENCION`, `TOLERANCIA_CORTES_BLOQUES`,
  `CODIGOS_EO_VALIDOS`) se toca.

## Qué NO hacer en esta spec

- No tocar `Costo_Detencion`/`Costo_Detencion_RIO` — la detención no se
  divide en tramos, sigue siendo un único valor por `Llave_Concatenada`.
- No inventar un "Caliente 2" ni ningún otro tramo adicional — la regla
  confirmada tiene exactamente 4 tramos.
- No aplicar esta spec antes que la 05 — sin `Partida_Tibia_2` en
  `Costos_de_P-D_Consolidado.xlsx`, esta columna no existiría al hacer el
  merge y `Costo_Partida` para el tramo `Tibia_2` quedaría en `NaN`.
