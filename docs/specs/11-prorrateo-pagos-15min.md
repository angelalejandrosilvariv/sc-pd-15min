# Spec 11 — Prorrateo de pagos SC P-D a nivel de 15 minutos

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — archivos nuevos `src/prorrateo_15min.py` y
`scripts/prorratear_pagos_15min.py`, más sus tests

## Contexto

El dueño del proyecto tiene, fuera de este repositorio, un script de
liquidación **horaria** (`prorratas_pagos_PD.py`, no forma parte de este
repo) que reparte el costo total de cada ciclo de partida/detención entre
los `Suministrador` del mercado, en proporción a cuánta energía retiró
cada uno durante las horas en que ese ciclo estuvo activo. Su lógica,
resumida:

1. Lee de un Excel (hoja "Datos Access") dos tablas dinámicas armadas a
   mano: `Ciclo -> Hora_Mensual` (qué horas del mes pertenecen a cada
   ciclo) y `Ciclo -> Precio` (el costo total del ciclo, columna G).
2. Lee retiros horarios desde un Parquet (`Retiros_h.parquet`), agrupados
   por `Hora_Mensual` + `Suministrador`, sumando `Medida_kWh`.
3. Cruza `Ciclo -> Hora_Mensual` con los retiros **por `Hora_Mensual`
   solamente** (no por central) — así, si dos ciclos de centrales
   distintas están activos en la misma hora, ambos "ven" el mismo retiro
   total del sistema en esa hora. Es decir, el reparto es por ventana
   temporal del ciclo, no por relación central-suministrador.
4. Para cada ciclo: `Total_kWh_Ciclo` = suma de `Medida_kWh` de todas las
   filas (hora + suministrador) que cayeron en sus horas activas.
   `Prorrata = Medida_kWh_Hora / Total_kWh_Ciclo`.
   `Monetario_Hora = Prorrata * Precio_Ciclo`.
5. Arma un resumen por `Suministrador` (suma de `Monetario`) y una
   auditoría de cuadratura por ciclo: `Delta_Ciclo = Precio - Monetario_Repartido`,
   alertando si `|Delta_Ciclo| > 0.01`.
6. Exporta un Excel resumen y un CSV de detalle en formato "Power Query"
   (separador `;`, coma decimal).

El dueño del proyecto ahora recibirá los retiros a **resolución de 15
minutos** en vez de horaria (muestra: `prueba_de_retiros_15min.csv`,
columnas relevantes `Cuarto de Hora`, `Suministrador`, `Medida_kWh`,
`Clave_Anio_Mes`) y quiere la misma lógica de reparto pero a nivel de
cuarto de hora, integrada a este repositorio.

**Decisiones ya tomadas con el dueño del proyecto** (no hace falta
volver a preguntarlas):

- El costo por ciclo (`Precio_Ciclo` del script viejo) sale del propio
  motor: hoja `Resumen_Ciclos_PD` del Excel que produce
  `sc_pd_motor_v7.py`, columnas `Etiqueta_Relacionada` (identificador de
  ciclo) y `Total SC_PD` (costo final ya filtrado). **No** se vuelve a
  leer el Excel dinámico de anclas ("Cuenta de Ciclo + fecha + hora" /
  "Etiquetas de fila") — esa tabla dinámica no existe en este repo y
  duplicaría lógica que el motor ya resuelve.
- El cruce sigue siendo por **índice secuencial del mes** (como
  `Hora_Mensual` en el script viejo), pero a nivel de cuarto de hora —
  ver más abajo `Cuarto_Hora_Mensual`. No se intenta relacionar
  `Suministrador`/`Retiro`/`nombre_barra` del archivo de retiros con
  `Central`/`Central_Relacionada`/`Empresa` del motor — son conceptos
  distintos (el reparto es por ventana temporal del ciclo, igual que en
  el script horario, según el punto 3 de arriba) y **no calzar es
  esperado**, no un error.
- Es un script nuevo e independiente (mismo patrón que
  `scripts/consolidar_politicas.py`), no una etapa nueva dentro de
  `sc_pd_motor_v7.py`.

## Qué construir

### 1. `Cuarto_Hora_Mensual`: índice secuencial de 15 minutos dentro del mes

El motor no tiene hoy ningún concepto de índice secuencial (trabaja
siempre con `FECHA_HORA` real) — hay que crearlo, replicando el mismo
patrón que `Hora_Mensual` pero a nivel de cuarto de hora:

