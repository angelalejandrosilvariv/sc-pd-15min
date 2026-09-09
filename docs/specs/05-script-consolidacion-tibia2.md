# Spec 05 — Traer `consolidar_politicas.py` al repo y capturar "Partida Tibia 2"

**Para:** ChatGPT/Codex (implementador de código de este repo)
**De:** Claude (planificador/testeador del proyecto)
**Estado:** listo para ejecutar
**Toca código:** sí — archivo nuevo `scripts/consolidar_politicas.py`

## Contexto

`Costos_de_P-D_Consolidado.xlsx` (el insumo que carga el motor) no se
escribe a mano: lo genera este script (`consolidar_politicas.py`), que el
dueño del proyecto corre por separado, leyendo los archivos `PO*.xlsx`
("Políticas PO") de la hoja `RESUMEN` y armando el consolidado.

Revisando un archivo `PO` real (`PO260609_20.xlsx`, hoja `RESUMEN`)
encontré que las columnas de esa hoja son:

```
col 11: Partida Fría (costo)       col 12: Tiempo F/S Fría
col 13: Partida Tibia (costo)      col 14: Tiempo F/S Tibia
col 15: Partida Tibia 2 (costo)    col 16: Tiempo F/S Tibia 2   <- NO SE LEE HOY
col 17: Partida Caliente (costo)   col 18: Tiempo F/S Caliente
col 19: Detención (costo)
```

El script actual lee las columnas 11-14 y salta directo a la 17 — **las
columnas 15 y 16 ("Partida Tibia 2" y su rango de horas) nunca se
capturan**, y por lo tanto tampoco existen en
`Costos_de_P-D_Consolidado.xlsx` ni llegan al motor.

Ejemplo real de `GUACOLDA-3_CAR` en ese mismo archivo PO:

| | Fría | Tibia | **Tibia 2** | Caliente |
|---|---|---|---|---|
| Horas | `> 144` | `24 a 72` | **`72 a 144`** | `< 24` |
| Costo (US$) | 50.050,69 | 30.838,53 | **31.963,69** | 18.011,61 |

Sin la columna 15/16, una parada de, por ejemplo, 100 horas en esa central
no tiene forma de cobrarse a 31.963,69 (su tarifa correcta) — hoy el motor
la clasificaría como "Tibia" normal (30.838,53), más barata de lo que
corresponde. El dueño del proyecto confirmó la regla completa de 4 tramos:

```
Caliente (< 24)  ->  Tibia (24 a 72)  ->  Tibia 2 (72 a 144)  ->  Fría (> 144)
```

Y confirmó que este script debe vivir en este repositorio de ahora en
adelante, junto con el resto del proyecto.

## Instrucción

### 1. Crear `scripts/consolidar_politicas.py` con el contenido de más abajo

Es una transcripción literal del script tal como lo entregó el dueño del
proyecto — **ya incluye el fix de Tibia 2** descrito en el punto 2. No hace
falta que reconstruyas la versión "sin el fix": crea el archivo
directamente con este contenido.

### 2. El fix ya incorporado en el código de abajo (para que entiendas qué cambió respecto al original)

Comparado con el script que compartió el dueño del proyecto, se agregó:

- `df_temp['Partida_Tibia_2'] = df_recortado[15].values` y
  `df_temp['Tiempo_Partida_Tibia_2'] = df_recortado[16].values` (mismo
  patrón que las otras columnas).
- `'Partida_Tibia_2'` y `'Tiempo_Partida_Tibia_2'` agregadas a
  `columnas_limpiar`, para que pasen por la misma limpieza (comas, `<`,
  guiones, `nan`) que las demás columnas de costo/tiempo.
- Una auditoría nueva, al final de la función, que para las filas donde
  `Partida_Tibia_2` es un número real (no exento), extrae el rango de
  `Tiempo_Partida_Tibia_2` (dos números, mismo patrón regex que ya usa el
  script) y compara contra `(Tibia_Num2_N, Fria_Num1_M)` — que deberían
  coincidir, porque el límite superior de "Tibia" y el límite inferior de
  "Fría" son los mismos bordes que enmarcan "Tibia 2". Si no coinciden,
  imprime una alerta con la unidad y los valores en conflicto (esto ya
  detectó, en los datos de ejemplo, un caso -`GUACOLDA-5_CAR`- donde el
  precio de Tibia 2 existe pero el texto de horas viene vacío (`"-"`); la
  alerta sirve para que el dueño del proyecto lo revise a mano, no para
  bloquear la ejecución).
