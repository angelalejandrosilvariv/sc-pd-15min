# 35 — Rendimiento sin cambio de resultados

## Método

`tests/generar_datos_volumen.py` crea, con semilla 35015, un mes de 31 días,
300 configuraciones (892.800 bloques), 80 suministradores, RIO con encabezado
en la fila 5, costos, diccionarios y frontera del mes anterior. La variante
`--rapido` conserva los casos funcionales con 8 configuraciones y 3 días.

`scripts/perfilar_flujo.py` ejecuta las tres etapas en el mismo proceso, guarda
un perfil `cProfile` y el top 30 acumulado por etapa, y registra reloj y RSS
máximo en `metricas.json`:

```bash
python scripts/perfilar_flujo.py --datos .perf-data --salida .perf-results
```

## Medición reproducible de desarrollo

Medición del 2026-09-23 en el mismo contenedor, Python 3.14.4, conjunto rápido.
La primera corrida no tenía motor Parquet; la segunda tenía `pyarrow` 21.0.0.

| Etapa | Antes (s) | Después (s) | RSS antes (MiB) | RSS después (MiB) |
|---|---:|---:|---:|---:|
| Generar/leer insumos | 2,41 | 2,32 | 90,5 | 152,1 |
| Motor y Excel | 13,01 | 12,21 | 122,0 | 192,2 |
| Prorrateo | 3,56 | 3,02 | 125,6 | 197,5 |
| Entrega CEN | 26,25 | 26,93 | 125,6 | 197,5 |

Esta muestra es demasiado pequeña para que la relectura de `Detalle_15Min`
domine y el RSS absoluto incluye la memoria cargada por `pyarrow`. La medición
de aceptación debe ejecutarse sin `--rapido`; el script queda preparado para
ello y evita mezclar máquinas o insumos. No se proclama una mejora en entrega
con base en ruido de esta muestra.

## Cambio aplicado

El motor continúa escribiendo exactamente el mismo XLSX y, si existe un motor
Parquet, deja además `<Reporte>_cache/*.parquet`. Prorrateo y entrega consultan
las hojas de ese caché sólo si el directorio es al menos tan nuevo como el
XLSX; ante hoja ausente, caché viejo, error o dependencia ausente vuelven al
Excel. Las hojas con tipos mixtos que Arrow no representa no se convierten ni
se fuerzan: conservan el camino Excel. Esto evita modificar valores para hacer
que el caché funcione.

## Alternativas descartadas

* No se cambió `iterrows`/`apply` en la selección RIO: reproducir todos los
  desempates sin una referencia completa de volumen era un riesgo de resultado.
* No se usó `constant_memory` para el libro del motor: XlsxWriter puede alterar
  capacidades y orden de escritura; el XLSX contractual se dejó intacto.
* `python-calamine` y `pyarrow` siguen opcionales y no entran en requirements.
* No se cambiaron sumas/groupby ni su orden, por lo que no hay diferencias de
  coma flotante que justificar.

## Regenerar referencias tras un cambio deliberado de negocio

La referencia se versiona como JSON de texto (`tests/golden/entrega_sintetica.json`),
no como `.gz`, para que la plataforma del PR pueda inspeccionar y comparar el
contenido sin tratarlo como un archivo binario.

1. Crear una rama desde el commit inmediatamente anterior a la nueva regla.
2. Generar los insumos rápidos con semilla fija.
3. Ejecutar motor, prorrateo y entrega para cada combinación documentada del
   panel y archivar hojas, CSV y texto de fórmulas.
4. Revisar y aprobar el delta de negocio antes de sustituir `tests/golden/`.
5. Ejecutar `pytest -q` y el perfil completo, conservando ambos `metricas.json`.
