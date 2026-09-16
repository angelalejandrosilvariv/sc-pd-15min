# 25 — Interruptor: tarifa de la configuración más cara del ciclo

**Toca código:** sí (`src/sc_pd_motor_v7.py`, `Carpeta_de_Trabajo/correr_motor.py`,
`Carpeta_de_Trabajo/interfaz.py`, `tests/test_tarifa_configuracion_maxima.py`)

**Cambia el monto liquidado:** sí. A diferencia de la spec 23, este interruptor nace
**encendido** (`TARIFA_CONFIGURACION = 'maxima'`) por decisión del 14-09-2026:
*"usaremos la más cara presente en el ciclo"*. `'instruida'` conserva el
comportamiento previo (spec 15) para comparaciones.

**Estado:** implementado, activo por defecto, con la alternativa disponible en el
panel, el runner y la interfaz.

---

## 1. El problema que resuelve

Cuando una central relacionada pasa por más de una configuración dentro de un
mismo ciclo (turbina sola → ciclo combinado, cambio de combustible, sub-unidades
que entran y salen), hay que decidir **qué tarifa de partida/detención cobra el
ciclo**. La base de costos tarifa por configuración y el spread entre
configuraciones hermanas llega a 57x (KELAR: 1.663 USD la turbina sola contra
94.034 el ciclo combinado completo).

Hasta la spec 24 el motor cobraba la tarifa de la configuración que **el RIO
instruyó** en la apertura/cierre del ciclo (`USAR_TARIFA_RIO_INSTRUIDA = 1`,
sección 14.1b). El modelo horario cobra la **más cara** que apareció en el ciclo:

```
Sobrecosto_PD xHyC!U     = tarifa_por_tramo(config, hora) × Z × AE × AG
PARTIDAS_DETENCIONES!S   = MAXIFS(xHyC!U, ciclo_relacionada, partida = "SI") × filtro_operacional
```

El experimento controlado (bitácora 2026-09-10, "Motor sobre dato horario")
demostró que esta única diferencia de regla explica la mayor parte de la brecha
entre ambos modelos: alimentando el v7 con el propio reporte horario, el 94,8% de
la brecha persiste, y el barrido de variantes mostró que ninguna otra regla mueve
cientos de millones.

## 2. La regla implementada

Por ciclo y por tipo (partida, detención):

1. Cada bloque de 15 min trae `Costo_Partida_ML` / `Costo_Detencion_ML`
   valorizados con la tarifa de **su propia configuración** y el tramo
   (Fría/Tibia/Caliente) del ciclo. Esto ya existía; el motor lo calculaba y lo
   descartaba al quedarse con el primer/último bloque.
2. Compiten solo los bloques que pasan dos filtros:
   - **Costo_Cero**: una configuración COGEN o con `Costo_Cero = SI` no puede
     ganar el máximo con una tarifa que luego se anularía.
   - **Combustible instruido**: si el RIO instruyó una configuración en la
     apertura (cierre) del ciclo, solo compiten las configuraciones con el mismo
     combustible (lo que sigue a `_GN…` / `_DIESEL`). Es la columna `AG` del
     horario, que multiplica a `U` antes del `MAXIFS`. Sin instrucción, compiten
     todas. Sin este filtro, NUEVARENCA&1 cobraba 66,6 MM (tarifa DIESEL) con el
     RIO instruyendo `GN_A` (18,1 MM).
3. Gana el bloque de mayor tarifa. Empate → el cronológicamente primero, así un
   ciclo con una sola configuración queda idéntico a `'instruida'`.
4. Viajan con la tarifa ganadora sus umbrales, su tramo y su filtro de
   Costo_Cero (`_CAMPOS_TARIFA_PARTIDA` / `_CAMPOS_TARIFA_DETENCION`), para que
   la fila exportada sea auditable con los datos de **esa** configuración.
5. Si el filtro de combustible deja fuera a **todas** las configuraciones con
   tarifa, el ciclo queda en 0 (igual que el horario) y se marca
   `Excluida_Combustible_Partida/Detencion = True` con observación propia. En
   2606 y 2608: 0 ciclos.

**Lo que NO cambia:** los filtros RIO (EP, motivo/SSCC, exención), el margen, la
detección de ciclos, el diferimiento y el traspaso. Bajo `'maxima'` el RIO sigue
decidiendo **si** se paga; deja de decidir **cuánto**.

## 3. Impacto medido

Corridas completas con el interruptor real (no el monkeypatch del experimento
previo), 2606 con empalme de mayo y 2608 sin julio.

| | Excel horario | v7 `'instruida'` | v7 `'maxima'` |
|---|---:|---:|---:|
| **2606** total | 1.028.628.659 | 823.168.889 (−20,0%) | **1.080.340.995 (+5,0%)** |
| 2606 Σ\|Δ\| por empresa | — | 255.292.186 | **133.703.770** |
| **2608** total | 957.823.663 | 536.027.769 (−44,0%) | **875.313.107 (−8,6%)** |
| 2608 Σ\|Δ\| por empresa | — | 489.242.385 | **151.369.636** |

- 2606: 141 de 1.224 ciclos tienen más de una configuración; +909,7 MM en
  partida y +207,0 MM en detención respecto de la tarifa instruida.
- 2608: 77 de 461 ciclos; +642,4 MM / +102,8 MM.
- 73 (2606) y 58 (2608) ciclos cuya configuración instruida no tiene tarifa
  quedaban en "revisar manualmente" bajo `'instruida'`; bajo `'maxima'` cobran.

Por empresa, 2606: ENGIE −6,3 MM (era −73,4), TAMAKAYA +14,2 MM (era −97,8),
ENEL +53,5 MM (era −14,2), COLBUN −22,4 MM (era −32,6). 2608: ENEL −7,6 MM (era
−293,0), ENGIE −60,4 MM (era −97,7), COLBUN −26,2 MM (era −42,1).

