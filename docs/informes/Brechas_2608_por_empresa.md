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

---

## Réplica con el Excel corregido (`Sobrecostos_PD_2608 pre fixed.xlsm`, 15-09-2026)

Mismo cruce, misma salida del motor, contra la versión corregida del Excel.

**Qué cambió en el Excel.** Solo dos centrales; el resto de `Sobrecosto_Ciclo` es
idéntico peso a peso:

| Central | Original | Corregido | Qué se arregló |
|---|---:|---:|---|
| MEJILLONES-CTM3_TG1+TV1 | 12 ciclos, SC 108.930.275 | **6 ciclos, SC 49.519.666** | `xHyC` ahora incluye la configuración `_GNL_P` (656 filas vs 599): los ciclos coinciden uno a uno con los del motor. Mecanismo (1) resuelto. |
| CMPCCORDILLERA | margen 12.007.920, SC 9.175.027 | **margen 61.458.014, SC 8.320.906** | `xHyC` ahora incluye `GN_B` (17 horas): el ciclo del 12-ago acredita 45,3 MM de margen (motor 43,9). Mecanismo (4) resuelto para esta central. |

Total del Excel sin traspasos: 957.823.663 → **897.558.934**. Motor: 971.292.712 (+8,2%).
Suma de |Δ| por empresa: 174,4 MM → **141,6 MM**.

**Las diez empresas contra el Excel corregido:**

| Empresa | Excel corregido | Motor | Δ | Qué queda |
|---|---:|---:|---:|---|
| ENGIE | 52.785.791 | 66.476.785 | **+13.690.993** | (6) frontera: ciclo 29-jul → 2-ago, motor cobra partida+det 16,9 MM, Excel 0; TOCOPILLA det 3,3 MM que el motor rechaza por RIO; det de MEJILLONES &4/&5 cruzadas entre RIO y Pruebas (se compensan) |
| GMETROPOLITANA | 30.904.611 | 54.942.204 | +24.037.593 | sin cambio: (2) +19,9, (5) +8,6, (6) +5,0, tarifa/margen −9,4 |
| SGA | 17.148.090 | 31.267.850 | +14.119.760 | sin cambio: (3) detenciones no marcadas en CORONEL |
| BE FORESTALES | 8.320.906 | 7.077.431 | −1.243.475 | (4) resuelto. Queda: &13 tarifa Excel 1,09 MM (máximo entre GN_A y GN_B) vs motor 0,71 (GN_A instruido, spec 25); margen de ciclos cortos truncado por hora (Excel 0) vs por bloque (motor 80–210 k); det &2 no marcada; det &14 rechazada por RIO |
| ANTILHUE | 3.852.834 | 4.656.334 | +803.500 | sin cambio: (2) |
| ENLASA | 1.653.932 | 2.377.955 | +724.022 | sin cambio: (7) PO del 5-ago sigue sin aplicarse |
| COLMITO | 2.820.033 | 3.326.888 | +506.855 | sin cambio |
| ELEKTRAGEN | 48.321 | 161.455 | +113.135 | sin cambio |
| ENERGIA_SIETE | 51.778 | 15.040 | −36.739 | sin cambio |
| NUEVA DEGAN | 0 | 9.901 | +9.901 | sin cambio: DEGAN-2 sigue sin existir en el Excel |

**Lectura.** La corrección confirma el diagnóstico: al agregar las configuraciones que
faltaban en `xHyC`, el Excel converge al motor exactamente en los dos mecanismos que
se le atribuían (partidas fantasma y energía fuera del margen). Los otros cinco
mecanismos siguen intactos porque no se tocaron: detenciones no marcadas (3),
frontera (6), PO de mitad de mes (7), y las dos decisiones abiertas (2) y (5).

Un hallazgo nuevo, menor, en CMPCCORDILLERA: en ciclos cortos el Excel acredita
margen 0 donde el motor acredita 80–210 k CLP. Es la resolución aplicada al
truncamiento: una hora con cuartos positivos y negativos se netea antes de truncar en
el Excel, mientras el motor trunca cuarto a cuarto (`MARGEN_NETEADO_POR_CICLO = 0`).
Ambos aplican "la misma" regla; el resultado depende del tamaño del bloque.

La corrección fue quirúrgica (dos centrales). El mismo mecanismo (4) puede seguir
presente en otras: ENEL_GENERACION no cambió en el Excel corregido (ATACAMA en junio
dejaba fuera el 62% de su energía) y sigue a +29,4 MM del motor.

---

## Segunda ronda (15-09): GUACOLDA y las diferencias porcentuales altas

Tabla completa contra el Excel corregido, ordenada por |Δ| en CLP:

