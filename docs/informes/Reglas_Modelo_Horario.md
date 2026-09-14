# Reglas del modelo horario, deducidas de sus fórmulas

**Fuente:** `Copia de Sobrecostos_PD_2606 def.xlsm` (junio 2026, definitivo).
Cotejado contra `Sobrecostos_PD_2608 pre.xlsm`: misma estructura de hojas.

**Método:** extracción de la fila patrón (fila 2) de cada hoja con `openpyxl`,
sin recalcular. Cada regla lleva la fórmula que la sustenta. Donde una columna
es dato y no fórmula, se dice explícitamente.

**Alcance:** reglas de cálculo del sobrecosto. El prorrateo a suministradores
(hojas `Pagos`, `RESUMEN`, `Datos Access`) queda fuera.

---

## 0. Lo que está en macros VBA — leído con `oletools`

Las columnas que definen el ciclo (`Proceso_Partida`, `horas_detenida`,
`proceso_detencion`, `Ciclo`) las escriben dos macros. Se extrajo el código
(`oletools 0.60.2`, 3.381 líneas en 21 módulos; los demás módulos son de
medidores, PRMTE y peajes, ajenos a este cálculo).

### 0.a Detección de partidas y detenciones — `C_Detecta_partidas_detenciones.Macro_general_PD_Optimizada`

Opera sobre las filas hora-configuración ordenadas por central y hora, y
compara cada fila con la **anterior y la siguiente de la misma configuración**:

```vba
If (gen <> 0 And gensig = 0) And cent = centsig Then arrH = "SI"   ' detención: esta hora genera, la siguiente no
If  gen <> 0 And genant = 0  And cent = centant Then arrF = "SI"   ' partida:   esta hora genera, la anterior no
```

- **Corte sin tolerancia:** cualquier hora en cero cierra el ciclo. Equivale a
  `TOLERANCIA_CORTES_BLOQUES = 0` del motor.
- Usa `<> 0`, no `> 0`: una generación **negativa** cuenta como encendida. El
  motor usa `> 0`. Inerte mientras no haya generación negativa (en 2606 no hay).
- Una hora aislada entre ceros es partida y detención a la vez.
- Mira la **fila** anterior, no la hora anterior: si a una configuración le
  falta una fila, no la ve como cero. Igual que el motor.
- `UsarMinimoTecnico = False`: la propagación de la rampa hasta el mínimo
  técnico existe en el código pero está **desactivada**.
- La sección "8. Detección ciclo de operación" tiene fechas fijas `200201` y
  `200229` (febrero 2020): código heredado que no gobierna nada hoy.

La macro corre con `Estado = 2` (hoja `PD x HyConf`, nivel **configuración**) y
con `Estado = 1` (hoja `PARTIDAS_DETENCIONES`, nivel **relacionada**, con la
generación sumada por relacionada-hora). Los flags de configuración alimentan
el costo horario; los de relacionada, la numeración del ciclo.

### 0.b Horas detenidas — misma macro, sección 4

```vba
For k = i - 1 To 2 Step -1
    If arrIn(k, 3) <> cent Then Exit For        ' cambió la central
    If arrH(kr, 1) = "SI" Then Exit For         ' llegó a la detención anterior
    t = t + 1
Next k
arrG(r, 1) = t
```

Para cada partida cuenta **filas** hacia atrás hasta la detención anterior de la
misma central. Como entre una detención y la partida siguiente todas las horas
están en cero, `t` = horas en cero.

**Si no hay detención anterior en los datos, cuenta hasta la primera fila de la
central.** Y la hoja `Gen` trae **solo el mes actual** (95.813 filas de 2606,
ninguna de 2605). Por lo tanto, para el primer ciclo del mes, `horas_detenida`
= horas en cero **desde las 00:00 del día 1**, no desde la detención real. Es
un piso, no una medición. Una central apagada desde el 20 de mayo que parte el
3 de junio recibe 48 horas, no 14 días.

### 0.c Numeración de ciclos — `Módulo4.CalcularCiclosOptimo` (nivel relacionada)

