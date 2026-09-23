# 34 — Interfaz con resultados visibles y botón "Prorratear" (PAGA en la entrega CEN)

**Toca código:** sí (`Carpeta_de_Trabajo/interfaz.py`, `src/resumen_salida.py` nuevo,
`src/prorrateo_15min.py`, `scripts/generar_entrega_cen.py`, `scripts/prorratear_pagos_15min.py`,
tests).

**Cambia el monto liquidado:** no. El motor no se toca. La entrega CEN solo cambia si se
le pasa un archivo de retiros: sin él, sale igual que en la spec 32 (PAGA = 0).

**Estado:** implementada y probada con datos sintéticos. Falta la verificación con agosto
(retiros reales) descrita en §5.

---

## 1. Pedido

Del dueño del proyecto (23-09-2026): una interfaz más amigable, donde la salida del motor se
vea mejor y con la información que importa, y un botón **"Prorratear"** para que en la
entrega CEN aparezcan los montos de quienes pagan.

Hasta ahora la columna `RESUMEN!PAGA` de la entrega salía en 0 (spec 32 §4.10: "no hay cuadro
`Pagos` en el motor"), y el prorrateo de la spec 11 existía solo como script aparte
(`correr_prorrateo.py`) sin conexión con la entrega.

## 2. Prorrateo dentro de la entrega CEN

`generar_entrega(..., retiros=RUTA)` y `generar_entrega_cen.py --retiros RUTA` (CSV o Parquet,
mismo formato que la spec 11):

1. Prorratea con la lógica de la spec 11 (`prorratear_ciclos_motor`), usando `Detalle_15Min`
   y `Resumen_Ciclos_PD` del reporte. **Solo reparte ciclos con `Total SC_PD` ≠ 0**: un
   diferido o uno cubierto por el margen no tiene nada que repartir; incluirlos solo generaba
   avisos de "sin retiros" falsos.
2. Agrega la hoja **`Cuadro de pagos`** (después de `RESUMEN`), una fila por ciclo y
   suministrador:

   | Col | Encabezado | Contenido |
   |---|---|---|
   | A | `Ciclo de operación` | etiqueta del ciclo |
   | B | `Suministrador` | del archivo de retiros |
   | C | `Retiro kWh ciclo` | suma de `Medida_kWh` del suministrador en los cuartos del ciclo |
   | D | `Total kWh ciclo` | suma de todos los retiros en los cuartos del ciclo |
   | E | `Prorrata` | `=IF(D2=0,0,C2/D2)` |
   | F | `Total Sobrecosto_P-D` | `=SUMIFS(Sobrecosto_Ciclo!$H,Sobrecosto_Ciclo!$A,A2,Sobrecosto_Ciclo!$B,1)` |
   | G | `PAGA` | `=E2*F2` |

   F toma el mismo H que liquida `Sobrecosto_Ciclo` (solo ciclos completos), así que la
   cadena de fórmulas queda `… → Sobrecosto_Ciclo!H → Cuadro de pagos!G → RESUMEN!B`.
3. `RESUMEN!B` (PAGA) = `=SUMIF('Cuadro de pagos'!$B,A2,'Cuadro de pagos'!$G)`; `SALDO` =
   RECIBE − PAGA. Los suministradores que no reciben se agregan al final del RESUMEN. El cruce
   empresa ↔ suministrador es **por nombre exacto**: una empresa que recibe y además retira
   queda en una sola fila con su saldo neto.
4. `RESUMEN!G1 = SUM(SALDO)` debe dar 0: lo pagado iguala lo recibido. Si algún ciclo con monto
   no tiene retiros en sus cuartos, la consola lo avisa y G1 muestra ese monto.
5. El detalle cuarto a cuarto va a `SCPD_<AAMM>_Prorrateo_Detalle_15min.csv`; el archivo de
   retiros se registra en `Menu` con su SHA-256; `Leeme` agrega la sección "PRORRATEO".

## 3. Interfaz

Pestañas:

- **Configurar**: lo mismo de antes (motor, archivos, salida, métodos), con desplazamiento y
  una marca ✓/✗ por archivo según exista.
- **Resultados**: se llena sola al terminar el motor, al abrir la interfaz si ya hay salida, o
  con "Cargar otra salida…". Muestra el total a pagar, ciclos pagados / cubiertos por el
  margen / rechazados / diferidos, el waterfall "del costo al pago" (hoja `Waterfall_Costos`),
  el resultado de los ciclos, el sobrecosto por empresa, los 15 ciclos de mayor sobrecosto,
  avisos (ciclos con "Revisar", sin empresa, etiquetas repetidas) y los interruptores con que se
  corrió.
- **Pagos (prorrateo)**: archivo de retiros, casilla "Incluir los pagos (PAGA) en la entrega
  CEN", tarjetas de cuadratura (a repartir, repartido, diferencia, suministradores) y la tabla
  de quién paga cuánto.
- **Registro**: la consola del motor, la del prorrateo y la de la entrega.

Barra fija abajo: **▶ Ejecutar motor**, **Prorratear**, **Generar entrega CEN**, versión
(Preliminar/Definitivo) y "Abrir carpeta" (abre la última entrega, si existe).

"Prorratear" calcula y muestra el reparto, deja `Prorrateo_15Min.xlsx` (pagos por
suministrador + cuadratura por ciclo) y `Prorrateo_15Min_Detalle.csv` junto a la salida, y
marca la casilla de incluir pagos. "Generar entrega CEN" pasa `--retiros` cuando la casilla
está marcada. La entrega corre en un proceso aparte y su consola aparece en vivo en Registro.

La lectura de la salida (`src/resumen_salida.py`) es independiente de tkinter y tiene pruebas
propias.

## 4. Pruebas

- `tests/test_generar_entrega_cen.py`: con retiros, la hoja nueva queda después de RESUMEN, los
  montos por ciclo y suministrador son los esperados, el diferido no se reparte, E1 (que recibe
  y paga) queda con saldo neto, `SUM(SALDO) = 0`, están las fórmulas, `Leeme` y `Menu`. Sin
  retiros, PAGA = 0 y no hay cuadro.
- `tests/test_resumen_salida.py`: indicadores, clasificación de ciclos, formatos CLP/MM, avisos y
  prorrateo desde el reporte (solo ciclos con monto).
- `tests/test_prorrateo_15min.py`: resumen por ciclo y suministrador cuadra con el detalle.
- La interfaz se manejó bajo Xvfb con una salida sintética: carga de resultados, prorrateo y
  entrega con pagos de punta a punta.

## 5. Verificación pendiente (Claude, con datos reales)

1. `Prorratear` con la salida de agosto y los retiros reales: la diferencia debe ser 0 o
   explicarse por ciclos sin retiros.
2. `Generar entrega CEN` con pagos, abrir en Excel: `RESUMEN!G1` ≈ 0 y
   `Cuadro de pagos!G` recalculado igual al valor guardado.
3. Revisar si los nombres de `Suministrador` del archivo de retiros coinciden con los de
   `Empresa` del diccionario. Si no, hace falta una tabla de equivalencias; esta spec no la
   crea.
