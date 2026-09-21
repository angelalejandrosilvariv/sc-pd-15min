# 33 — Interruptor: partida sincronizada en pruebas (EP) tras una orden de partida fallida

**Toca código:** sí (`src/sc_pd_motor_v7.py`, `Carpeta_de_Trabajo/correr_motor.py`,
`Carpeta_de_Trabajo/interfaz.py`, `tests/test_partida_en_pruebas.py`, `Guia_Lectura`).

**Cambia el monto liquidado:** sí, cuando se activa. Nace **apagado**
(`PARTIDA_EN_PRUEBAS = 'rechazar'`, comportamiento actual) y se activa desde el panel, el
runner o la interfaz. Decisión del 21-09-2026: la característica queda disponible como
opción mientras el CEN resuelve la observación de Guacolda.

**Estado:** especificada; implementación por Codex; verificación con agosto por Claude.

---

## 1. El caso

Observación de la empresa al Excel horario de agosto 2026: *"Se solicita incorporar el
pago por costo de partida fría de Guacolda 1, por la partida instruida a las 23:16 del
21/08/2026 … respaldada por la PID 20260822_01"*. El RIO (ya con la corrección
O2026-0050411 incorporada) dice, para `GUACOLDA-1_CAR`:

| ID RIO | Fecha / hora | CON | MOT | EO | Comentario |
|---|---|---|---|---|---|
| 2791340 | 21/08 23:16 | PP | OM | DRO | — |
| 2791342 | 22/08 12:16 | FS | OT | DF | "Falla en la pártida" (IF 2026004644) |
| 2776722 | 23/08 00:50 | EP | EP | PO | "E/S en pruebas, según IF 2026004644." |
| 2776857 | 23/08 05:00 | MT | OM | RO | "Disponible y cancela IF 2026004644." |
| 2777693 | 23/08 09:00 | PS | OM | RO | — |

Generación: 0 MWh el 21 y el 22; primer bloque con generación el 23/08 00:45. El motor
abre `GUACOLDA-1_CAR&1` a las 00:45, la instrucción vigente es EP y rechaza la partida
("Máquina en Pruebas"); paga la detención OM (1,29 MM). Tarifa de la partida fría (908 h
detenida): 68,58 MM; margen del ciclo 0.

Lectura del dueño del proyecto: el EP no fue una prueba por decisión de la empresa sino
el cierre de la partida **que el CEN ordenó por mérito** y que sufrió una falla; la
cancelación del IF con la unidad disponible bajo OM, sin haberse detenido, lo confirma.
Bajo esa lectura la partida es válida.

## 2. Por qué no basta con "queda disponible OM"

En agosto hay 21 ciclos con partida rechazada por EP (344,9 MM de tarifas). En 13 el RIO
deja después la unidad disponible con OM ("cancela IF / SDCF / MM / DI") sin detenerse.
Pero las cronologías son tres:

| Grupo | Qué pasó | Ciclos 2608 | Δ SC si se paga |
|---|---|---|---|
| **1. Orden OM fallida** | PP/PMT OM → la unidad **no sincroniza** → falla (DF / IF) → reingreso EP → disponible OM | GUACOLDA-1&1, CHUYACA_DIESEL&3 | **+69,0 MM** |
| 2. Salida intempestiva | operando bajo OM → dispara (FS OT DF "salida intempestiva", IF) → reingreso EP → cancela IF | ATACAMA-1TG1AB&5, MEJILLONES-CTM3&5, SANISIDRO-1&6, GUACOLDA-3&1, GUACOLDA-3&2, GUACOLDA-4&1, TOCOPILLA-U16&1 | +67 MM (el resto del grupo da 0 por margen) |
| 3. Retorno de mantención | sin orden previa; sincroniza en pruebas al salir de MM / SDCF → cancela MM/SDCF con OM | TOCOPILLA-U16&2, NEHUENCO-2&3, SANISIDRO-2&1, GUACOLDA-5&1 | +109 MM |

El argumento de la observación (el CEN ordenó, la orden falló, la unidad completó la
orden) solo describe al grupo 1. En el 2 la repartida la provoca la falla de la propia
central en operación; en el 3 la sincronización en pruebas es decisión de la empresa. Por
eso el interruptor distingue las dos lecturas y ninguna se activa sola.

## 3. El interruptor

