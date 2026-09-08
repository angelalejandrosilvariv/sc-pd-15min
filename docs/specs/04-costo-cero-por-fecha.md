# Spec 04 — `Costo_Cero` debe respetar la fecha, no ser un valor único por central

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`, posiblemente `src/fase1_integridad.py`, `tests/`

## Contexto

Revisando `Costos_de_P-D_Consolidado.xlsx` (junio 2026, 79.052 filas, 688
`UNIDAD` distintas) encontré que **`CHUYACA_DIESEL`** es la única central
cuyo `Costo_Cero` cambia dentro del mismo mes:

| Período | `Costo_Cero` | `Partida_Fria` | `Detencion` |
|---|---|---|---|
| 1 al 16 de junio | `SI` (exenta) | 0 | 755,7 |
| 17 al 30 de junio | `NO` (facturable) | 476,8 | 726,2 |

Le pregunté al dueño del proyecto si esto tiene sentido de negocio y
confirmó: **sí, las políticas pueden cambiar día a día**, y el `Costo_Cero`
es parte de esa política — no es un valor fijo por central para todo el
mes.

Esto explica un pendiente que ya estaba declarado en el histórico del
proyecto ("`CHUYACA_DIESEL` ausente del motor completo"): con el archivo de
costos real cargado, esta central sí participa, pero el motor hoy la trata
mal.

### El problema en el código actual

En `src/sc_pd_motor_v7.py`, sección 4 (líneas ~368-386):

```python
cols_costos = ['Llave_Concatenada', 'Fria_Num1_M', 'Tibia_Num1_O', 'Tibia_Num2_N',
               'Caliente_Num1_P', 'Partida_Fria', 'Partida_Tibia', 'Partida_Caliente', 'Detencion']
...
df_costos_pd = df_externo[cols_costos].drop_duplicates(subset=['Llave_Concatenada'], keep='last')

# --- Filtro Costo_Cero ---
diccionario_busqueda = df_externo.drop_duplicates(subset=['UNIDAD'], keep='last') \
                                 .set_index('UNIDAD')['Costo_Cero'].to_dict()
resultado_buscarx = reporte_sin_ceros['Central'].map(diccionario_busqueda)
mask_no_cogen = ~reporte_sin_ceros['Central'].astype(str).str.contains('COGEN', case=False, na=False)
reporte_sin_ceros['Costo_Final'] = np.where(mask_no_cogen, resultado_buscarx.fillna('No_Aplica'), 'No_Aplica')

