# 31 — Paquete de entrega para auditoría del Coordinador

**Toca código:** sí (`scripts/generar_entrega_cen.py`, runner, interfaz y exposición
de candidatas del motor). **Cambia el monto liquidado:** no.

## Objetivo y operación

La salida oficial del v7 se transforma en una carpeta `Entrega_SCPD_<AAMM>` con
seis CSV UTF-8 y `SCPD_<AAMM>_Auditoria.xlsx`. Puede ejecutarse con el botón
**Generar entrega CEN**, editando las variables `NOMBRE_*` de
`Carpeta_de_Trabajo/correr_entrega.py`, o por consola:

```bash
python scripts/generar_entrega_cen.py Reporte_Sobrecostos_PD_Final.xlsx
```

`parametros.csv` registra los escalares en mayúsculas del panel v7, fecha, commit,
nombre y SHA-256 de cada entrada. `bloques.csv` limita el detalle a etiquetas
publicadas; `ciclos.csv` conserva el orden oficial y agrega la antigüedad de ambas
instrucciones; `candidatas_tarifa.csv` explica la selección máxima sin alterar la
función de liquidación; `empresas.csv` replica el resumen y `diccionario.csv` cubre
todas las columnas anteriores.

## Libro auditable

El libro contiene Leeme, Parametros, Ciclos, Bloques, Candidatas, Empresas,
Resumen_Empresa, Resumen_Central y Diccionario. Las cuatro tablas de datos tienen
tablas Excel, fórmulas estructuradas de margen, costos, SC y checks, formato de
fecha/número y encabezado inmovilizado. Los resúmenes usan SUMIFS. Con
`--tablas-dinamicas` se intenta la automatización protegida de Excel; si no está
disponible se informa y las hojas SUMIFS siguen siendo una entrega válida.

Para resolución `hora` o margen neteado por ciclo no se escribe la fórmula
inexacta de margen por bloque; el valor publicado sigue disponible y Leeme declara
la fórmula base. `Detalle_15Min` ya conserva `CMg`, `CV` y `Dolar` procedentes del
reporte de 15 minutos; el generador garantiza además esas columnas en el CSV, aun
si abre una salida histórica que no las contenía (en tal caso quedan vacías).

## Verificación

La suite sintética debe comprobar los siete artefactos, cobertura del diccionario,
inventario de interruptores, fórmulas/checks y degradación limpia sin Excel. La
validación de agosto real y checks en cero corresponde a Claude, según la bitácora.

## Verificación con datos reales (16-09-2026)

Agosto con julio empalmado, Excel abierto por COM y recalculado: `Check_SC` y
`Check_Margen` = 0 en los 390 ciclos, `Candidatas[Tarifa_max_recalc]` sin errores,
resúmenes por empresa y por central suman 939.959.962 = `SC_por_Empresa`. Cuatro
correcciones fueron necesarias para llegar ahí:

1. **Referencias estructuradas**: xlsxwriter expande `[@Col]` a `[[#This Row],Col]`
   (sin nombre de tabla ni corchetes internos) y Excel no abre el libro sin reparar.
   `_referencias_completas()` escribe `Tabla[[#This Row],[Col]]`.
2. **Insumos del margen**: `Detalle_15Min` no traía `CMg`, `CV`, `Dolar`; el motor ahora
   los exporta (solo columnas, más `UNIDAD GENERADORA`).
3. **Bloques del mes anterior**: `Detalle_15Min` es solo el mes; los ciclos que vienen del
   mes anterior tienen margen de julio. El motor exporta la hoja `Detalle_Frontera` y el
   paquete la concatena (65.657 bloques en agosto, 22.332 de julio).
4. **Candidatas por extremo**: el filtro de combustible se evalúa por separado para la
   partida (instrucción de apertura) y la detención (instrucción de cierre); antes se
   exigían ambos y algunos ciclos quedaban sin candidata.

Además la verificación destapó el erratum de la spec 25 (valorización al dólar del
extremo). `--tablas-dinamicas` sigue siendo un aviso: no crea tablas dinámicas; las hojas
`Resumen_*` con `SUMIFS`/`COUNTIF` son la salida oficial.