```vba
' abre ciclo nuevo si:
'   (gen_anterior = 0 And gen > 0 And ninguna Instrucción "SIF" en las filas i..i-5)  Or  F = "SI"
' si no: si la fila anterior fue detención (H = "SI") -> 0 (apagada); si no, arrastra el número
' número = máximo del grupo + 1     -> correlativo por relacionada dentro del mes
```

- La regla `SIF` impediría abrir ciclo nuevo si en las 6 horas previas hubo
  una instrucción con ese código. **En 2606 el código no aparece** (los motivos
  son OM, OT, EP, RE, SDCF, MM): regla presente pero inerte.
- Aquí usa `> 0` (en la detección usa `<> 0`): inconsistencia interna, inerte.
- El número es correlativo dentro del mes: equivale a
  `RENUMERAR_CICLOS_DEL_MES = 1`.

### 0.d Cómo se juntan: la mezcla de configuraciones, trazada de punta a punta

1. La macro marca `Proceso_Partida = "SI"` **por configuración** en `PD x HyConf`.
2. `Sobrecosto_PD xHyC!U` calcula el costo horario de partida **por configuración**.
3. `PARTIDAS_DETENCIONES!S = MAXIFS(U, ciclo_relacionada, G = "SI")` toma el
   **máximo** entre todas las horas marcadas como partida de todas las
   configuraciones que caen dentro del mismo ciclo de relacionada.

Si la turbina a gas parte a las 02:45 bajo `TG1_TG1` y la de vapor a las 06:15
bajo `TG1+0.5TV`, ambas horas tienen `Proceso_Partida = "SI"`, ambas pertenecen
al ciclo `KELAR-TG12&n`, y el `MAXIFS` elige la tarifa de `TG1+0.5TV`. No es un
descuido de datos: es la consecuencia directa de detectar por configuración,
numerar por relacionada y agregar con máximo.

### Hojas de datos puros (sin fórmula ni macro de cálculo)

`Pruebas` (lista de hora-central en estado de pruebas, cargada por
`Módulo11.Consolida_Pruebas`) y `Ciclos inconclusos` (traspasados del mes
anterior, pegados a mano o por proceso externo).

---

## 1. Entidad del ciclo — central relacionada

```
PD x HyConf!M   = IFNA(VLOOKUP(central, Gen!$Q:$R, 2, 0), central)     ← diccionario config → relacionada
PD x HyConf!N   = fecha & hora & M                                        ← clave relacionada
PARTIDAS_DETENCIONES!N = M & "&" & I                                     ← Clave Ciclo = relacionada & nº ciclo
```

El diccionario configuración → relacionada vive en `Gen!Q:R`. El ciclo se
numera **por central relacionada**, igual que el motor v7. Las
sub-configuraciones de una misma relacionada comparten ciclo.

**Motor v7:** idéntico en concepto (`Central_Relacionada`, `Ciclo_ID_Relacionada`).
**Motor turbina:** distinto por diseño (ciclo por `UNIDAD GENERADORA`).

## 2. Política de costos vigente — carry-forward

```
Menu!R = día & "-" & hora
Menu!S = IFNA(VLOOKUP(R, políticas publicadas, 1, 0), S_fila_anterior)   ← si no hay política a esa hora, se arrastra la anterior
Sobrecosto_PD xHyC!AH = VLOOKUP(fecha&"-"&hora, Menu!R:S, 2, 0)          ← política vigente de la hora
```

**Motor:** equivalente — `merge_asof(direction='backward')` sobre `Fecha_PO`.

## 3. Horas detenidas del ciclo

```
Sobrecosto_PD xHyC!H = IF(G="SI", MAXIFS(PARTIDAS_DETENCIONES!G, N, ciclo), "")
```

Toma el máximo de `horas_detenida` (dato de macro) para el ciclo. Si el ciclo no
tiene historia, `MAXIFS` devuelve **0**.

**Motor:** `Horas_Detenida_Ciclo = Inicio_Ciclo − Termino_Ciclo_Anterior`, por
diferencia de tiempo. Nulo si no hay ciclo anterior conocido.

