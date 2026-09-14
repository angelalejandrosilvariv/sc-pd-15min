# 26 — Motor de contraste «Reglas del Horario»

**Toca código:** sí — `src/sc_pd_motor_reglas_horario.py`,
`Carpeta_de_Trabajo/interfaz.py`, `tests/test_motor_reglas_horario.py` y
documentación de uso.

**Toca los motores v7 o Turbina:** **no.** Es un tercer motor independiente.

**Cambia el monto liquidado de producción:** **no.** Este motor es un **modelo de
contraste**, no de producción, y no reemplaza al v7 ni debe usarse para liquidar.

**Estado:** formalizado, disponible en la interfaz y cubierto por pruebas unitarias.

---

## 1. Propósito y límite

`sc_pd_motor_reglas_horario.py` aplica al reporte de 15 minutos las reglas que se
dedujeron de las fórmulas y macros del Excel horario. Permite dos comparaciones
controladas: contra el Excel aísla el efecto de resolución; contra el v7 sobre el
mismo dato aísla el efecto de las reglas. La fuente normativa de esta spec es
`docs/informes/Reglas_Modelo_Horario.md`; la numeración siguiente es exactamente
la de ese informe.

No es una reimplementación productiva del libro: faltan insumos internos y procesos
manuales del Excel, y varias conductas se reproducen deliberadamente aun cuando el
v7 dispone de información más completa.

## 2. Reglas del Excel que aplica

| Regla | Aplicación en el motor de contraste |
|---|---|
| **0.a** | Marca partida/detención por configuración, con generación `!= 0`, sin tolerancia; una primera fila no puede ser partida. El ciclo relacionado se corta con cualquier cero. |
| **0.b** | No empalma el mes anterior. Para el primer ciclo usa como piso el primer bloque disponible de la relacionada en el mes. |
| **0.c** | Numera ciclos por central relacionada y dentro del mes. |
| **0.d** | Conserva flags por configuración, ciclos por relacionada y luego toma el máximo del ciclo. |
| **1** | La entidad de ciclo es `Central_Relacionada`, mediante el diccionario configuración → relacionada. |
| **2** | Arrastra la última política PO vigente con un cruce temporal hacia atrás. |
| **3** | Calcula las horas detenidas desde la detención anterior o desde el piso del mes; nunca deja nulo. |
| **4** | Usa caliente si `h <= umbral_caliente`, fría si `h >= umbral_fría`, tibia en medio; si el umbral frío es cero usa fría. Los bordes son inclusivos y no existe Tibia 2. |
| **5** | Cobra solo con horas detenidas positivas y toma el máximo de partida y detención entre configuraciones presentes en el ciclo. |
| **6** | El factor operacional paga por motivo OM, estado PDO, OT con SSCC, o primer ciclo `&1` sin instrucción. |
| **7** | Excluye costo cuando el estado operacional leído del RIO es EP, sustituto documentado de la hoja `Pruebas`. |
| **8** | La instrucción PP/PMT filtra solamente por el sufijo de combustible (`GN…` o `DIESEL`); sin instrucción, deja pasar. |
| **9** | Calcula `(CMg - CV) × Dólar × generación`, truncando el margen por bloque antes de sumar el ciclo. |
| **10** | Liquida `MAX(0, costo partida + costo detención - margen)`. |
| **11** | Traspasa el último ciclo de cada relacionada únicamente si sigue generando en el último bloque del mes. |
| **12** | Asigna empresa por configuración y usa la relacionada como fallback. |

Además excluye configuraciones `COGEN`: no existe una fórmula visible para ello,
pero el resultado del Excel contiene cero ciclos de las dos COGEN observadas. Es
una regla de entrada inferida del resultado, explicitada y probada en vez de quedar
oculta dentro del pipeline.

## 3. Qué NO aplica y por qué

1. **Regla 0.c, ventana SIF de seis horas.** Está en VBA, pero fue inerte en el
   mes estudiado y el reporte/RIO usado no entrega evidencia suficiente para
   reproducirla sin inventar una interpretación.
2. **Regla 7, hoja `Pruebas`.** Es un dato puro interno que el proyecto no posee.
   Se aproxima con `ESTADO OPERACIONAL = EP` del RIO; por tanto se conserva la
   intención, no la fuente exacta.
3. **Regla 9, consumo propio.** El dato de 15 minutos no trae `cons_prop`; se usa
   generación cruda. En junio el consumo propio legible era cero, pero no se
   afirma equivalencia general.
4. **Reglas 10 y 11, costos/márgenes heredados desde `Ciclos inconclusos`.** No se
   dispone de esa hoja ni de su proceso externo. El motor traspasa ciclos al cierre,
   pero no los recibe ni acumula desde el mes anterior.
5. **Regla 13, ajuste manual de cambio de hora.** El reporte de 15 minutos ya usa
   una línea temporal continua, por lo que no se replica el ajuste de filas del Excel.
6. **Prorrateo posterior a suministradores.** Está expresamente fuera del alcance
   del informe de reglas y de este motor.

Tampoco aplica los interruptores propios del v7/Turbina (neteo por ciclo, tarifa
máxima/instruida, baja generación, búsqueda relajada, atribución entre turbinas o
diferimiento configurable). En la interfaz aparecen deshabilitados para este motor;
la regla horaria correspondiente es fija. El único selector compartido que acepta
es la fuente del margen, para facilitar el contraste del insumo.

## 4. Interfaz y salida

La tercera opción se denomina **«Reglas del Horario — contraste, aplica las reglas
del Excel al dato 15 min»**. Su salida por defecto es
`Reporte_Sobrecostos_PD_ReglasHorario.xlsx`. El runner de Spyder
`Carpeta_de_Trabajo/correr_motor_reglas_horario.py` sigue siendo una alternativa.

## 5. Pruebas

`tests/test_motor_reglas_horario.py` protege las funciones puras y las decisiones
observables: flags de partida/detención, piso al día 1, bordes inclusivos y ausencia
de Tibia 2, combustible, las cuatro ramas del factor operacional, exclusión COGEN y
traspaso exclusivo del último ciclo que genera al cierre.

Suite esperada después de esta spec: **94 pruebas** (87 preexistentes + 7 nuevas).

## 6. Pendientes que esta spec no resuelve

1. Validar el contraste completo con archivos operacionales de otro mes; las pruebas
   unitarias no sustituyen una reconciliación peso a peso.
2. Conseguir o formalizar los insumos `Pruebas` y `Ciclos inconclusos` si se requiere
   reproducir el libro completo.
3. La decisión sobre el primer ciclo sin historia del motor de producción sigue
   abierta. La excepción `&1` pertenece solo a este modelo de contraste.
