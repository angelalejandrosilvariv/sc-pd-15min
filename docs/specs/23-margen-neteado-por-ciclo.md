# 23 — Interruptor: netear el margen dentro del ciclo antes de truncarlo

**Toca código:** sí (`src/sc_pd_motor_v7.py`, `Carpeta_de_Trabajo/correr_motor.py`,
`tests/test_margen_neteado_por_ciclo.py`)

**Cambia el monto liquidado:** sí, cuando el interruptor se activa. Apagado (default)
el motor produce exactamente el mismo número que antes de esta spec.

**Estado:** implementado como interruptor, **apagado por defecto**. Encenderlo es una
decisión de negocio pendiente de aprobación, no un fix.

---

## 1. El problema

El motor descarta el margen negativo **bloque a bloque**, antes de sumarlo al ciclo:

```python
# src/sc_pd_motor_v7.py — calcular_margen_bloques()
return np.where(margen_unitario > 0, margen_unitario * generacion, 0)
```

Después vuelve a truncar, ahora a nivel de ciclo:

```python
df_compacto['Total SC_PD'] = np.maximum(
    0, df_compacto['Costos_Totales_PD'] - df_compacto['Margen_Suma_Ciclo'])
```

La consecuencia es que un ciclo con un bloque en +100 y otro en −100 registra un
margen de **+100**, no de 0. El truncamiento por bloque puede acreditarle a un ciclo
una autocobertura que el ciclo, tomado como un todo, nunca tuvo.

Caso real en 2606 — **TOCOPILLA-U16, ciclo del 23-jun**:

| Concepto | CLP |
|---|---:|
| Margen neto real del ciclo | **−20.601.044** |
| Margen acreditado por el criterio actual | **+76.923.870** |
| Costo P-D del ciclo | 50.594.150 |
| Pago resultante hoy | **0** |

La central perdió dinero vendiendo energía durante todo el ciclo y aun así el costo
de partida/detención se consideró autocubierto. MEJILLONES-CTM3 presenta el mismo
patrón: margen neto −59.945.000, acreditado +88.837.000.

## 2. El contraargumento (por qué el default sigue siendo 0)

**El modelo horario hace exactamente lo mismo que el motor.** Verificado sobre
`Copia de Sobrecostos_PD_2606 def.xlsm`:

```
Sobrecosto_PD xHyC!Y  = IF(X2-W2<0, 0, X2-W2)      W=CV, X=CMg  -> trunca POR FILA hora-central
Sobrecosto_PD xHyC!AB = Z2*Y2*AA2                   Margen = USD x diferencia_truncada x Gen_neta
Sobrecosto_Ciclo!E    = SUMIF(...AC:AC, A2, ...AB:AB)   suma los márgenes YA truncados
Sobrecosto_Ciclo!H    = IF(C2+D2+F2>E2+G2, C2+D2+F2-E2-G2, 0)   segundo clamp, a nivel ciclo
```

Los dos truncamientos del motor son un calco de los dos del Excel. Las magnitudes
también coinciden, lo que confirma que ambos miden el mismo fenómeno:

| | Filas truncadas | % | CLP truncados |
|---|---:|---:|---:|
| Modelo horario (hora-central) | 8.276 de 19.510 | 42,4% | −28.244.798.402 |
| Motor 15min (bloque de 15 min) | 309.326 de 787.820 | 39,3% | −40.377.925.560 |

Se puede leer legítimamente que **cada bloque con CMg < CV es un bloque en que la
central no se autocubrió**, y que una hora mala no debería borrar la autocobertura
que sí ocurrió en una hora buena. Bajo esa lectura el truncamiento por bloque es
deliberado, no un descuido.

La pregunta regulatoria de fondo — que el código no puede resolver — es si "el margen
cubrió el costo de partida" se mide instante a instante o sobre el ciclo, que es la
unidad en que efectivamente se cobra la partida/detención.

## 3. Impacto medido sobre 2606

Corridas completas con `Reporte_PD_15min_2606.csv` + empalme 2605, ambos RIO y costos
de mayo desde `T:`.

| Criterio | Pago final | vs. actual |
|---|---:|---:|
| `MARGEN_NETEADO_POR_CICLO = 0` (actual) | 823.168.889 | — |
| `MARGEN_NETEADO_POR_CICLO = 1` | 1.099.088.306 | **+275.919.417 (+33,5%)** |

- 337 de 1.035 ciclos cambian, **todos al alza**.
- 667 ciclos tienen margen neto negativo.
- Concentración: ENEL (50 ciclos, +99,1 MM), ENGIE (22, +81,0 MM) y COLBUN
  (42, +51,8 MM) explican el 84% del delta.

### Contraste contra el modelo horario, por empresa

El total del horario para 2606 es **1.028.628.659 CLP** (987 ciclos con empresa
asignada, más 28 "se traspasa al próximo mes"). Extracción validada peso a peso
contra la hoja `RESUMEN` del propio Excel.

| | Total | Δ neto vs horario | Suma \|Δ\| por empresa |
|---|---:|---:|---:|
| Horario | 1.028.628.659 | — | — |
| Criterio 0 | 823.168.889 | −205.459.770 (−20,0%) | 255.292.186 |
| Criterio 1 | 1.099.088.306 | +70.459.647 (+6,8%) | **275.118.686** |

**Advertencia para quien apruebe esto:** el criterio 1 acerca el *total* al horario
pero **desalinea un poco más la plata que recibe cada empresa** (275,1 MM contra
255,3 MM de desviación absoluta). ENEL pasa de −14,2 MM a **+84,9 MM** sobre el
horario. El criterio 1 **no se puede justificar como "se parece más al modelo
horario"** — hay que defenderlo por su lectura de la regla, no por cercanía.