## 4. Tramo de partida y tarifa

```
P,Q,R,S = XLOOKUP(política & central, Costos_de_P-D!A, M/N/O/P)   ← umbrales fría / tibia_i / tibia_f / caliente
T = IF(AND(H<>0, N="SI"), IF(H<=S, "caliente", IF(H>=P, "fria", "tibia")), "-")
U = IF(N="SI", IF(P=0, tarifa_fría, tarifa_por_tramo[fría=col5, tibia=col6, caliente=col7]), 0) × Z × AE × AG
V = IF(O="SI", tarifa_detención[col8], 0) × Z × AE × AG
```

Reglas concretas:

- **Caliente** si `horas ≤ umbral_caliente`; **fría** si `horas ≥ umbral_fría`;
  **tibia** en otro caso. Bordes **inclusivos** en ambos extremos.
- Si el umbral de fría es 0 (turbinas sin tramos), **siempre tarifa fría**.
- **No existe tramo "Tibia 2"** en el horario. El motor lo tiene (specs 05 y 06).
- `Z` = dólar de la hora (`CMG_CONS_PROP_USD!I`).

**Motor:** tramos `Fria si horas > Fria_Num1_M`, `Caliente si horas < Caliente_Num1_P`,
`Tibia_2 si horas > Tibia_Num2_N`, tibia en otro caso — bordes **estrictos**. Difiere
del horario exactamente en el umbral y en la existencia de Tibia_2.

## 5. Cuándo se cobra la partida — y a qué precio: el MÁXIMO del ciclo

```
Sobrecosto_PD xHyC!N = IF(AND(G="SI", H>0), "SI", 0)     ← hay partida solo si horas_detenida > 0
PARTIDAS_DETENCIONES!S = MAXIFS(Sobrecosto_PD xHyC!U, J, ciclo, G, "SI") × filtro_operacional
PARTIDAS_DETENCIONES!T = MAXIFS(Sobrecosto_PD xHyC!V, J, ciclo, I, "SI") × filtro_operacional
```

**Esta es la fórmula más importante del modelo.** El costo de partida del ciclo
es el **máximo** de los costos horarios de partida entre todas las horas del
ciclo marcadas como partida. Como `U` se calcula por hora **y por
configuración**, si dentro de un mismo ciclo aparecen varias sub-configuraciones
(turbina sola, turbina + vapor, ciclo combinado), **gana la tarifa más cara**.

Esto es exactamente el mecanismo que la spec 15 identificó como "mezcla de
configuraciones hermanas", y explica por qué KELAR-TG12 cobra 60 millones donde
el motor cobra 7,4: el ciclo contiene horas bajo `KELAR-TG1_TG1+0.5TV_DIESEL` y
el `MAXIFS` toma esa tarifa para todo el ciclo.

**Motor v7:** cobra la tarifa de la configuración **instruida por el RIO** en el
bloque de partida (`USAR_TARIFA_RIO_INSTRUIDA = 1`), una sola. Es la diferencia
de regla que domina la brecha (94,8% según el experimento controlado).

## 6. Filtro operacional (motivo / instrucción)

```
factor = IF(OR(P="OM", Q="PDO", AND(P="OT", Z=1)), 1,
            IF(AND(RIGHT(N,2)="&1", P=""), 1, 0))
```

donde `P` = Instrucción (`Instrucciones RIO` col 13 por clave relacionada-hora),
`Q` = Operación (col 14), `Z` = presta SSCC (si el ciclo tiene registro en
`Sobrecosto_Ciclo!S`).

Se paga si:
- motivo **OM**, o
- estado operacional **PDO**, o
- motivo **OT** *y* la central presta SSCC, o
- es el **primer ciclo del mes (`&1`) y no hay instrucción** — se paga igual.

**Motor:** `CODIGOS_EO_VALIDOS = ['PDO']` (spec 03 lo confirmó contra esta
fórmula), `Filtro_Op` por motivo/SSCC. La excepción `&1 sin instrucción` no
existe en el motor: ahí aplica `REGLA_EXENCION = 'sin_historia'`, que exime en
vez de pagar. **Sentido opuesto en el primer ciclo del mes.**