| Empresa | Excel corregido | Motor | Δ | Δ % | Ciclos Excel / motor | Causa |
|---|---:|---:|---:|---:|---|---|
| ENEL_GENERACION | 471.058.535 | 500.476.466 | +29.417.931 | +6% | 85 / 87 | no revisado en detalle en agosto; en junio, (4) ATACAMA |
| GMETROPOLITANA | 30.904.611 | 54.942.204 | +24.037.593 | +78% | 5 / 7 | (2), (5), (6), tarifa/margen |
| SGA | 17.148.090 | 31.267.850 | +14.119.760 | +82% | 44 / 29 | (3) |
| ENGIE | 52.785.791 | 66.476.785 | +13.690.993 | +26% | 7 / 10 | (6b) MEJILLONES &1; TOCOPILLA det por RIO |
| TAMAKAYA_ENERGIA | 87.235.575 | 79.532.813 | −7.702.762 | −9% | 6 / 6 | KELAR &1: Excel paga partida 7,7 MM, RIO sin motivo para el motor |
| GUACOLDA | 5.550.626 | 1.293.821 | −4.256.806 | −77% | 6 / 9 | (8) HUASCO-3 −5,55; (9) GUACOLDA-1 +1,29 |
| COLBUN | 173.447.485 | 175.470.261 | +2.022.776 | +1% | 39 / 28 | — |
| BE FORESTALES | 8.320.906 | 7.077.431 | −1.243.475 | −15% | 14 / 15 | ver réplica |
| EMELDA | 914.180 | 1.727.467 | +813.287 | +89% | 3 / 3 | cruce RIO: cada modelo paga ciclos distintos de 1–2 MWh |
| ANTILHUE | 3.852.834 | 4.656.334 | +803.500 | +21% | 4 / 5 | (2) |
| GM_HOLDINGS | 12.436.418 | 13.193.432 | +757.014 | +6% | 9 / 9 | — |
| ENLASA | 1.653.932 | 2.377.955 | +724.022 | +44% | 61 / 63 | (7) |
| ORAZUL_CHILE | 1.041.872 | 361.250 | −680.622 | −65% | 4 / 4 | (10) YUNGAY sin historia |
| QUICKSTART | 8.474.327 | 8.982.417 | +508.091 | +6% | 39 / 40 | — |
| COLMITO | 2.820.033 | 3.326.888 | +506.855 | +18% | 11 / 11 | (6b) &1 recibe margen de julio; (4) |
| INERSA | 10.922.759 | 11.057.246 | +134.487 | +1% | 30 / 30 | — |
| ELEKTRAGEN | 48.321 | 161.455 | +113.135 | +234% | 3 / 3 | (5), (4) |
| ENERGIA_SIETE | 51.778 | 15.040 | −36.739 | −71% | 15 / 15 | (4) |
| NUEVA DEGAN | 0 | 9.901 | +9.901 | n/a | 0 / 2 | DEGAN-2 no existe en el Excel |
| EMELVA | 5.061 | 0 | −5.061 | −100% | 1 / 1 | (8) |
| ELECTRICA_MOKA, ENORCHILE, ON GROUP, LOS_GUINDOS | | | ≈ 0 | 0% | | idénticos |

**Por qué hay tantos porcentajes altos.** Los % grandes están en empresas con pocos
ciclos y montos chicos, donde un solo ciclo que pasa o no pasa un filtro cambia el total
en 50–200%. En CLP, el 90% de la desviación absoluta está en cinco empresas
(ENEL, GMETROPOLITANA, SGA, ENGIE, TAMAKAYA) y todas tienen mecanismo identificado.
Las diferencias de filtro en ciclos de 1–2 MWh (EMELDA, EMELVA, ELEKTRAGEN, KELAR &1)
son de la misma familia: el Excel busca la instrucción RIO en la hora exacta; el motor
usa la última instrucción vigente (`merge_asof`) y una ventana de ±30 min. Cuando un
ciclo dura 45 minutos, esa diferencia decide si se paga o no.

### GUACOLDA: por qué el motor cobra 1,29 MM

Es una sola detención: **GUACOLDA-1_CAR, 23-ago 00:45 → 09:45**, 309 MWh a 9 MW. La
unidad llevaba 908 horas detenida (desde mediados de julio). Según el RIO:

| Tramo | Consigna / motivo / estado | Filtro del motor |
|---|---|---|
| 00:45 | FS / OT / DF | — |
| 01:00 → 04:45 | **EP / EP / PO** (pruebas) | partida rechazada por EP |
| 05:00 → 08:45 | MT / OM / RO (mínimo técnico, operación) | — |
| 09:00 → 09:45 | PS / OM / RO, luego FS / OM / DRO | detención aprobada (motivo OM) |

El motor rechaza la partida (fue una prueba) y **cobra la detención** porque el RIO la
registra con motivo OM. Margen 0 (CMg < CV toda la mañana).

El Excel ve la misma partida (10,0 MM, fría) y la misma detención (1,16 MM), pero le
suma un **margen de 905,8 MM heredado de julio** vía `Ciclos inconclusos` (columna
"Margen ciclo inconcluso") y liquida 0. Ese margen es de un ciclo de julio que terminó
a mediados de julio; nada tiene que ver con la prueba del 23 de agosto. Ver (6b).

Los otros 4,26 MM de GUACOLDA van al revés: **HUASCO-3**, un ciclo de una hora y 7 MWh el
13-ago con 730 h detenida. El Excel cobra la partida fría de 5,55 MM; el motor la
rechaza porque el RIO no trae motivo. Es el mecanismo (8).

Pregunta de regla que deja GUACOLDA-1: **una partida en pruebas (EP) seguida de una
detención instruida con OM, ¿paga la detención?** Hoy el motor evalúa cada extremo por
separado y la paga.

### (6b) Corrección al mecanismo (6): lo que el Excel hace con los ciclos inconclusos

