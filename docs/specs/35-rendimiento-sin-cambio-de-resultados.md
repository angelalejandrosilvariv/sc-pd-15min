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

## Escritura de fórmulas de la entrega CEN

Medición del 2026-09-24 en el mismo contenedor y con Python 3.14.4. Los insumos
se generaron con `tests/generar_datos_volumen.py`, semilla 35015, 120
configuraciones y 31 días (357.120 bloques de entrada y 324.896 bloques en
ciclos). Se reutilizó exactamente el mismo XLSX del motor en las dos corridas y
se midió únicamente `generar_entrega`:

```bash
python -c 'from tests.generar_datos_volumen import generar; generar(".perf-data-120", configuraciones=120, dias=31)'
```

La llamada explícita fija el tamaño de aceptación; el valor predeterminado del
generador se conserva para los perfiles generales de 300 configuraciones.

| Entrega CEN | Tiempo (s) |
|---|---:|
| Antes | 2.171,670 |
| Después | 599,951 |

La mejora evita que XlsxWriter pruebe su catálogo completo de expresiones
regulares para cada fórmula. Las tres plantillas que usan `MAXIFS` incluyen de
antemano el prefijo OOXML `_xlfn.` y la hoja especializada se limita a retirar
las llaves de fórmula matricial y el signo igual inicial. Una prueba compara
todas las plantillas con el preprocesamiento original de XlsxWriter para que
una futura función nueva sin prefijo no pueda omitir esa conversión.

## Exportación del libro del motor

La exportación de cada hoja usa ahora `Worksheet.write_row` con valores nativos
y un `Workbook` en modo `constant_memory`. Se conservan las celdas vacías para
`NaN`, `None`, `NaT` y `pd.NA`, los tipos booleano, entero y flotante, y los
formatos de fecha y fecha-hora de pandas. El cálculo de ancho conserva la regla
anterior (máximo entre datos y encabezado, dos caracteres de margen y tope 50),
pero obtiene las longitudes con operaciones vectorizadas en vez de ejecutar una
lambda de Python por celda.

La medición se ejecutó el 2026-09-25 en el mismo contenedor y con Python 3.14.4.
Los insumos se generaron una sola vez con semilla 35015, 120 configuraciones y
31 días: 357.120 bloques de entrada y 324.896 bloques en ciclos. Ambas corridas
usaron exactamente esos archivos y `HORAS_SIN_HISTORIA='nulo'`; el reloj abarca
la llamada completa a `motor.main`.

```bash
python -c 'from tests.generar_datos_volumen import generar; generar(".perf-data-export-120", configuraciones=120, dias=31)'
```

| Motor y Excel | Tiempo (s) |
|---|---:|
| Antes (`DataFrame.to_excel`) | 572,000 |
| Después (`Worksheet.write_row`) | 352,163 |

La prueba dedicada escribe la misma tabla con ambos caminos, la vuelve a leer
con `pandas.read_excel` y exige igualdad exacta de valores/tipos, anchos de
columna, encabezado y formatos temporales. La regresión de punta a punta sigue
protegiendo las huellas de todas las hojas del libro real.

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

## Caché retirado

El caché Parquet se retiró porque no preservaba exactamente los valores del
XLSX: un comentario vacío se leía como `""` desde Parquet y como `NaN` desde
Excel. Esa diferencia cambiaba la evaluación de `extremo()` en la entrega CEN
y podía cambiar `Presta SSCC` de 1 a 0. La entrega y el prorrateo vuelven a leer
siempre el XLSX.

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