```python
# Partida cuya instruccion vigente es EP (maquina en pruebas).
#   'rechazar'                        = comportamiento actual: no se paga (spec 27 / decision 7).
#   'validar_orden_om_fallida'        = se paga si el CEN habia ordenado la partida (PP/PMT con
#                                       motivo valido) dentro de VENTANA_ORDEN_FALLIDA_H horas,
#                                       esa orden no llego a sincronizar (sin generacion entre la
#                                       orden y el inicio del ciclo) y dentro del ciclo el RIO deja
#                                       la unidad disponible con motivo valido sin detenerse.
#   'validar_si_queda_disponible_om'  = se paga toda partida EP que dentro del ciclo queda
#                                       disponible con motivo valido sin detenerse (incluye
#                                       salidas intempestivas y retornos de mantencion).
# CAMBIA EL MONTO A PAGAR. Ver docs/specs/33-partida-en-pruebas-tras-orden-fallida.md
PARTIDA_EN_PRUEBAS = 'rechazar'
PARTIDAS_EN_PRUEBAS_VALIDAS = ('rechazar', 'validar_orden_om_fallida', 'validar_si_queda_disponible_om')
VENTANA_ORDEN_FALLIDA_H = 48
```

Cualquier otro valor aborta con mensaje, como `TARIFA_CONFIGURACION`.

## 4. La regla

Se aplica en la sección 14 del motor, **después** de la búsqueda relajada y **antes** de
`costos_clasicos()`, solo a los ciclos con `Filtro_Disp_Partida == 0` cuya
`Consigna_Partida` (tras la búsqueda relajada) sea `EP`. Sea `rel` la central
relacionada, `t0 = Inicio_Ciclo`, `t1 = Termino_Ciclo`.

**Motivo válido** de un registro RIO: el mismo criterio de `calcular_filtros` sin la
exención: `MOTIVO == 'OM'` o `ESTADO OPERACIONAL ∈ CODIGOS_EO_VALIDOS` o (`MOTIVO == 'OT'`
y comentario con `SSCC|CTF|CSF|CPF`).

**Condición D (queda disponible)**: existe un registro RIO de `rel` con `t0 ≤ t ≤ t1`,
`CONSIGNAS ∉ {EP, FS, PS}` y motivo válido. El primero de esos registros es `t_disp`.

**Condición O (orden fallida)**: existe un registro RIO de `rel` con `CONSIGNAS ∈ {PP,
PMT}`, motivo válido y `t0 − VENTANA_ORDEN_FALLIDA_H h ≤ t < t0`; el último es `t_orden`.
Y **no hay generación** de `rel` en ningún bloque con `t_orden ≤ FECHA_HORA < t0` (se
evalúa sobre `reporte`, el reporte completo antes de quitar ceros, sumando todas las
configuraciones de la relacionada). Si hubo generación, la orden ya produjo otro ciclo y
no aplica.

| `PARTIDA_EN_PRUEBAS` | Se valida si |
|---|---|
| `'rechazar'` | nunca |
| `'validar_orden_om_fallida'` | D **y** O |
| `'validar_si_queda_disponible_om'` | D |

**Efecto al validar** (solo la partida; la detención no cambia):

- `Filtro_Disp_Partida = 1`, `Filtro_Op_Partida = 1`, `Vigencia_RIO_Partida = 1`.
- La instrucción de la partida pasa a ser la que la justifica, para que la cadena del
  libro de auditoría (spec 32, `PARTIDAS_DETENCIONES!S`) la reproduzca: con O,
  `Consigna_Partida / Motivo_Partida / Estado_Op_Partida / Comentario_Partida /
  Fuente_Filtros_RIO_Partida` toman los valores del registro de `t_orden`; solo con D, los
  del registro de `t_disp`.
- El registro EP original se conserva en columnas nuevas: `Consigna_Reingreso_Pruebas`
  (`EP`), `Fuente_Reingreso_Pruebas` (timestamp), `Comentario_Reingreso_Pruebas`.
- Columnas nuevas de auditoría: `Partida_En_Pruebas_Validada` (`''`, `'orden OM
  fallida'` o `'queda disponible OM'`), `Orden_Partida_Fallida` (`t_orden` o NaT),
  `Disponible_OM_Desde` (`t_disp`).
- `Obs_Partida`: `"Aprobado: partida en pruebas validada — orden {CON} {MOT} del
  {t_orden:%d/%m %H:%M} sin sincronizar; disponible {MOT} el {t_disp:%d/%m %H:%M}"` (o la
  variante sin orden). Se escribe en `asignar_observaciones_liquidacion` o justo después,
  sin romper las observaciones existentes.
- Tramo y tarifa **no cambian**: siguen saliendo de `Horas_Detenida_Ciclo` y de la
  configuración ganadora (spec 25). Las horas detenidas de GUACOLDA-1 son las 908 h
  reales; la orden fallida no cuenta como operación.

**Lo que no hace**: no toca ciclos cuya partida ya estaba aprobada, ni la detención, ni el
diferimiento, ni el margen. Con `'rechazar'` el motor es idéntico al actual (misma suite,
mismos 939.959.962 en agosto).

