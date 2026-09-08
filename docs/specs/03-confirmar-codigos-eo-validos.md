# Spec 03 — Confirmar `CODIGOS_EO_VALIDOS`: ya no es un pendiente de negocio

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — solo un comentario en `src/sc_pd_motor_v7.py`, ningún cambio de comportamiento

## Contexto

`CODIGOS_EO_VALIDOS = ['PDO']` (sección 0 del panel de control) estaba
marcado como pendiente de confirmar porque, al revisar el RIO real de
julio 2026, la columna `ESTADO OPERACIONAL` no traía ningún valor `"PDO"`
en esa muestra — solo `N, RO, DN, LF, DRO, PO, DF, DLF, LP, MM`.

El dueño del proyecto me compartió la fórmula de Excel original que este
código reemplaza:

```
=SI.ERROR(MAX.SI.CONJUNTO('Sobrecosto_PD xHyC'!U:U;'Sobrecosto_PD xHyC'!J:J;
PARTIDAS_DETENCIONES!N2;'Sobrecosto_PD xHyC'!G:G;F2)
*SI(O(P2="OM";Q2="PDO";Y(P2="OT";Z2=1));1;
SI(Y(DERECHA(N2;2)="&1";P2="");1;0)); 0)
```

Verificamos juntos, celda por celda, que:

- `P2` es `MOTIVO` (coincide con `df[col_motivo] == 'OM'` en `calcular_filtros`).
- `Z2` es el chequeo SSCC/CTF/CSF/CPF ya presente en el motor (`cond_sscc`).
- `N2` es `CENTRAL&numero_de_ciclo` (coincide con `Etiqueta_Relacionada`).
- `Q2` (columna "Operación" en la hoja `PARTIDAS_DETENCIONES`) sale de un
  `BUSCARV` que consulta **directamente la columna `ESTADO OPERACIONAL`
  del RIO**, sin ninguna traducción intermedia — la misma columna que el
  motor Python ya usa en `CODIGOS_EO_VALIDOS`.

Es decir: el motor no tiene un bug de mapeo de columnas en este punto — el
Excel original compara exactamente lo mismo, contra el mismo valor
`"PDO"`, en la misma columna. Y el dueño del proyecto confirmó, revisando
otro archivo RIO real, que la columna `ESTADO OPERACIONAL` **sí** contiene
el valor `"PDO"` en algunos registros — solo no aparecía en la muestra de
julio 2026 que se usó para la auditoría original, probablemente porque es
un estado poco frecuente.

**Conclusión:** `CODIGOS_EO_VALIDOS = ['PDO']` queda confirmado tal como
está. No hay ningún cambio de valor ni de lógica que hacer — el único
cambio es de documentación, para que el comentario dentro del código deje
de sugerir que algo está mal o pendiente.

## Instrucción

En `src/sc_pd_motor_v7.py`, reemplazar el comentario actual:

```python
# Codigos de la columna EO del RIO que habilitan el reconocimiento del costo.
# PENDIENTE DE CONFIRMAR: la formula original de Excel usaba "PDO", que no
# aparece en la columna EO. Ajusta esta lista cuando lo confirmes con el CEN.
CODIGOS_EO_VALIDOS = ['PDO']
```

por:

```python
# Codigos de la columna EO del RIO que habilitan el reconocimiento del costo.
# Confirmado: coincide con la formula de Excel original (columna "Operacion"
# de PARTIDAS_DETENCIONES, que hace BUSCARV directo contra ESTADO OPERACIONAL
# del RIO comparando contra "PDO"). El valor no aparecio en la muestra de RIO
# de julio 2026 usada en la auditoria inicial, pero el dueno del proyecto
# confirmo su presencia en otro mes real de RIO. No es un pendiente de negocio.
CODIGOS_EO_VALIDOS = ['PDO']
```

**No cambiar el valor `['PDO']`**, solo el comentario. No hay ningún otro
cambio de código en esta spec.

## Actualizar `bitacora.md`

Agregar una entrada nueva (no reemplazar las anteriores) documentando este
cierre, con referencia a esta spec.
