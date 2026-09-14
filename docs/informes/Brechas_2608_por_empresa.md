# Agosto 2026 — brechas por empresa entre el motor v7 y el Excel horario

**Fecha:** 2026-09-14
**Corrida analizada:** `Reporte_Sobrecostos_PD_Final.xlsx` generado desde la interfaz con el
motor v7, `TARIFA_CONFIGURACION = 'maxima'`, `MARGEN_NETEADO_POR_CICLO = 0`,
`UMBRAL_RUIDO_MWH = 0.5`, empalme con julio (reporte 2607 v2, RIO 07 y costos 07).
**Referencia:** `Sobrecostos_PD_2608 pre.xlsm` (preliminar del CEN), hojas
`Sobrecosto_Ciclo` (liquidación por ciclo) y `Sobrecosto_PD xHyC` (detalle hora-central,
que es donde se ven las fechas de cada ciclo del Excel).

| Total SC P-D agosto | CLP |
|---|---:|
| Excel horario (preliminar) | 957.823.663 |
| Motor v7 tarifa máxima, con julio | **971.292.712 (+1,4%)** |

Se pidió explicar diez empresas. Cada una se cruzó ciclo a ciclo. Las brechas se
reducen a **siete mecanismos**; cinco son defectos del Excel con caso concreto,
dos son decisiones de regla pendientes.

## Resumen

| Empresa | Excel | Motor | Δ | Mecanismos (ver numeración abajo) |
|---|---:|---:|---:|---|
| ENGIE | 112.196.400 | 66.476.785 | **−45.719.615** | (1) partidas fantasma 44,9 MM; filtro RIO en TOCOPILLA −3,3 |
| GMETROPOLITANA | 30.904.611 | 54.942.204 | **+24.037.593** | (2) +19,9; (5) +8,6; (6) +5,0; tarifa/margen −9,4 |
| SGA | 17.148.090 | 31.267.850 | **+14.119.760** | (3) ≈ +11,6; (2) +1,45; (5) +1,44 |
| BE FORESTALES | 9.175.027 | 7.077.431 | −2.097.596 | (4) configuración GN_B fuera del Excel |
| ANTILHUE | 3.852.834 | 4.656.334 | +803.500 | (2) parada de 1 h |
| ENLASA | 1.653.932 | 2.377.955 | +724.022 | (7) política PO del 5-ago |
| COLMITO | 2.820.033 | 3.326.888 | +506.855 | (4) y tarifa del ciclo &1 |
| ELEKTRAGEN | 48.321 | 161.455 | +113.135 | (5) y (4) |
| ENERGIA_SIETE | 51.778 | 15.040 | −36.739 | (4) |
| NUEVA DEGAN | 0 | 9.901 | +9.901 | DEGAN-2_DIESEL no existe en el Excel |

## Los siete mecanismos

### (1) Partidas fantasma por configuración de pruebas — defecto del Excel

MEJILLONES-CTM3 pasa varias veces a la configuración `MEJILLONES-CTM3_TG1+TV1_GNL_P`
(consigna EP en el RIO) y **sigue generando** a 35–55 MW. Esa configuración no existe en
`Sobrecosto_PD xHyC`, así que el Excel ve un hueco de generación, cierra el ciclo y
abre otro con partida nueva.

Lo que el motor ve en cada "hueco" del Excel:

| Hueco del Excel | Configuración que generó | Consigna | Bloques | MWh |
|---|---|---|---:|---:|
| 1-ago 19:30 → 2-ago 02:00 | `_GNL_P` | EP | 26 | 931 |
| 6-ago 16:15 → 21:45 | `TG1_GNL_P` | EP | 23 | 1.268 |
| 17-ago 15:15 → 16:00 | `TG1_GNL_B` | FS/EP | 4 | 17 |
| 26-ago 18:00 → 27-ago 04:45 | `_GNL_P` | EP | 44 | 2.580 |
| 27-ago 16:00 → 28-ago 04:45 | `_GNL_P` | EP | 52 | 2.924 |
| 28-ago 16:30 → 29-ago 04:45 | `_GNL_P` | EP | 50 | 2.847 |

Resultado: el Excel tiene 12 ciclos de MEJILLONES; el motor 6. Ciclos del Excel con
fechas (de `xHyC`) y lo que cobra `Sobrecosto_Ciclo`:

| Excel | Inicio | Fin | SC Excel | Ciclo real (motor) | Observación |
|---|---|---|---:|---|---|
| &1 | 1-ago 03:00 | 1-ago 19:00 | 0 | A: 29-jul 08:30 → 2-ago 21:45 | Margen 591 MM en `Sobrecosto_Ciclo`, 0 en `xHyC` (inconsistencia interna) |
| &2 | 2-ago 02:00 | 2-ago 21:00 | 16.615.917 | A | **Fantasma** |
| &3 | 4-ago 05:00 | 6-ago 00:00 | 16.681.319 | B: idéntico | Coincide con el motor |
| &4 | 6-ago 05:00 | 6-ago 15:00 | 14.252.131 | C: 6-ago 05:00 → 15-ago 08:15 | Partida real |
| &5 | 6-ago 22:00 | 15-ago 08:00 | 16.427.492 | C | **Fantasma** |
| &6 | 17-ago 04:00 | 17-ago 10:00 | 16.407.854 | D: idéntico | Coincide (motor rechaza det. por RIO: 14,2) |
| &7 | 17-ago 15:00 | 17-ago 18:00 | 0 | E: 17-ago 15:15 → 18-ago 21:45 | Ambos rechazan la partida (pruebas / EP) |
| &8 | 18-ago 01:00 | 18-ago 21:00 | 14.231.714 | E | **Fantasma** |
| &9 | 19-ago 04:00 | 26-ago 17:00 | 0 | F: 19-ago 04:15 → 31-ago 23:45 | Margen cubre |
| &10 | 27-ago 05:00 | 27-ago 15:00 | 0 | F | Fantasma, no cobrada |
| &11 | 28-ago 05:00 | 28-ago 16:00 | 14.313.848 | F | **Fantasma** |
| &12 | 29-ago 05:00 | 31-ago 23:00 | traspasa | F | Motor: diferido |

Partidas fantasma cobradas por el Excel: &2, &5, &8, &11 = **61,6 MM**. Contra eso, el
motor cobra el ciclo real A (16,9 MM) que el Excel deja en 0 por su margen inconsistente.
Neto ENGIE en MEJILLONES: −42,5 MM. TOCOPILLA-U16: el Excel paga una detención de
3,27 MM que el motor rechaza porque el RIO no trae motivo OM/PDO/SSCC.

### (2) Paradas cortas invisibles a resolución horaria — decisión de regla

| Central | Parada según 15 min | Bloques en cero | Efecto en el motor |
|---|---|---:|---|
| NUEVARENCA_TG1+TV1 | 13-ago 10:00 → 11:00 | 3 | Nuevo ciclo &4, partida **caliente** 18,6 MM + det 4,0 − margen 2,6 = +19,9 MM |
| ANTILHUE-1_DIESEL | 4-ago 13:30 → 14:45 | 4 | Nuevo ciclo &2: 640.869 + 363.315 = +1,0 MM |
| CORONEL | 14-ago 00:00 → 06:45 | 27 | Nuevo ciclo &11: +1,45 MM (el Excel mantiene &16 abierto sin filas de generación en esas horas) |

En el Excel las horas que contienen esos bloques tienen generación, así que el ciclo es
continuo. El motor aplica la definición vigente (`TOLERANCIA_CORTES_BLOQUES = 0`): toda
interrupción de la generación es una detención y la generación siguiente es una partida.
El caso de CORONEL (6,75 h) es una detención real; los de 45 y 75 minutos son la
pregunta abierta: **¿una salida menor a una hora es una partida tarificable?**

### (3) Detenciones que el Excel no marca — defecto del Excel

CORONEL (SGA) tiene 21 ciclos reales en agosto (el Excel lista 37 porque su macro crea
16 "ciclos" sin ninguna hora con generación, todos en 0). El motor ve los mismos 21 más
el de la parada de 6,75 h. El RIO trae motivo OM en todos los cierres, y el motor paga
las 22 detenciones. El Excel solo marca `Detencion = SI` en 12 y `Partida = SI` en 16.

Ejemplo, cierre del 6-ago (Excel &5 / motor &3):

| Hora | Gen Excel (MWh) | `Detencion` Excel | RIO (motor) |
|---|---:|---|---|
| 17:00 | 24,93 | 0 | MT / OM |
| 18:00 | 24,94 | 0 | MT / OM |
| 19:00 | 2,23 | **0** | PS / OM, luego FS / OM / DRO |

La planta se detuvo a las 19:15 y el Excel no lo registra; se repite en &7, &12, &14,
&21, &27, &33 y otros. Nueve detenciones (≈1,1 MM cada una) y cinco partidas (≈0,35 MM)
omitidas explican ≈ 11,6 MM de los 14,1 MM de SGA. El resto: la parada de 6,75 h del
mecanismo (2) y un ciclo de un bloque (7-ago 03:00, 2,8 MWh) que el Excel anula por
Pruebas y el motor cobra completo (1,44 MM).

### (4) Energía del ciclo fuera del margen — defecto del Excel (ya visto en ATACAMA, junio)