```python
def calcular_cuarto_hora_mensual(fecha_hora: pd.Series) -> pd.Series:
    """1-indexado: día 1, primer cuarto de hora del mes ([00:00,00:15)) = 1."""
    minuto_del_dia = fecha_hora.dt.hour * 60 + fecha_hora.dt.minute
    return (fecha_hora.dt.day - 1) * 96 + (minuto_del_dia // 15) + 1
```

**Esto es una hipótesis de trabajo, no un hecho confirmado** — la
muestra de retiros (`prueba_de_retiros_15min.csv`) solo trae ~99 filas de
una combinación (`nombre_barra`, `Suministrador`, `Retiro`), con valores
de `Cuarto de Hora` entre 1 y 76, insuficiente para confirmar el
convenio exacto (ej. si es 1-indexado, si el cuarto representa el inicio
o el fin del intervalo, etc.). Antes de dar por buena esta función contra
datos reales completos:

- Verificar que el valor máximo de `Cuarto de Hora` en el archivo real de
  un mes con `n` días sea `n * 96` (ej. 2.976 para un mes de 31 días).
- Si no calza, ajustar la fórmula (offset, indexado desde 0, etc.) hasta
  que sí — y dejar un comentario corto explicando el ajuste real
  encontrado.

### 2. Membresía ciclo -> cuartos de hora, desde `Detalle_15Min`

`Detalle_15Min` (hoja del Excel del motor, ver
`src/sc_pd_motor_v7.py`, función que arma `resumen_relacionada`/
`detalle_mes`, columnas `Etiqueta_Relacionada`, `Central`, `FECHA_HORA`,
entre otras) trae **una fila por `Central` + `FECHA_HORA`** dentro de un
ciclo activo. Como una `Central_Relacionada` puede agrupar más de una
`Central` (config) activa en el mismo cuarto de hora, hay que deduplicar
por `(Etiqueta_Relacionada, FECHA_HORA)` antes de construir la tabla de
membresía:

```python
def construir_membresia_ciclos(detalle_15min: pd.DataFrame) -> pd.DataFrame:
    membresia = detalle_15min[['Etiqueta_Relacionada', 'FECHA_HORA']].drop_duplicates()
    membresia['Cuarto_Hora_Mensual'] = calcular_cuarto_hora_mensual(membresia['FECHA_HORA'])
    return membresia[['Etiqueta_Relacionada', 'Cuarto_Hora_Mensual']].rename(
        columns={'Etiqueta_Relacionada': 'Ciclo'})
```

### 3. Retiros 15-minutales agrupados

Leer el archivo de retiros (CSV como la muestra; dejar la función
preparada para aceptar también `.parquet` según extensión, ya que no
está confirmado en qué formato llegará a producción), agrupar por
`Cuarto de Hora` + `Suministrador` sumando `Medida_kWh` **sin aplicar
valor absoluto** (igual que el script horario, que sumaba el valor tal
cual viene) — la proporción `Prorrata` da igual con signo negativo
consistente dentro de un mismo grupo, porque numerador y denominador
comparten signo.

### 4. Cruce y cálculo — replica exacta de la lógica del script horario, a nivel de cuarto de hora

```python
def prorratear_retiros(membresia_ciclos, retiros_agrupados, precios_ciclo):
    """
    membresia_ciclos: columnas Ciclo, Cuarto_Hora_Mensual (de construir_membresia_ciclos)
    retiros_agrupados: columnas Cuarto_Hora_Mensual, Suministrador, Medida_kWh
    precios_ciclo: columnas Ciclo, Precio_Ciclo (de Resumen_Ciclos_PD: Etiqueta_Relacionada, Total SC_PD)
    """
    # 1. Solo ciclos que están en precios_ciclo (igual que el filtro del script viejo)
    # 2. Cruce por Cuarto_Hora_Mensual (NO por Suministrador/Central) -> un mismo retiro
    #    puede "verse" repartido entre varios ciclos activos simultaneamente, a proposito.
    # 3. Total_kWh_Ciclo = suma de Medida_kWh de todas las filas (cuarto+suministrador) del ciclo
    # 4. Prorrata = Medida_kWh_Cuarto / Total_kWh_Ciclo
    # 5. Monetario_Cuarto = Prorrata * Precio_Ciclo
    ...
```

Columnas de salida del detalle (mismo nombre que el script viejo,
`Hora` -> `Cuarto`):

`Suministrador, Cuarto_Hora_Mensual, Medida_kWh_Cuarto, Total_kWh_Ciclo, Prorrata_Respecto_Ciclo, Ciclo, Precio_Ciclo, Monetario_Cuarto`

### 5. Auditoría de cuadratura — igual que el script viejo