El mecanismo (6) decía que la partida de un ciclo que cruza la frontera "se pierde en
ambos meses". Es cierto para NUEVARENCA, pero incompleto. `Sobrecosto_Ciclo` tiene dos
columnas, "Total Costos Partida ciclo inconcluso" y "Margen ciclo inconcluso", que
traen desde la hoja `Ciclos inconclusos` (julio) la partida y **todo el margen** del
ciclo que julio marcó como traspasado, y se lo suman al **primer ciclo de agosto (&1)**
de la misma central. En agosto son 22 ciclos, con 127,0 MM de partida y **33.795 MM de
margen** heredados.

Dos problemas:

1. Se pega al `&1` aunque sea otro ciclo físico. GUACOLDA-1: la prueba del 23-ago
   recibe 905,8 MM de margen de un ciclo de julio. MEJILLONES &1 (fixed): 591 MM.
   COLMITO &1: 4,7 MM sobre un ciclo de 45 min y 13 MWh.
2. El margen heredado es el de todo el ciclo de julio, así que **anula cualquier costo
   de agosto** en esa central: de los 22 ciclos con herencia, 21 liquidan 0.

El motor no hereda nada: el ciclo de julio que cierra en agosto se liquida completo en
agosto con su propio margen (spec 17); los ciclos nuevos de agosto se liquidan solos.

### (8) `&1` sin instrucción RIO paga — regla del Excel

`factor_operacional` del Excel paga el primer ciclo del mes (`&1`) aunque no haya
instrucción RIO (regla 6 de `Reglas_Modelo_Horario.md`). El motor exige motivo, salvo
que el ciclo no tenga historia (`REGLA_EXENCION = 'sin_historia'`); con julio empalmado
casi todos tienen historia, así que no exime. Casos: HUASCO-3 (5,55 MM, 1 hora, 7 MWh),
MAITENCILLO (EMELVA, 5 k), EMELDA-1 del 25-ago (0,9 MM, 1 MWh).

### (9) Partida en pruebas con detención OM — decisión de regla

GUACOLDA-1 del 23-ago (arriba). El motor paga la detención (1,29 MM).

### (10) Sin historia con dos meses de datos — mejora pendiente del motor

YUNGAY-1 y YUNGAY-2 (ORAZUL) parten el 18-ago sin haber generado en julio ni en agosto.
`Horas_Detenida_Ciclo` queda nula → `Tipo_Partida = No_Aplica` → partida 0. El Excel
cobra fría (313 k cada una). Con julio empalmado el motor **sabe** que llevan al menos
48 días detenidas; debería usar esa cota inferior (`Inicio_Ciclo − inicio de los datos`)
y clasificar fría cuando ya supera el umbral. Es una mejora del motor, no una regla
nueva; cabe como spec.

---

## Tercera ronda (15-09): solo ciclos que inician y terminan en agosto, sin herencia de julio

Pedido: comparar únicamente los ciclos completos dentro del mes, porque el margen
heredado del Excel no está actualizado. Definición usada:

- **Excel corregido:** ciclos no traspasados que no generaban a la hora 1 del 1-ago.
  SC recalculado desde sus propias columnas, `MAX(0, partida + detención − margen)`,
  **ignorando** "Total Costos Partida ciclo inconcluso" y "Margen ciclo inconcluso".
  366 ciclos.
- **Motor:** `Estado_Ciclo_Mes = 'Inicia y termina este mes'`. 374 ciclos.
- Apareo ciclo a ciclo por central y traslape temporal: 357 pares, 17 ciclos solo en
  el motor, 9 solo en el Excel. Script: `scripts_brechas_2608/solo_mes2.py`;
  detalle en `SoloMes_2608_pares.xlsx` (scratchpad).

| Solo ciclos del mes | Excel corregido (sin herencia) | Motor | Δ |
|---|---:|---:|---:|
| SC P-D | 914.259.268 | 933.074.643 | **+18.815.375 (+2,1%)** |
| Ciclos idénticos al peso | | | **198 de 357 pares** |
| Σ\|Δ\| ciclo a ciclo | | | 207.602.030 |

Los dos modelos, sobre los mismos ciclos y sin arrastre de julio, difieren 2,1% en
total. La desviación bruta por ciclo (207,6 MM) se compensa en gran parte porque los
mecanismos empujan en sentidos opuestos.

### Descomposición por causa (357 pares + no apareados)

