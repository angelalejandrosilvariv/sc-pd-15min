# 24 — Modelo alternativo: ciclos por turbina (`sc_pd_motor_turbina.py`)

**Toca código:** sí — `src/sc_pd_motor_turbina.py` (nuevo, copia independiente del
v7), `Carpeta_de_Trabajo/correr_motor_turbina.py`, `tests/test_motor_turbina.py`

**Toca el motor v7:** **no.** El v7 no cambia en absoluto; este es un segundo
motor que se corre aparte.

**Estado:** **experimental**, implementado y medido. No reemplaza al v7. Sigue
abierta la decisión de negocio de la sección 7.

---

## 1. Qué cambia y por qué

El v7 detecta el ciclo de partida/detención a nivel de `Central_Relacionada`, la
entidad que define el diccionario configuración → relacionada. Una central como
KELAR agrupa tres máquinas físicas —KELAR-TG1, KELAR-TG2 y KELAR-TV— que arrancan
y se detienen por separado; en el v7 quedan disueltas en un solo ciclo de
`KELAR-TG12`, y el arranque propio de la turbina de vapor desaparece.

Este motor detecta el ciclo a nivel de **`UNIDAD GENERADORA`** (la turbina).
En junio 2026 son 275 turbinas contra 120 relacionadas; tras el filtro de costo
cero, 94 contra 89. Solo **cinco relacionadas agrupan más de una turbina**, y son
exactamente las que concentran las brechas contra el horario: ATACAMA-1TG1AB,
ATACAMA-2TG2AB, KELAR-TG12, ARICA, SANISIDRO.

El nivel turbina destapó además que el diccionario fusionaba plantas distintas:
`SANISIDRO-1 → [SANISIDRO-1, SANISIDRO-2]` y
`ARICA-M2AR_DIESEL → [ARICA-M1AR, ARICA-M2AR]`.

## 2. Tres niveles que no pueden ser el mismo

Los datos obligan a separar lo que el v7 resolvía con una sola llave:

| Nivel | Se resuelve por | Por qué |
|---|---|---|
| **Ciclo** | `UNIDAD GENERADORA` | Es el hecho físico. Lo único que cambia respecto del v7. |
| **Tarifa** | `CONFIGURACION` | `Costos_de_P-D_Consolidado` está indexado por configuración: solo 3 de 275 turbinas calzan con su columna `UNIDAD` (1,1%), contra 261 de 378 configuraciones (69%). No existe tarifa por turbina. |
| **RIO** | `CONFIGURACION` | El RIO tampoco identifica la turbina: su `UNIDAD GENERADORA` está a nivel de planta (`KELAR`, `ATACAMA-1`). Registra planta + configuración. |

Consecuencia de implementación: en este motor **el cruce maestro con el RIO se
hace por configuración** (`left_by='Central'`), no por la entidad del ciclo. Es
además más fiel al documento del CEN, que define el registro por configuración.

## 3. Implementación

Copia completa de `sc_pd_motor_v7.py` con estos cambios, todos comentados en el
código:

- **Panel:** `COLUMNA_NIVEL_CICLO = 'UNIDAD GENERADORA'`,
  `ATRIBUCION_TARIFA_TURBINA = 'prorrata'`, `VENTANA_EVENTO_CUARTOS = 2`,
  `RUTA_SALIDA` propia (`Reporte_Sobrecostos_PD_Turbina.xlsx`).
- **Entidad del ciclo:** `Central_Relacionada := UNIDAD GENERADORA`. Se conserva
  el nombre de columna para no tocar las 196 referencias del resto del motor; la
  relacionada del diccionario se guarda aparte en `Relacionada_Diccionario`, solo
  informativa, para poder comparar contra el v7.
- **RIO por configuración:** `Central_Relacionada_RIO := NOMBRE CONFIGURACIÓN`
  (sin pasar por el diccionario); el `merge_asof` maestro, el rescate en ventana,
  la corrección de mezcla, la secuencia RIO y la búsqueda relajada de filtros usan
  la configuración del bloque o del límite del ciclo como llave.
- **Atribución entre turbinas** (sección 4): `agrupar_eventos_de_configuracion()`
  y `atribuir_tarifa_entre_turbinas()`, aplicadas después de `costos_clasicos()`
  y antes del diferimiento.
- **Export:** columnas `Central_Partida/Detencion`, `Evento_*`,
  `Turbinas_En_Evento_*`, `Factor_Atribucion_*` en `Resumen_Ciclos_PD`; hoja nueva
  `Atribucion_Turbinas`; `Central_Relacionada` se exporta como
  `Unidad_Generadora`.

## 4. Atribución de la tarifa entre turbinas del mismo evento

Varias turbinas pueden arrancar bajo una misma configuración. La tabla de costos
tiene **una** tarifa para esa configuración, que ya escala con cuántas máquinas
incluye: en KELAR, `TG1_TG1` vale 1.663 USD y `TG12_TG1+TG2+TV1` 94.034 USD.
Cómo se reparte es decisión de negocio, y el interruptor permite comparar:

| `ATRIBUCION_TARIFA_TURBINA` | Regla |
|---|---|
| `'prorrata'` | El evento paga una vez; se reparte entre las turbinas por generación. |
| `'primera'` | El evento paga una vez, completa, a la turbina que abrió. |
| `'cada_turbina'` | Cada turbina paga la tarifa completa. Multiplica en multi-turbina. |