## 4. Implementación

Tres seams, todos con default que preserva el comportamiento actual.

**a) Panel de control** — nuevo interruptor junto a `CALCULAR_MARGEN_EN_EL_MOTOR`:

```python
MARGEN_NETEADO_POR_CICLO = 0
```

**b) `calcular_margen_bloques(reporte, calcular_en_motor=1, netear_por_ciclo=0)`**

Con `netear_por_ciclo=1` devuelve el producto **con signo**; el truncamiento deja de
ocurrir aquí. Con 0 mantiene el `np.where` original.

**c) `compactar_resumen_ciclos(..., netear_por_ciclo=0)`**

Con 1, después de agregar por ciclo:

```python
compacto['Margen_Neto_Ciclo'] = compacto['Margen_Suma_Ciclo']       # neto firmado
compacto['Margen_Suma_Ciclo'] = np.maximum(0, compacto['Margen_Suma_Ciclo'])
```

Sin ese `MAX`, un ciclo con margen neto negativo cobraría su costo P-D **más** la
pérdida en energía. Medido: sin truncar, el pago sube a 11.565.686.567 CLP contra un
costo efectivo validado de 1.694.803.967 — se pagarían ~7 veces los costos P-D. Esa
variante no es defendible y no se implementa.

**d) `columnas_resumen_ciclos(..., netear_por_ciclo=0)`**

Con 1 inserta `Margen_Neto_Ciclo` justo después de `Margen_Suma_Ciclo`. Es
imprescindible: el export usa una lista blanca fija de columnas, así que sin esto el
neto firmado se descarta y el criterio queda **sin trazabilidad** — no habría forma
de ver qué ciclos quedaron bajo cero.

**e) Salida por consola** — la sección `CRITERIO DE MARGEN` ahora declara cuál de los
dos truncamientos está activo y, cuando es el 1, advierte que no es el del horario.

**f) `Guia_Lectura`** — entradas nuevas para `Margen_Suma_Ciclo` y `Margen_Neto_Ciclo`.

**g) `Carpeta_de_Trabajo/correr_motor.py`** — expone el interruptor junto al de
margen que ya estaba.

## 5. Pruebas

`tests/test_margen_neteado_por_ciclo.py`, 7 casos:

- el default es idéntico a llamar con `netear_por_ciclo=0` explícito;
- con 0 no aparece la columna de auditoría (ni en el resumen ni en el export);
- con 1 el margen por bloque conserva el signo;
- +100 y −40 en el mismo ciclo dan 60, no 100;
- un ciclo con neto −70 se trunca a 0 pero deja `Margen_Neto_Ciclo = −70` trazable;
- con 1 la columna se exporta inmediatamente después de `Margen_Suma_Ciclo`;
- con solo bloques positivos, ambos criterios coinciden.

Suite completa: 58 pruebas.

## 6. Pendientes que esta spec NO resuelve

1. **Aprobación de negocio.** Encender el interruptor cambia el monto liquidado y se
   aparta del modelo horario vigente. Requiere decisión del CEN o del área.

2. **Fragilidad latente con generación negativa.** Con `netear_por_ciclo=0`, el
   truncamiento evalúa el signo del margen **unitario** y recién después multiplica
   por la generación. Si `GENERACION` fuera negativa (consumo, bombeo), un margen
   unitario positivo por una generación negativa produce un `Margen` negativo que
   **pasa el filtro**. Verificado sobre 2606: **0 filas con generación negativa**, así
   que hoy es inerte. Deliberadamente **no se corrigió acá** para no mezclar un cambio
   de robustez con un cambio de regla; con `netear_por_ciclo=1` el problema desaparece
   solo, porque ya no se filtra por signo.

3. **La brecha más grande no es esta, y ya está resuelta por diseño.** TAMAKAYA
   (KELAR-TG12) difiere del horario en −97.815.745 CLP — el 48% de la brecha total
   bajo el criterio 0 — y es **inmune a los dos criterios de margen**: su margen es 0
   en ambos modelos.

   Esa diferencia es el **efecto deliberado de la spec 15**, ya documentado en la
   bitácora. Para los ciclos 5 y 6 el horario pricea `KELAR-TG1_TG1+0.5TV_DIESEL`
   como *caliente*, mientras el motor pricea la configuración exacta que instruyó el
   RIO, `KELAR-TG1_TG1_DIESEL`, como *fría* a 8.328,30 USD. El spread entre
   configuraciones de KELAR en la base de costos llega a 57x (Partida_Fria: 1.663 la
   turbina sola contra 94.034 el ciclo combinado completo), así que la elección de
   configuración pesa mucho más que cualquier criterio de margen.

   El horario mezcla configuraciones hermanas en una sola bolsa; la spec 15 corrigió
   eso porque el CEN registra las instrucciones **por configuración**. **No es un
   pendiente**: converger con el horario acá significaría revertir la spec 15.

   Nota para quien lea el panel: `USAR_CONFIG_DOMINANTE` no aplica bajo este
   escenario — con `USAR_TARIFA_RIO_INSTRUIDA = 1` el motor lo ignora, porque la
   configuración RIO ya es la misma para todas las sub-configuraciones que comparten
   un instante. La interacción está explicada en el comentario de
   `USAR_TARIFA_RIO_INSTRUIDA` (líneas 194-197), no en el de `USAR_CONFIG_DOMINANTE`;
   verificado empíricamente: correr con el interruptor en 1 da cifras idénticas peso
   a peso, y el motor lo anuncia en una línea del log.