- **No se modificó ninguna otra lógica** (fechas, `Llave_Concatenada`,
  `Costo_Cero`, extracción de `Fria_Num1_M`/`Tibia_Num1_O`/`Tibia_Num2_N`/
  `Caliente_Num1_P`) — todo eso queda idéntico al original.

### 3. Verificación antes de commitear

1. `python -c "import ast; ast.parse(open('scripts/consolidar_politicas.py', encoding='utf-8').read())"`
   no debe lanzar `SyntaxError`.
2. El archivo debe seguir siendo ejecutable de forma independiente
   (`python scripts/consolidar_politicas.py` desde una carpeta con
   `Politicas PO/PO*.xlsx`), igual que el original.

## Código para `scripts/consolidar_politicas.py`

```python
# -*- coding: utf-8 -*-
"""
Created on Tue Jun  9 16:51:51 2026

@author: angel.silva
"""

import pandas as pd
import numpy as np
import os
import glob

def consolidar_politicas():
    # 1. Definir la ruta de los archivos
    ruta_base = os.getcwd()
    ruta_pol = os.path.join(ruta_base, "Politicas PO")
    
    # Buscar solo los archivos Excel que comiencen con "PO"
    archivos_excel = glob.glob(os.path.join(ruta_pol, "PO*.xls*"))
    
    if not archivos_excel:
        print("No se encontraron archivos que comiencen con 'PO' en la ruta especificada.")
        return

    datos_consolidados = []

    # 2. Iterar sobre cada archivo de política filtrado
    for archivo in archivos_excel:
        nombre_archivo = os.path.basename(archivo)
        
        # Omitimos las dos primeras letras ("PO") para extraer la fecha y hora
        nom = nombre_archivo[2:]
        dia = nom[:6]
        hor_str = nom[7:9]
        
        try:
            hora = int(hor_str)
        except ValueError:
            hora = 1
            
        # 3. Leer la hoja "RESUMEN" del archivo actual
        try:
            df = pd.read_excel(archivo, sheet_name="RESUMEN", header=None)
        except Exception as e:
            print(f"Error leyendo la hoja RESUMEN en {nombre_archivo}: {e}")
            continue
            
        # 4. Buscar la celda con "E max generable" para definir la fila de inicio
        mask = df.apply(lambda col: col.astype(str).str.contains("E max generable", case=False, na=False))
        
        if not mask.any().any():
            print(f"No se encontró 'E max generable' en {nombre_archivo}")
            continue
            
        fila_encontrada = mask.idxmax().max()
        fila_inicio = fila_encontrada + 3
        
        # Recortar el dataframe desde la fila de inicio
        df_recortado = df.iloc[fila_inicio:].copy()
        
        # Detener la lectura al encontrar "Total" u "Observaciones"
        mask_fin = df_recortado[1].astype(str).str.contains('^Total|^Observaciones', case=False, na=False)
        if mask_fin.any():
            idx_fin = mask_fin.idxmax()
            df_recortado = df_recortado.loc[:idx_fin - 1].copy()
            
        # Detener también en la primera celda que esté realmente vacía
        mask_vacia = df_recortado[1].isna() | (df_recortado[1].astype(str).str.strip() == '')
        if mask_vacia.any():
            idx_vacio = mask_vacia.idxmax()
            df_recortado = df_recortado.loc[:idx_vacio - 1].copy()
        
        # 5. Extraer las columnas equivalentes a las letras de Excel
        df_temp = pd.DataFrame()
        df_temp['DIA'] = [dia] * len(df_recortado)
        df_temp['HORA'] = [hora] * len(df_recortado)
        
        df_temp['UNIDAD'] = df_recortado[1].values                    
        df_temp['Partida_Fria'] = df_recortado[11].values             
        df_temp['Partida_Tibia'] = df_recortado[13].values            
        df_temp['Partida_Caliente'] = df_recortado[17].values         
        df_temp['Detencion'] = df_recortado[19].values                
        df_temp['Tiempo_Partida_Fria'] = df_recortado[12].values      
        df_temp['Tiempo_Partida_Tibia'] = df_recortado[14].values     
        df_temp['Tiempo_Partida_Caliente'] = df_recortado[18].values  
        
        datos_consolidados.append(df_temp)

    # 6. Unir todos los dataframes recopilados
    if datos_consolidados:
        df_final = pd.concat(datos_consolidados, ignore_index=True)
        
        # 7. Reemplazos masivos
        columnas_limpiar = [
            'Partida_Fria', 'Partida_Tibia', 'Partida_Caliente', 'Detencion', 
            'Tiempo_Partida_Fria', 'Tiempo_Partida_Tibia', 'Tiempo_Partida_Caliente'
        ]
                            
        for col in columnas_limpiar:
            df_final[col] = df_final[col].astype(str)
            df_final[col] = df_final[col].str.replace(',', '.', regex=False)
            df_final[col] = df_final[col].str.replace('<', '< ', regex=False)
            df_final[col] = df_final[col].str.replace('-', '0', regex=False)
            df_final[col] = df_final[col].replace('nan', np.nan)
            
        # 8. --- LIMPIEZA DE NOMBRES Y COLUMNAS CALCULADAS ---
        
        # Eliminar asteriscos entre paréntesis (ej: " (***)", " (**)") y quitar espacios extra
        df_final['UNIDAD'] = df_final['UNIDAD'].astype(str).str.replace(r'\s*\(\*+\)', '', regex=True).str.strip()
        
        # Fórmula concatenada
        df_final['Llave_Concatenada'] = (
            df_final['DIA'].astype(str) + 
            "-" + 
            df_final['HORA'].astype(str) + 
            df_final['UNIDAD']
        )

        # Fórmula Costo Cero
        df_final['Costo_Cero'] = np.where(
            (df_final['Partida_Fria'].astype(str).str.strip() == '0') | 
            (df_final['Partida_Fria'].astype(str).str.strip() == '-'),
            'SI',
            'NO'
        )

        # 9. --- EXTRACCIÓN DE NÚMEROS (Reemplazo de la macro ExtraerNumeros_Costos_PD) ---
        
        # Definimos el patrón Regex para atrapar secuencias numéricas (con o sin decimales)
        patron_numeros = r'(\d+(?:\.\d+)?)'
        
        # M: 1er número de 'Tiempo_Partida_Fria' (Columna I en VBA)
        df_final['Fria_Num1_M'] = df_final['Tiempo_Partida_Fria'].astype(str).str.findall(patron_numeros).str[0].astype(float)
        
        # O: 1er número de 'Tiempo_Partida_Tibia' (Columna J en VBA)
        df_final['Tibia_Num1_O'] = df_final['Tiempo_Partida_Tibia'].astype(str).str.findall(patron_numeros).str[0].astype(float)
        
        # N: 2do número de 'Tiempo_Partida_Tibia' (Columna J en VBA)
        df_final['Tibia_Num2_N'] = df_final['Tiempo_Partida_Tibia'].astype(str).str.findall(patron_numeros).str[1].astype(float)
        
        # P: 1er número de 'Tiempo_Partida_Caliente' (Columna K en VBA)
        df_final['Caliente_Num1_P'] = df_final['Tiempo_Partida_Caliente'].astype(str).str.findall(patron_numeros).str[0].astype(float)
                
        # 10. Exportar el resultado a un nuevo archivo Excel
        archivo_salida = "Costos_de_P-D_Consolidado.xlsx"
        df_final.to_excel(archivo_salida, index=False)
        print(f"¡Proceso terminado con éxito! Archivo guardado como {archivo_salida}")
    else:
        print("No se extrajeron datos de ningún archivo.")

# Ejecutar la función
consolidar_politicas()

```