- `total_original` = suma de `Precio_Ciclo` sobre los ciclos incluidos.
- `total_repartido` (resumen y detalle) = suma de `Monetario`.
- Por ciclo: `Delta_Ciclo = Precio_Ciclo - Monetario_Repartido`, alerta si
  `abs(Delta_Ciclo) > 0.01`.
- **Caso nuevo a manejar explícitamente** (no existía en el script viejo
  de forma visible): si `Total_kWh_Ciclo` de un ciclo es `0` (ningún
  retiro cruzó con sus cuartos de hora activos, o los retiros se anulan
  entre sí), no debe lanzar `ZeroDivisionError` ni propagar `NaN` en
  silencio al total repartido — ese ciclo debe quedar excluido del
  reparto y listado explícitamente en la auditoría (mismo estilo que las
  demás alertas del motor, ej. `"[!] N ciclo(s) sin retiros para
  prorratear (no se pudo repartir su costo): ..."`).

### 6. Exportación

Mantener el mismo formato que el script viejo (continuidad para quien
consume el archivo hoy): Excel resumen por `Suministrador` +
CSV de detalle en formato Power Query (separador `;`, coma decimal).

### 7. Separación testable

Igual que `fase1_integridad.py` para el motor: las funciones puras
(`calcular_cuarto_hora_mensual`, `construir_membresia_ciclos`,
`prorratear_retiros`, y la función de auditoría de cuadratura) van en
`src/prorrateo_15min.py`, importables y testeables sin tocar disco.
`scripts/prorratear_pagos_15min.py` es el wrapper delgado: define rutas,
lee los archivos (Excel del motor, archivo de retiros), llama a las
funciones de `src/prorrateo_15min.py`, imprime la auditoría y exporta.

## Criterio de aceptación

- Tests nuevos en `tests/test_prorrateo_15min.py`, cubriendo:
  - `calcular_cuarto_hora_mensual`: casos conocidos (día 1 00:00 -> 1,
    día 1 00:15 -> 2, día 2 00:00 -> 97).
  - `construir_membresia_ciclos`: una `Central_Relacionada` con 2
    `Central` distintas activas en el mismo `FECHA_HORA` produce **una
    sola** fila de membresía para ese ciclo+cuarto (no duplica).
  - `prorratear_retiros` con datos sintéticos pequeños (2-3 ciclos, 2
    suministradores, algunos cuartos compartidos entre ciclos
    concurrentes): la suma de `Monetario_Cuarto` por ciclo debe igualar
    `Precio_Ciclo` dentro de 0.01, y un ciclo con `Total_kWh_Ciclo == 0`
    no debe romper la ejecución ni contaminar el total repartido de los
    demás ciclos.
  - Regresión de signo: si todos los `Medida_kWh` de un grupo son
    negativos, el resultado de `Prorrata_Respecto_Ciclo` sigue siendo
    positivo y la cuadratura se mantiene.
  - Un ciclo presente en `Resumen_Ciclos_PD` pero ausente en
    `Detalle_15Min` (sin cuartos de hora) se excluye sin error.
- `python -c "import ast; ast.parse(open('scripts/prorratear_pagos_15min.py', encoding='utf-8').read())"`
  no lanza `SyntaxError`.
- `pytest -q -m ""` sigue en verde (incluye los tests nuevos).
- Si hay datos reales disponibles en el entorno de implementación
  (Excel de salida del motor de un mes real + archivo de retiros
  15-minutal completo de ese mismo mes), correr
  `scripts/prorratear_pagos_15min.py` de punta a punta y reportar en la
  respuesta: el total repartido, la cantidad de ciclos con diferencia de
  cuadratura > 0.01 (si hay alguno, explicar por qué), y confirmar que el
  valor máximo de `Cuarto de Hora` encontrado en el archivo de retiros
  coincide con `dias_del_mes * 96` (validación del punto 1).

## Qué NO hacer en esta spec

- No modificar `src/sc_pd_motor_v7.py` ni `src/fase1_integridad.py`.
- No intentar relacionar `Suministrador`/`Retiro`/`nombre_barra` de los
  retiros con `Central`/`Central_Relacionada`/`Empresa` del motor — el
  reparto es por ventana temporal del ciclo, no por relación
  central-suministrador (confirmado con el dueño del proyecto).
- No aplicar valor absoluto a `Medida_kWh` en ningún punto del cálculo.
- No bloquear la ejecución si `Total_kWh_Ciclo` de un ciclo da 0 —
  excluirlo del reparto y avisar, como se describe en el punto 5.
- No asumir sin validar el convenio exacto de `Cuarto de Hora` del
  archivo de retiros — dejar la verificación del punto 1 como parte del
  criterio de aceptación cuando haya datos reales.
