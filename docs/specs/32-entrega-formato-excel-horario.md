# 32 — Entrega al Coordinador con el formato del Excel horario

**Toca código:** sí (`scripts/generar_entrega_cen.py`, `src/sc_pd_motor_v7.py` solo
exportación, `tests/test_generar_entrega_cen.py`, `Carpeta_de_Trabajo/correr_entrega.py`,
`interfaz.py` sin cambios funcionales). **Cambia el monto liquidado:** no.

**Reemplaza** el libro de la spec 31. Los CSV pasan a ser el volcado plano de las hojas
de este libro. Decisión del 16-09-2026: *"el entregable debe tener un formato lo más
parecido al Excel horario que ya existe"*.

**Estado:** especificada; implementación por Codex; verificación con datos reales por
Claude (Codex no tiene los archivos).

---

## 1. Por qué

El Coordinador audita hoy un libro (`Sobrecostos_PD_AAMM.xlsm`) cuyas hojas conoce de
memoria: `Sobrecosto_PD xHyC` (una fila por hora y configuración), `PARTIDAS_DETENCIONES`
(una fila por hora y central relacionada), `Sobrecosto_Ciclo` (una fila por ciclo),
`Ciclos inconclusos`, `RESUMEN`, más las hojas de insumos `Instrucciones RIO`, `Pruebas`,
`Costos_de_P-D`, `Central_Empresa`. Sabe qué columna mirar y qué `SUMIF` sigue a cuál.

El libro de la spec 31 (tablas `Ciclos`/`Bloques`/`Candidatas` con nombres del motor)
obliga a aprender otra estructura. Esta spec reconstruye **las mismas hojas, con los
mismos nombres, encabezados y letras de columna**, a resolución de 15 minutos, y con la
misma cadena de fórmulas entre hojas (`xHyC → PARTIDAS_DETENCIONES → Sobrecosto_Ciclo →
RESUMEN`). Donde la regla del motor difiere de la del Excel (tarifa al dólar del extremo,
vigencia ±30 min, filtro EP en el extremo del ciclo, SSCC por comentario), la fórmula
cambia lo mínimo y la hoja `Leeme` lo declara.

Las columnas que el Excel no tiene (cuarto de hora, filtros del motor, checks) van
**después** de la última columna del Excel, para no mover ninguna letra.

## 2. Convenciones de tiempo y llaves

| Concepto | Excel horario | Este libro (15 min) |
|---|---|---|
| `fecha` | `AAMMDD` entero (260811) | igual |
| `hora` | 1..24 (hora 1 = 00:00–00:59) | igual: `FECHA_HORA.hour + 1` |
| `cuarto` | no existe | 1..4 (`FECHA_HORA.minute // 15 + 1`), columna nueva al final |
| `Id` (xHyC!A) | `fecha & hora & central` | `fecha & hora & "." & cuarto & central` → `2608119.1COLMITO_GN_A` |
| `Ciclo + fecha + hora` (P_D!O) | `fecha & hora & relacionada` | `fecha & hora & "." & cuarto & relacionada` |
| `Clave Ciclo` / `Ciclo de operación` | `RELACIONADA&n` | `Etiqueta_Relacionada` del motor, sin cambios |
| `Politica vigente` | `260801-1` | prefijo de `Llave_FHC` del bloque (`260818-1`) |

`FECHA_HORA` es el inicio del bloque. El punto en el `Id` se lee como fracción de la
hora (9.1 = primer cuarto de la hora 9) y evita la ambigüedad de concatenar sin
separador.

## 3. Alcance de filas