filtro_seguro = reporte_sin_ceros['Costo_Final'].astype(str).str.strip().str.upper()
reporte_sin_ceros = reporte_sin_ceros[filtro_seguro == 'NO'].copy()
```

`diccionario_busqueda` colapsa `Costo_Cero` a **un solo valor por
`UNIDAD`** (el que aparece último en `df_externo`, que además puede incluir
dos meses concatenados si `RUTA_COSTOS_MES_PASADO` está activo), y ese
único valor se aplica a **todos** los bloques de 15 minutos de esa central,
sin mirar la fecha. Para `CHUYACA_DIESEL` en junio, el último valor es
`'NO'`, así que hoy el motor trataría como facturable también los días 1
al 16, cuando el propio archivo de costos dice que esos días estaba exenta.

Esto es inconsistente con el resto del motor: las tarifas
(`Partida_Fria/Tibia/Caliente`, `Detencion`) **sí** se resuelven por fecha,
vía `Llave_FHC_Inicio`/`Llave_FHC_Fin` cruzados contra `Llave_Concatenada`
(sección 11, líneas ~917-940). `Costo_Cero` es el único campo de este
archivo que no pasa por ese mecanismo.

## Fix requerido

**No** cambiar el resultado para los ~687 centrales que tienen `Costo_Cero`
constante durante todo el período cargado — el fix solo debe cambiar el
comportamiento para centrales como `CHUYACA_DIESEL`, cuyo valor varía.

### 1. El pre-filtro temprano (sección 2/4) pasa a ser un filtro amplio, no el filtro final

Hoy el filtro temprano decide de forma **definitiva y por central completa**
si una central entra o no al resto del pipeline. Cambiar el criterio de
`keep='last'` a **"¿esta unidad tiene *algún* registro con `Costo_Cero ==
'NO'` en el período cargado?"** (usar `.groupby('UNIDAD')['Costo_Cero']` con
`.transform(lambda s: (s.astype(str).str.strip().str.upper() == 'NO').any())`,
vectorizado, sin loop de Python). Esto:

- Para las ~687 centrales con `Costo_Cero` constante, es **exactamente
  igual** al comportamiento actual (si siempre es `'SI'`, se sigue
  excluyendo temprano; si siempre es `'NO'`, se sigue incluyendo).
- Para `CHUYACA_DIESEL` (y cualquier central similar en el futuro), deja
  de excluirse ninguna parte del mes en esta etapa — sus 30 días completos
  siguen adelante en el pipeline, incluida la detección de ciclos (que
  debe verlos todos: el ciclo físico de la máquina no distingue si un
  bloque es o no facturable).
- La regla de `mask_no_cogen` (excluir siempre las `COGEN`) se mantiene
  igual, sin cambios.

### 2. `Costo_Cero` se agrega a `cols_costos` y se resuelve por fecha, igual que las tarifas

Agregar `'Costo_Cero'` a la lista `cols_costos` (línea ~368), para que
viaje dentro de `df_costos_pd` con la misma llave (`Llave_Concatenada`) que
ya usan `Partida_Fria`, `Detencion`, etc.

### 3. Aplicar el gate real de `Costo_Cero` en la sección 11, al mismo tiempo que se cruzan las tarifas

Después de los merges de la sección 11 (línea ~917 para partida, ~937 para
detención), donde hoy se obtienen `Fria_Num1_M`, `Partida_Fria`, etc. por
`Llave_FHC_Inicio`/`Llave_FHC_Fin`, también se obtiene `Costo_Cero` para
esa fecha específica. Con eso:

- Construir un multiplicador `Filtro_CostoCero_Partida` /
  `Filtro_CostoCero_Detencion` (0 o 1): `0` cuando, para esa fecha
  concreta, `Costo_Cero == 'SI'` **o** la central es `COGEN`; `1` en caso
  contrario (`Costo_Cero == 'NO'`).
- Aplicar este multiplicador al costo efectivo, igual que ya se hace con
  `Filtro_Conf`/`Filtro_Disp`/`Filtro_Op` en `costos_clasicos()` de
  `src/fase1_integridad.py` — ya sea extendiendo esa función para aceptar
  este quinto factor, o multiplicando `Costo_Partida_Base`/
  `Costo_Detencion_Base` por este gate antes de llamar a
  `costos_clasicos()` (lo que resulte más simple sin romper los tests
  existentes de `costos_clasicos`).
- Agregar una observación distinguible en `Obs_Partida`/`Obs_Detencion`
  (sección 14.7 / `marcar_sin_tarifa_rio`) para este caso — algo como
  `"Exento: Costo_Cero=SI en la fecha de partida"` — para que no se
  confunda con "Sin tarifa" ni con un rechazo por RIO. Igual que ya se
  corrigió antes para `Obs_Partida`, la causa real debe quedar visible.

### 4. Repetir el mismo cambio para la rama `USAR_TARIFA_RIO_INSTRUIDA` (sección 11.1 / 14.1b)

El interruptor `USAR_TARIFA_RIO_INSTRUIDA = 1` está **activo por defecto**,
así que en la práctica es `Tipo_Partida_RIO` / `Costo_Partida_RIO` el que
determina el cobro real, no `Tipo_Partida`/`Costo_Partida` de la sección
11. Ese bloque (sección 11.1, `cols_tarifa_rio`) también necesita el mismo
tratamiento de `Costo_Cero` por fecha, aplicado a
`Costo_Partida_RIO_ML`/`Costo_Detencion_RIO_ML` antes de que lleguen a
`df_compacto`.

## Criterio de aceptación

- Ningún cambio de resultado para centrales con `Costo_Cero` constante
  (verificar con un test que reproduzca ese caso).
- Test nuevo que reproduzca el caso `CHUYACA_DIESEL`: una central
  sintética con generación en dos ciclos, uno completamente antes del
  cambio de `Costo_Cero` (debe dar `Costo_Partida_Efectivo == 0` con la
  observación de exención) y otro completamente después (debe cobrarse
  normal). Puede vivir en `tests/test_fase1_integridad.py` o un archivo
  nuevo `tests/test_costo_cero_por_fecha.py`.
- `pytest -q -m ""` sigue en verde, incluyendo el test de rendimiento.
- Ningún interruptor de negocio (`USAR_CONFIG_DOMINANTE`,
  `USAR_TARIFA_RIO_INSTRUIDA`, `REGLA_EXENCION`, `TOLERANCIA_CORTES_BLOQUES`,
  `CODIGOS_EO_VALIDOS`) se toca.

## Qué NO hacer en esta spec

- No cambiar cómo se decide `Costo_Cero` para centrales cuyo valor es
  constante durante todo el período cargado (el 99,9% de los casos) —
  el resultado ahí debe ser idéntico al actual.
- No tocar la regla `COGEN` (siempre excluida, sin importar `Costo_Cero`).
- No especular sobre el motivo de negocio por el que `CHUYACA_DIESEL`
  cambia de estado — eso ya está confirmado como válido por el dueño del
  proyecto, el fix es puramente de que el código respete la fecha.