**Definición de evento** — dos reglas, ambas necesarias:

1. Encadenado por cercanía dentro de la **misma configuración**: se abre evento
   nuevo cuando el salto respecto del anterior supera `VENTANA_EVENTO_CUARTOS`.
2. **Una turbina no puede aparecer dos veces en el mismo evento.** Si se repite,
   es otro arranque suyo y abre evento nuevo.

La regla 2 corrige un defecto de la primera versión: sin ella, el encadenamiento
fusionaba por transitividad los arranques sucesivos de una sola máquina — con
ventana de 24 h llegó a juntar 19 ciclos de `TENOGAS-1a26_GLP` abarcando 202,5
horas, y el reparto perdía todo sentido. Cubierto por
`test_la_misma_turbina_repetida_no_se_fusiona_por_transitividad`.

Auditoría: el factor de atribución suma exactamente 1 por evento (verificado
sobre los 1.063 eventos de partida y 1.046 de detención de junio).

## 5. Resultados medidos (junio 2026, empalme de mayo, ambos RIO)

| Modelo | SC P-D | vs horario (1.028.628.659) | Σ\|Δ\| por empresa |
|---|---:|---:|---:|
| v7 (relacionada) | 823.168.889 | −20,0% | 255.292.186 |
| Turbina · prorrata | 943.149.530 | −8,3% | 185.599.096 |
| Turbina · primera | 943.149.530 | −8,3% | 185.599.096 |
| Turbina · cada_turbina | 946.106.550 | −8,0% | 188.556.116 |

Los tres modos caben en 3,0 millones (0,3%). Solo cambian 4 empresas; las otras
22 quedan idénticas al v7.

**KELAR se reconcilia con el horario.** Con ciclos por turbina, KELAR-TV aparece
con ciclos propios y su arranque del 27-jun cobra **61.419.507 CLP** bajo
`KELAR-TG1_TG1+0.5TV_DIESEL` — exactamente lo que cobra el horario — pero por
una razón física documentada (la turbina de vapor efectivamente arrancó), no por
mezclar configuraciones. TAMAKAYA pasa de −97,8 M a −17,2 M contra el horario.

**ENEL se sobre-corrige: +25,2 M sobre el horario.** Es ATACAMA: al separar TGA,
TGB y TV, cada turbina paga su propia partida.

## 6. La ventana de evento no es una palanca (con esta llave)

Se barrió `VENTANA_EVENTO_CUARTOS` de ±0,5 h a ±24 h, offline, sobre la salida
`cada_turbina` (que trae tarifas sin repartir), validando primero que el método
reproduce las tres corridas reales del motor a ±30 min con 0 CLP de diferencia.

Con la regla corregida el barrido es **completamente plano**: 0 eventos de
partida compartidos con costo en juego y 13 de detención (56.613.895 CLP),
idénticos en todo el rango. Razón: las turbinas de una misma planta arrancan bajo
**configuraciones distintas** por construcción — cuando el vapor entra, la
configuración cambia — así que nunca comparten llave. Los 13 de detención se
capturan a ±30 min porque las máquinas se apagan juntas.

`VENTANA_EVENTO_CUARTOS` se queda en 2. Subirla no hace nada.

## 7. Decisión abierta: la llave del evento

El evento físico es el **arranque de la planta**, no el de una configuración.
Tres turbinas de ATACAMA-1 arrancan en 1 h 45 min registrando tres
configuraciones distintas y hoy pagan tres tarifas completas (20.680.906 CLP
por un solo arranque de ciclo combinado el 18-jun).

Medido offline, cambiar la llave de evento de configuración a **planta**
(`Relacionada_Diccionario`, usada solo para saber qué turbinas son de la misma
estación) sí responde a la ventana:

| Ventana | ENEL vs horario, llave configuración | Llave planta |
|---|---:|---:|
| ±0,5 h | +25.205.459 | +17.201.842 |
| ±1 h | +25.205.459 | +9.236.368 |
| ±2 h | +25.205.459 | −8.501.178 |

ENEL cruza el horario alrededor de ±1,5–2 h. **No está implementado**: requiere
decidir (a) la llave, (b) la ventana bajo esa llave y (c) cómo paga el evento
cuando las turbinas registraron tarifas distintas (aparece una tercera opción,
`mayor_tarifa`: el evento paga una vez la configuración más cara).

Nota: la Σ\|Δ\| agregada contra el horario **empeora** con la llave planta
(185,6 → 193,1 M a ±2 h), porque la mayoría de las empresas ya cobran menos que
el horario y cualquier reducción las aleja. Ese indicador está sesgado hacia
"parecerse al horario", que no es el objetivo; la decisión debe tomarse por el
mérito físico de la regla.

## 8. Lo que el experimento controlado cambió (ver bitácora 2026-09-10)

Alimentando el **v7** con el reporte horario, el 94,8% de la brecha contra el
Excel resultó ser de **reglas**, no de resolución. Este motor se construyó
inicialmente como herramienta de convergencia; con ese resultado, su adopción
debe decidirse por sus propios méritos (sección 7), no por cuánto acerca al
horario.
