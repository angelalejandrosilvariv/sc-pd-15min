# Spec 21 — Fix: nombre de archivo incorrecto por defecto para el diccionario de empresas

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — `src/sc_pd_motor_v7.py`, `scripts/diagnosticar_observacion.py`,
`Carpeta_de_Trabajo/correr_motor.py`, `Carpeta_de_Trabajo/correr_diagnostico.py`,
`README.md`

## Contexto

El dueño del proyecto reportó: "no esta funcionando el cruce para saber
la empresa, eso antes estaba funcionando".

**Causa raíz:** el nombre de archivo por defecto para
`RUTA_DICCIONARIO_EMPRESA` está mal desde la spec 00 (la spec original
que restauró el motor) — quedó como `Diccionario_configuracion_empresa.xlsx`
en todo el código, pero el archivo real que usa el dueño del proyecto
(confirmado en la spec 10, que sí documenta el nombre correcto, y en
todas las corridas reales hechas durante esta sesión) se llama
**`Diccionario_central_empresa.xlsx`**.

Mientras el dueño del proyecto pasara la ruta completa y correcta a
mano, esto no se notaba. Pero la sección de carga (línea ~818 de
`src/sc_pd_motor_v7.py`) hace:

```python
if RUTA_DICCIONARIO_EMPRESA and os.path.exists(RUTA_DICCIONARIO_EMPRESA):
    ...
else:
    print("\n  [!] No se encontro el diccionario de empresas. Se omite el corte por empresa.")
    reporte_sin_ceros['Empresa'] = 'Sin_Empresa'
```

Si el archivo no se encuentra bajo el nombre por defecto, **todo el
reporte queda con `Empresa = 'Sin_Empresa'`**, sin avisar más que una
línea de log fácil de pasar por alto — esto es exactamente el síntoma
reportado. Con la spec 19 (`Carpeta_de_Trabajo/`), este problema se
volvió más visible: antes el dueño del proyecto quizás pasaba la ruta
completa a mano; ahora, si deja su archivo (ya llamado
`Diccionario_central_empresa.xlsx`) en `Carpeta_de_Trabajo/` sin
renombrarlo, no calza con el nombre por defecto que quedó escrito en
los lanzadores nuevos (heredado del mismo error de la spec 00).

## Qué construir

Reemplazar el nombre de archivo por defecto en los 4 lugares donde
aparece escrito como `Diccionario_configuracion_empresa.xlsx`, dejándolo
como `Diccionario_central_empresa.xlsx`. Es un cambio de una sola
cadena de texto por archivo, nada más:

1. `src/sc_pd_motor_v7.py`, línea ~131:
   ```python
   RUTA_DICCIONARIO_EMPRESA = r"Diccionario_central_empresa.xlsx"   # "" para desactivar
   ```
2. `scripts/diagnosticar_observacion.py`, línea ~29 (dentro del dict `RUTAS`):
   ```python
       "RUTA_DICCIONARIO_EMPRESA": r"Diccionario_central_empresa.xlsx",
   ```
3. `Carpeta_de_Trabajo/correr_motor.py`, línea ~26:
   ```python
   NOMBRE_DICCIONARIO_EMPRESA = "Diccionario_central_empresa.xlsx"
   ```
4. `Carpeta_de_Trabajo/correr_diagnostico.py`, línea ~27:
   ```python
   NOMBRE_DICCIONARIO_EMPRESA = "Diccionario_central_empresa.xlsx"
   ```
5. `README.md`, línea ~19 (texto de documentación, mismo cambio de nombre).

No cambiar nada más en ninguno de estos archivos — ni la lógica de
`asignar_empresas`, ni la carga del diccionario, ni ningún otro nombre
de archivo (`RUTA_DICCIONARIO` para centrales/configuraciones es un
archivo **distinto**, `Diccionario_central_config.xlsx`, y no se toca).

## Criterio de aceptación

- Los 5 archivos listados quedan con `Diccionario_central_empresa.xlsx`
  en vez de `Diccionario_configuracion_empresa.xlsx`.
- `grep -rn "Diccionario_configuracion_empresa" .` sobre el repo ya no
  encuentra ninguna coincidencia fuera de `docs/specs/00-restaurar-motor-v7.md`
  y `docs/specs/19-carpeta-de-trabajo-unica-para-spyder.md` (specs
  históricas ya implementadas — no se editan retroactivamente).
- Si hay datos reales disponibles en el entorno de implementación con un
  archivo `Diccionario_central_empresa.xlsx`, correr el motor completo y
  confirmar en la respuesta que la auditoría "DICCIONARIO
  CENTRAL_RELACIONADA -> EMPRESA" encuentra el archivo y mapea
  centrales a empresas (no cae en la rama "No se encontro el
  diccionario de empresas").
- `pytest -q -m ""` sigue en verde (no debería haber tests que dependan
  del nombre de archivo por defecto, ya que siempre se pasa por
  `rutas`/variables editables).

## Qué NO hacer en esta spec

- No modificar `asignar_empresas`, la lógica de rescate por
  configuración, ni ningún otro comportamiento de la sección
  "Diccionario Central_Relacionada -> Empresa".
- No tocar `RUTA_DICCIONARIO` (el diccionario de
  central/configuración, archivo distinto) ni ningún otro nombre de
  archivo por defecto.
- No editar `docs/specs/00-restaurar-motor-v7.md` ni
  `docs/specs/19-carpeta-de-trabajo-unica-para-spyder.md` — son specs
  históricas ya implementadas, quedan como registro de lo que se pidió
  en su momento.
