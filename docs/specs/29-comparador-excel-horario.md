# 29 — Comparador oficial contra el Excel horario del CEN

**Toca código:** sí (`scripts/comparar_con_excel_horario.py`,
`Carpeta_de_Trabajo/correr_comparacion.py`)

**Cambia el monto liquidado:** no. Es una herramienta de conciliación; no modifica
ningún motor.

---

## 1. Objetivo

Formalizar los análisis manuales de agosto de 2026 en una herramienta repetible. La
entrada es la salida `Reporte_Sobrecostos_PD_Final.xlsx` del v7 y el libro horario
`.xlsm` del CEN. El libro horario se abre con `openpyxl` en modos `read_only` y
`data_only`.

## 2. Alcances y apareo

Se publican dos alcances: mes completo, usando el SC publicado del Excel, y ciclos que
inician y terminan dentro del mes. En el segundo, el motor se filtra por
`Estado_Ciclo_Mes`; el Excel excluye traspasos y ciclos cuya primera hora de generación
sea la hora 1 del día 1, y recalcula `MAX(0, partida + detención - margen)` sin herencia.
Las fechas Excel son el mínimo y máximo `fecha + hora - 1` con generación positiva.

El apareo es por central relacionada y traslape temporal. Como el dato Excel es
horario, su término se extiende 59 minutos. Los ciclos no apareados se conservan.

## 3. Diagnóstico

Cada delta se descompone por sustitución secuencial de partida, detención y margen en
`MAX(0, P + D - M)`. Una aserción garantiza que los efectos reconstruyan el delta. Las
causas R1/R1b, R2, R3, R4, R5 (con subtipos), R6, R7 y R9 reproducen las definiciones
del informe y usan los internos de `Sobrecosto_PD xHyC`, `PARTIDAS_DETENCIONES` y las
observaciones/vigencias del motor.

## 4. Salida

El libro contiene `Resumen`, `Por_Empresa`, `Pares`, `Causa_Raiz`,
`Causa_x_Empresa`, `Ciclos_Excel` y `Frontera`. Las tres primeras tablas ejecutivas
requeridas (`Resumen`, `Por_Empresa`, `Causa_Raiz`) también se imprimen en consola.
`Frontera` reúne ciclos del motor fuera del mes y ciclos `&1` del Excel con herencia.

## 5. Operación

Copiar ambos libros a `Carpeta_de_Trabajo`, editar las tres variables `NOMBRE_*` de
`correr_comparacion.py` y ejecutar el runner. También existe CLI:

```bash
python scripts/comparar_con_excel_horario.py MOTOR.xlsx HORARIO.xlsm SALIDA.xlsx
```

## 6. Validación y pendientes

La prueba automatizada usa libros pequeños creados en tiempo de ejecución y cubre
fechas, SC propio, traslape/no traslape, ciclos exclusivos, identidad algebraica con
el truncamiento activo y familias de causa. No se versionan datos operacionales.

**Pendiente:** Claude ejecutará la verificación con los datos reales del CEN.