| Causa | Ciclos | Δ neto | Δ bruto | Dónde |
|---|---:|---:|---:|---|
| Filtro de partida (uno paga, el otro no) | 10 | +14,7 | 43,7 | ATACAMA-2 &4 y &13 **+28,1** (Excel anula partidas instruidas, ver (11)); KELAR &1 −7,7 y HUASCO-3 −5,6 (regla `&1` del Excel, (8)) |
| Tarifa partida + detención + margen | 11 | −40,3 | 40,3 | SANISIDRO-2 (8 ciclos, −27,4): Excel toma el máximo entre GN_A y GN_B, motor el combustible instruido (spec 25); NUEVARENCA &2 −9,4 |
| Ciclo solo en el motor | 17 | +25,0 | 25,0 | paradas cortas (2): NUEVARENCA 19,9; CORONEL 1,4; ANTILHUE 1,0; QUICKSTART 0,7; ENEL 1,3 |
| Filtro de detención | 17 | +0,4 | 20,6 | SGA +6,6 (Excel no marca, (3)); SANISIDRO-1 &5 −4,5 (FS/OT sin SSCC, motor rechaza); TOCOPILLA −3,3; MEJILLONES ±2,2 |
| Margen | 32 | −19,9 | 19,9 | motor acredita más margen: ENEL −10,1, COLBUN −8,3 (NEHUENCO-2), SGA, BE FORESTALES — truncamiento por bloque vs por hora |
| Filtro partida + filtro detención | 11 | +8,1 | 10,0 | SGA +6,9 (CORONEL), EMELDA +0,8, INERSA +0,4 |
| Tarifa partida + tarifa detención | 56 | +9,4 | 9,4 | NEHUENCO-2 &2 +7,7 (motor toma una configuración que el Excel no considera porque no tiene hora de partida propia); ENLASA +0,5 (7) |
| Filtro partida + margen | 2 | +8,7 | 8,7 | NUEVARENCA &5 +8,6 (lista Pruebas vs RIO, (5)) |
| Otras combinaciones | 19 | +12,7 | 13,4 | tarifa partida sola +3,4 (SANISIDRO-1), tarifa detención −1,5, ciclos solo en Excel −0,7 |
| Idéntico | 198 | 0 | 0 | |

### Por empresa (solo ciclos del mes)

| Empresa | Excel corregido | Motor | Δ | Δ % |
|---|---:|---:|---:|---:|
| ENEL_GENERACION | 486.396.459 | 488.764.728 | +2.368.268 | **0%** |
| COLBUN | 177.903.088 | 175.470.261 | −2.432.827 | −1% |
| TAMAKAYA_ENERGIA | 87.235.575 | 79.532.813 | −7.702.762 | −9% |
| ENGIE | 52.785.791 | 49.552.726 | −3.233.065 | −6% |
| GMETROPOLITANA | 26.273.313 | 45.359.932 | +19.086.619 | +73% |
| SGA | 17.148.090 | 31.267.850 | +14.119.760 | +82% |
| GM_HOLDINGS | 12.436.418 | 13.193.432 | +757.014 | +6% |
| INERSA | 10.922.759 | 11.057.246 | +134.487 | +1% |
| QUICKSTART | 8.474.327 | 8.982.417 | +508.091 | +6% |
| BE FORESTALES | 8.320.906 | 7.077.431 | −1.243.475 | −15% |
| LOS_GUINDOS | 7.374.556 | 7.374.556 | 0 | 0% |
| GUACOLDA | 6.713.243 | 1.293.821 | −5.419.423 | −81% |
| ANTILHUE | 3.852.834 | 4.656.334 | +803.500 | +21% |
| COLMITO | 3.195.520 | 3.326.888 | +131.367 | +4% |
| ENLASA | 1.653.932 | 2.377.955 | +724.022 | +44% |
| ENORCHILE | 1.172.693 | 1.172.693 | 0 | 0% |
| ORAZUL_CHILE | 1.041.872 | 361.250 | −680.622 | −65% |
| EMELDA | 914.180 | 1.727.467 | +813.287 | +89% |
| ELECTRICA_MOKA | 332.526 | 332.423 | −103 | 0% |
| resto (< 200 k) | | | | |

Con el arrastre de julio fuera, **ENEL queda en 0%** (+2,4 MM sobre 486): sus +36 MM
del corte anterior eran herencia. ENGIE y COLBUN quedan dentro del ±6%. Lo que queda
grande es lo mismo de las rondas anteriores: GMETROPOLITANA (paradas cortas y lista
Pruebas) y SGA (detenciones que el Excel no marca).

### (11) El Excel atribuye la instrucción RIO al ciclo equivocado — defecto del Excel

ATACAMA-2, ciclos &4 (17-ago) y &13 (29-ago), 14,0 y 14,1 MM de partida fría cada uno.
El RIO tiene la instrucción de partida **PMT / OM** a las 04:55 (17-ago) y 03:57
(29-ago), diez minutos después del primer bloque con generación. El motor la encuentra
y paga. En la hoja `Instrucciones RIO` del Excel esa fila queda con `Ciclo =
ATACAMA-2TG2AB&0` y `Ciclo Partida siguiente = &1` — no se asocia al ciclo &4 / &13 —
porque el Excel marca la hora de partida de la configuración que fija el `MAXIFS`
(`TG2A+TG2B+TV2`, que entra a las 09:00) y no la de la turbina que arrancó a las 04:45.
Resultado: `factor_operacional = 0`, partida 0, en dos arranques instruidos por el CEN
con motivo OM. Son **28,1 MM** que el Excel deja de cobrar a ENEL.

### Lo que este corte confirma sobre el motor

- **A favor del motor**, con caso concreto: (3) detenciones no marcadas, (11)
  instrucción atribuida al ciclo equivocado, (8) `&1` sin instrucción pagado, (7) PO
  no actualizada, (6b) herencia de julio.
- **Decisiones pendientes** que explican casi todo lo demás: (2) paradas de 45–75
  minutos (+25,0 MM en total), (5) lista Pruebas vs RIO (+8,6), (9) partida EP con
  detención OM (+1,3).