## Ahora, el fix real: reemplaza el bloque de extracción de columnas y el bloque de limpieza/auditoría

Dentro del archivo que acabas de crear, aplica estos 3 cambios puntuales:

**Cambio A** — en el bloque "5. Extraer las columnas equivalentes a las
letras de Excel", agrega estas dos líneas justo después de
`df_temp['Tiempo_Partida_Caliente'] = df_recortado[18].values`:

```python
        df_temp['Partida_Tibia_2'] = df_recortado[15].values
        df_temp['Tiempo_Partida_Tibia_2'] = df_recortado[16].values
```

**Cambio B** — en `columnas_limpiar` (bloque "7. Reemplazos masivos"),
agrega `'Partida_Tibia_2'` y `'Tiempo_Partida_Tibia_2'` a la lista:

```python
        columnas_limpiar = [
            'Partida_Fria', 'Partida_Tibia', 'Partida_Tibia_2', 'Partida_Caliente', 'Detencion',
            'Tiempo_Partida_Fria', 'Tiempo_Partida_Tibia', 'Tiempo_Partida_Tibia_2', 'Tiempo_Partida_Caliente'
        ]
```

**Cambio C** — después del bloque "9. EXTRACCIÓN DE NÚMEROS" (después de
la línea que define `Caliente_Num1_P`), agrega la auditoría de
consistencia Tibia 2, antes de exportar el archivo:

```python
        # 9.1 --- AUDITORIA: CONSISTENCIA DE "PARTIDA TIBIA 2" ---
        # El limite superior de Tibia y el limite inferior de Fria deberian
        # coincidir con el rango que describe Tiempo_Partida_Tibia_2, porque
        # ambos tramos comparten el mismo borde. Si no coinciden, se avisa
        # (no se corta la ejecucion) para que se revise el dato de origen.
        con_tibia2 = df_final['Partida_Tibia_2'].astype(str).str.strip().replace({'0': np.nan, 'nan': np.nan})
        filas_tibia2 = df_final[con_tibia2.notna()].copy()
        if not filas_tibia2.empty:
            rango_tibia2 = filas_tibia2['Tiempo_Partida_Tibia_2'].astype(str).str.findall(patron_numeros)
            inicio_tibia2 = rango_tibia2.str[0].astype(float)
            fin_tibia2 = rango_tibia2.str[1].astype(float)
            esperado_inicio = filas_tibia2['Tibia_Num2_N']
            esperado_fin = filas_tibia2['Fria_Num1_M']
            inconsistentes = filas_tibia2[
                (inicio_tibia2.round(3) != esperado_inicio.round(3)) |
                (fin_tibia2.round(3) != esperado_fin.round(3))
            ]
            if not inconsistentes.empty:
                print(f"\n[!] {len(inconsistentes)} fila(s) con 'Partida Tibia 2' cuyo rango de horas")
                print("    no coincide con (Tibia_Num2_N, Fria_Num1_M). Revisar a mano:")
                cols_aviso = ['DIA', 'HORA', 'UNIDAD', 'Tiempo_Partida_Tibia_2', 'Tibia_Num2_N', 'Fria_Num1_M']
                print(inconsistentes[cols_aviso].to_string(index=False))
            else:
                print(f"\nOK: {len(filas_tibia2)} fila(s) con 'Partida Tibia 2' y rango de horas consistente.")
```

## Criterio de aceptación

- `scripts/consolidar_politicas.py` existe, parsea sin error, y al
  correrlo sobre los mismos archivos `PO*.xlsx` de ejemplo produce un
  `Costos_de_P-D_Consolidado.xlsx` con las columnas nuevas
  `Partida_Tibia_2` y `Tiempo_Partida_Tibia_2` pobladas para las unidades
  que las tengan (ej. `GUACOLDA-1` a `-5`), y en `0`/vacío para las que no
  (idéntico al patrón de `Partida_Tibia`).
- Ninguna columna ni fila existente cambia de valor respecto al script
  original — el único cambio observable es que aparecen las 2 columnas
  nuevas y el mensaje de auditoría al final.

## Qué NO hacer en esta spec

- No tocar la extracción de `Fria_Num1_M`, `Tibia_Num1_O`, `Tibia_Num2_N`,
  `Caliente_Num1_P`, ni la lógica de `Costo_Cero`, `Llave_Concatenada` o el
  parseo de `DIA`/`HORA` — todo eso queda igual.
- No modificar `src/sc_pd_motor_v7.py` en esta spec — eso es
  `docs/specs/06-motor-cuarto-tramo-tibia2.md`, a aplicar después de esta.