Las brechas que quedan tienen causas ya identificadas y ajenas a esta regla:
COLBUN (membresía de bloques en el margen), ENGIE 2608 (filtro EP y diferimiento
de ciclos abiertos), SGA (resolución 15 min), ENEL 2606 (energía que el Excel
deja fuera del margen de ATACAMA, ver bitácora 2026-09-10).

## 4. Implementación

**a) Panel** — `TARIFA_CONFIGURACION = 'maxima'` junto a
`USAR_TARIFA_RIO_INSTRUIDA`; valores válidos en `TARIFAS_CONFIGURACION_VALIDAS`,
cualquier otro aborta con mensaje.

**b) `combustible_configuracion(serie)`** — combustible de una configuración con
el mismo criterio del horario (DIESEL es un combustible, no solo `_GN`).

**c) `tarifa_configuracion_maxima(resumen_relacionada, compacto)`** — aplica la
regla sobre el detalle por bloque y reemplaza en el compacto la tarifa base, sus
campos asociados y agrega `Config_Tarifa_Partida/Detencion`, `Configs_En_Ciclo`,
`Excluida_Combustible_*`. Guarda la tarifa del primer/último bloque en
`Costo_*_Base_Original`.

**d) `compactar_resumen_ciclos(..., tarifa_configuracion='instruida')`** — llama
a (c) cuando es `'maxima'`. El default de la función sigue siendo `'instruida'`
para que las pruebas anteriores no cambien.

**e) Sección 14.1b** — con `'maxima'` deja de reemplazar la tarifa base por la
instruida; conserva `Config_RIO_Usada_*` y guarda lo que habría cobrado la
instruida en `Costo_*_RIO_Instruida`, para medir la regla ciclo a ciclo.
`Config_RIO_Sin_Tarifa_*` deja de bloquear el cobro.

**f) Sección 14.1 (configuración dominante)** — se ignora bajo `'maxima'`, con
aviso en consola: la tarifa ya no depende de qué configuración dominó.

**g) Consola** — bloque `TARIFA POR CONFIGURACION` con ciclos multi-configuración,
impacto bruto, top 10 y ciclos excluidos por combustible.

**h) Export** — `columnas_resumen_ciclos(..., tarifa_configuracion)` inserta las
columnas de auditoría; `Guia_Lectura` las explica.

**i) `correr_motor.py` e `interfaz.py`** — el interruptor es visible y editable
(radio "Tarifa del ciclo (solo motor v7)"). El motor Turbina (spec 24) mantiene
su propia lógica de atribución y no lo usa.

## 5. Pruebas

`tests/test_tarifa_configuracion_maxima.py`, 16 casos: default idéntico al
comportamiento previo; valor inválido aborta; la tarifa más cara gana aunque dure
un bloque; arrastra los umbrales de la ganadora; una sola configuración ≡
`'instruida'`; COGEN no gana; el combustible instruido restringe las candidatas;
sin instrucción compiten todas; ciclo sin candidata queda en 0 y marcado; se
decide ciclo a ciclo; el resto del compacto no se altera; columnas de export en
su lugar y ausentes bajo `'instruida'`.

Suite completa: **87 pruebas**.

## 6. Pendientes que esta spec NO resuelve

1. **La spec 15 sigue vigente como argumento.** Cobrar la configuración más cara
   contradice la lectura "el CEN instruye por configuración" que motivó
   `USAR_TARIFA_RIO_INSTRUIDA`. La decisión de negocio fue alinear la regla con
   el horario; el interruptor deja ambas lecturas corribles para cuando se
   discuta con el CEN. Los 24 ciclos contestables identificados en la bitácora
   (47,9 MM) siguen siendo el caso concreto para esa conversación.
2. **El combustible instruido sale de la apertura/cierre**, no de la instrucción
   PP/PMT como en el horario (`Instrucciones RIO!U`). En 2606 y 2608 ningún ciclo
   quedó excluido, así que la diferencia es hoy inerte; si aparece un caso,
   `Excluida_Combustible_*` lo delata.
3. **El motor Turbina no aplica esta regla**: su unidad de ciclo es la máquina y
   la mezcla de configuraciones se resuelve con `ATRIBUCION_TARIFA_TURBINA`.

## 7. Erratum 16-09-2026 — valorización al dólar del extremo

La implementación original comparaba las candidatas por `Costo_Partida_ML` del bloque,
es decir tarifa USD × dólar **de ese bloque**, y tomaba el máximo. En un ciclo de varios
días eso hacía ganar al bloque del dólar más alto, no a la configuración más cara, y
valorizaba la partida a un dólar distinto del de su fecha (hasta +2,7% en GUACOLDA-4,
julio→agosto). Detectado al construir el paquete de auditoría (spec 31): el `MAXIFS` de
la hoja `Candidatas` no reproducía `Costo_Partida_Base` en 36 ciclos.

Corrección (`tarifa_valorizada_al_extremo()`): cada candidata se valoriza como tarifa
USD de su configuración × dólar del **bloque de apertura** (partida) o **de cierre**
(detención); la ganadora fija `Costo_*_Base` con ese valor. Sin `Costo_*`/`Valor_Dolar`
en el detalle (pruebas sintéticas) se conserva `Costo_*_ML`. Impacto: 2608 con julio
941.327.164 → **939.959.962** (−1,37 MM, 30 ciclos); 2606 con mayo 1.065.936.984 →
**1.065.608.599** (−0,33 MM). La vista `candidatas_tarifa_configuracion()` usa la misma
valorización, por lo que el `MAXIFS` del libro reproduce la tarifa base en todos los
ciclos no diferidos.