- **Diferencias de regla propias del motor**, ya conocidas: tarifa restringida al
  combustible instruido (spec 25; −27 MM en SANISIDRO-2 contra un Excel que ignora el
  combustible) y margen truncado por bloque (−19,9 MM; a favor de las empresas).

---

## Diagnóstico de causa raíz (15-09): por qué difieren los ciclos completos del mes

Método: sobre los 357 pares + 26 ciclos no apareados de la tercera ronda, la diferencia
de SC de cada ciclo se descompuso **exactamente** en tres efectos por sustitución
secuencial — `SC(P,D,M) = MAX(0, P + D − M)`: efecto partida = `SC(P_motor, D_excel,
M_excel) − SC(P_excel, D_excel, M_excel)`, efecto detención y efecto margen análogos;
los tres suman el ΔSC del ciclo (verificado: Σ efectos = +18.815.375 = ΔSC total). Cada
efecto se asignó a una causa raíz leyendo los internos de ambos modelos: en el Excel
las hojas `Sobrecosto_PD xHyC` (flags `Partida`/`Detencion`, costos U/V, `Disponible`,
`Conf despachada RIO`) y `PARTIDAS_DETENCIONES` (columnas `Instrucción`, `Presta SSCC`,
`Monto Partidas/Detenciones`); en el motor `Obs_Partida/Detencion`, `Config_Tarifa_*`
y `Horas_Detenida_Ciclo`. Script: `scripts_brechas_2608/diagnostico.py`; detalle por
ciclo en `Diagnostico_2608.xlsx` (hoja `Efectos`).

| Causa raíz | Efectos | Neto (CLP) | Bruto (CLP) | Naturaleza |
|---|---:|---:|---:|---|
| **R3** Excel no asocia la instrucción RIO al ciclo (factor operacional 0) | 16 | **+66.411.863** | 66.411.863 | defecto del Excel |
| **R9** Margen: truncamiento por bloque (motor) vs por hora (Excel) | 47 | **−61.420.666** | 61.420.666 | resolución (convexidad) |
| **R6** Tarifa: configuración que fija la tarifa | 47 | +888.793 | 47.328.113 | regla, dos sentidos |
| **R5** Motor rechaza por RIO donde el Excel paga | 13 | −25.296.154 | 25.296.154 | regla: fuente SSCC / `&1` |
| **R1** Parada corta: ciclo que solo existe en el motor | 13 | +24.967.808 | 24.967.808 | resolución, decisión |
| **R2** Excel no marca la detención / partida | 12 | +9.732.238 | 9.732.238 | defecto del Excel |
| **R4** Excel anula por lista Pruebas / combustible | 11 | +4.528.532 | 4.528.532 | fuente distinta, decisión |
| **R8** Motor sin historia (horas nulas → partida 0) | 3 | −888.670 | 888.670 | debilidad del motor |
| **R7** Tarifa: política PO de mitad de mes | 107 | +554.712 | 554.712 | defecto del Excel |
| R1b Ciclo solo en el Excel (apareo) | 3 | −692.449 | 692.449 | resolución |
| **Total** | | **+18.815.375** | 241.850.573 | |

### R3 — el Excel busca la instrucción en la hora-reloj equivocada (+66,4 MM)

Mecanismo, con las celdas: `PARTIDAS_DETENCIONES!Instrucción` se obtiene por
`VLOOKUP` sobre `Instrucciones RIO` con la clave `AAMMDDH + relacionada` de la **hora en
que la configuración que fija el MAXIFS empieza a generar**. La instrucción del CEN se
emite minutos **antes** de la partida y cae en la hora anterior:

| Ciclo | Partida en xHyC (hora clave) | Instrucción RIO (hora) | `Instrucción` que lee el Excel | Partida Excel | Motor |
|---|---|---|---|---:|---:|
| ATACAMA-2 &4 | 17-ago h6 (`2608176`) | PMT/OM 04:55 (h5) | vacío → 0 | 0 | 13.962.570 |
| ATACAMA-2 &13 | 29-ago h10 (`26082910`) | PMT/OM 03:57 (h4) | vacío | 0 | 14.146.812 |
| SANISIDRO-1 &11 | 27-ago h21 | OM 19:30 y 19:56 (h20) | vacío | 0 | 16.101.546 |
| NUEVARENCA &4 | 16-ago h17 | OM 15:00 (h16), 17:01 (h18) | vacío | 0 | 24.441.188 |
| CANDELARIA-1 &6 | 22-ago h3 (`2608223`) | PCP/OM 02:24–02:54 (h3) **y una fila 02:54 con MOTIVO en blanco** | vacío (el VLOOKUP devuelve la fila en blanco) | 0 | 856.658 |

El motor cruza cada bloque con la **última instrucción vigente** (`merge_asof`
backward) y, si falta, busca en ±30 min (`ACTIVAR_BUSQUEDA_RELAJADA`). Son partidas
instruidas con OM que el Excel deja en 0: 52 partidas y 53 detenciones del Excel tienen
`Instrucción` vacía en agosto; 16 de ellas están en ciclos completos apareados y suman
66,4 MM. Corrige la atribución del 14-09: NUEVARENCA &4 es R3, no lista Pruebas.

### R9 — truncar por bloque acredita más margen que truncar por hora (−61,4 MM)

