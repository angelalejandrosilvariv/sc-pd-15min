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
