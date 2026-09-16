# 31 — Paquete de entrega para auditoría del Coordinador

**Toca código:** sí (`scripts/generar_entrega_cen.py`, runner, interfaz y exportación
de auditoría de `src/sc_pd_motor_v7.py`).

**Cambia el monto liquidado:** no. Solo expone insumos y genera artefactos de revisión.

## 1. Objetivo y contenido

`generar_entrega_cen.py` transforma la última salida del v7 en una carpeta
`Entrega_SCPD_<AAMM>` con cinco CSV de datos/parámetros, un diccionario CSV y un libro
`Auditoria.xlsx`. Incluye hashes SHA-256 de entradas, commit, fecha UTC e interruptores.

Los CSV contienen bloques de ciclos liquidados, ciclos completos en el orden del
resumen del motor, candidatas de tarifa, empresas y metadatos. El diccionario cubre
todas sus columnas y aprovecha `Guia_Lectura`.

## 2. Trazabilidad añadida al motor

El detalle conserva `CMg`, `CV` y `Dolar`; si internamente solo existe
`Valor_Dolar`, se publica además el alias `Dolar`. Se exporta `Candidatas_Tarifa`,
obtenida por `candidatas_tarifa_configuracion()`: la función replica los filtros de
combustible y costo cero y marca la configuración elegida, pero no alimenta ni cambia
el cálculo de liquidación.

## 3. Libro auditable

El libro tiene `Leeme`, `Parametros`, `Ciclos`, `Bloques`, `Candidatas`, `Empresas`,
`Resumen_Empresa`, `Resumen_Central` y `Diccionario`. Sus tablas contienen fórmulas
estructuradas para recalcular margen, costos efectivos, SC, diferencias y tarifa
máxima. Si el margen se netea por ciclo o se resuelve por hora, el recálculo por bloque
se deja sin fórmula y `Leeme` conserva los interruptores que explican el criterio.

Los resúmenes SUMIFS siempre quedan disponibles. `--tablas-dinamicas` intenta usar
Excel mediante un import protegido de `win32com`; su ausencia solo produce un aviso.

## 4. Operación y validación

Se puede usar el botón **Generar entrega CEN**, editar las variables `NOMBRE_*` de
`Carpeta_de_Trabajo/correr_entrega.py`, o ejecutar:

```bash
python scripts/generar_entrega_cen.py Reporte_Sobrecostos_PD_Final.xlsx
```

Los tests construyen una salida sintética, verifican los siete archivos, cobertura del
diccionario, parámetros, fórmulas y funcionamiento sin Excel instalado. Claude debe
validar agosto real y confirmar `Check_SC = Check_Margen = 0`.