`Margen = MAX(0, CMg − CV) × USD × Gen`. El Excel lo evalúa por hora con el CMg y CV
horarios; el motor por cuarto de hora. Como `MAX(0, ·)` es convexa, la suma de bloques
truncados es **siempre ≥** la hora truncada cuando CMg o CV varían dentro de la hora.
Verificado en SANISIDRO-2 con el reporte 2608_v2: CMg varía dentro de la hora en 293 de
573 horas con generación y CV en 553; el margen del mes es 644,2 MM truncando por bloque
contra 583,5 MM truncando el promedio horario: **+60,6 MM** solo por convexidad
(observado en el cruce: 642 vs 565). Es la única causa de las 47 en que el motor acredita
menos SC en todos los casos salvo uno. No es defecto de nadie: es la resolución actuando
sobre el truncamiento; `MARGEN_NETEADO_POR_CICLO` no lo cambia.

### R6 — qué configuración fija la tarifa (±47,3 MM, neto +0,9)

Ambos cobran "la configuración más cara del ciclo", pero sobre conjuntos distintos:

- **Excel:** `MAXIFS(xHyC!U, ciclo, Partida="SI")` — solo configuraciones que tienen
  **hora de partida propia** dentro del ciclo, sin filtro efectivo de combustible
  (`AF` queda vacío cuando no hay PP/PMT en la hora clave, y entonces `AG = 1`).
- **Motor (spec 25):** toda configuración que **generó** en el ciclo, restringida al
  combustible instruido en la apertura.

Resultado en dos sentidos: SANISIDRO-2 −11,8 MM (Excel toma GN_B con RIO instruyendo
GN_A), NUEVARENCA −4,5; pero SANISIDRO-1 +12,7 y NEHUENCO-2 +4,4 (el motor toma una
configuración `FSTVU`/combinada que generó sin "partir" por sí misma). Neto ≈ 0.

### R5 — el motor rechaza por RIO donde el Excel paga (−25,3 MM)

Dos sub-causas exactas, leídas en `PARTIDAS_DETENCIONES`:

1. **OT + SSCC.** El Excel paga OT si `Presta SSCC = 1`, y esa columna vale 1 en 400 de
   414 partidas: en la práctica **OT siempre paga** (39 partidas y 23 detenciones OT
   pagadas en agosto). El motor exige que el `COMENTARIO` del RIO mencione
   SSCC/CTF/CSF/CPF: rechaza 5 partidas OT (8,4 MM base) y 6 detenciones OT (11,2 MM).
   Casos: KELAR-TG12 &1 −7,7; SANISIDRO-1 &5 −4,5; TOCOPILLA-U16 &2 −3,3.
2. **`&1` sin instrucción.** `IF(AND(RIGHT(N,2)="&1", P=""), 1, 0)`: HUASCO-3 −5,55
   (1 hora, 7 MWh); EMELDA-1 &1 −0,9; MEJILLONES &4 det −2,2.

### R1 — paradas que solo existen a 15 minutos (+25,0 MM)

13 ciclos del motor sin contraparte en el Excel porque la interrupción cabe dentro de
una hora con generación: NUEVARENCA 13-ago 10:00–11:00 (+19,9), CORONEL 6,75 h (+1,4),
ATACAMA-1 (+1,3), ANTILHUE 75 min (+1,0), LLANOSBLANCOS/CHAGUAL/TENOGAS (+1,1). Regla
vigente `TOLERANCIA_CORTES_BLOQUES = 0`; decisión pendiente (2).

### R2, R4, R7, R8 — el resto

- **R2 (+9,7):** la macro del Excel no pone `Detencion = SI` en 8 cierres de CORONEL ni
  `Partida = SI` en 2 (última hora con poca generación); el RIO dice OM.
- **R4 (+4,5):** el Excel anula por su hoja `Pruebas` (`Disponible = 0`) o por
  combustible (`Conf despachada RIO = 0`) donde el RIO no dice EP: EMELDA, CORONEL
  7-ago 03:00, LOSVIENTOS, SANJAVIER.
- **R7 (+0,55):** 107 partidas/detenciones de ENLASA con la tarifa de la PO `260801` en
  vez de la `260805` (16,11 → 22,02 USD).
- **R8 (−0,9):** YUNGAY-1/2 y TENOGAS &1 sin ciclo anterior en dos meses de datos: el
  motor deja `Horas_Detenida_Ciclo` nula y no cobra; debería usar la cota inferior.

### Balance del diagnóstico

| Quién explica la diferencia | Neto |
|---|---:|
| Defectos del Excel (R3 + R2 + R7) | +76,7 MM a favor del motor |
| Resolución 15 min sobre reglas idénticas (R9 + R1 + R1b) | −37,1 MM |
| Reglas distintas por decisión (R5 SSCC/`&1`, R4 Pruebas, R6 configuración) | −19,9 MM |
| Debilidad del motor (R8) | −0,9 MM |
| **Total** | **+18,8 MM** |

Los 18,8 MM netos esconden 241,9 MM brutos que se compensan. Quitando los defectos del
Excel, el motor queda **58 MM por debajo** del Excel en ciclos completos, y esa
diferencia es casi toda resolución (margen por bloque) y la fuente del SSCC.

---

## Cuarta ronda (15-09): motor con specs 27 y 28 vs Excel corregido

