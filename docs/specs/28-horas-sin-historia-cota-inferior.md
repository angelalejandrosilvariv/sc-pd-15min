# 28 — Interruptor: cota inferior de horas detenidas sin ciclo anterior

**Toca código:** sí (`src/fase1_integridad.py`, `src/sc_pd_motor_v7.py`,
`Carpeta_de_Trabajo/correr_motor.py`, `Carpeta_de_Trabajo/interfaz.py`,
`tests/test_horas_sin_historia.py`)

**Cambia el monto liquidado:** sí. Nace activo
(`HORAS_SIN_HISTORIA = 'cota_inferior'`). `'nulo'` conserva exactamente la
clasificación anterior.

---

## 1. El problema

El primer ciclo de cada central relacionada no tiene `Fin_Ciclo_Anterior`, por lo
que `Horas_Detenida_Ciclo` queda nula. Aunque el reporte anterior esté empalmado y
demuestre que la unidad no generó durante semanas, esa nulidad producía
`Tipo_Partida = No_Aplica` y partida cero (mecanismo 10, causa R8 de
`docs/informes/Brechas_2608_por_empresa.md`).

YUNGAY-1 y YUNGAY-2 (ORAZUL) arrancaron el 18-ago-2026 sin generación observada
desde el inicio de julio: la detención comprobable es de al menos 48 días, superior
al umbral Fría. El Excel reconoce **313.210 CLP por unidad**; el motor anterior no
reconocía partida. TENOGAS_GLP presenta el mismo mecanismo el 3-ago.

## 2. La regla

Para un ciclo sin anterior:

```
Horas_Cota_Inferior = Inicio_Ciclo - primer FECHA_HORA de todos los datos cargados
```

El primer dato incluye el mes anterior cuando se empalmó. Si la cota es
**estrictamente mayor** que `Fria_Num1_M` de la política aplicable, la partida se
clasifica Fría. Esto es seguro: agregar más historia solo puede aumentar las horas
y no cambiará el tramo. Si no supera el umbral, queda `No_Aplica`, costo cero y
`Obs_Partida = "Sin historia suficiente: cota N h < umbral Fria"`. Con `'nulo'`
no se usa la cota.

`Horas_Detenida_Ciclo` deliberadamente **permanece nula**. La marca
`Horas_Detenida_Estimada` indica que la cota sí permitió determinar Fría; no afirma
conocer la duración real. Ambos campos de auditoría se exportan.

## 3. Exención RIO

`REGLA_EXENCION = 'sin_historia'` sigue mirando la nulidad de
`Horas_Detenida_Ciclo`, no `Horas_Detenida_Estimada`. Por tanto, un ciclo clasificado
Fría mediante cota **sigue exento** si falta RIO. La razón es independiente: la
exención responde a falta de historia RIO, mientras la cota resuelve únicamente el
tramo de horas. Mezclar ambas ausencias rompería una regla existente.

## 4. Implementación

- `horas_cota_inferior()` es una función pura que devuelve cota solo donde no hay
  horas reales de un ciclo anterior.
- `clasificar_partida()` usa la cota únicamente para probar el tramo Fría.
- El motor calcula la cota con el mínimo `FECHA_HORA` del reporte ya empalmado.
- `Resumen_Ciclos_PD` y `Guia_Lectura` exponen la cota y la marca estimada.
- El runner y la interfaz ofrecen `'cota_inferior'` / `'nulo'`; el control queda
  deshabilitado para Turbina y Reglas del Horario. Esos motores no se modifican.

## 5. Pruebas

`tests/test_horas_sin_historia.py` cubre: cota sobre umbral → Fría; bajo umbral →
`No_Aplica`; `'nulo'` idéntico al comportamiento previo; ciclo con anterior sin
cambios; columnas y guía exportables.

## 6. Pendientes

Validar en una corrida productiva de agosto empalmada con julio el monto de YUNGAY
y TENOGAS_GLP. Los datos operacionales no se versionan y no forman parte de la
suite sintética.