- `Sobrecosto_PD xHyC` y `PARTIDAS_DETENCIONES`: **solo bloques de ciclos del mes
  actual** (`Detalle_15Min`), igual que el paquete anterior ("bloques del ciclo
  simplemente"). No se rellenan horas sin generación como hace el Excel.
- `xHyC mes anterior`: los bloques del mes anterior de los ciclos que vienen de él
  (`Detalle_Frontera`), con las mismas columnas que `Sobrecosto_PD xHyC`. Existe para
  que `Ciclos inconclusos!X` (margen heredado) sea una fórmula y no un número suelto.
- `Sobrecosto_Ciclo`: una fila por ciclo de `Resumen_Ciclos_PD`, mismo orden.
- `Ciclos inconclusos`: tabla "Próximo mes" = ciclos diferidos (`Estado_Ciclo_Mes` en
  `Continua proximo mes` / `Continua todo el mes`); tabla "Mes anterior" = ciclos con
  `Estado_Ciclo_Mes = Viene del mes anterior` (liquidados este mes con partida en el mes
  anterior).

## 4. Hojas, en este orden

1. `Menu` 2. `Leeme` 3. `Costos_de_P-D` 4. `Pruebas` 5. `Instrucciones RIO`
6. `Central_Empresa` 7. `Sobrecosto_PD xHyC` 8. `PARTIDAS_DETENCIONES`
9. `Sobrecosto_Ciclo` 10. `RESUMEN` 11. `Ciclos inconclusos` 12. `xHyC mes anterior`
13. `Diccionario`.

Se omiten `Gen`, `CV`, `CMG_CONS_PROP_USD` (el reporte de 15 min es el insumo y sus
valores ya viajan en xHyC!E/W/X/Z), `Programacion`, `PD x HyConf`, `Hoja1`, `Pagos`,
`Datos Access`, `Revisor`, `PLABACOM`.

Todas las hojas: encabezado en la fila 1, paneles inmovilizados en la fila 2, ancho de
columna razonable, formato numérico `#,##0` en montos CLP y `0.00` en MWh/USD. Sin
tablas Excel (`add_table`): el Excel horario usa rangos planos y las fórmulas
`SUMIF/MAXIFS` por letra de columna. Los rangos en fórmulas van **acotados a la última
fila con datos** (`'Sobrecosto_PD xHyC'!$U$2:$U$65658`), no a la columna completa, para
que el recálculo sea tolerable.

### 4.1 `Menu`

| Celda / rango | Contenido |
|---|---|
| A1 `DIA`, A2 | primer día del mes en `AAMMDD` (260801) — lo usan las fórmulas como `Menu!$A$2` |
| B1 `Mes`, B2 | `AAMM` |
| D1 `Version`, D2 | `Preliminar` / `Definitivo` (parámetro `--version`, default `Preliminar`) |
| A4 `ARCHIVO`, B4 `SHA-256`, filas 5.. | archivos de entrada que recibió el generador |
| D4 `Interruptor`, E4 `Valor`, F4 `Spec`, filas 5.. | el inventario de `parametros` de la spec 31 (panel efectivo + `motor_version` + `fecha_corrida`) |

### 4.2 `Leeme`

Texto en la columna A, una idea por fila. Debe decir, al menos:

- qué es cada hoja y en qué se diferencia de la homónima del Excel horario;
- la cadena: `RESUMEN!C = SUMIF(Sobrecosto_Ciclo!I, H)`; `Sobrecosto_Ciclo!C/D =
  SUMIF(PARTIDAS_DETENCIONES!N, S/T)`; `E = SUMIF(xHyC!AC, AB)`; `PARTIDAS_DETENCIONES!S
  = MAXIFS(xHyC!U por ciclo y Proceso_Partida) × filtros del ciclo`;
- las cuatro diferencias de regla frente al Excel horario y dónde se ven:
  1. **tarifa al dólar del extremo** — `xHyC!U` usa `USD apertura ciclo` (col. nueva), no
     `Z` del bloque; spec 25 §7;
  2. **filtro Pruebas/EP y filtro operacional se evalúan en la instrucción de apertura /
     cierre del ciclo**, por eso multiplican en `PARTIDAS_DETENCIONES!S/T` y no en
     `xHyC!U/V` (`xHyC!AE` queda informativo);
  3. **vigencia ±30 min** de la instrucción (`PARTIDAS_DETENCIONES!AF`), spec 27;
  4. **`Presta SSCC`** sale del `COMENTARIO` de la instrucción del ciclo (1/0), no del
     `ISNUMBER` sobre `Sobrecosto_Ciclo`;
- que la exención "sin historia" (`PARTIDAS_DETENCIONES!AE`) reemplaza la regla
  `RIGHT(N,2)="&1" y P=""` del Excel;
- que `Generación_neta` (xHyC!AA) es igual a `generacion` porque el reporte de 15 min ya
  viene neto de consumos propios;
- que `Margen` (xHyC!AB) es fórmula solo con `RESOLUCION_MARGEN='bloque'` y
  `MARGEN_NETEADO_POR_CICLO=0`; con otra combinación se escribe el valor del motor y
  se avisa aquí;
- que las columnas a la derecha de la última del Excel son del motor y no existen en el
  horario;
- los CSV del paquete son estas mismas hojas volcadas como valores.

### 4.3 `Costos_de_P-D`

Fuente: hoja nueva del motor `Costos_PD_Usados` (ver §6). Encabezados y letras del
Excel; las columnas Q en adelante son nuevas.

| Col | Encabezado | Origen |
|---|---|---|
| A | `id` | `Llave_Concatenada` |
| B | `dia` | `DIA` |
| C | `tipo` | `HORA` (es el "tipo" de política del Excel) |
| D | `Unidad` | `UNIDAD` |
| E | `Costo Partida fría` | `Partida_Fria` |
| F | `Costo Partida tibia` | `Partida_Tibia` |
| G | `Costo Partida caliente` | `Partida_Caliente` |
| H | `Costo Detención` | `Detencion` |
| I | `Tiempo Partida fría` | `Tiempo_Partida_Fria` |
| J | `Tiempo Partida tibia` | `Tiempo_Partida_Tibia` |
| K | `Tiempo Partida caliente` | `Tiempo_Partida_Caliente` |
| L | `Costo_Cero` | `Costo_Cero` |
| M | `fria` | `Fria_Num1_M` |
| N | `tibia_i` | `Tibia_Num2_N` |
| O | `tibia_f` | `Tibia_Num1_O` |
| P | `Caliente` | `Caliente_Num1_P` |
| Q | `Costo Partida tibia 2` | `Partida_Tibia_2` (el Excel no lo tiene) |
| R | `Tiempo Partida tibia 2` | `Tiempo_Partida_Tibia_2` |

### 4.4 `Pruebas`

Bloques cuya instrucción vigente trae `CONSIGNAS = EP` (`Disponible (1) / Pruebas (0)`
= 0 en `Detalle_15Min` ∪ `Detalle_Frontera`). Columnas como el Excel: A `Id` (mismo
formato que xHyC!A), B `fecha`, C `hora`, D `central`, E `Configuracion`; nuevas:
F `cuarto`, G `FECHA_HORA`, H `Central relacionada`, I `Fuente RIO`.

### 4.5 `Instrucciones RIO`

Fuente: hoja nueva del motor `RIO_Usado` (§6): el RIO empalmado que realmente usó el
cruce (mes anterior recortado + mes actual, deduplicado como el motor). Una fila por
registro.

| Col | Encabezado | Contenido |
|---|---|---|
| A | `Clave` | `fecha & hora & "." & cuarto & Configuración` |
| B | `Clave relacionada` | `fecha & hora & "." & cuarto & Relacionada` |
| C | `Dia` | día del mes |
| D | `Hora` | `HH:MM` |
| E | `E/S` | vacío (no existe en el RIO de 15 min) |
| F | `Central` | `U. GENERADORA` |
| G | `Sube` | `POTENCIA MÁXIMA` |
| H | `Baja` | `POTENCIA MÍNIMA` |
| I | `Queda` | `POTENCIA INSTRUIDA` |
| J | `COMENTARIO` | `COMENTARIO` |
| K | `Configuración` | `NOMBRE CONFIGURACIÓN` |
| L | `Estado Embalse` | `ESTADO DE EMBALSE` |
| M | `Consigna` | `CONSIGNAS` (CON) |
| N | `MOTIVO` | `MOTIVO` (MOT) |
| O | `Operación` | `ESTADO OPERACIONAL` (EO) |
| P | `Neomante` | vacío |
| Q | `Relacionada` | `Central_Relacionada_RIO` |
| R | `Ciclo` | `Etiqueta_Relacionada` del ciclo cuya apertura o cierre usó este registro (cruce por `Fuente_Config_RIO` = `FECHA_HORA_RIO` y relacionada, contra `Resumen_Ciclos_PD`); si ninguno, `No encontrado` |
| S | `SSCC` | 1 si `COMENTARIO` contiene `SSCC`, `CTF`, `CSF` o `CPF` (sin distinguir mayúsculas); 0 si no. **Numérico**, para que `SUMIF` funcione |
| T | `Ciclo Partida siguiente` | vacío |
| U | `Clave Ciclo partida` | `R` cuando `N` es `PP` o `PMT`, si no vacío |
| V | `Combustible Partida` | `combustible_configuracion(K)` |
| W | `FECHA_HORA_RIO` | timestamp |
| X | `Usada en` | `Partida`, `Detencion`, `Partida y Detencion` o vacío |
| Y | `Mes` | `anterior` / `actual` |

Columnas que el RIO no trae se dejan vacías con su encabezado, para conservar letras.

### 4.6 `Central_Empresa`

Fuente: hoja nueva del motor `Central_Empresa` (§6). A `Central` (relacionada o
configuración, tal como está en el diccionario), B `Empresa`. Nada más: las columnas
H:J del Excel (razón social, RUT) no existen en el motor.

### 4.7 `Sobrecosto_PD xHyC`

Una fila por bloque × configuración de `Detalle_15Min`, ordenada por `central` y
`FECHA_HORA` (como el Excel). Sea `N` la última fila con datos.

| Col | Encabezado | Contenido |
|---|---|---|
| A | `Id` | valor, §2 |
| B | `fecha` | entero `AAMMDD` |
| C | `hora` | 1..24 |
| D | `central` | `Central` (configuración) |
| E | `generacion` | `GENERACION` |
| F | `Remunerar` | vacío |
| G | `Proceso_Partida` | `SI` si `FECHA_HORA = Inicio_Generacion_Central` (primer bloque de esa configuración dentro del ciclo); si no vacío |
| H | `horas_detenida` | en filas `G = SI`: `Horas_Detenida_Ciclo`, o `Horas_Cota_Inferior` si aquella es nula y la cota existe; vacío en el resto |
| I | `proceso_detencion` | `SI` si `FECHA_HORA = Termino_Generacion_Central`; vacío si no |
| J | `Ciclo de operación` | `Etiqueta_Relacionada` |
| K | `check01-PD` | 0 |
| L | `con_costo_PD` | `D` si la configuración tiene tarifa (`Costo_Partida` no nulo o `Costo_Detencion > 0`), si no `NO` |
| M | `Costo_cero_PD` | `Costo_Cero` (`SI` / `NO`; `No_Aplica` si nulo) |
| N | `Partida` | `SI` si `G = SI` y `Tarifa partida USD > 0`; si no 0 |
| O | `Detencion` | fórmula `=+I2` |
| P | `part_fria` | `Fria_Num1_M` |
| Q | `part_tibia_i` | `Tibia_Num2_N` |
| R | `part_tibia_f` | `Tibia_Num1_O` |
| S | `part_cal` | `Caliente_Num1_P` |
| T | `tipo_partida` | en filas `G = SI`: `Tipo_Partida` del bloque en minúsculas (`fria`, `tibia`, `tibia_2`, `caliente`); `-` en el resto |
| U | `COSTO_PARTIDA [$]` | **fórmula** `=IF(N2="SI",VLOOKUP(AH2&D2,'Costos_de_P-D'!$A$2:$R$<n>,IF(T2="fria",5,IF(T2="tibia",6,IF(T2="tibia_2",17,7))),FALSE)*AK2*AG2*AM2,0)` — tarifa USD de la configuración según tramo × dólar de apertura del ciclo (AK) × combustible instruido (AG) × Costo_Cero (AM). Reproduce `_Candidata_Partida` de `tarifa_configuracion_maxima()` |
| V | `COSTO_DETENCION [$]` | **fórmula** `=IF(O2="SI",VLOOKUP(AH2&D2,'Costos_de_P-D'!$A$2:$R$<n>,8,FALSE)*AL2*AO2*AN2,0)` — tarifa detención × dólar de cierre (AL) × combustible instruido al cierre (AO) × Costo_Cero detención (AN) |
| W | `CV` | `CV` |
| X | `CMg` | `CMg` |
| Y | `Diferencia Cmg-CV` | fórmula `=IF(X2-W2<0,0,X2-W2)` |
| Z | `USD` | `Dolar` |
| AA | `Generación_neta` | fórmula `=E2` |
| AB | `Margen` | fórmula `=Z2*Y2*AA2` (condición de §4.2; si no, valor `Margen`) |
| AC | `Clave Ciclo` | fórmula `=J2` |
| AD | `Programación` | vacío |
| AE | `Disponible (1) / Pruebas (0)` | `Disponible (1) / Pruebas (0)` del bloque (informativo, ver §4.2) |
| AF | `Combustible Partida` | combustible instruido en la apertura del ciclo: `combustible_configuracion(Configuracion RIO del primer bloque del ciclo)` |
| AG | `Conf despachada RIO` | 1 si `AF = ""` o `combustible_configuracion(D) = AF`; si no 0 (= `pasa_combustible_partida`) |
| AH | `Politica vigente` | prefijo de `Llave_FHC` hasta la central (`260818-1`) |
| AI | `Empresa` | `Empresa` |
| **AJ** | `cuarto` | 1..4 |
| AK | `USD apertura ciclo` | `Valor_Dolar` del primer bloque del ciclo (`FECHA_HORA = Inicio_Ciclo_Global`) |
| AL | `USD cierre ciclo` | `Valor_Dolar` del último bloque (`Termino_Ciclo_Global`) |
| AM | `Filtro Costo_Cero partida` | `Filtro_CostoCero_Partida` |
| AN | `Filtro Costo_Cero detención` | `Filtro_CostoCero_Detencion` |
| AO | `Conf despachada RIO detención` | 1 si combustible instruido al cierre vacío o igual al de `D` (= `pasa_combustible_detencion`) |
| AP | `Combustible Detención` | combustible instruido al cierre (`Configuracion RIO` del último bloque del ciclo) |
| AQ | `Tarifa partida USD` | `Costo_Partida` |
| AR | `Tarifa detención USD` | `Costo_Detencion` |
| AS | `Central relacionada` | `Central_Relacionada` |
| AT | `Clave relacionada` | `fecha & hora & "." & cuarto & Central_Relacionada` (es `PD x HyConf!N` del Excel; la usa `PARTIDAS_DETENCIONES!D`) |
| AU | `FECHA_HORA` | timestamp |
| AV | `Instrucción` | `MOTIVO` |
| AW | `Operación` | `ESTADO OPERACIONAL` |
| AX | `Consigna` | `CONSIGNAS` |
| AY | `Configuración RIO` | `Configuracion RIO` |
| AZ | `Comentario RIO` | `COMENTARIO` |
| BA | `Fuente RIO` | `Fuente_Config_RIO` |
| BB | `Vigencia RIO` | `Vigencia_RIO` |
| BC | `Filtro operacional` | `Filtro_Operacional` |
| BD | `Margen motor` | `Margen` (valor, para el check) |
| BE | `Check margen` | fórmula `=ROUND(AB2-BD2,0)` |

`VLOOKUP` sobre `Costos_de_P-D` con `T = tibia_2` apunta a la columna Q (índice 17).
Si la política del bloque no existe en `Costos_de_P-D` (`Llave_FHC` con `SinFecha`), la
fórmula da `#N/A`: se envuelve en `IFERROR(...,0)` y `Leeme` lo explica (ese ciclo no
tiene tarifa en el motor tampoco).

### 4.8 `PARTIDAS_DETENCIONES`

Una fila por bloque × central relacionada (agrupando las configuraciones de
`Detalle_15Min`), ordenada por `central` y `FECHA_HORA`. Sea `M` la última fila.

| Col | Encabezado | Contenido |
|---|---|---|
| A | `fecha` | `AAMMDD` (el Excel tiene `|` por accidente; aquí `fecha`) |
| B | `hora` | 1..24 |
| C | `central` | `Central_Relacionada` |
| D | `generacion` | fórmula `=SUMIF('Sobrecosto_PD xHyC'!$AT$2:$AT$N,O2,'Sobrecosto_PD xHyC'!$E$2:$E$N)` |
| E | `Remunerar` | vacío |
| F | `Proceso_Partida` | `SI` si `FECHA_HORA = Inicio_Ciclo` del ciclo; vacío si no |
| G | `horas_detenida` | en `F = SI`: como xHyC!H |
| H | `proceso_detencion` | `SI` si `FECHA_HORA = Termino_Ciclo` **y** el ciclo no está diferido; vacío si no |
| I | `Ciclo` | `Ciclo_ID_Relacionada` |
| J | `con_costo_PD` | vacío |
| K | `Costo_cero_PD` | `NO` si `Filtro_CostoCero_Partida = 1`, `SI` si 0 |
| L | `Costo PD` | 1 |
| M | `Central relacionada` | fórmula `=C2` |
| N | `Clave Ciclo` | fórmula `=M2&"&"&I2` |
| O | `Ciclo + fecha + hora` | fórmula `=A2&B2&"."&AK2&M2` |
| P | `Instrucción` | en `F = SI`: `Motivo_Partida` del ciclo; en `H = SI`: `Motivo_Detencion`; resto: `MOTIVO` del bloque |
| Q | `Operación` | ídem con `Estado_Op_Partida` / `Estado_Op_Detencion` / `ESTADO OPERACIONAL` |
| R | `Programación` | vacío |
| S | `Monto Partidas` | **fórmula solo en filas `F = SI`**, 0 en el resto: `=IFERROR(MAXIFS('Sobrecosto_PD xHyC'!$U$2:$U$N,'Sobrecosto_PD xHyC'!$J$2:$J$N,N2,'Sobrecosto_PD xHyC'!$G$2:$G$N,"SI")*IF(OR(P2="OM",Q2="PDO",AND(P2="OT",Z2=1),AND(AE2=1,P2="Sin_Registro_RIO")),1,0)*AF2*AG2*AH2,0)` |
| T | `Monto Detenciones` | **fórmula solo en filas `H = SI`**, 0 en el resto: igual con `$V`, `$I` y los filtros de detención de la misma fila |
| U | `Vacio` | vacío |
| V | `N° Partidas` | en filas `F = SI` o `H = SI`: `=COUNTIFS('Sobrecosto_PD xHyC'!$J$2:$J$N,N2,'Sobrecosto_PD xHyC'!$G$2:$G$N,"SI")`; vacío en el resto |
| W | `Monto Partidas` | ídem `=SUMIFS(xHyC!$U, xHyC!$J, N2, xHyC!$G, "SI")` |
| X | `N° Detenciones` | ídem con `$I` |
| Y | `Monto Detenciones` | ídem `SUMIFS` de `$V` |
| Z | `Presta SSCC` | 1 si el `COMENTARIO` de la instrucción usada en la fila (la del ciclo en los extremos, la del bloque en el resto) contiene `SSCC|CTF|CSF|CPF`; si no 0 |
| AA | `Bloque mes` | `(día-1)*96 + (hora-1)*4 + cuarto` (reemplaza `Hora mes`) |
| AB | `RIO PP` | `=COUNTIFS('Instrucciones RIO'!$B$2:$B$r,O2,'Instrucciones RIO'!$M$2:$M$r,"PP")` |
| AC | `RIO PS` | ídem `"PS"` |
| AD | `Revisar` | `=IF(AB2+AC2>1,1,0)` |
| **AE** | `Exención sin historia` | `Flag_Exencion` del ciclo (1/0) |
| AF | `Vigencia RIO` | en extremos: `Vigencia_RIO_Partida` / `Vigencia_RIO_Detencion` del ciclo; resto: `Vigencia_RIO` del bloque |
| AG | `Disponible (1) / Pruebas (0)` | en extremos: `Filtro_Disp_Partida` / `Filtro_Disp_Detencion`; resto: valor del bloque |
| AH | `Conf despachada RIO` | en extremos: `Filtro_Conf_Partida` / `Filtro_Conf_Detencion` (1 bajo `USAR_TARIFA_RIO_INSTRUIDA = 1`); resto 1 |
| AI | `Filtro operacional motor` | en extremos: `Filtro_Op_Partida` / `Filtro_Op_Detencion`; resto: `Filtro_Operacional` del bloque. Para contrastar con el `IF(OR(...))` de S/T |
| AJ | `Consigna` | `Consigna_Partida` / `Consigna_Detencion` / `CONSIGNAS` |
| AK | `cuarto` | 1..4 |
| AL | `FECHA_HORA` | timestamp |
| AM | `Fuente RIO` | `Fuente_Config_RIO` (timestamp de la instrucción) |
| AN | `Antigüedad instrucción (min)` | `FECHA_HORA − Fuente RIO` en minutos |
| AO | `Estado ciclo mes` | `Estado_Ciclo_Mes` |
| AP | `Empresa` | `Empresa` |

Los filtros de los extremos vienen de `Resumen_Ciclos_PD` (ya pasaron por la búsqueda
relajada de la sección 14 del motor), **no** del primer/último bloque de
`Detalle_15Min`; de lo contrario `S` no reproduciría `Costo_Partida_Efectivo`.

### 4.9 `Sobrecosto_Ciclo`

Una fila por ciclo, orden de `Resumen_Ciclos_PD`. Sea `C` la última fila.

| Col | Encabezado | Contenido |
|---|---|---|
| A | `Ciclo de operación` | `Etiqueta_Relacionada` |
| B | `Ciclo completo` | 1 si el ciclo se liquida este mes (`Estado_Ciclo_Mes` en `Inicia y termina este mes`, `Viene del mes anterior`); 0 si se difiere |
| C | `Total Costos Partida` | `=SUMIF(PARTIDAS_DETENCIONES!$N$2:$N$M,A2,PARTIDAS_DETENCIONES!$S$2:$S$M)` |
| D | `Total Costos Detención` | ídem con `$T` |
| E | `Total Margen` | `=SUMIF('Sobrecosto_PD xHyC'!$AC$2:$AC$N,A2,'Sobrecosto_PD xHyC'!$AB$2:$AB$N)` |
| F | `Total Costos Partida ciclo inconcluso` | `=SUMIF('Ciclos inconclusos'!$S$3:$S$k,A2,'Ciclos inconclusos'!$V$3:$V$k)+SUMIF('Ciclos inconclusos'!$S$3:$S$k,A2,'Ciclos inconclusos'!$W$3:$W$k)` |
| G | `Margen ciclo inconcluso` | `=SUMIF('Ciclos inconclusos'!$S$3:$S$k,A2,'Ciclos inconclusos'!$X$3:$X$k)` |
| H | `Total Sobrecosto_P-D` | `=IF(C2+D2+F2>E2+G2,C2+D2+F2-E2-G2,0)` (idéntica al Excel) |
| I | `Empresa` | `=IF(B2=1,VLOOKUP(Q2,Central_Empresa!$A$2:$B$e,2,0),"Se traspasa al proximo mes")` |
| J | `Copia Ciclo` | `=A2` |
| K | `Cuadro de pagos?` | `=IFERROR(VLOOKUP(I2,RESUMEN!$A$2:$A$z,1,0),"Falta en cuadro de pagos")` |
| L, M | — | vacías |
| N | `Verificadores` | vacío |
| O | `PO` | 0 |
| P | `SIF` | 0 |
| Q | `Ciclo` | `=LEFT(A2,FIND("&",A2,1)-1)` |
| R | `Maximo ciclo` | `=MAXIFS(PARTIDAS_DETENCIONES!$I$2:$I$M,PARTIDAS_DETENCIONES!$C$2:$C$M,Q2)` |
| S | `SSCC` | `=SUMIF('Instrucciones RIO'!$R$2:$R$r,A2,'Instrucciones RIO'!$S$2:$S$r)` |
| **T** | `Check SC` | `=ROUND(H2*B2-<col Total SC_PD>,0)` |
| U | `Check partida` | `=ROUND(C2+F2-<col Costo_Partida_Efectivo>,0)` |
| V | `Check detención` | `=ROUND(D2-<col Costo_Detencion_Efectivo>,0)` |
| W | `Check margen` | `=ROUND(E2+G2-<col Margen_Suma_Ciclo>,0)` |
| X.. | **todas las columnas de `Resumen_Ciclos_PD`** en su orden oficial (`columnas_resumen_ciclos`), más `Antiguedad_Instruccion_*_min` | valores del motor |

`<col …>` es la letra real que reciba cada columna del motor en X..; el generador la
calcula.

Los ciclos diferidos tienen `Costo_*_Efectivo = 0` en el motor (spec de diferimiento),
por eso los checks usan `H2*B2` y `F/E` heredados solo aplican con `B = 1`.

### 4.10 `RESUMEN`

| Col | Encabezado | Contenido |
|---|---|---|
| A | `Empresa` | todas las empresas de `SC_por_Empresa` ∪ `Central_Empresa!B` presentes en `Sobrecosto_Ciclo`, orden de `SC_por_Empresa` (mayor a menor) |
| B | `PAGA` | 0 (no hay cuadro `Pagos` en el motor) |
| C | `RECIBE` | `=SUMIF(Sobrecosto_Ciclo!$I$2:$I$C,A2,Sobrecosto_Ciclo!$H$2:$H$C)` |
| D | `SALDO` | `=+C2-B2` |
| E | `rep` | `=+COUNTIF($A$2:$A$z,A2)` |
| F | `CHECK` | `=ROUND(C2-H2,0)` |
| G1 | — | `=SUM(D:D)` (como el Excel) |
| H | `Motor Total_SC_PD_CLP` | valor de `SC_por_Empresa` |
| I | `Ciclos` | `=COUNTIFS(Sobrecosto_Ciclo!$I$2:$I$C,A2)` |

### 4.11 `Ciclos inconclusos`

Dos tablas lado a lado, como el Excel: fila 1 títulos (`A1 = Próximo mes`, `S1 = Mes
anterior`), fila 2 encabezados, datos desde la fila 3.

**Próximo mes (A:P)** — ciclos diferidos, encabezados de `Sobrecosto_Ciclo!A:P`. C/D/E
con las mismas fórmulas de `Sobrecosto_Ciclo` (lo que acumulan este mes), F/G = 0,
`H = 0`, `I = "Se traspasa al proximo mes"`, K = `"Falta en cuadro de pagos"`.

**Mes anterior (S:AI)** — ciclos `Viene del mes anterior`:

| Col | Encabezado | Contenido |
|---|---|---|
| S | `Ciclo de operación` | `=T3` (en el Excel renumera a `&1`; el motor ya trae la etiqueta del ciclo empalmado) |
| T | `Ciclo de operación` | `Etiqueta_Relacionada` |
| U | `Ciclo completo` | 1 |
| V | `Total Costos Partida` | `Costo_Partida_Efectivo` del motor (la partida ocurrió el mes anterior; su bloque `G = SI` no está en xHyC) |
| W | `Total Costos Detención` | 0 |
| X | `Total Margen` | `=SUMIF('xHyC mes anterior'!$AC$2:$AC$f,T3,'xHyC mes anterior'!$AB$2:$AB$f)` |
| Y, Z | inconclusos | 0 |
| AA | `Total Sobrecosto_P-D` | vacío |
| AB | `Empresa` | `Empresa` |
| AD | `Cuadro de pagos?` | vacío |
| AG..AI | `Verificadores`, `PO`, `SIF` | vacío / 0 |

### 4.12 `xHyC mes anterior`

Mismas columnas y fórmulas que `Sobrecosto_PD xHyC`, sobre `Detalle_Frontera`. Si no hay
hoja `Detalle_Frontera` o está vacía, la hoja se crea solo con encabezados.

### 4.13 `Diccionario`

Una fila por (hoja, columna): `hoja`, `columna`, `letra`, `significado`, `origen motor`,
`fórmula o valor`. Cubre todas las hojas anteriores.

## 5. CSV del paquete

`Entrega_SCPD_<AAMM>/` conserva el nombre. Un CSV por hoja de datos, con el nombre de
la hoja saneado (`SCPD_2608_Sobrecosto_PD_xHyC.csv`, `SCPD_2608_PARTIDAS_DETENCIONES.csv`,
`SCPD_2608_Sobrecosto_Ciclo.csv`, `SCPD_2608_RESUMEN.csv`, `SCPD_2608_Ciclos_inconclusos.csv`
(las dos tablas apiladas con columna `tabla`), `SCPD_2608_Instrucciones_RIO.csv`,
`SCPD_2608_Pruebas.csv`, `SCPD_2608_Costos_de_P-D.csv`, `SCPD_2608_Central_Empresa.csv`,
`SCPD_2608_xHyC_mes_anterior.csv`), más `SCPD_2608_parametros.csv` (igual que hoy) y
`SCPD_2608_diccionario.csv`. Los CSV llevan **valores**: donde el libro tiene fórmula,
el CSV lleva el resultado calculado en pandas con la misma regla (así el Coordinador
puede validar la fórmula contra el CSV). UTF-8 con BOM, separador coma, fechas ISO.

Los CSV `bloques`, `ciclos`, `candidatas_tarifa` y `empresas` de la spec 31
desaparecen; `Resumen_Ciclos_PD` completo ya viaja en `Sobrecosto_Ciclo` (columnas X..)
y las candidatas se leen en xHyC (`G = SI` por configuración con su `U`).

## 6. Cambios en el motor (solo exportación)

`main()` agrega tres hojas al `Reporte_Sobrecostos_PD_Final.xlsx`, sin tocar ningún
cálculo:

- `RIO_Usado`: el DataFrame `rio` tras el empalme y deduplicación (todas sus columnas
  originales mapeadas + `FECHA_HORA_RIO`, `Central_Relacionada_RIO`) más una columna
  `Mes` (`anterior`/`actual` según `FECHA_HORA_RIO < f_min_actual`).
- `Costos_PD_Usados`: `df_externo` tal como se leyó (mes anterior + actual), sin
  deduplicar.
- `Central_Empresa`: dos columnas `Central`, `Empresa` con `empresa_por_relacionada`; si
  no hay diccionario de empresas, hoja vacía con encabezados.

`Guia_Lectura` describe las tres hojas. `devolver_diagnostico` no cambia.

## 7. Generador

`scripts/generar_entrega_cen.py` conserva la firma `generar_entrega(reporte,
carpeta_salida, archivos_entrada, panel, tablas_dinamicas)`; `tablas_dinamicas` deja de
existir (eliminar el flag y el aviso; la interfaz y `correr_entrega.py` no lo pasan). Se
agrega `version: str = "Preliminar"` (CLI `--version`). Lee del reporte:
`Resumen_Ciclos_PD`, `Detalle_15Min`, `Detalle_Frontera` (opcional), `SC_por_Empresa`,
`Parametros_Motor`, `Guia_Lectura`, y las tres hojas nuevas (`RIO_Usado`,
`Costos_PD_Usados`, `Central_Empresa`; si faltan, avisa y crea las hojas solo con
encabezados, y `Instrucciones RIO!R/S` no se pueden construir → `Sobrecosto_Ciclo!S`
queda en 0).

Estructura sugerida: una función pura por hoja que devuelva `(DataFrame de valores,
dict columna → plantilla de fórmula)`; un escritor común que vuelque valores, escriba
las fórmulas fila a fila con `{r}` sustituido por el número de fila y `{N}`/`{M}`/… por
las últimas filas de cada hoja, y un volcado a CSV de los mismos DataFrames de valores.
Escribir con `xlsxwriter`, `constant_memory` **desactivado** (hay que escribir por
columnas), `set_calc_mode('auto')`, y sin `add_table`.

Las plantillas de fórmula se guardan en un diccionario de módulo (`FORMULAS`) para que
las pruebas las verifiquen sin abrir Excel.

## 8. Interfaz y runner

Sin cambios de comportamiento: el botón **Generar entrega CEN** y `correr_entrega.py`
producen la carpeta nueva. Se quita la casilla / variable de tablas dinámicas si existía.
`correr_entrega.py` gana `VERSION = "Preliminar"`.

## 9. Pruebas (sintéticas, sin datos reales)

Reemplazar `tests/test_generar_entrega_cen.py`. Construir un reporte sintético con dos
centrales relacionadas, tres ciclos (uno con dos configuraciones y tarifa máxima en la
segunda, uno diferido, uno que viene del mes anterior con `Detalle_Frontera`), RIO con un
comentario `SSCC`, costos con `tibia_2`. Verificar:

1. La carpeta trae los 12 CSV y el libro; `Menu!A2` = `AAMM01`.
2. Nombres y orden de hojas exactos (§4); encabezados A..AI de xHyC, A..AD de
   PARTIDAS_DETENCIONES, A..S de Sobrecosto_Ciclo idénticos a las tablas de esta spec.
3. `Id` y `Ciclo + fecha + hora` con el formato `fecha&hora&"."&cuarto&central`.
4. `G = SI` exactamente en el primer bloque de cada configuración por ciclo; `I = SI` en el
   último; `PARTIDAS_DETENCIONES!F/H` en los extremos del ciclo; `H` vacío en el
   diferido.
5. Los valores calculados en pandas para `U`, `V`, `S`, `T`, `C`, `D`, `E`, `H`
   reproducen `Costo_Partida_Efectivo`, `Costo_Detencion_Efectivo`, `Margen_Suma_Ciclo` y
   `Total SC_PD` de `Resumen_Ciclos_PD` (es la misma comprobación que harán los checks en
   Excel, pero en Python).
6. Las plantillas de `FORMULAS` contienen los rangos acotados (`$U$2:$U$` + última fila) y
   ninguna referencia estructurada (`[@`, `[[#This Row]`).
7. El libro se abre con `openpyxl` y las celdas de fórmula (`U2`, `S` de una fila `F = SI`,
   `Sobrecosto_Ciclo!C2`, `RESUMEN!C2`) contienen las fórmulas esperadas.
8. `Ciclos inconclusos!S3 = "=T3"`, `X3` referencia `'xHyC mes anterior'`.
9. Si el reporte no trae `RIO_Usado`, el generador no cae y `Instrucciones RIO` queda
   solo con encabezados.
10. `Instrucciones RIO!S` es 1 para el comentario con `SSCC` y 0 en otro caso; `R` trae la
    etiqueta del ciclo que la usó.

Además, en `tests/` del motor: una prueba de que `main()` con `devolver_diagnostico`
sigue devolviendo lo mismo, y que el export contiene las tres hojas nuevas (puede
hacerse sobre un reporte mínimo si ya existe un fixture; si no, verificar la lista
`hojas` por inspección del código con una prueba de humo del módulo).

## 10. Verificación con datos reales (Claude)

Con agosto 2026 empalmado con julio (`main` actual, 939.959.962 CLP):

1. El libro abre en Excel sin reparación; recálculo completo < 3 min.
2. `Sobrecosto_Ciclo!T:W` (checks) = 0 en los 390 ciclos.
3. `RESUMEN!F` = 0 en todas las empresas y `RESUMEN!G1` = 939.959.962.
4. `xHyC!BE` = 0 en todos los bloques.
5. Muestreo manual de tres ciclos conocidos contra el Excel horario v2: `COLMITO&1`
   (una configuración), `NEHUENCO-2` multi-configuración, `TOCOPILLA-U16&1` (rechazo
   EP): la lectura de las hojas debe ser reconocible para quien usa el horario.

Resultados, hallazgos y correcciones se documentan en esta spec y en la bitácora.

## 11. Fuera de alcance

- Reproducir la macro del Excel (`Menu`, `PD x HyConf`, `Programacion`).
- Tablas dinámicas (`Hoja1`, `Datos Access`): el Coordinador puede crearlas sobre
  `Sobrecosto_Ciclo` como hoy.
- Cambiar el nombre de las columnas del motor en `Resumen_Ciclos_PD`.