Corrida: `main` en `f820455` (tarifa máxima, `VIGENCIA_INSTRUCCION_RIO_MIN = 30`,
`HORAS_SIN_HISTORIA = 'cota_inferior'`, umbral 1,0 MWh), **sin julio** (los archivos de
julio están en `T:` y no se copiaron a local). Excel corregido, sin traspasos.

| | Excel corregido | Motor | Δ |
|---|---:|---:|---:|
| Mes completo | 897.558.934 | **910.213.848** | +12,65 MM (+1,4%) |
| Σ\|Δ\| por empresa, mes completo | | | **49,9 MM** (era 141,6) |
| Solo ciclos del mes, sin herencia | 914.259.268 | **910.213.848** | −4,05 MM (−0,4%) |
| Pares idénticos al peso | | | **210 de 353** (era 198) |

**Advertencia de lectura.** Sin julio, los ciclos que ya generaban a la hora 1 quedan
"sin historia suficiente" y el motor no cobra su partida — exactamente lo que hace el
Excel con los `&1`. Esa coincidencia explica buena parte del acercamiento en el mes
completo (NUEVARENCA &1, SANISIDRO-1 &1, MEJILLONES &1 pagan solo detención, igual que
el Excel) y también el −12,5 MM de COLBUN en ciclos del mes: NEHUENCO-2 &1 (2-ago, cota
44 h) cobra la tarifa TG1 (16,6 MM) porque la cota no alcanza el umbral de 90 h de la
configuración combinada; con julio empalmado tendría sus horas reales y cobraría
26,7 MM. Con julio, esos ciclos vuelven a cobrarse como el 14-09.

**Qué cambió respecto de la tercera ronda por efecto de las specs 27 y 28:**

| Empresa | Δ tercera ronda (con julio) | Δ ahora (sin julio) | Por qué |
|---|---:|---:|---|
| SGA | +14,1 | **+5,0** | spec 27 rechaza 7 detenciones de CORONEL con instrucción de 12–24 h antes (−8,0); el Excel tampoco las pagaba |
| GMETROPOLITANA | +19,1 | **+15,2** | spec 27 rechaza NUEVARENCA &5 (−8,6); +4,6 es &1 sin julio (artefacto) |
| ENEL | +2,4 | −5,5 | ATACAMA-2 &1 y SANISIDRO-1 &1 con cota / sin julio |
| COLBUN | −2,4 | −12,5 | NEHUENCO-2 &1 con cota TG1 (artefacto sin julio, −10) |
| ORAZUL | −0,7 | **−0,05** | spec 28: YUNGAY-1/2 cobran fría por cota, como el Excel |
| INERSA | +0,1 | −0,4 | spec 28 (+0,26 TENOGAS &1) y spec 27 (−0,39 TENOGAS &16) |
| EMELDA | +0,8 | +1,2 | spec 28 cobra EMELDA-1 &1 (Fría por cota); spec 27 rechaza det de EMELDA-2 |
| TAMAKAYA, ENGIE, ANTILHUE, ENLASA, GM_HOLDINGS, QUICKSTART | | sin cambio | |

Causas raíz sobre ciclos del mes (mismo método de la sección anterior): R6 tarifa
±68,8 (neto −20,7), R9 margen −54,3, R3 instrucción mal asociada en el Excel +48,7, R1
paradas cortas +35,5 (de los cuales ≈10,5 son ciclos de la hora 1 sin julio), R5 −18,8,
R2/R4 +7,2, R7 +0,55, R1b −2,2. Detalle en `Diagnostico_2608_v2.xlsx` (scratchpad).

Para cerrar agosto con la comparación definitiva hace falta correr con julio empalmado:
`Reporte_PD_15min_2607_v2.csv`, `RIO_07_2026.xlsx` y `Costos_de_P-D_Consolidado_2607.xlsx`
copiados a `Carpeta_de_Trabajo`.

---

## Quinta ronda (15-09): comparación definitiva de agosto — motor `main` con julio empalmado vs Excel corregido

Reemplaza la cuarta ronda (que corrió sin julio). Julio copiado a `Carpeta_de_Trabajo`
desde `T:` (solo lectura): `Reporte_PD_15min_2607_v2.csv`, `RIO_07_2026.xlsx`,
`Costos_de_P-D_Consolidado_2607.xlsx`. Motor: `main` en `f820455` — tarifa máxima
(spec 25), vigencia RIO 30 min (spec 27), cota inferior de horas (spec 28), umbral
1,0 MWh. Reporte de agosto `2608_v2` (mismo margen que el reporte original en todas las
empresas con ciclos completos). Excel corregido, sin traspasos.

| | Excel corregido | Motor | Δ |
|---|---:|---:|---:|
| Mes completo | 897.558.934 | **941.327.164** | +43,77 MM (+4,9%) |
| Σ\|Δ\| por empresa, mes completo | | | **71,4 MM** (14-09: 141,6) |
| Solo ciclos del mes, sin herencia | 914.259.268 | **914.820.834** | **+0,56 MM (+0,1%)** |
| Pares idénticos al peso | | | **207 de 352** |

