# 27 — Interruptor: vigencia de la instrucción RIO que justifica una partida o detención

**Toca código:** sí (`src/sc_pd_motor_v7.py`, `Carpeta_de_Trabajo/correr_motor.py`,
`Carpeta_de_Trabajo/interfaz.py`, `tests/test_vigencia_instruccion_rio.py`)

**Cambia el monto liquidado:** sí. Nace **activo** (`VIGENCIA_INSTRUCCION_RIO_MIN = 30`)
por decisión del 15-09-2026: *"solo deberíamos buscar en ±30 minutos"*. Con 0 el
motor vuelve al comportamiento anterior.

---

## 1. El problema

El cruce maestro con el RIO (sección 10) asocia a cada bloque la **última
instrucción anterior**, hasta 24 horas atrás (`merge_asof` backward, tolerancia 24 h).
Los filtros de partida y detención (sección 11) leen motivo, consigna y estado de esa
instrucción. Si el resultado no pasa, la búsqueda relajada (sección 14) revisa
±`VENTANA_CUARTOS_HORA` cuartos (±30 min) y toma el registro que pase más filtros.

La asimetría es que hacia adelante el motor mira 30 minutos, pero hacia atrás 24
horas. Una instrucción OM emitida la noche anterior para otro evento habilitaba la
partida o detención de hoy. Casos reales de agosto 2026 (`ventana_rio.py`):

| Ciclo | Evento | Última instrucción anterior | Antigüedad |
|---|---|---|---|
| NUEVARENCA_TG1+TV1 &5 | partida 16-ago 16:30 | PP / OM 15:00 (y PMT / OM a las 17:01, +31 min) | 90 min |
| CORONEL &3, &5, &7, &8, &9, &12, &17 | detenciones | PP / PS / FS con OM de la mañana o del día anterior | 12–24 h |
| TENOGAS_GLP &16 | partida y detención 20-ago | PP / OT 04:06 | 14 h |
| EMELDA-2 &1 | detención 27-ago 22:45 | FS / OM 22:04 | 41 min |

## 2. La regla

`Filtro_Operacional = f_op × Vigencia_RIO`, con

```
Vigencia_RIO = 1  si  (FECHA_HORA − Fuente_Config_RIO) ≤ VIGENCIA_INSTRUCCION_RIO_MIN
             = 1  si  no hay instrucción (NaT) — la exención 'sin_historia' ya trata ese caso
             = 1  si  la instrucción es posterior al bloque (rescatada en ventana)
             = 0  en otro caso
```

Se evalúa por bloque; el compacto toma el primer bloque para la partida y el último
para la detención (`Vigencia_RIO_Partida / Detencion`). La búsqueda relajada sigue
mirando ±30 min y solo puede rescatar el ciclo con una instrucción cercana, así que la
ventana efectiva es **[−VIGENCIA, +VENTANA_CUARTOS_HORA × 15] minutos** alrededor del
inicio o término del ciclo. Con 30 y 2, ±30 min.

Lo que **no** cambia: `Configuracion RIO` por bloque (tarifa instruida, filtro de
combustible de la spec 25, auditoría de cobertura) sigue saliendo del cruce a 24 h;
`Filtro_Disp` (EP) tampoco se limita — una unidad declarada en pruebas sigue en
pruebas hasta nueva instrucción.

## 3. Impacto medido

| Corrida | `VIGENCIA = 0` (anterior) | `VIGENCIA = 30` | Δ |
|---|---:|---:|---:|
| 2608 sin julio, tarifa máxima | 875.313.107 | **857.661.488** | −17.651.618 |
| 2606 con empalme 2605, tarifa máxima | 1.080.340.995 | **1.063.758.505** | −16.582.490 |

Agosto: 11 ciclos, todos "inicia y termina este mes": NUEVARENCA &5 −8,56 MM (la partida
del 16-ago pierde su instrucción PP de 90 min antes; el PMT de +31 min queda un minuto
fuera de la ventana), CORONEL 7 detenciones −8,05 MM, EMELDA-2 −0,5, TENOGAS −0,39,
CMPCCORDILLERA −0,15. Todos aparecen con `Obs = "Rechazo: instruccion RIO fuera de
vigencia (> 30 min)"`.

Sensibilidad (agosto, ciclos completos, `ventana_rio.py`):

| Ventana hacia atrás | Partidas que caen | CLP | Detenciones que caen | CLP |
|---|---:|---:|---:|---:|
| 30 min | 4 | 25,4 MM | 12 | 14,2 MM |
| 60 min | 4 | 25,4 MM | 9 | 11,5 MM |
| 120 min | 3 | 1,0 MM | 6 | 8,2 MM |
| 240 min | 3 | 1,0 MM | 2 | 1,2 MM |

Advertencia para quien fije el valor: entre 30 y 120 minutos la diferencia son
partidas con una instrucción **PP / OM** (programación de partida) emitida 60–90 min
antes del primer bloque, que es el plazo normal de sincronización de un ciclo
combinado. Con 30 min, NUEVARENCA &5 se rechaza pese a tener PP 15:00 y PMT 17:01 para
una partida a las 16:30.

## 4. Implementación

- Panel: `VIGENCIA_INSTRUCCION_RIO_MIN = 30`.
- `filtro_vigencia_rio(fecha_hora, fuente_rio, vigencia_min)`: función pura, devuelve
  el multiplicador 0/1 por bloque.
- Sección 11: `Vigencia_RIO` por bloque y `Filtro_Operacional = f_op × Vigencia_RIO`;
  consola con el número de bloques con motivo válido pero instrucción vencida.
- `compactar_resumen_ciclos`: `Vigencia_RIO_Partida` (first) y `Vigencia_RIO_Detencion`
  (last); si el detalle no trae la columna (pruebas) se asume 1.
- Sección 14.7: observación específica `Rechazo: instruccion RIO fuera de vigencia (> N
  min)` en vez de "Sin Motivo ni SSCC".
- Export: las dos columnas junto a `Filtro_Op_*`; `Guia_Lectura`.
- `correr_motor.py` e `interfaz.py` (campo "Aceptar como justificación una
  instrucción RIO dada hasta N min antes").

## 5. Pruebas

`tests/test_vigencia_instruccion_rio.py`, 5 casos: 0 no limita; 30 acepta hasta 30 y
rechaza 31+; una instrucción posterior al bloque es vigente; sin instrucción no se
toca (exención); columnas exportadas junto a los filtros. Suite: **99 pruebas**.

## 6. Pendientes

1. El valor de la ventana es decisión de negocio. 30 min está aplicado; la tabla de
   sensibilidad muestra qué se pierde y a qué costo con 60, 120 o 240.
2. Alternativa no implementada: aceptar hacia atrás sin límite solo instrucciones
   cuya consigna sea de partida (PP/PMT) para partidas y de parada (PS/FS) para
   detenciones. Resolvería NUEVARENCA &5 sin abrir la puerta a instrucciones de otro
   evento; quedaría como `VIGENCIA_POR_CONSIGNA` si se pide.