`Sobrecosto_PD xHyC` está indexada por configuración y no contiene todas las
configuraciones de la relacionada. CMPCCORDILLERA (BE FORESTALES) aparece en el Excel
solo como `GN_A` (64 horas) y `GNL_A` (9 horas). El motor además ve `GN_B`:

| Configuración | MWh (motor) | Margen (motor) | ¿En el Excel? |
|---|---:|---:|---|
| CMPCCORDILLERA_GN_A | 1.928 | 11,9 MM | sí |
| CMPCCORDILLERA_GNL_A | 359 | 7,1 MM | sí |
| CMPCCORDILLERA_GN_B | 497 | **51,7 MM** | **no** |

El 12-ago de 18:00 a 23:00 la planta generó 48–50 MW bajo GN_B con CMg alto; el Excel no
tiene esas horas, así que cobra partidas que el ciclo se autocubrió (margen total Excel
12,0 MM contra 70,7 MM del motor). Mismo mecanismo, en montos menores, en COLMITO,
ENERGIA_SIETE y ELEKTRAGEN.

### (5) Lista `Pruebas` vs RIO — decisión de regla

El Excel anula costos cuando la hora-central figura en su hoja `Pruebas`; el motor lo
hace cuando el RIO dice `EP`. Casos donde difieren:

| Ciclo | Excel | Motor | Δ |
|---|---|---|---:|
| NUEVARENCA 16-ago 16:30 (Excel &4) | partida 0 por Pruebas | RIO sin EP: cobra 24,4 MM | +8,6 MM |
| CORONEL 7-ago 03:00 (1 bloque, 2,8 MWh) | 0 por Pruebas | cobra 1,44 MM | +1,4 MM |
| CHILOE_DIESEL 4-ago 16:00 | partida 0 | cobra 83.767 | +0,1 MM |

Es el mismo filtro con fuentes distintas. **Hay que decidir cuál manda** (o exigir que
la lista Pruebas y el RIO coincidan).

### (6) Frontera de julio: la partida se pierde en el Excel — defecto del Excel

Ciclos que arrancaron en julio y cerraron los primeros días de agosto:

| Ciclo | Motor | Excel julio | Excel agosto |
|---|---|---|---|
| NUEVARENCA 26-jul 15:30 → 1-ago 01:30 | partida 26,4 (tibia) + det 4,7 − margen 21,6 = **9,6 MM** | "se traspasa" | solo detención 4,6 MM (sin horas detenidas en el mes no hay partida) |
| MEJILLONES 29-jul 08:30 → 2-ago 21:45 | 16,9 MM | "se traspasa" | &1 con SC 0 (margen inconsistente) |

El Excel de julio traspasa el ciclo y el de agosto no lo puede tarificar porque su
hoja `Gen` solo tiene el mes en curso. La partida no se cobra en ningún mes. El motor la
cobra el mes en que el ciclo cierra (spec 17).

### (7) Política PO de mitad de mes — defecto del Excel

La PO `260805` cambia la tarifa de PENON_DIESEL, TENO_DIESEL y TRAPEN_DIESEL (ENLASA):

| | Hasta 4-ago | Desde 5-ago |
|---|---:|---:|
| Partida_Fria / Detención (USD) | 16,11 | **22,02** |

El Excel muestra `Politica vigente = 260801-1` en las 63 partidas del mes y cobra 14,7 k
CLP por ciclo; el motor cruza cada partida con la política vigente en ese instante
(`merge_asof` sobre `Llave_FHC`) y cobra 20,1 k. Diferencia: 0,7 MM.

## El único término que va contra el motor

NUEVARENCA, ciclo del 2 al 8 de agosto: el Excel cobra 28,5 MM de partida (máximo
entre **todos** los combustibles del ciclo) y acredita 6,9 MM de margen; el motor
cobra 24,6 MM (máximo dentro del combustible instruido, GN_A, spec 25) y acredita
11,8 MM. Δ −9,4 MM. Es la interacción de la regla de combustible de la spec 25 con el
mecanismo (4).

## Qué hacer con esto

1. **Para el CEN**, con caso concreto y fechas: mecanismos (1), (3), (4), (6) y (7).
   Son 61,6 MM de partidas que no ocurrieron (ENGIE), ≈11 MM de detenciones reales no
   cobradas (SGA), margen omitido (BE FORESTALES, ATACAMA en junio), partidas perdidas
   en la frontera y tarifas desactualizadas.
2. **Decisiones internas**: (2) tolerancia a paradas menores a una hora y (5) fuente
   del filtro de pruebas. Ambas caben como interruptor con spec, patrón de la spec 25.

Scripts de este análisis en `docs/informes/scripts_brechas_2608/` (rutas locales
escritas a mano; `xhyc_central.py <patron>` extrae las filas hora-central del Excel para
una central y los demás las cruzan contra `Reporte_Sobrecostos_PD_Final.xlsx`).