Sobre los mismos ciclos, los dos modelos coinciden en 0,1%. La diferencia del mes
completo (+43,8 MM) es casi toda frontera: el motor liquida en agosto los ciclos que
venían de julio (MEJILLONES-CTM3 16,9 MM, NUEVARENCA 9,6 MM: 26,5 MM en 8 ciclos
"viene del mes anterior") que el Excel deja en 0 con el margen heredado de julio
(mecanismo 6b), más lo que el Excel no cobra en sus `&1` por falta de horas.

### Mes completo por empresa

| Empresa | Excel corregido | Motor | Δ | Δ % |
|---|---:|---:|---:|---:|
| ENEL_GENERACION | 471.058.535 | 488.764.728 | +17.706.193 | +4% |
| GMETROPOLITANA | 30.904.611 | 46.382.100 | +15.477.489 | +50% |
| ENGIE | 52.785.791 | 66.476.785 | +13.690.993 | +26% |
| TAMAKAYA_ENERGIA | 87.235.575 | 79.532.813 | −7.702.762 | −9% |
| SGA | 17.148.090 | 22.118.186 | +4.970.096 | +29% |
| GUACOLDA | 5.550.626 | 1.293.821 | −4.256.806 | −77% |
| COLBUN | 173.447.485 | 175.470.261 | +2.022.776 | +1% |
| BE FORESTALES | 8.320.906 | 6.928.482 | −1.392.423 | −17% |
| ANTILHUE | 3.852.834 | 4.656.334 | +803.500 | +21% |
| GM_HOLDINGS | 12.436.418 | 13.193.432 | +757.014 | +6% |
| ENLASA | 1.653.932 | 2.377.955 | +724.022 | +44% |
| QUICKSTART | 8.474.327 | 8.982.417 | +508.091 | +6% |
| COLMITO | 2.820.033 | 3.326.888 | +506.855 | +18% |
| INERSA | 10.922.759 | 10.539.074 | −383.685 | −4% |
| EMELDA | 914.180 | 1.226.701 | +312.521 | +34% |
| ELEKTRAGEN, ORAZUL, ENERGIA_SIETE, NUEVA DEGAN, EMELVA | | | < 0,12 MM | |
| ELECTRICA_MOKA, ENORCHILE, ON GROUP, LOS_GUINDOS | | | 0 | 0% |

### Qué hicieron las specs 27 y 28 respecto de la corrida del 14-09 (ambas con julio)

Total 971.292.712 → **941.327.164 (−29,97 MM)**.

| Empresa | Δ | Ciclos |
|---|---:|---|
| ENEL | −11,7 | SANISIDRO-1 &1 (31-jul → 1-ago): partida 15,0 MM rechazada por vigencia; el Excel también le da 0 |
| SGA | −9,1 | 7 detenciones de CORONEL con instrucción de 12–24 h antes (spec 27); el Excel tampoco las pagaba |
| GMETROPOLITANA | −8,6 | NUEVARENCA &5: PP/OM 90 min antes y PMT/OM 31 min después, rechazada por vigencia; el Excel también da 0 (R3) |
| INERSA | −0,5 | TENOGAS &16 por vigencia (−0,39) y &1 por cota (+0,26 vs 14-09 con partida 0) |
| EMELDA | −0,5 | detención de EMELDA-2 por vigencia |
| ORAZUL | **+0,6** | YUNGAY-1/2 cobran fría por cota (spec 28), igual que el Excel |
| BE FORESTALES | −0,15 | detención de CMPC &2 por vigencia |

Con julio empalmado la spec 28 solo actúa en 4 ciclos (YUNGAY-1/2, TENOGAS &1,
SANJAVIER-2: 0,89 MM), que es su alcance previsto. La spec 27 rechaza 5 partidas y 12
detenciones; en todos los casos con contraparte en el Excel, el Excel tampoco pagaba.

### Causas raíz sobre ciclos del mes (mismo método de la sección "Diagnóstico")

| Causa | Neto | Bruto |
|---|---:|---:|
| R9 margen por bloque vs por hora | −54,3 | 54,3 |
| R3 Excel no asocia la instrucción al ciclo | +48,7 | 48,7 |
| R6 configuración que fija la tarifa | +0,9 | 47,3 |
| R5 motor rechaza por RIO (SSCC / `&1`) | −25,3 | 25,3 |
| R1 paradas cortas | +25,0 | 25,0 |
| R2 + R4 flags y lista Pruebas del Excel | +7,2 | 7,2 |
| R7 PO de mitad de mes | +0,55 | 0,55 |
| R1b apareo | −2,2 | 2,2 |
| **Total** | **+0,56** | 210,5 |

R3 baja de 66,4 a 48,7 MM porque la spec 27 ahora rechaza NUEVARENCA &5 (el Excel
también); R5 no cambia. Lo que queda abierto sigue siendo lo mismo: fuente del SSCC
(−19,6), paradas menores a una hora (+25,0), lista Pruebas vs RIO (+4,5) y la lectura
del margen a 15 minutos (−54,3, a favor de las empresas).

### Cifras de referencia para regresiones (agosto con julio, `main` f820455)

| Corrida | Total |
|---|---:|
| Motor v7 tarifa máxima, vigencia 30, cota inferior, con julio | **941.327.164** |
| Excel corregido sin traspasos | 897.558.934 |
| Excel corregido, solo ciclos del mes sin herencia | 914.259.268 |