## 5. Consola

Bloque `PARTIDA EN PRUEBAS (EP)` en la sección 14: valor del interruptor; ciclos con
partida EP; cuántos cumplen D, cuántos D y O; ciclos validados con `t_orden`, `t_disp`,
tarifa y Δ del `Total SC_PD`; total del impacto. Con `'rechazar'` imprime igual el
diagnóstico (cuántos habrían pasado con cada variante) sin cambiar nada: es la
sensibilidad que el CEN necesita ver.

## 6. Export

`columnas_resumen_ciclos` inserta, antes de `Costo_Partida_Efectivo`:
`Partida_En_Pruebas_Validada`, `Orden_Partida_Fallida`, `Disponible_OM_Desde`,
`Consigna_Reingreso_Pruebas`, `Fuente_Reingreso_Pruebas`, `Comentario_Reingreso_Pruebas`
(siempre presentes; vacías con `'rechazar'`). `Parametros_Motor` ya recoge el interruptor
por ser escalar en mayúsculas. `Guia_Lectura` explica las seis columnas y el interruptor.

El generador de la entrega (spec 32) no necesita cambios: `PARTIDAS_DETENCIONES!P/Q/Z/AF/AG`
leen `Motivo_Partida`, `Estado_Op_Partida`, `Comentario_Partida`, `Vigencia_RIO_Partida`
y `Filtro_Disp_Partida`, que ya traen la instrucción validada.

## 7. Runner e interfaz

- `correr_motor.py`: variable `PARTIDA_EN_PRUEBAS = "rechazar"` con el comentario del
  panel, pasada en el diccionario a `motor.main`.
- `interfaz.py`: radio **"Partida sincronizada en pruebas (EP) — solo motor v7"** con tres
  opciones: *Rechazar (vigente)*, *Validar si el CEN la ordenó y la orden falló antes de
  sincronizar*, *Validar si queda disponible con motivo válido en el mismo ciclo*. Mismo
  patrón que el radio de tarifa (spec 25). El motor Turbina y Reglas del Horario no lo
  usan.

## 8. Pruebas (`tests/test_partida_en_pruebas.py`, sintéticas)

Construir compacto + RIO + reporte mínimos y verificar:

1. Valor inválido aborta.
2. `'rechazar'`: ciclo EP queda rechazado y las seis columnas nuevas existen vacías.
3. Caso Guacolda (PP OM a −25 h, FS DF, EP al inicio, MT OM dentro del ciclo, sin
   generación entre orden e inicio): `'validar_orden_om_fallida'` lo valida; toma la
   instrucción de la orden (`Motivo_Partida = 'OM'`, `Consigna_Partida = 'PP'`);
   `Costo_Partida_Efectivo = Costo_Partida_Base × Conf × CostoCero`; la detención no cambia.
4. Mismo caso pero con generación entre la orden y el inicio (la orden sí sincronizó y
   hubo otro ciclo): `'validar_orden_om_fallida'` **no** lo valida;
   `'validar_si_queda_disponible_om'` sí.
5. Ciclo EP sin registro disponible OM dentro del ciclo (pruebas puras): ninguna
   variante lo valida.
6. Orden fuera de `VENTANA_ORDEN_FALLIDA_H`: no valida con `'validar_orden_om_fallida'`.
7. El registro disponible debe estar dentro del ciclo: uno posterior a `Termino_Ciclo`
   no cuenta.
8. Un registro `OT` con comentario `SSCC` cuenta como motivo válido; uno `OT` sin SSCC no.
9. `columnas_resumen_ciclos` contiene las seis columnas en su lugar y `Guia_Lectura` las
   describe.

## 9. Verificación con datos reales (Claude)

Agosto con julio: `'rechazar'` = 939.959.962 (sin cambio). `'validar_orden_om_fallida'`
debe validar GUACOLDA-1&1 (+68,58 MM) y evaluar CHUYACA_DIESEL&3 (depende de si el RIO la
deja disponible OM dentro del ciclo); ningún otro. `'validar_si_queda_disponible_om'`
debe validar los 13 ciclos de la §2 (+244,9 MM). Junio con mayo para regresión.
Resultados a esta spec y a la bitácora.

## 10. Pendiente de negocio

La decisión de fondo (si el CEN paga la partida ordenada que falló, y con qué evidencia)
no está tomada; el interruptor deja las dos lecturas corribles y el bloque de consola
muestra la sensibilidad de cada una. Los grupos 2 y 3 de la §2 (salidas intempestivas y
retornos de mantención) quedan documentados como casos distintos al de Guacolda.