## 7. Filtro de pruebas (EP)

```
Sobrecosto_PD xHyC!AE = IF(COUNTIF(Pruebas!A, Id) > 0, 0, 1)
```

Cero costo si la hora-central figura en la hoja `Pruebas` (lista de datos).

**Motor:** `Filtro_Disp` desde el RIO (`ESTADO OPERACIONAL = EP`). Misma
intención, **fuente distinta**: el horario usa una lista aparte, el motor lee el
RIO.

## 8. Filtro de configuración instruida — solo el combustible

```
Instrucciones RIO!V  = combustible tras "_GN" en la configuración instruida
Instrucciones RIO!U  = clave del ciclo de partida (si consigna PP o PMT)
Sobrecosto_PD xHyC!AF = VLOOKUP(ciclo, Instrucciones RIO!U:V, 2)      ← combustible instruido para ese ciclo
Sobrecosto_PD xHyC!AG = IF(AF="", 1, IF(sufijo_combustible(central) = AF, 1, 0))
```

El horario **no** exige que la configuración instruida coincida; solo que el
**combustible** (sufijo `_GN…` / `_DIESEL`) coincida con el instruido en la
partida (`PP`/`PMT`). Si no hay instrucción, pasa.

**Motor:** no filtra por configuración (`Filtro_Conf` siempre 1 bajo
`USAR_TARIFA_RIO_INSTRUIDA`), pero **cobra la tarifa de la configuración
instruida**, no la propia. Enfoques distintos al mismo problema.

## 9. Margen

```
Sobrecosto_PD xHyC!Y  = IF(X−W < 0, 0, X−W)        W = CV, X = CMg  → truncado POR HORA
Sobrecosto_PD xHyC!AA = (1 − cons_prop) × generación    ← generación neta
Sobrecosto_PD xHyC!AB = Z × Y × AA                      ← USD × diferencia × gen neta
Sobrecosto_Ciclo!E    = SUMIF(AC, ciclo, AB)             ← suma de márgenes YA truncados
```

**Motor:** idéntico con `MARGEN_NETEADO_POR_CICLO = 0`. Verificado en el
experimento controlado: cuatro centrales de ENEL calzan peso a peso. La única
diferencia estructural es `cons_prop`, que el reporte de 15 min no trae; en
junio vale 0 en todas las filas legibles.

## 10. Liquidación del ciclo

```
Sobrecosto_Ciclo!C = SUMIF(PARTIDAS_DETENCIONES!N, ciclo, S)    ← partidas
Sobrecosto_Ciclo!D = SUMIF(…, T)                                  ← detenciones
Sobrecosto_Ciclo!H = IF(C+D+F > E+G, C+D+F − E − G, 0)            ← MAX(0, costos − margen)
```

`F` y `G` son costos y margen heredados de `Ciclos inconclusos` (mes anterior),
solo para el ciclo `&1`.

**Motor:** `Total SC_PD = MAX(0, Costos_Totales_PD − Margen_Suma_Ciclo)`. Idéntico.

## 11. Ciclos de frontera

```
Sobrecosto_Ciclo!B = IF(ciclo ≠ último_ciclo_de_la_central, 1,
                        IF(generación de la central en la última hora del mes = 0, 1, 0))
Sobrecosto_Ciclo!I = IF(B=1, empresa, "Se traspasa al proximo mes")
```

Un ciclo está **completo** si no es el último de su central, o si la central
está en cero en la última hora del mes. Si no, se traspasa: no se liquida este
mes y entra al siguiente vía `Ciclos inconclusos` (columnas F/G del ciclo `&1`).

**Motor:** `DIFERIR_CICLOS_SIN_TERMINAR = 1` (spec 17) — misma regla, distinta
implementación. El motor además **empalma el mes anterior** para calcular
`Horas_Detenida` del primer ciclo; el horario lo resuelve con
`Ciclos inconclusos` y con lo que la macro haya calculado.

## 12. Empresa

