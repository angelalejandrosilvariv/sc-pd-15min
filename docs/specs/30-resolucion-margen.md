# 30 — Resolución temporal configurable del margen

**Toca código:** sí (`src/sc_pd_motor_v7.py`, `Carpeta_de_Trabajo/correr_motor.py`,
`Carpeta_de_Trabajo/interfaz.py`, `tests/test_resolucion_margen.py`).

**Cambia el monto liquidado:** solo al seleccionar `'hora'`. El default
`RESOLUCION_MARGEN = 'bloque'` conserva exactamente el cálculo anterior.

## Problema y regla

El motor v7 calcula `MAX(0, CMg − CV) × Dólar × Generación` por cuarto de hora,
mientras el Excel horario aplica el `MAX` después de llevar los datos a una hora.
Por convexidad, las variaciones alrededor del CV pueden acreditar más margen en la
resolución de 15 minutos. No es un defecto de ninguno de los cálculos: son dos
resoluciones distintas que ahora pueden compararse dentro del mismo motor.

Con `'hora'`, `margen_por_hora()` agrupa por `(Central,
FECHA_HORA.floor('h'))`: suma generación; calcula CMg y CV ponderados por generación
(promedio simple si la suma es cero); promedia Dólar en forma simple; y calcula el
margen horario. Después lo distribuye entre los bloques en proporción a su
generación, de modo que `Detalle_15Min` y la agregación posterior por ciclo no
cambian. Las horas incompletas se calculan con los bloques disponibles.

`MARGEN_NETEADO_POR_CICLO = 1` evita el truncamiento horario y conserva el signo,
igual que antes lo hacía por bloque, para que el neteo ocurra al compactar el ciclo.
Con generación horaria cero, el margen y su reparto son cero.

## Superficies y validación

- Panel del v7: `RESOLUCION_MARGEN = 'bloque' | 'hora'`; un valor distinto aborta
  con un mensaje explícito.
- Consola: `CRITERIO DE MARGEN` declara la resolución; con `'hora'` muestra como
  referencia el total que habría resultado con `'bloque'`.
- `Guia_Lectura`, runner de Spyder e interfaz documentan/exponen el interruptor.
  El radio queda deshabilitado para Turbina y Reglas del Horario, cuyos motores no
  fueron modificados.

## Pruebas

`tests/test_resolucion_margen.py` cubre: default sin regresión; equivalencia cuando
CMg es constante dentro de la hora; desigualdad convexa y conservación de la suma
al repartir; hora incompleta; conservación del signo con neteo; y rechazo del valor
inválido.

La verificación con archivos operacionales queda a cargo de Claude.