```
Sobrecosto_PD xHyC!AI = XLOOKUP(central, Central_Empresa!A, B)
Sobrecosto_Ciclo!I    = VLOOKUP(relacionada, Central_Empresa!A:B, 2)
```

Por configuración, con fallback a relacionada. **Motor:** idéntico
(`Diccionario_central_empresa`, spec 10).

## 13. Cambio de hora

```
PARTIDAS_DETENCIONES!AA = "Hora mes" con ajuste ±1 según Menu!I10 (día "1 hora más") / Menu!I11 ("1 hora menos")
```

El horario corrige manualmente el cambio de hora legal. El reporte de 15 min
ya viene en hora continua; el motor no necesita el ajuste.

---

## Cuadro de diferencias de regla — horario vs motor v7

| # | Regla | Horario | Motor v7 | Efecto medido (2606) |
|---|---|---|---|---|
| 5 | Tarifa de partida del ciclo | **MAX** entre las configuraciones presentes | La configuración **instruida por el RIO** | Domina la brecha: TAMAKAYA −116,6 M, ENEL −71,6 M |
| 4 | Bordes del tramo | `≤ caliente`, `≥ fría` (inclusivos) | `<`, `>` (estrictos) | Solo en horas exactamente iguales al umbral |
| 4 | Tramo Tibia 2 | No existe | Existe (specs 05/06) | No cuantificado |
| 6 | Primer ciclo del mes sin instrucción RIO | **Se paga** (`&1` y `P=""`) | **Se exime** (`sin_historia`) | Sentido opuesto; en 2608 son 60 ciclos |
| 7 | Estado de pruebas | Lista `Pruebas` | RIO `EO = EP` | Fuente distinta, no cuantificado |
| 8 | Configuración instruida | Filtra por **combustible** | Cobra la **tarifa instruida** | Enfoques distintos |
| 9 | Margen | Truncado por hora | Truncado por bloque | **Ninguno** — coinciden al 1% por MWh |
| 9 | Generación neta | `(1 − cons_prop) × gen` | `gen` cruda | Inerte en 2606 (cons_prop = 0) |
| 11 | Frontera | `Ciclos inconclusos` | Empalme del mes anterior | No aislado |
| 1 | Entidad del ciclo | Relacionada | Relacionada (v7) / Turbina (alternativo) | Ver spec 24 |
| 0.a | Corte del ciclo | Cualquier hora en cero, sin tolerancia | Igual (`TOLERANCIA_CORTES_BLOQUES = 0`) | **Ninguno** |
| 0.a | Generación negativa | Cuenta como encendida (`<> 0`) | Cuenta como apagada (`> 0`) | Inerte en 2606 |
| 0.b | Horas detenidas del primer ciclo | **Piso al día 1 00:00** (no carga mes anterior) | Empalme real del mes anterior; nulo si no hay | Opuesto: el horario **cobra** con horas truncadas, el motor **exime** |
| 0.c | Regla `SIF` (6 h) | Existe, inerte en 2606 | No existe | Ninguno este mes |
| 0.d | Partida flag por configuración + ciclo por relacionada + `MAXIFS` | **Es el mecanismo** de la mezcla | Tarifa instruida, una sola | Ver regla 5 |

Las reglas 2, 10, 12 y el corte del ciclo (0.a) son **idénticas**.

---

## Lo que esto cambia en la lectura de la brecha

Con el VBA leído, la diferencia de "horas detenidas del primer ciclo" pasa de
inferencia a hecho, y es más profunda de lo que parecía: **el horario no
empalma el mes anterior en ningún nivel.** Para el primer ciclo de cada central
usa un piso (horas en cero desde el día 1) y una excepción de pago (`&1` sin
instrucción RIO paga igual). El motor hace lo contrario: empalma mayo cuando lo
tiene, y cuando no lo tiene exime.

Eso significa que en un mes sin empalme (como la corrida de agosto) el motor y
el horario divergen **por construcción** en el primer ciclo de cada central:
uno cobra, el otro no. Son 60 ciclos en 2608. No es resolución ni tarifa; es una
decisión de regla que ninguno de los dos modelos documentaba.
