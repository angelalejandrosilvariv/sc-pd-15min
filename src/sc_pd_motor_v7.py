# -*- coding: utf-8 -*-
"""
Created on Mon Sep  7 16:59:29 2026
Modificado Sep 8 2026: empalme del RIO con el mes anterior (ver BUG 7 abajo).

@author: angel.silva
"""

# -*- coding: utf-8 -*-
"""
MOTOR DE SOBRECOSTOS DE PARTIDA Y DETENCION (SC P-D) - RESOLUCION 15 MINUTOS
Version 7

Correcciones acumuladas:
  [BUG 1] shift() sobre columna booleana devolvia dtype 'object'. El operador ~
          aplicaba negacion bitwise (~True = -2, ~False = -1, ambos truthy), por
          lo que TODAS las filas quedaban marcadas como inicio de ciclo y cada
          bloque de 15 min se convertia en un ciclo independiente.
          -> shift(1, fill_value=False) + astype(bool).
  [BUG 2] El mapeo difuso de columnas del RIO enganchaba las columnas
          equivocadas: MOTIVO nunca se leia (columna real 'MOT'), ESTADO
          OPERACIONAL tomaba 'ESTADO OPERACIONAL COMBUSTIBLE' en vez de 'EO',
          y CONSIGNAS tomaba 'CONSIGNA LIMITACION' en vez de 'CON'.
          -> Mapeo explicito + validacion que aborta si falta una columna.
  [BUG 3] El empalme con el mes pasado concatenaba sin recortar ni deduplicar,
          duplicando energia si los archivos se traslapan.
          -> Recorte a FECHA_HORA < inicio del mes actual + deduplicacion.
  [BUG 4] La extraccion de politicas PO exigia 8 digitos (AAAAMMDD) pero la
          Llave_Concatenada real usa 6 (AAMMDD-H, ej. '260701-1'). Ninguna
          llave cruzaba y el waterfall completo salia en cero.
          -> Deteccion automatica del formato + verificacion del cruce.
  [BUG 5] Con el empalme activado, el ID de ciclo venia corrido desde el mes
          anterior. Dos consecuencias: las etiquetas del Excel no eran
          comparables entre meses, y la exencion "primer ciclo sin registro
          RIO" dejo de aplicarse porque ningun ciclo del mes tenia ID = 1.
          -> Renumeracion de presentacion (14.2) + regla de exencion
             parametrizada (REGLA_EXENCION).
  [BUG 6] Cuando una central puede operar bajo mas de una configuracion (ej.
          turbina sola vs ciclo combinado con turbina a vapor), el costo de
          partida/detencion se decidia con el bloque cronologicamente
          PRIMERO/ULTIMO del ciclo, sin importar cuanta generacion aporto esa
          configuracion. Si la turbina enciende un cuarto de hora antes de que
          se sume el vapor, ese cuarto de hora aislado cobraba su propia
          tarifa (mas barata) para TODO el ciclo. Confirmado en terreno para
          NEHUENCO-1, TOCOPILLA-U16, KELAR-TG12, ATACAMA-1/2TG y otras -
          impacto medido en cientos de millones de CLP/mes.
          -> USAR_CONFIG_DOMINANTE = 1 reasigna la partida/detencion a la
             configuracion que domino el ciclo por generacion (seccion 14.1).
             Apagado por defecto: con 0 el comportamiento es identico al v4.
  [BUG 7] El RIO se cargaba SOLO del mes actual (RUTA_RIO), a diferencia del
          reporte de 15 min y de la tabla de costos, que si empalman con el
          mes anterior. Para un ciclo que arranco en el mes pasado y sigue
          vivo (o termina) en el mes actual, el merge_asof hacia atras no
          tenia NINGUN registro RIO al cual mirar - no era un problema de
          tolerancia (24h), sino que la fuente completa faltaba para ese
          rango de fechas. Confirmado en el reporte de Junio 2026: 24 ciclos
          que arrancaron en Mayo (SANTAMARIA_CAR, CAMPICHE_CAR, las GUACOLDA,
          etc.) quedaron con Config_RIO_Usada_Partida = 'Sin_Registro_RIO' y
          su costo de partida se cobro en CLP 0 con observacion "Revisar
          manualmente: config RIO sin tarifa", pese a representar ~90% del
          monto total en esa categoria (CLP 529M de CLP 590M potenciales,
          bajo el calculo de referencia por configuracion propia).
          -> RUTA_RIO_MES_PASADO empalma el RIO del mes anterior con el mismo
             patron ya usado en BUG 3 para el reporte de 15 min: recorte a
             FECHA_HORA_RIO < inicio del mes actual + deduplicacion. Se
             extrajo la carga y el parseo del RIO a la funcion leer_rio()
             para no duplicar la logica entre mes actual y mes pasado.
             Apagado con RUTA_RIO_MES_PASADO = "" (comportamiento identico al
             v6, salvo por el refactor a funcion).
  [BUG 8] El filtro de grupos sin generacion comparaba una suma agregada con
          cero exacto. Un grupo con consumo auxiliar que cancelaba su
          generacion podia desaparecer aunque contuviera bloques activos.
          -> La seccion 2 evalua (s.fillna(0) != 0).any() bloque a bloque.
  [BUG 9] La consolidacion no leia "Partida Tibia 2" y el motor clasificaba
          solo tres tramos, subcobrando detenciones entre Tibia_Num2_N y
          Fria_Num1_M. Ahora el consolidado y ambas ramas tarifarias usan los
          cuatro tramos confirmados.
  [v6]    Cambio de diseno, no un bug: hasta v5, si la configuracion propia
          (la que genero, o la dominante) no calzaba con lo que el RIO
          reportaba como despachado, el costo de partida/detencion se
          anulaba por completo - como si la partida no hubiera ocurrido. Pero
          la generacion ya confirma que la partida SI ocurrio; lo unico en
          duda es que tarifa corresponde. USAR_TARIFA_RIO_INSTRUIDA = 1
          reemplaza el filtro de configuracion por completo: se cobra la
          tarifa de la configuracion que el RIO instruyo en el primer/ultimo
          bloque del ciclo COMPLETO (tal cual, sin buscar el momento en que
          el RIO se actualiza). Ya no hace falta elegir una "configuracion
          dominante" (USAR_CONFIG_DOMINANTE se ignora si este esta activo),
          porque Configuracion RIO ya es el mismo dato para todas las
          sub-configuraciones que comparten un instante. Los otros dos
          filtros (Maquina en Pruebas, Sin Motivo ni SSCC) NO cambian. Si la
          configuracion que instruye el RIO no tiene tarifa en la tabla de
          costos (o no hay ningun registro de RIO), el costo NO se cobra
          automatico: queda marcado "Revisar manualmente", distinto de un
          rechazo por filtro. Apagado por defecto (secciones 10.1, 11.1 y
          14.1b).

El ID interno sigue siendo continuo a proposito: un ciclo que parte el 30 del
mes anterior y termina el 2 del actual debe seguir siendo UN solo ciclo. La
renumeracion es solo para el reporte y conserva la etiqueta original.
"""

import os
import re
import sys
import pandas as pd
import numpy as np

from fase1_integridad import (calcular_ciclos, clasificar_partida, costos_clasicos,
                              deduplicar_rio_priorizando_motivo,
                              empalmar_reportes, filtro_costo_cero, marcar_sin_tarifa_rio)

# ==========================================
# 0. PANEL DE CONTROL Y RUTAS DE ARCHIVOS
# ==========================================
# MES ACTUAL
RUTA_REPORTE_15MIN = r"C:\Kpi SC_PD\5 a 6\Reporte_PD_15min_2606.csv"
# MES ANTERIOR (para resolver ciclos inconclusos en la frontera). "" para desactivar.
RUTA_REPORTE_MES_PASADO  = r"C:\Kpi SC_PD\4 a 5\Reporte_PD_15min_2605.csv"
RUTA_RIO                 = r"RIO_06_2026.xlsx"
# [BUG 7] RIO del mes anterior. Mismo rol que RUTA_REPORTE_MES_PASADO: sin
# esto, un ciclo que arranco en el mes pasado y sigue vivo en el actual no
# tiene NINGUN registro RIO al cual mirar hacia atras, y su partida/detencion
# se cobra en CLP 0 con "Revisar manualmente: config RIO sin tarifa" aunque
# la generacion confirme que si ocurrio. "" para desactivar (comportamiento
# identico al v6).
RUTA_RIO_MES_PASADO      = r"RIO_05_2026.xlsx"
RUTA_COSTOS_PD           = r"Costos_de_P-D_Consolidado.xlsx"
RUTA_COSTOS_MES_PASADO   = r"T:\Facturacion\Plabacom\2026\2605\02 Definitivo\SOBRECOSTOS PD\Costos_de_P-D_Consolidado.xlsx"
RUTA_DICCIONARIO         = r"Diccionario_central_config.xlsx"
RUTA_DICCIONARIO_EMPRESA = r"Diccionario_configuracion_empresa.xlsx"   # "" para desactivar
RUTA_SALIDA              = r"Reporte_Sobrecostos_PD_Final.xlsx"

# --- Logica de negocio ---
ACTIVAR_BUSQUEDA_RELAJADA = 1   # 1 = busca el registro RIO mas conveniente en una ventana
VENTANA_CUARTOS_HORA      = 2   # +/- 2 cuartos = +/- 30 min
FILTRAR_CICLOS_BAJA_GEN   = 1   # Rechaza ciclos con generacion <= UMBRAL_RUIDO_MWH
UMBRAL_RUIDO_MWH          = 1.0
RENUMERAR_CICLOS_DEL_MES  = 1   # 1 = etiquetas del reporte parten en 1 cada mes

# Cuando una central puede operar bajo mas de una configuracion (ej. turbina
# sola vs ciclo combinado con turbina a vapor), el costo de partida/detencion
# hoy se decide con la configuracion del bloque cronologicamente PRIMERO/
# ULTIMO del ciclo, sin importar si esa configuracion aporto el 0.1% o el 99%
# de la generacion. Si la turbina enciende un cuarto de hora antes de que se
# sume el vapor, ese cuarto de hora aislado cobra su propia tarifa (mas
# barata) para TODO el ciclo. Confirmado en terreno para NEHUENCO-1,
# TOCOPILLA-U16, KELAR-TG12, ATACAMA-1/2 y otras — ver Auditoria_Config_Dominante.
#   0 = comportamiento actual (bloque cronologico primero/ultimo)
#   1 = usa la configuracion que domino el ciclo por generacion, no la que
#       aparecio primero/ultimo en el tiempo. Afecta Central_Partida/Detencion,
#       Costo_Partida/Detencion_Base y los filtros/campos RIO asociados.
USAR_CONFIG_DOMINANTE = 0

# Mide (sin cambiar ningun costo) que proporcion de la generacion del mes
# tiene una instruccion de RIO directa, cuanta la encuentra solo gracias a
# los mecanismos de ampliacion (misma config coexistente en el bloque, o
# ventana de busqueda relajada), y cuanta no tiene instruccion en absoluto.
# Ver seccion 10.1. Correr con 0 si no se necesita, para ahorrar tiempo.
AUDITAR_INSTRUCCION_RIO = 1

# v6: en vez de anular el costo cuando la configuracion propia no calza con
# el RIO, se cobra la tarifa de la configuracion QUE EL RIO INSTRUYO en el
# primer/ultimo bloque del ciclo completo (tal cual, sin buscar el momento en
# que el RIO se actualiza). La central partio - eso ya lo confirma la
# generacion - lo unico que puede estar mal es que tarifa aplicar, y esa la
# define el RIO, no nuestra propia Central.
#   - Reemplaza COMPLETAMENTE el filtro de configuracion (Filtro_Conf pasa a
#     ser siempre 1). Los otros dos filtros (Maquina en Pruebas, Sin Motivo)
#     NO cambian.
#   - Ya no usa 'configuracion dominante' (USAR_CONFIG_DOMINANTE se ignora si
#     este interruptor esta en 1): Configuracion RIO ya es la misma para
#     todas las sub-configuraciones que comparten un mismo instante, asi que
#     no hace falta elegir cual predomina.
#   - Si la configuracion que instruye el RIO no tiene tarifa en la tabla de
#     costos (o no hay ningun registro de RIO), el costo NO se cobra
#     automaticamente: queda en 0 con Obs_Partida/Detencion = "Revisar
#     manualmente", distinto de un rechazo por filtro.
USAR_TARIFA_RIO_INSTRUIDA = 1

# Regla de exencion cuando el RIO no tiene registro de motivo.
#   'sin_historia' : exime a los ciclos sin ciclo anterior conocido
#                    (Horas_Detenida_Ciclo nula). Es el equivalente correcto de
#                    la regla original una vez que el empalme mensual esta
#                    activo, porque el ID de ciclo ya no parte en 1.
#   'primer_ciclo' : replica literalmente la regla antigua (Ciclo_ID == 1). Con
#                    el empalme activo practicamente no exime a nadie.
#   'off'          : sin exencion. Sin motivo en el RIO, no se reconoce costo.
REGLA_EXENCION = 'sin_historia'

# Un ciclo va desde que la central parte generando hasta que deja de generar.
# TOLERANCIA_CORTES_BLOQUES debe quedar en 0 para respetar esa definicion.
TOLERANCIA_CORTES_BLOQUES = 0

# Formatos aceptados para Llave_Concatenada. Se prueban en orden y se usa el
# primero que reconozca alguna llave. El de 8 digitos va primero porque el
# patron de 6 tambien haria match con el prefijo de una llave de 8.
PATRONES_PO = [(r'^(\d{8})-(\d{1,2})', '%Y%m%d'),
               (r'^(\d{6})-(\d{1,2})', '%y%m%d')]

# Codigos de la columna EO del RIO que habilitan el reconocimiento del costo.
# PENDIENTE DE CONFIRMAR: la formula original de Excel usaba "PDO", que no
# aparece en la columna EO. Ajusta esta lista cuando lo confirmes con el CEN.
CODIGOS_EO_VALIDOS = ['PDO']

# Los bloques vienen etiquetados con la hora de INICIO del cuarto de hora. La
# maquina en realidad se detiene 15 min despues del ultimo bloque con
# generacion. Con 1 se corrige Horas_Detenida_Ciclo; con 0 se conserva el
# comportamiento historico. Cambiar esto mueve la frontera Fria/Tibia/Caliente.
AJUSTAR_FIN_BLOQUE = 0
MINUTOS_BLOQUE     = 15

# --- Interruptores de auditoria ---
AUDITAR_MAPEO_RIO            = 1
AUDITAR_MAPEO_DICCIONARIO    = 1
AUDITAR_LIMITES_CICLOS       = 1
AUDITAR_ENERGIA_INTER_CICLOS = 1


def validar_meses_reporte(df, etiqueta, fecha_hora_original=None):
    """Aborta si un reporte nominalmente mensual se dispersa en varios meses."""
    meses = df['FECHA_HORA'].dt.to_period('M')
    conteos = meses.value_counts().sort_index()
    if len(conteos) <= 2:
        return

    originales = (fecha_hora_original.reindex(df.index) if fecha_hora_original is not None
                  else df['FECHA_HORA'].astype(str))
    mes_principal = conteos.idxmax()
    indices_problematicos = df.index[meses != mes_principal][:12]
    muestra = pd.DataFrame({
        'FECHA_HORA_original': originales.loc[indices_problematicos],
        'FECHA_HORA_parseada': df.loc[indices_problematicos, 'FECHA_HORA'],
    })

    print("\n" + "!" * 78)
    print(f"  ALERTA CRITICA: {etiqueta} contiene {len(conteos)} meses-calendario")
    print("  Filas por mes:")
    for mes, cantidad in conteos.items():
        print(f"    {mes}: {cantidad:,} filas")
    print("  Muestra de filas fuera del mes principal "
          f"({mes_principal}; original -> parseada):")
    print(muestra.to_string(index=False))
    print("!" * 78)
    sys.exit(
        f"ERROR: {etiqueta} contiene fechas en {len(conteos)} meses-calendario; "
        "revisa el formato de FECHA_HORA."
    )


def leer_reporte(ruta, etiqueta):
    """Carga un CSV de 15 minutos y normaliza FECHA_HORA como mes-primero."""
    df = pd.read_csv(ruta, sep=",", low_memory=False)
    fecha_hora_original = df['FECHA_HORA'].astype(str).str.strip()
    df['FECHA_HORA'] = pd.to_datetime(
        fecha_hora_original, format='mixed', dayfirst=False, errors='coerce'
    )
    nulas = df['FECHA_HORA'].isna().sum()
    if nulas:
        print(f"  [!] {etiqueta}: {nulas:,} filas con FECHA_HORA ilegible fueron descartadas.")
        df = df.dropna(subset=['FECHA_HORA'])
    validar_meses_reporte(df, etiqueta, fecha_hora_original)
    return df


def rescatar_config_rio_en_limites(resumen, rio_subset, activar, ventana_cuartos_hora):
    """Rescata la configuracion RIO de los limites de ciclo dentro de una ventana.

    Este cruce es deliberadamente independiente del cruce maestro y de la
    busqueda relajada de filtros: solo completa configuraciones ausentes en los
    bloques globales de partida/detencion y conserva la fecha RIO usada.
    """
    resultado = resumen.copy()
    resultado['Config_RIO_Rescatada_Ventana'] = False
    if activar != 1 or resultado.empty or rio_subset.empty:
        return resultado

    es_limite = ((resultado['FECHA_HORA'] == resultado['Inicio_Ciclo_Global'])
                 | (resultado['FECHA_HORA'] == resultado['Termino_Ciclo_Global']))
    pendientes = resultado.index[
        es_limite & resultado['Configuracion RIO'].eq('Sin_Registro_RIO')]
    if pendientes.empty:
        return resultado

    rio_valido = rio_subset.dropna(
        subset=['FECHA_HORA_RIO', 'Central_Relacionada_RIO', 'NOMBRE CONFIGURACIÓN'])
    por_central = {central: grupo for central, grupo in
                   rio_valido.groupby('Central_Relacionada_RIO', sort=False)}
    tolerancia = pd.Timedelta(minutes=ventana_cuartos_hora * 15)

    for indice in pendientes:
        fila = resultado.loc[indice]
        candidatos = por_central.get(fila['Central_Relacionada'])
        if candidatos is None:
            continue
        diferencias = (candidatos['FECHA_HORA_RIO'] - fila['FECHA_HORA']).abs()
        dentro = diferencias <= tolerancia
        if not dentro.any():
            continue
        mejor_indice = diferencias[dentro].idxmin()
        mejor = candidatos.loc[mejor_indice]
        resultado.at[indice, 'Configuracion RIO'] = mejor['NOMBRE CONFIGURACIÓN']
        resultado.at[indice, 'Fuente_Config_RIO'] = mejor['FECHA_HORA_RIO']
        resultado.at[indice, 'Config_RIO_Rescatada_Ventana'] = True

    return resultado


def main(rutas: dict, panel: dict | None = None):
    """Ejecuta el motor con rutas/interruptores opcionales sobre el panel actual."""
    globals().update(rutas or {})
    globals().update(panel or {})

    # ==========================================
    # UTILIDADES
    # ==========================================
    _audit_log = []


    def audit_gen(label, df, col_gen='GENERACION', prev_gen=None, prev_rows=None):
        """Registra filas y MWh en un punto de control del pipeline."""
        gen_actual = pd.to_numeric(df[col_gen], errors='coerce').sum() if col_gen in df.columns else 0
        rows_actual = len(df)
        linea = f"  [{label}]  filas={rows_actual:>7,}  gen={gen_actual:>14,.2f} MWh"
        if prev_gen is not None and prev_gen > 0:
            delta_gen = prev_gen - gen_actual
            pct = 100 * delta_gen / prev_gen
            linea += f"  |  dgen={delta_gen:>+12,.2f} MWh ({pct:>6.2f}%)  dfilas={(prev_rows or 0) - rows_actual:>+7,}"
        print(linea)
        _audit_log.append({
            'paso': label,
            'filas': rows_actual,
            'gen_MWh': round(gen_actual, 2),
            'delta_gen': round((prev_gen or gen_actual) - gen_actual, 2) if prev_gen is not None else 0,
            'pct_perdida': round(100 * ((prev_gen - gen_actual) / prev_gen), 2) if prev_gen and prev_gen > 0 else 0,
        })
        return gen_actual, rows_actual


    def print_audit_summary():
        print("\n" + "=" * 78)
        print("  RESUMEN DE AUDITORIA - GENERACION POR PASO")
        print("=" * 78)
        print(f"  {'Paso':<40} {'Filas':>8}  {'Gen (MWh)':>14}  {'d Gen (MWh)':>14}  {'% perdido':>9}")
        print("  " + "-" * 74)
        for r in _audit_log:
            print(f"  {r['paso']:<40} {r['filas']:>8,}  {r['gen_MWh']:>14,.2f}  {r['delta_gen']:>+14,.2f}  {r['pct_perdida']:>8.2f}%")
        print("=" * 78)


    # ==========================================
    # 1. CARGA Y EMPALME DE FRONTERA MENSUAL
    # ==========================================
    print("\n" + "=" * 78)
    print("  CARGA DE ARCHIVOS FUENTE")
    print("=" * 78)

    reporte_actual = leer_reporte(RUTA_REPORTE_15MIN, "Mes actual")
    gen_base, rows_base = audit_gen("0. Carga inicial (mes actual)", reporte_actual)

    f_min_actual = reporte_actual['FECHA_HORA'].min()
    f_max_actual = reporte_actual['FECHA_HORA'].max()
    print(f"  Ventana del mes actual: {f_min_actual}  ->  {f_max_actual}")

    # --- [BUG 3] Empalme con el mes anterior, recortado y deduplicado ---
    if RUTA_REPORTE_MES_PASADO and os.path.exists(RUTA_REPORTE_MES_PASADO):
        print("  Acoplando mes anterior para resolver ciclos de frontera...")
        reporte_pasado = leer_reporte(RUTA_REPORTE_MES_PASADO, "Mes pasado")
        n_antes = len(reporte_pasado)

        reporte_pasado = reporte_pasado[reporte_pasado['FECHA_HORA'] < f_min_actual].copy()
        print(f"  Recorte del mes pasado: {n_antes:,} -> {len(reporte_pasado):,} filas "
              f"(se descarta todo lo >= {f_min_actual}).")

        reporte = empalmar_reportes(reporte_pasado, reporte_actual, _audit_log)
        print("  Empalme temporal realizado: duplicados reales deduplicados y "
              "colisiones con datos distintos agregadas.")
    else:
        print("  [!] No se encontro el archivo del mes anterior. Se procesa solo el mes actual.")
        print(f"      Ruta buscada: {RUTA_REPORTE_MES_PASADO}")
        reporte = empalmar_reportes(
            reporte_actual.iloc[0:0].copy(), reporte_actual, _audit_log)

    # --- Deteccion de timestamps repetidos (cambio de hora o duplicados reales) ---
    llave_ts = ['FECHA_HORA', 'UNIDAD GENERADORA', 'Central', 'CONFIGURACION']
    rep = reporte.duplicated(subset=llave_ts, keep=False)
    if rep.any():
        print("\n" + "!" * 78)
        print("  ALERTA: TIMESTAMPS REPETIDOS")
        print(f"  {rep.sum():,} filas comparten la misma llave temporal.")
        muestra = reporte[rep].sort_values(llave_ts)
        gen_iguales = (muestra.groupby(llave_ts)['GENERACION'].nunique() == 1).sum()
        print(f"  Grupos con generacion IDENTICA (probable duplicado): {gen_iguales:,}")
        print("  Si son duplicados reales hay que deduplicar; si la generacion difiere,")
        print("  es inyeccion repartida y corresponde sumarla (comportamiento actual).")
        print(muestra[llave_ts + ['GENERACION']].head(12).to_string(index=False))
        print("!" * 78)
        _audit_log.append({
            'paso': '1c. Alerta timestamps repetidos remanentes',
            'filas': int(rep.sum()),
            'gen_MWh': round(pd.to_numeric(reporte.loc[rep, 'GENERACION'], errors='coerce').sum(), 2),
            'delta_gen': 0, 'pct_perdida': 0,
        })


    # ==========================================
    # 2. FILTRO DE GRUPOS SIN GENERACION Y MARGEN
    # ==========================================
    tiene_gen = reporte.groupby(['UNIDAD GENERADORA', 'Central', 'CONFIGURACION'])['GENERACION'] \
                       .transform(lambda s: (s.fillna(0) != 0).any())
    reporte_sin_ceros = reporte[tiene_gen.astype(bool)].copy()
    gen_prev, rows_prev = audit_gen("1. Filtro grupos sin generacion", reporte_sin_ceros)

    # El margen es cero o positivo por definicion de negocio.
    reporte_sin_ceros['Margen'] = np.where(
        reporte_sin_ceros['CMg-CV'] > 0,
        reporte_sin_ceros['CMg-CV'] * reporte_sin_ceros['GENERACION'],
        0
    )


    # ==========================================
    # 3. IDENTIFICACION DE CICLOS  [BUG 1 CORREGIDO]
    # ==========================================
    def calcular_ciclos_por_nivel(df, nivel_agrupacion, nombre_columna_id):
        """Adapta la utilidad compartida de ciclos a los nombres del motor."""
        return calcular_ciclos(
            df, grupo=nivel_agrupacion,
            tolerancia_cortes=TOLERANCIA_CORTES_BLOQUES,
            nombre_columna_id=nombre_columna_id)


    # ==========================================
    # 4. COSTOS CONSOLIDADOS Y DICCIONARIOS
    # ==========================================
    print("\nCargando bases de Costos Consolidados (PO)...")
    df_externo_act = pd.read_excel(RUTA_COSTOS_PD, sheet_name=0)

    if RUTA_COSTOS_MES_PASADO and os.path.exists(RUTA_COSTOS_MES_PASADO):
        df_externo_pas = pd.read_excel(RUTA_COSTOS_MES_PASADO, sheet_name=0)
        df_externo = pd.concat([df_externo_pas, df_externo_act], ignore_index=True)
        print("  Costos del mes pasado acoplados.")
    else:
        print("  [!] Sin archivo de costos del mes pasado. Los ciclos de frontera no")
        print("      podran heredar su tarifa de partida.")
        df_externo = df_externo_act.copy()

    cols_costos = ['Llave_Concatenada', 'Fria_Num1_M', 'Tibia_Num1_O', 'Tibia_Num2_N',
                   'Caliente_Num1_P', 'Partida_Fria', 'Partida_Tibia', 'Partida_Tibia_2',
                   'Partida_Caliente', 'Detencion', 'Costo_Cero']
    faltan = [c for c in cols_costos if c not in df_externo.columns]
    if faltan:
        sys.exit(f"ERROR: faltan columnas en {RUTA_COSTOS_PD}: {faltan}")

    df_costos_pd = df_externo[cols_costos].drop_duplicates(subset=['Llave_Concatenada'], keep='last')

    # --- Filtro Costo_Cero ---
    tiene_costo = (df_externo['Costo_Cero'].astype(str).str.strip().str.upper().eq('NO')
                   .groupby(df_externo['UNIDAD']).transform('any'))
    unidades_facturables = set(df_externo.loc[tiene_costo, 'UNIDAD'])
    resultado_buscarx = reporte_sin_ceros['Central'].isin(unidades_facturables)
    mask_no_cogen = ~reporte_sin_ceros['Central'].astype(str).str.contains('COGEN', case=False, na=False)
    reporte_sin_ceros['Costo_Final'] = np.where(mask_no_cogen & resultado_buscarx, 'NO', 'No_Aplica')

    filtro_seguro = reporte_sin_ceros['Costo_Final'].astype(str).str.strip().str.upper()
    reporte_sin_ceros = reporte_sin_ceros[filtro_seguro == 'NO'].copy()
    gen_prev, rows_prev = audit_gen("2. Filtro Costo_Cero == NO", reporte_sin_ceros,
                                    prev_gen=gen_prev, prev_rows=rows_prev)

    # --- Diccionario Central -> Central_Relacionada ---
    df_diccionario = pd.read_excel(RUTA_DICCIONARIO, sheet_name=0)
    col_llave, col_valor = df_diccionario.columns[0], df_diccionario.columns[1]
    df_diccionario[col_llave] = df_diccionario[col_llave].astype(str).str.strip()
    df_diccionario[col_valor] = df_diccionario[col_valor].astype(str).str.strip()
    diccionario_central = df_diccionario.drop_duplicates(subset=[col_llave]) \
                                        .set_index(col_llave)[col_valor].to_dict()
    reporte_sin_ceros['Central_Relacionada'] = reporte_sin_ceros['Central'].astype(str).str.strip() \
                                                                           .map(diccionario_central)

    if AUDITAR_MAPEO_DICCIONARIO == 1:
        print("\n" + "=" * 78)
        print("  AUDITORIA: DICCIONARIO CENTRAL -> CENTRAL RELACIONADA")
        print("=" * 78)

        mes_act = reporte_sin_ceros[reporte_sin_ceros['FECHA_HORA'] >= f_min_actual]
        huerfanas = mes_act[mes_act['Central_Relacionada'].isna()]['Central'].unique()
        if len(huerfanas) > 0:
            gen_afectada = mes_act[mes_act['Central'].isin(huerfanas)]['GENERACION'].sum()
            print(f"  [!] {len(huerfanas)} centrales sin entrada en el diccionario "
                  f"({gen_afectada:,.2f} MWh del mes actual quedan fuera del calculo):")
            for c in sorted(huerfanas)[:40]:
                print(f"      - {c}")
            if len(huerfanas) > 40:
                print(f"      ... y {len(huerfanas) - 40} mas.")
        else:
            print("  OK: todas las centrales del mes tienen relacionada asignada.")

        pref_k = df_diccionario[col_llave].str.extract(r'^([A-Za-z0-9\-]+?)(?:_|$)', expand=False)
        pref_v = df_diccionario[col_valor].str.extract(r'^([A-Za-z0-9\-]+?)(?:_|$)', expand=False)
        sospechosas = df_diccionario[(pref_k.notna()) & (pref_v.notna()) &
                                     (pref_k.str[:8] != pref_v.str[:8])]
        if not sospechosas.empty:
            print(f"\n  [!] {len(sospechosas)} filas del diccionario donde el prefijo de la")
            print("      configuracion no coincide con el de la relacionada. Revisa si son")
            print("      agrupaciones legitimas o errores de tipeo:")
            print(sospechosas.head(20).to_string(index=False))

    # --- Diccionario Central_Relacionada -> Empresa ---
    empresa_por_relacionada = {}
    if RUTA_DICCIONARIO_EMPRESA and os.path.exists(RUTA_DICCIONARIO_EMPRESA):
        df_emp = pd.read_excel(RUTA_DICCIONARIO_EMPRESA, sheet_name=0)
        col_rel_e, col_emp = df_emp.columns[0], df_emp.columns[1]
        df_emp[col_rel_e] = df_emp[col_rel_e].astype(str).str.strip()
        df_emp[col_emp] = df_emp[col_emp].astype(str).str.strip()

        print("\n" + "=" * 78)
        print("  AUDITORIA: DICCIONARIO CENTRAL_RELACIONADA -> EMPRESA")
        print("=" * 78)
        print(f"  Columnas usadas: '{col_rel_e}' -> '{col_emp}'")

        dup = df_emp[df_emp.duplicated(subset=[col_rel_e], keep=False)]
        if not dup.empty:
            print(f"  [!] {dup[col_rel_e].nunique():,} centrales relacionadas aparecen mas de una vez")
            print("      en el diccionario, posiblemente con empresa distinta. Se usa la ULTIMA fila:")
            print(dup.sort_values(col_rel_e).to_string(index=False))

        empresa_por_relacionada = (df_emp.drop_duplicates(subset=[col_rel_e], keep='last')
                                   .set_index(col_rel_e)[col_emp].to_dict())
        print(f"  {len(empresa_por_relacionada):,} centrales relacionadas mapeadas a "
              f"{df_emp[col_emp].nunique():,} empresas.")

        reporte_sin_ceros['Empresa'] = (reporte_sin_ceros['Central_Relacionada'].astype(str).str.strip()
                                        .map(empresa_por_relacionada))
        sin_emp = reporte_sin_ceros[reporte_sin_ceros['Empresa'].isna()
                                    & reporte_sin_ceros['Central_Relacionada'].notna()]
        if not sin_emp.empty:
            print(f"  [!] {sin_emp['Central_Relacionada'].nunique()} centrales relacionadas sin empresa "
                  f"({sin_emp['GENERACION'].sum():,.2f} MWh). Quedaran como 'Sin_Empresa':")
            for c in sorted(sin_emp['Central_Relacionada'].dropna().unique())[:25]:
                print(f"      - {c}")
        else:
            print("  OK: todas las centrales relacionadas vigentes tienen empresa asignada.")
        reporte_sin_ceros['Empresa'] = reporte_sin_ceros['Empresa'].fillna('Sin_Empresa')
    else:
        print("\n  [!] No se encontro el diccionario de empresas. Se omite el corte por empresa.")
        reporte_sin_ceros['Empresa'] = 'Sin_Empresa'


    # ==========================================
    # 5. POLITICA VIGENTE (PO) Y LLAVE_FHC  [BUG 4 CORREGIDO]
    # ==========================================
    print("\nReconstruyendo linea de tiempo de Politicas (PO) desde la base de Costos...")
    llaves_txt = df_externo['Llave_Concatenada'].astype(str).str.strip()

    extract_llave, fmt_fecha = None, None
    for patron, fmt in PATRONES_PO:
        prueba = llaves_txt.str.extract(patron)
        n_ok = prueba[0].notna().sum()
        if n_ok > 0:
            extract_llave, fmt_fecha = prueba, fmt
            print(f"  Formato detectado: {fmt}  ({n_ok:,} de {len(llaves_txt):,} llaves reconocidas).")
            break

    if extract_llave is None:
        print("  [!] No se reconocio el formato de Llave_Concatenada. Ejemplos reales:")
        for v in llaves_txt.dropna().unique()[:10]:
            print(f"      {v}")
        sys.exit("ERROR: ajusta PATRONES_PO al formato real de Llave_Concatenada.")

    df_politicas = (extract_llave.dropna().drop_duplicates()
                    .rename(columns={0: 'FECHA_TXT', 1: 'Hora_Inicio'}))

    df_politicas['Hora_str'] = df_politicas['Hora_Inicio'].astype(str)
    mask_24 = df_politicas['Hora_str'] == '24'
    df_politicas.loc[mask_24, 'Hora_str'] = '0'

    df_politicas['Fecha_PO'] = pd.to_datetime(
        df_politicas['FECHA_TXT'] + ' ' + df_politicas['Hora_str'] + ':00',
        format=fmt_fecha + ' %H:%M', errors='coerce')
    df_politicas.loc[mask_24, 'Fecha_PO'] += pd.Timedelta(days=1)

    # La llave base se reconstruye tal cual aparece en el archivo, para que el
    # cruce posterior calce caracter por caracter.
    df_politicas['Llave_PO_Base'] = df_politicas['FECHA_TXT'] + "-" + df_politicas['Hora_Inicio'].astype(str)
    df_pol_asof = df_politicas[['Fecha_PO', 'Llave_PO_Base']].dropna().sort_values('Fecha_PO')
    print(f"  {len(df_pol_asof):,} politicas PO reconstruidas "
          f"({df_pol_asof['Fecha_PO'].min()} -> {df_pol_asof['Fecha_PO'].max()}).")

    horas_por_dia = df_pol_asof['Fecha_PO'].dt.date.value_counts()
    print(f"  Politicas por dia: min={horas_por_dia.min()}, max={horas_por_dia.max()}, "
          f"dias cubiertos={len(horas_por_dia)}")

    reporte_sin_ceros = reporte_sin_ceros.sort_values('FECHA_HORA').reset_index(drop=True)
    reporte_sin_ceros = pd.merge_asof(
        reporte_sin_ceros, df_pol_asof,
        left_on='FECHA_HORA', right_on='Fecha_PO', direction='backward')

    sin_po = reporte_sin_ceros['Llave_PO_Base'].isna().sum()
    if sin_po:
        print(f"  [!] {sin_po:,} bloques sin politica PO vigente hacia atras.")

    reporte_sin_ceros['Llave_FHC'] = (reporte_sin_ceros['Llave_PO_Base'].fillna("SinFecha-1")
                                      + reporte_sin_ceros['Central'].astype(str))
    reporte_sin_ceros = reporte_sin_ceros.drop(columns=['Fecha_PO', 'Llave_PO_Base'])

    llaves_costos = set(df_costos_pd['Llave_Concatenada'].astype(str).str.strip())
    pct_cruce = 100 * reporte_sin_ceros['Llave_FHC'].isin(llaves_costos).mean()
    print(f"  Cruce Llave_FHC vs tabla de costos: {pct_cruce:.1f}% de los bloques encuentran tarifa.")
    if pct_cruce < 50:
        print("  [!] CRUCE BAJO. Compara las llaves generadas contra las del archivo:")
        print("     generadas:", list(reporte_sin_ceros['Llave_FHC'].unique()[:3]))
        print("     archivo  :", list(llaves_costos)[:3])


    # ==========================================
    # 6-7. CICLOS POR CENTRAL RELACIONADA
    # ==========================================
    ciclos_relacionada = calcular_ciclos_por_nivel(reporte_sin_ceros, ['Central_Relacionada'],
                                                   'Ciclo_ID_Relacionada')
    reporte_sin_ceros = reporte_sin_ceros.merge(ciclos_relacionada,
                                                on=['Central_Relacionada', 'FECHA_HORA'], how='left')

    n_ciclos_max = int(ciclos_relacionada['Ciclo_ID_Relacionada'].max() or 0)
    n_ciclos_tot = ciclos_relacionada[ciclos_relacionada['Ciclo_ID_Relacionada'] > 0] \
        .groupby('Central_Relacionada')['Ciclo_ID_Relacionada'].max().sum()
    print(f"\n  Ciclos detectados en la linea de tiempo completa: {int(n_ciclos_tot):,} "
          f"(maximo por central relacionada: {n_ciclos_max:,})")
    print("  Este ID es continuo desde el mes anterior a proposito. La renumeracion")
    print("  para el reporte se hace mas adelante (seccion 14.2).")


    def resumen_central_relacionada_por_bloque(df):
        df_activos = df[(df['Ciclo_ID_Relacionada'] > 0)
                        & (df['Central_Relacionada'].notna())
                        & (df['GENERACION'] > 0)].copy()
        if df_activos.empty:
            return pd.DataFrame()

        ciclo_global = df_activos.groupby(['Central_Relacionada', 'Ciclo_ID_Relacionada']).agg(
            Inicio_Ciclo_Global=('FECHA_HORA', 'min'),
            Termino_Ciclo_Global=('FECHA_HORA', 'max')
        ).reset_index().sort_values(by=['Central_Relacionada', 'Inicio_Ciclo_Global'])

        ciclo_global['Termino_Anterior'] = ciclo_global.groupby('Central_Relacionada')['Termino_Ciclo_Global'].shift(1)

        ajuste = pd.Timedelta(minutes=MINUTOS_BLOQUE) if AJUSTAR_FIN_BLOQUE == 1 else pd.Timedelta(0)
        ciclo_global['Horas_Detenida_Ciclo'] = (
            (ciclo_global['Inicio_Ciclo_Global'] - (ciclo_global['Termino_Anterior'] + ajuste))
            .dt.total_seconds() / 3600.0
        )

        tiempos_central = df_activos.groupby(['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Central']).agg(
            Inicio_Generacion_Central=('FECHA_HORA', 'min'),
            Termino_Generacion_Central=('FECHA_HORA', 'max')
        ).reset_index()

        resumen = df_activos.merge(ciclo_global, on=['Central_Relacionada', 'Ciclo_ID_Relacionada'], how='left')
        resumen = resumen.merge(tiempos_central,
                                on=['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Central'], how='left')

        df_llaves_fhc = df[['Central', 'FECHA_HORA', 'Llave_FHC']].drop_duplicates(
            subset=['Central', 'FECHA_HORA'], keep='first')
        resumen = resumen.merge(
            df_llaves_fhc.rename(columns={'FECHA_HORA': 'Hora_Match_Ini', 'Llave_FHC': 'Llave_FHC_Inicio'}),
            left_on=['Central', 'Inicio_Generacion_Central'], right_on=['Central', 'Hora_Match_Ini'], how='left')
        resumen = resumen.merge(
            df_llaves_fhc.rename(columns={'FECHA_HORA': 'Hora_Match_Fin', 'Llave_FHC': 'Llave_FHC_Fin'}),
            left_on=['Central', 'Termino_Generacion_Central'], right_on=['Central', 'Hora_Match_Fin'], how='left')

        resumen['Etiqueta_Relacionada'] = (resumen['Central_Relacionada'].astype(str) + "&"
                                           + resumen['Ciclo_ID_Relacionada'].astype(int).astype(str))

        columnas = ['Etiqueta_Relacionada', 'Central_Relacionada', 'Ciclo_ID_Relacionada', 'Central',
                    'Empresa', 'Inicio_Ciclo_Global', 'Termino_Ciclo_Global', 'Horas_Detenida_Ciclo',
                    'Inicio_Generacion_Central', 'Termino_Generacion_Central',
                    'FECHA_HORA', 'GENERACION', 'Margen', 'Llave_FHC', 'Llave_FHC_Inicio', 'Llave_FHC_Fin']
        return resumen[columnas].sort_values(by=['FECHA_HORA', 'Central_Relacionada'])


    resumen_relacionada = resumen_central_relacionada_por_bloque(reporte_sin_ceros)
    if resumen_relacionada.empty:
        sys.exit("ERROR: no quedaron bloques con generacion tras los filtros. Revisa las auditorias previas.")

    gen_prev, rows_prev = audit_gen("3. Detalle por bloque en ciclos", resumen_relacionada,
                                    prev_gen=gen_prev, prev_rows=rows_prev)

    # Conservar solo los ciclos que tocan el mes actual
    ciclos_vivos_este_mes = resumen_relacionada.loc[
        resumen_relacionada['FECHA_HORA'] >= f_min_actual, 'Etiqueta_Relacionada'].unique()
    resumen_relacionada = resumen_relacionada[
        resumen_relacionada['Etiqueta_Relacionada'].isin(ciclos_vivos_este_mes)].copy()

    arranca_antes = resumen_relacionada['Inicio_Ciclo_Global'] < f_min_actual
    sigue_despues = resumen_relacionada['Termino_Ciclo_Global'] >= f_max_actual
    resumen_relacionada['Estado_Ciclo_Mes'] = np.select(
        [arranca_antes & sigue_despues, arranca_antes, sigue_despues],
        ['Continua todo el mes', 'Viene del mes anterior', 'Continua proximo mes'],
        default='Inicia y termina este mes'
    )

    # --- [BUG 5] Bandera de exencion, independiente del numero de ciclo ---
    if REGLA_EXENCION == 'sin_historia':
        resumen_relacionada['Flag_Exencion'] = resumen_relacionada['Horas_Detenida_Ciclo'].isna()
    elif REGLA_EXENCION == 'primer_ciclo':
        resumen_relacionada['Flag_Exencion'] = resumen_relacionada['Ciclo_ID_Relacionada'] == 1
    else:
        resumen_relacionada['Flag_Exencion'] = False
    resumen_relacionada['Flag_Exencion'] = resumen_relacionada['Flag_Exencion'].astype(bool)
    print(f"\n  Regla de exencion sin registro RIO: '{REGLA_EXENCION}'. "
          f"Bloques marcados: {int(resumen_relacionada['Flag_Exencion'].sum()):,}")


    # ==========================================
    # 8. CARGA DEL RIO  [BUG 2 CORREGIDO]  [BUG 7: EMPALME CON MES ANTERIOR]
    # ==========================================
    print("\n" + "=" * 78)
    print("  CARGA DEL RIO")
    print("=" * 78)

    # Mapeo EXPLICITO. El mapeo difuso anterior enganchaba:
    #   'CONSIGNA LIMITACION'            -> CONSIGNAS      (correcto: 'CON')
    #   'ESTADO OPERACIONAL COMBUSTIBLE' -> ESTADO OPERAC. (correcto: 'EO')
    #   ninguna                          -> MOTIVO         (correcto: 'MOT')
    MAPA_RIO = {
        'CON': 'CONSIGNAS',
        'MOT': 'MOTIVO',
        'EO': 'ESTADO OPERACIONAL',
        'COMENTARIO': 'COMENTARIO',
        'NOMBRE CONFIGURACIÓN': 'NOMBRE CONFIGURACIÓN',
        'NOMBRE CONFIGURACION': 'NOMBRE CONFIGURACIÓN',
    }
    REQ_RIO = ['CONSIGNAS', 'MOTIVO', 'ESTADO OPERACIONAL', 'NOMBRE CONFIGURACIÓN',
               'COMENTARIO', 'FECHA', 'HORA']


    def leer_rio(ruta, etiqueta, abortar_si_faltan_columnas):
        """
        Carga y normaliza un archivo RIO (mes actual o mes pasado): mapeo
        explicito de columnas, construccion de FECHA_HORA_RIO y mapeo a
        Central_Relacionada_RIO. Se extrajo a funcion en el [BUG 7] para no
        duplicar esta logica entre el mes actual y el mes anterior.

        abortar_si_faltan_columnas=True corta la ejecucion si faltan columnas
        obligatorias (se usa para el mes actual, que es indispensable). Para el
        mes pasado se prefiere solo advertir y desactivar el empalme, para no
        tumbar todo el proceso por un archivo secundario con formato distinto.
        """
        df = pd.read_excel(ruta, skiprows=4)
        df.columns = [str(c).strip().upper() for c in df.columns]
        df = df.rename(columns={k: v for k, v in MAPA_RIO.items() if k in df.columns})
        df = df.loc[:, ~df.columns.duplicated()]

        faltantes = [c for c in REQ_RIO if c not in df.columns]
        if faltantes:
            if abortar_si_faltan_columnas:
                print(f"\nColumnas encontradas en {etiqueta}:")
                for c in df.columns:
                    print(f"   - {c}")
                sys.exit(f"\nERROR: faltan columnas obligatorias en {etiqueta}: {faltantes}\n"
                        f"Ajusta el diccionario MAPA_RIO en la seccion 8 con los nombres reales.")
            else:
                print(f"  [!] {etiqueta}: faltan columnas {faltantes}. Se omite este archivo "
                      f"(no se empalma el RIO del mes pasado).")
                return None

        df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
        hora_str = df['HORA'].astype(str).str.strip()
        df['FECHA_HORA_RIO'] = pd.to_datetime(
            df['FECHA'].dt.strftime('%Y-%m-%d') + ' ' + hora_str.str.replace('24:00', '00:00', regex=False),
            errors='coerce')
        df.loc[hora_str.str.startswith('24:00'), 'FECHA_HORA_RIO'] += pd.Timedelta(days=1)

        df['NOMBRE CONFIGURACIÓN'] = df['NOMBRE CONFIGURACIÓN'].astype(str).str.strip()
        df['Central_Relacionada_RIO'] = (df['NOMBRE CONFIGURACIÓN'].map(diccionario_central)
                                         .fillna(df['NOMBRE CONFIGURACIÓN']).astype(str).str.strip())
        for c in ['CONSIGNAS', 'MOTIVO', 'ESTADO OPERACIONAL']:
            df[c] = df[c].astype(str).str.strip().replace({'nan': np.nan, '-': np.nan})
        df['COMENTARIO'] = df['COMENTARIO'].astype(str).replace({'nan': ''})

        df = df.dropna(subset=['FECHA_HORA_RIO']).sort_values('FECHA_HORA_RIO').reset_index(drop=True)
        print(f"  {etiqueta} cargado: {len(df):,} registros "
              f"({df['FECHA_HORA_RIO'].min()} -> {df['FECHA_HORA_RIO'].max()}).")
        return df


    rio_actual = leer_rio(RUTA_RIO, "RIO mes actual", abortar_si_faltan_columnas=True)

    # --- [BUG 7] Empalme con el RIO del mes anterior, mismo patron que BUG 3 ---
    if RUTA_RIO_MES_PASADO and os.path.exists(RUTA_RIO_MES_PASADO):
        print("  Acoplando RIO del mes anterior para resolver ciclos de frontera...")
        rio_pasado = leer_rio(RUTA_RIO_MES_PASADO, "RIO mes pasado", abortar_si_faltan_columnas=False)

        if rio_pasado is not None:
            n_antes = len(rio_pasado)
            rio_pasado = rio_pasado[rio_pasado['FECHA_HORA_RIO'] < f_min_actual].copy()
            print(f"  Recorte del RIO mes pasado: {n_antes:,} -> {len(rio_pasado):,} registros "
                  f"(se descarta todo lo >= {f_min_actual}).")

            rio = pd.concat([rio_pasado, rio_actual], ignore_index=True)

            llave_dedup_rio = ['FECHA_HORA_RIO', 'Central_Relacionada_RIO']
            n_dup = rio.duplicated(subset=llave_dedup_rio).sum()
            if n_dup:
                print(f"  [!] {n_dup:,} registros RIO duplicados tras el empalme. Se conserva el "
                      f"que trae MOTIVO informado (mismo criterio de prioridad usado en el cruce maestro).")
                rio['_prio'] = rio['MOTIVO'].notna().astype(int)
                rio = (rio.sort_values(llave_dedup_rio + ['_prio'])
                          .drop_duplicates(subset=llave_dedup_rio, keep='last')
                          .drop(columns=['_prio']))
            rio = rio.sort_values('FECHA_HORA_RIO').reset_index(drop=True)
            print("  Empalme del RIO realizado.")
        else:
            rio = rio_actual
    else:
        print("  [!] No se encontro el RIO del mes anterior. Los ciclos que arrancaron antes")
        print("      de este mes no tendran instruccion RIO en su apertura.")
        print(f"      Ruta buscada: {RUTA_RIO_MES_PASADO}")
        rio = rio_actual

    if AUDITAR_MAPEO_RIO == 1:
        print("  Valores encontrados tras el mapeo (verifica que tengan sentido):")
        for c in ['MOTIVO', 'CONSIGNAS', 'ESTADO OPERACIONAL']:
            vals = rio[c].astype(str).str.strip().value_counts().head(8)
            print(f"   {c:<20}: " + ", ".join(f"{k}={v:,}" for k, v in vals.items()))
        eo_presentes = set(rio['ESTADO OPERACIONAL'].astype(str).str.strip().unique())
        faltan_eo = [c for c in CODIGOS_EO_VALIDOS if c not in eo_presentes]
        if faltan_eo:
            print(f"\n  [!] Los codigos {faltan_eo} de CODIGOS_EO_VALIDOS no aparecen en la")
            print("      columna EO de este RIO. Confirma el codigo correcto con el CEN,")
            print("      o esa rama del filtro operacional nunca se activara.")

    centrales_modelo = set(resumen_relacionada['Central_Relacionada'].dropna().unique())
    cobertura = len(centrales_modelo & set(rio['Central_Relacionada_RIO'].unique()))
    print(f"  Cobertura de llaves: {cobertura} de {len(centrales_modelo)} centrales "
          f"relacionadas tienen registros en el RIO.")


    # ==========================================
    # 10. CRUCE MAESTRO (MERGE_ASOF)
    # ==========================================
    rio_cols = ['FECHA_HORA_RIO', 'Central_Relacionada_RIO', 'CONSIGNAS', 'MOTIVO',
                'NOMBRE CONFIGURACIÓN', 'ESTADO OPERACIONAL', 'COMENTARIO']

    # Ante varias instrucciones en el mismo instante para la misma central, se
    # prioriza la que trae MOTIVO informado en vez de quedarse con la ultima.
    rio_subset = deduplicar_rio_priorizando_motivo(rio[rio_cols]).sort_values('FECHA_HORA_RIO')

    resumen_relacionada = resumen_relacionada.sort_values('FECHA_HORA').reset_index(drop=True)
    resumen_relacionada = pd.merge_asof(
        resumen_relacionada, rio_subset,
        left_on='FECHA_HORA', right_on='FECHA_HORA_RIO',
        left_by='Central_Relacionada', right_by='Central_Relacionada_RIO',
        direction='backward', tolerance=pd.Timedelta('24 hours'))

    resumen_relacionada = resumen_relacionada.rename(columns={
        'NOMBRE CONFIGURACIÓN': 'Configuracion RIO',
        'FECHA_HORA_RIO': 'Fuente_Config_RIO'}) \
                                             .drop(columns=['Central_Relacionada_RIO'], errors='ignore')

    for col in ['CONSIGNAS', 'MOTIVO', 'ESTADO OPERACIONAL', 'Configuracion RIO']:
        resumen_relacionada[col] = resumen_relacionada[col].fillna('Sin_Registro_RIO')
    resumen_relacionada['COMENTARIO'] = resumen_relacionada['COMENTARIO'].fillna('')

    # El cruce maestro solo mira hacia atras. En los limites de ciclo, rescata
    # una configuracion registrada pocos minutos despues (o antes), sin alterar
    # ni ese cruce general ni la busqueda relajada posterior de filtros RIO.
    resumen_relacionada = rescatar_config_rio_en_limites(
        resumen_relacionada, rio_subset, ACTIVAR_BUSQUEDA_RELAJADA,
        VENTANA_CUARTOS_HORA)
    rescatadas = resumen_relacionada['Config_RIO_Rescatada_Ventana']
    n_rescatadas_partida = int((
        rescatadas
        & (resumen_relacionada['FECHA_HORA'] == resumen_relacionada['Inicio_Ciclo_Global'])
    ).sum())
    n_rescatadas_detencion = int((
        rescatadas
        & (resumen_relacionada['FECHA_HORA'] == resumen_relacionada['Termino_Ciclo_Global'])
    ).sum())
    print(f"  Configuracion RIO rescatada en ventana: {n_rescatadas_partida:,} bloques de partida, "
          f"{n_rescatadas_detencion:,} bloques de detencion.")


    # ==========================================
    # 10.1 LLAVE DE TARIFA SEGUN CONFIGURACION INSTRUIDA POR RIO (v6)
    # ==========================================
    # Llave de tarifa segun la configuracion QUE EL RIO INSTRUYO, en vez
    # de segun la Central propia que genero. Reutiliza la misma tabla de
    # politicas vigentes (df_pol_asof) ya construida en la seccion 5 - el
    # resultado es un cruce independiente, no toca 'Llave_FHC' (la version
    # basada en Central propia, que USAR_CONFIG_DOMINANTE sigue usando).
    if USAR_TARIFA_RIO_INSTRUIDA == 1:
        resumen_relacionada = resumen_relacionada.sort_values('FECHA_HORA').reset_index(drop=True)
        resumen_relacionada = pd.merge_asof(
            resumen_relacionada, df_pol_asof, left_on='FECHA_HORA', right_on='Fecha_PO', direction='backward')
        resumen_relacionada['Llave_FHC_RIO'] = (resumen_relacionada['Llave_PO_Base'].fillna("SinFecha-1")
                                                + resumen_relacionada['Configuracion RIO'].astype(str))
        resumen_relacionada = resumen_relacionada.drop(columns=['Fecha_PO', 'Llave_PO_Base'])


    # ==========================================
    # 10.2 AUDITORIA: COBERTURA DE INSTRUCCION RIO
    # ==========================================
    # Mide, para TODA la generacion de julio (no solo los ciclos que tocamos),
    # que proporcion de la energia tiene una instruccion de RIO (Motivo informado)
    # y de donde sale esa instruccion:
    #   Directa   : el propio bloque de esa configuracion ya trae Motivo informado.
    #   Ampliada  : el bloque propio NO trae motivo, pero se encuentra igual
    #               porque (a) OTRA configuracion que coexiste en el MISMO
    #               instante si lo trae, o (b) hay un registro con motivo dentro
    #               de la ventana de +/- VENTANA_CUARTOS_HORA cuartos de hora
    #               (la misma tolerancia que usa la busqueda relajada). Ambos
    #               mecanismos se cuentan juntos.
    #   No instruida: ninguno de los mecanismos anteriores encuentra un motivo.
    # Esto es puramente informativo - no cambia ningun costo. Sirve para calibrar
    # que tan seguido se esta usando cada mecanismo de ampliacion, y en que
    # centrales se concentra la generacion sin instruccion real.
    if AUDITAR_INSTRUCCION_RIO == 1:
        print("\n" + "=" * 78)
        print("  10.1 AUDITORIA: COBERTURA DE INSTRUCCION RIO")
        print("=" * 78)

        activos = resumen_relacionada[resumen_relacionada['GENERACION'] > 0].copy()
        activos['Instruido_Propio'] = activos['MOTIVO'] != 'Sin_Registro_RIO'

        # Mecanismo (a): otra configuracion en el MISMO Central_Relacionada +
        # FECHA_HORA si trae motivo.
        activos['Instruido_MismoBloque'] = (
            activos.groupby(['Central_Relacionada', 'FECHA_HORA'])['Instruido_Propio'].transform('any'))

        # Mecanismo (b): dentro de +/- VENTANA_CUARTOS_HORA cuartos de hora hay
        # ALGUN registro del RIO (de cualquier configuracion) con motivo
        # informado, para esa misma Central_Relacionada. Se busca solo para lo
        # que ya quedo sin cubrir por (a), para no recorrer todo el mes dos veces.
        pendientes = activos[~activos['Instruido_Propio'] & ~activos['Instruido_MismoBloque']].copy()
        if not pendientes.empty:
            rio_instruido = (rio[rio['MOTIVO'].notna()][['FECHA_HORA_RIO', 'Central_Relacionada_RIO']]
                             .dropna().rename(columns={'Central_Relacionada_RIO': 'Central_Relacionada',
                                                        'FECHA_HORA_RIO': 'FECHA_HORA_Instruccion'})
                             .sort_values('FECHA_HORA_Instruccion'))
            pendientes = pendientes.sort_values('FECHA_HORA')
            indice_original = pendientes.index  # merge_asof descarta el indice, se guarda para reasignar despues
            resultado = pd.merge_asof(
                pendientes.reset_index(drop=True), rio_instruido,
                left_on='FECHA_HORA', right_on='FECHA_HORA_Instruccion',
                by='Central_Relacionada', direction='nearest',
                tolerance=pd.Timedelta(minutes=VENTANA_CUARTOS_HORA * 15))
            instruido_ventana = pd.Series(resultado['FECHA_HORA_Instruccion'].notna().values, index=indice_original)
            activos['Instruido_Ventana'] = False
            activos.loc[indice_original, 'Instruido_Ventana'] = instruido_ventana
        else:
            activos['Instruido_Ventana'] = False

        activos['Cobertura_RIO'] = np.select(
            [activos['Instruido_Propio'],
             activos['Instruido_MismoBloque'] | activos['Instruido_Ventana']],
            ['Directa', 'Ampliada'], default='No instruida')

        resumen_cobertura = activos.groupby('Cobertura_RIO')['GENERACION'].sum()
        total_gen = resumen_cobertura.sum()
        print(f"  Generacion total analizada: {total_gen:,.2f} MWh\n")
        for cat in ['Directa', 'Ampliada', 'No instruida']:
            g = resumen_cobertura.get(cat, 0.0)
            print(f"    {cat:<14}: {g:>14,.2f} MWh  ({100*g/total_gen if total_gen else 0:5.1f}%)")

        print("\n  Por central (solo 'No instruida', ordenado por MWh, top 15):")
        no_instr = (activos[activos['Cobertura_RIO'] == 'No instruida']
                   .groupby('Central_Relacionada')['GENERACION'].sum()
                   .sort_values(ascending=False))
        print(no_instr.head(15).to_string())

        print("\n  Por central (solo 'Ampliada', ordenado por MWh, top 15):")
        ampliada = (activos[activos['Cobertura_RIO'] == 'Ampliada']
                   .groupby('Central_Relacionada')['GENERACION'].sum()
                   .sort_values(ascending=False))
        print(ampliada.head(15).to_string())

        cobertura_export = activos[['Central_Relacionada', 'Central', 'FECHA_HORA', 'GENERACION',
                                    'MOTIVO', 'Cobertura_RIO']].copy()


    # ==========================================
    # 11. FILTROS OPERACIONALES Y COSTOS
    # ==========================================
    def calcular_filtros(df, col_central, col_conf_rio, col_consigna, col_motivo,
                         col_eo, col_coment, col_exencion):
        """
        Devuelve los tres multiplicadores 0/1 de rechazo.

        col_exencion debe ser una columna BOOLEANA que marca los ciclos a los que
        se les da el beneficio de la duda cuando el RIO no trae motivo. Antes esto
        era 'Ciclo_ID == 1', pero con el empalme mensual ningun ciclo del mes tiene
        ID 1 y la exencion dejaba de aplicarse.
        """
        suf_c = df[col_central].astype(str).str.extract(r'(_GN.*)', expand=False).fillna('')
        suf_r = df[col_conf_rio].astype(str).str.extract(r'(_GN.*)', expand=False).fillna('')
        f_conf = np.where((suf_c != '') & (suf_r != '') & (suf_c != suf_r), 0, 1)

        f_disp = np.where(df[col_consigna].astype(str).str.strip().str.upper() == 'EP', 0, 1)

        cond_sscc = df[col_coment].astype(str).str.contains('SSCC|CTF|CSF|CPF', case=False, na=False)
        cond_1 = ((df[col_motivo] == 'OM')
                  | (df[col_eo].isin(CODIGOS_EO_VALIDOS))
                  | ((df[col_motivo] == 'OT') & cond_sscc))
        cond_2 = df[col_exencion].astype(bool) & (df[col_motivo] == 'Sin_Registro_RIO')
        f_op = np.where(cond_1 | cond_2, 1, 0)
        return f_conf, f_disp, f_op


    f_conf, f_disp, f_op = calcular_filtros(
        resumen_relacionada, 'Central', 'Configuracion RIO', 'CONSIGNAS',
        'MOTIVO', 'ESTADO OPERACIONAL', 'COMENTARIO', 'Flag_Exencion')
    resumen_relacionada['Conf despachada RIO'] = f_conf
    resumen_relacionada['Disponible (1) / Pruebas (0)'] = f_disp
    resumen_relacionada['Filtro_Operacional'] = f_op

    # --- Tarifas de partida ---
    resumen_relacionada = resumen_relacionada.merge(
        df_costos_pd, left_on='Llave_FHC_Inicio', right_on='Llave_Concatenada', how='left'
    ).drop(columns=['Llave_Concatenada'])

    resumen_relacionada = clasificar_partida(resumen_relacionada)
    resumen_relacionada['Filtro_CostoCero_Partida'] = filtro_costo_cero(
        resumen_relacionada['Costo_Cero'], resumen_relacionada['Central'])

    # --- Tarifas de detencion ---
    resumen_relacionada = resumen_relacionada.merge(
        df_costos_pd[['Llave_Concatenada', 'Detencion', 'Costo_Cero']].rename(
            columns={'Detencion': 'Costo_Detencion', 'Costo_Cero': 'Costo_Cero_Detencion'}),
        left_on='Llave_FHC_Fin', right_on='Llave_Concatenada', how='left'
    ).drop(columns=['Llave_Concatenada'])
    resumen_relacionada['Costo_Detencion'] = pd.to_numeric(
        resumen_relacionada['Costo_Detencion'], errors='coerce').fillna(0)
    resumen_relacionada['Filtro_CostoCero_Detencion'] = filtro_costo_cero(
        resumen_relacionada['Costo_Cero_Detencion'], resumen_relacionada['Central'])

    # --- Paso a moneda local ---
    maestro_dolar = (reporte[['FECHA_HORA', 'Dolar']].dropna(subset=['Dolar'])
                     .drop_duplicates(subset=['FECHA_HORA'])
                     .set_index('FECHA_HORA')['Dolar'].to_dict())
    resumen_relacionada['Valor_Dolar'] = resumen_relacionada['FECHA_HORA'].map(maestro_dolar).ffill().bfill()
    resumen_relacionada['Costo_Partida_ML'] = resumen_relacionada['Costo_Partida'] * resumen_relacionada['Valor_Dolar']
    resumen_relacionada['Costo_Detencion_ML'] = resumen_relacionada['Costo_Detencion'] * resumen_relacionada['Valor_Dolar']


    # ==========================================
    # 11.1 TARIFA SEGUN CONFIGURACION INSTRUIDA POR RIO (v6)
    # ==========================================
    # En paralelo a la tarifa segun Central propia de arriba. Columnas con
    # sufijo _RIO para no chocar con las que ya existen.
    if USAR_TARIFA_RIO_INSTRUIDA == 1:
        cols_tarifa_rio = {'Fria_Num1_M': 'Fria_Num1_M_RIO', 'Tibia_Num2_N': 'Tibia_Num2_N_RIO',
                           'Caliente_Num1_P': 'Caliente_Num1_P_RIO',
                           'Partida_Fria': 'Partida_Fria_RIO', 'Partida_Tibia': 'Partida_Tibia_RIO',
                           'Partida_Tibia_2': 'Partida_Tibia_2_RIO',
                           'Partida_Caliente': 'Partida_Caliente_RIO', 'Detencion': 'Detencion_RIO',
                           'Costo_Cero': 'Costo_Cero_RIO'}
        tabla_rio = df_costos_pd[['Llave_Concatenada'] + list(cols_tarifa_rio.keys())].rename(columns=cols_tarifa_rio)

        resumen_relacionada = resumen_relacionada.merge(
            tabla_rio, left_on='Llave_FHC_RIO', right_on='Llave_Concatenada', how='left'
        ).drop(columns=['Llave_Concatenada'])

        # True cuando la configuracion que instruye el RIO no tiene ninguna fila
        # en la tabla de tarifas (o no hay registro de RIO en absoluto, ya que
        # 'Sin_Registro_RIO' tampoco calzara con ninguna UNIDAD real). Este es el
        # caso que se marca para revision manual, no se paga automatico.
        resumen_relacionada['Config_RIO_Sin_Tarifa'] = resumen_relacionada['Fria_Num1_M_RIO'].isna()

        resumen_relacionada = clasificar_partida(resumen_relacionada, '_RIO')
        resumen_relacionada['Filtro_CostoCero_RIO'] = filtro_costo_cero(
            resumen_relacionada['Costo_Cero_RIO'], resumen_relacionada['Configuracion RIO'])

        resumen_relacionada['Costo_Detencion_RIO'] = pd.to_numeric(
            resumen_relacionada['Detencion_RIO'], errors='coerce').fillna(0)
        resumen_relacionada['Costo_Partida_RIO_ML'] = (resumen_relacionada['Costo_Partida_RIO']
                                                        * resumen_relacionada['Valor_Dolar'])
        resumen_relacionada['Costo_Detencion_RIO_ML'] = (resumen_relacionada['Costo_Detencion_RIO']
                                                          * resumen_relacionada['Valor_Dolar'])


    # ==========================================
    # 14. RESUMEN COMPACTO POR CICLO
    # ==========================================
    resumen_relacionada = resumen_relacionada.sort_values(
        by=['Central_Relacionada', 'Ciclo_ID_Relacionada', 'FECHA_HORA', 'GENERACION'])

    df_compacto = resumen_relacionada.groupby(
        ['Etiqueta_Relacionada', 'Central_Relacionada', 'Ciclo_ID_Relacionada'], as_index=False
    ).agg(
        Inicio_Ciclo=('FECHA_HORA', 'min'), Termino_Ciclo=('FECHA_HORA', 'max'),
        Generacion_Suma_Ciclo=('GENERACION', 'sum'), Margen_Suma_Ciclo=('Margen', 'sum'),
        Horas_Detenida_Ciclo=('Horas_Detenida_Ciclo', 'first'),
        Flag_Exencion=('Flag_Exencion', 'first'),
        Central_Partida=('Central', 'first'), Central_Detencion=('Central', 'last'),
        Costo_Partida_Base=('Costo_Partida_ML', 'first'), Costo_Detencion_Base=('Costo_Detencion_ML', 'last'),
        Filtro_CostoCero_Partida=('Filtro_CostoCero_Partida', 'first'),
        Filtro_CostoCero_Detencion=('Filtro_CostoCero_Detencion', 'last'),
        Filtro_Conf_Partida=('Conf despachada RIO', 'first'),
        Filtro_Disp_Partida=('Disponible (1) / Pruebas (0)', 'first'),
        Filtro_Op_Partida=('Filtro_Operacional', 'first'),
        Consigna_Partida=('CONSIGNAS', 'first'), Motivo_Partida=('MOTIVO', 'first'),
        Estado_Op_Partida=('ESTADO OPERACIONAL', 'first'),
        Fuente_Config_RIO_Partida=('Fuente_Config_RIO', 'first'),
        Config_RIO_Rescatada_Ventana_Partida=('Config_RIO_Rescatada_Ventana', 'first'),
        Filtro_Conf_Detencion=('Conf despachada RIO', 'last'),
        Filtro_Disp_Detencion=('Disponible (1) / Pruebas (0)', 'last'),
        Filtro_Op_Detencion=('Filtro_Operacional', 'last'),
        Consigna_Detencion=('CONSIGNAS', 'last'), Motivo_Detencion=('MOTIVO', 'last'),
        Estado_Op_Detencion=('ESTADO OPERACIONAL', 'last'),
        Fuente_Config_RIO_Detencion=('Fuente_Config_RIO', 'last'),
        Config_RIO_Rescatada_Ventana_Detencion=('Config_RIO_Rescatada_Ventana', 'last'),
        Estado_Ciclo_Mes=('Estado_Ciclo_Mes', 'first')
    )

    # ==========================================
    # 14.1 REASIGNACION A CONFIGURACION DOMINANTE
    # ==========================================
    # Ver comentario de USAR_CONFIG_DOMINANTE en el panel de control. Se calcula
    # aparte del .agg() de arriba (que queda intacto) y se sobreescribe despues,
    # para que con el interruptor en 0 el comportamiento sea IDENTICO al v4.
    # Si USAR_TARIFA_RIO_INSTRUIDA esta activo, este mecanismo ya no hace falta
    # (ver 14.1b) y se ignora.
    if USAR_CONFIG_DOMINANTE == 1 and USAR_TARIFA_RIO_INSTRUIDA == 1:
        print("\n  [!] USAR_CONFIG_DOMINANTE y USAR_TARIFA_RIO_INSTRUIDA estan ambos en 1.")
        print("      USAR_TARIFA_RIO_INSTRUIDA tiene prioridad; se ignora la reasignacion")
        print("      a configuracion dominante (seccion 14.1) y corre 14.1b en su lugar.")

    if USAR_CONFIG_DOMINANTE == 1 and USAR_TARIFA_RIO_INSTRUIDA == 0:
        print("\n" + "=" * 78)
        print("  14.1 REASIGNACION A CONFIGURACION DOMINANTE")
        print("=" * 78)

        gen_por_config = resumen_relacionada.groupby(
            ['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Central'])['GENERACION'].sum()
        idx_dom = gen_por_config.groupby(level=[0, 1]).idxmax()
        central_dominante = gen_por_config.loc[idx_dom].reset_index()[
            ['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Central']
        ].rename(columns={'Central': 'Central_Dominante'})

        marcado = resumen_relacionada.merge(
            central_dominante, on=['Central_Relacionada', 'Ciclo_ID_Relacionada'], how='left')
        solo_dominante = marcado[marcado['Central'] == marcado['Central_Dominante']]

        # Apertura/cierre de la configuracion DOMINANTE (no del ciclo completo).
        # Se toman todos los campos "_Partida"/"_Detencion" del MISMO bloque para
        # no mezclar el RIO de una configuracion con el costo de otra.
        apertura = (solo_dominante.sort_values('FECHA_HORA')
                    .groupby(['Central_Relacionada', 'Ciclo_ID_Relacionada'], as_index=False).first())
        cierre = (solo_dominante.sort_values('FECHA_HORA')
                  .groupby(['Central_Relacionada', 'Ciclo_ID_Relacionada'], as_index=False).last())

        # 'Conf despachada RIO' se calcula POR SUB-CONFIGURACION (compara el
        # sufijo de esa config especifica contra lo que informa el RIO en ese
        # instante). El resto del RIO (Configuracion RIO, Consigna, Motivo,
        # Estado_Op) SI se comparte entre todas las sub-configuraciones que
        # reportan en el mismo bloque, porque el cruce con el RIO se hace por
        # Central_Relacionada + FECHA_HORA, no por sub-configuracion.
        # Si en el mismo bloque de 15 min coexisten dos sub-configuraciones (ej.
        # turbina sola y turbina+vapor reportando en paralelo mientras se suma la
        # segunda unidad) y CUALQUIERA de ellas calza con lo instruido por el
        # RIO, la partida debe pasar el filtro - no solo si calza la que quedo
        # elegida como dominante.
        conf_por_bloque = (resumen_relacionada
                           .groupby(['Central_Relacionada', 'Ciclo_ID_Relacionada', 'FECHA_HORA'])
                           ['Conf despachada RIO'].max().reset_index()
                           .rename(columns={'Conf despachada RIO': 'Filtro_Conf_Bloque'}))

        # Alineacion explicita de tipos antes del cruce: 'apertura'/'cierre' vienen
        # de una cadena de merges/filtros que puede haber promovido
        # Ciclo_ID_Relacionada a float64 en el camino (ej. al pasar por un
        # idxmax()/reset_index() con NaN de por medio), mientras que
        # 'conf_por_bloque' sale directo de resumen_relacionada. Un cruce con
        # llaves de distinto tipo puede fallar en silencio y dejar NaN, que el
        # fillna(0) generico de mas abajo convierte en un "rechazo" que en
        # realidad es un fallo de cruce, no una decision de negocio.
        for llave_df in (apertura, cierre, conf_por_bloque):
            llave_df['Ciclo_ID_Relacionada'] = llave_df['Ciclo_ID_Relacionada'].astype('int64')
            llave_df['FECHA_HORA'] = pd.to_datetime(llave_df['FECHA_HORA'])

        apertura = apertura.merge(conf_por_bloque,
                                  on=['Central_Relacionada', 'Ciclo_ID_Relacionada', 'FECHA_HORA'], how='left')
        cierre = cierre.merge(conf_por_bloque,
                              on=['Central_Relacionada', 'Ciclo_ID_Relacionada', 'FECHA_HORA'], how='left')

        sin_cruce_ap = apertura['Filtro_Conf_Bloque'].isna().sum()
        sin_cruce_ci = cierre['Filtro_Conf_Bloque'].isna().sum()
        if sin_cruce_ap or sin_cruce_ci:
            print(f"  [!] {sin_cruce_ap:,} aperturas y {sin_cruce_ci:,} cierres no encontraron su propio")
            print("      bloque en conf_por_bloque (deberia ser 0 siempre, ya que el bloque de")
            print("      apertura/cierre sale del mismo resumen_relacionada). Esto es un bug del")
            print("      cruce, no un rechazo real - revisar antes de confiar en el resultado.")
            if sin_cruce_ap:
                print("      Ejemplos sin cruce en apertura:")
                print(apertura[apertura['Filtro_Conf_Bloque'].isna()]
                      [['Central_Relacionada', 'Ciclo_ID_Relacionada', 'FECHA_HORA']].head(5).to_string(index=False))
        else:
            print("  OK: todas las aperturas y cierres encontraron su propio bloque "
                  "(el cruce de Filtro_Conf_Bloque es confiable).")
        # Si por algun motivo no hubo cruce, se usa el valor propio de la config
        # dominante (comportamiento equivalente a no aplicar la ampliacion al
        # resto del bloque) en vez de dejarlo en NaN -> 0 silencioso.
        apertura['Filtro_Conf_Bloque'] = apertura['Filtro_Conf_Bloque'].fillna(apertura['Conf despachada RIO'])
        cierre['Filtro_Conf_Bloque'] = cierre['Filtro_Conf_Bloque'].fillna(cierre['Conf despachada RIO'])

        apertura_sel = apertura[['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Central',
                                 'Costo_Partida_ML', 'Filtro_CostoCero_Partida', 'Filtro_Conf_Bloque',
                                 'Disponible (1) / Pruebas (0)', 'Filtro_Operacional',
                                 'CONSIGNAS', 'MOTIVO', 'ESTADO OPERACIONAL']].copy()
        apertura_sel.columns = ['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Central_Partida',
                                'Costo_Partida_Base', 'Filtro_CostoCero_Partida', 'Filtro_Conf_Partida', 'Filtro_Disp_Partida',
                                'Filtro_Op_Partida', 'Consigna_Partida', 'Motivo_Partida', 'Estado_Op_Partida']

        cierre_sel = cierre[['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Central',
                             'Costo_Detencion_ML', 'Filtro_CostoCero_Detencion', 'Filtro_Conf_Bloque',
                             'Disponible (1) / Pruebas (0)', 'Filtro_Operacional',
                             'CONSIGNAS', 'MOTIVO', 'ESTADO OPERACIONAL']].copy()
        cierre_sel.columns = ['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Central_Detencion',
                              'Costo_Detencion_Base', 'Filtro_CostoCero_Detencion', 'Filtro_Conf_Detencion', 'Filtro_Disp_Detencion',
                              'Filtro_Op_Detencion', 'Consigna_Detencion', 'Motivo_Detencion', 'Estado_Op_Detencion']

        # Se conserva el valor original para trazabilidad y para el resumen de auditoria.
        df_compacto['Central_Partida_Original'] = df_compacto['Central_Partida']
        df_compacto['Costo_Partida_Base_Original'] = df_compacto['Costo_Partida_Base']
        df_compacto['Central_Detencion_Original'] = df_compacto['Central_Detencion']
        df_compacto['Costo_Detencion_Base_Original'] = df_compacto['Costo_Detencion_Base']

        cols_partida = list(apertura_sel.columns[2:])
        cols_detencion = list(cierre_sel.columns[2:])
        df_compacto = df_compacto.drop(columns=cols_partida + cols_detencion)
        df_compacto = df_compacto.merge(apertura_sel, on=['Central_Relacionada', 'Ciclo_ID_Relacionada'], how='left')
        df_compacto = df_compacto.merge(cierre_sel, on=['Central_Relacionada', 'Ciclo_ID_Relacionada'], how='left')

        cambio_partida = df_compacto['Central_Partida'] != df_compacto['Central_Partida_Original']
        cambio_detencion = df_compacto['Central_Detencion'] != df_compacto['Central_Detencion_Original']
        delta_partida = (df_compacto['Costo_Partida_Base'] - df_compacto['Costo_Partida_Base_Original']).sum()
        delta_detencion = (df_compacto['Costo_Detencion_Base'] - df_compacto['Costo_Detencion_Base_Original']).sum()

        print(f"  Ciclos con partida reasignada  : {int(cambio_partida.sum()):,} "
              f"(impacto bruto: {delta_partida:+,.0f} CLP)")
        print(f"  Ciclos con detencion reasignada: {int(cambio_detencion.sum()):,} "
              f"(impacto bruto: {delta_detencion:+,.0f} CLP)")
        if cambio_partida.any():
            top_cambios = (df_compacto[cambio_partida]
                           .assign(Dif=lambda d: d['Costo_Partida_Base'] - d['Costo_Partida_Base_Original'])
                           .reindex(columns=['Etiqueta_Relacionada', 'Central_Relacionada',
                                            'Central_Partida_Original', 'Central_Partida', 'Dif'])
                           .sort_values('Dif', key=abs, ascending=False))
            print("\n  Top 15 por impacto:")
            print(top_cambios.head(15).to_string(index=False))

        # Estas filas ya pasaron por un cruce exacto (mismo bloque de 15 min, con
        # el chequeo de "cualquier configuracion del bloque" aplicado). La
        # busqueda relajada de mas abajo (ACTIVAR_BUSQUEDA_RELAJADA) es un
        # mecanismo mas grueso (ventana de +/- 30 min) pensado para cuando NO hay
        # cruce exacto con el RIO - si se le permite tocar estas filas, puede
        # encontrar un registro de un momento distinto y pisar el valor que ya
        # confirmamos correcto. Se marcan para que la busqueda relajada las
        # respete y no las reprocese.
        df_compacto['_Confiable_Partida'] = cambio_partida
        df_compacto['_Confiable_Detencion'] = cambio_detencion
    else:
        # Con el interruptor apagado, ninguna fila paso por la reasignacion, asi
        # que la busqueda relajada de mas abajo debe comportarse identico al v4.
        df_compacto['_Confiable_Partida'] = False
        df_compacto['_Confiable_Detencion'] = False


    # ==========================================
    # 14.1b TARIFA SEGUN CONFIGURACION INSTRUIDA POR RIO (v6)
    # ==========================================
    # Reemplaza Costo_Partida_Base/Costo_Detencion_Base por la tarifa de la
    # configuracion que el RIO instruyo en el primer/ultimo bloque del ciclo
    # COMPLETO (no de una configuracion dominante - ya no hace falta elegir una,
    # porque Configuracion RIO es la misma para todas las sub-configuraciones que
    # comparten el mismo instante). El filtro de configuracion (Filtro_Conf) deja
    # de existir: pasa a ser siempre 1, porque lo que se paga ya es por
    # definicion lo que el RIO instruyo. Los otros dos filtros (Maquina en
    # Pruebas, Sin Motivo) NO se tocan aqui, y siguen pudiendo pasar por la
    # busqueda relajada normalmente (a proposito: estas filas NO se marcan como
    # '_Confiable', para no bloquear ese refinamiento).
    if USAR_TARIFA_RIO_INSTRUIDA == 1:
        print("\n" + "=" * 78)
        print("  14.1b TARIFA SEGUN CONFIGURACION INSTRUIDA POR RIO")
        print("=" * 78)

        apertura_rio = resumen_relacionada[
            resumen_relacionada['FECHA_HORA'] == resumen_relacionada['Inicio_Ciclo_Global']]
        apertura_rio = apertura_rio.drop_duplicates(subset=['Central_Relacionada', 'Ciclo_ID_Relacionada'])
        apertura_rio = apertura_rio[['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Configuracion RIO',
                                     'Costo_Partida_RIO_ML', 'Filtro_CostoCero_RIO', 'Config_RIO_Sin_Tarifa']].rename(columns={
            'Configuracion RIO': 'Config_RIO_Usada_Partida',
            'Costo_Partida_RIO_ML': 'Costo_Partida_Base_Nuevo',
            'Filtro_CostoCero_RIO': 'Filtro_CostoCero_Partida_Nuevo',
            'Config_RIO_Sin_Tarifa': 'Config_RIO_Sin_Tarifa_Partida'})

        cierre_rio = resumen_relacionada[
            resumen_relacionada['FECHA_HORA'] == resumen_relacionada['Termino_Ciclo_Global']]
        cierre_rio = cierre_rio.drop_duplicates(subset=['Central_Relacionada', 'Ciclo_ID_Relacionada'])
        cierre_rio = cierre_rio[['Central_Relacionada', 'Ciclo_ID_Relacionada', 'Configuracion RIO',
                                 'Costo_Detencion_RIO_ML', 'Filtro_CostoCero_RIO', 'Config_RIO_Sin_Tarifa']].rename(columns={
            'Configuracion RIO': 'Config_RIO_Usada_Detencion',
            'Costo_Detencion_RIO_ML': 'Costo_Detencion_Base_Nuevo',
            'Filtro_CostoCero_RIO': 'Filtro_CostoCero_Detencion_Nuevo',
            'Config_RIO_Sin_Tarifa': 'Config_RIO_Sin_Tarifa_Detencion'})

        df_compacto['Costo_Partida_Base_Original'] = df_compacto['Costo_Partida_Base']
        df_compacto['Costo_Detencion_Base_Original'] = df_compacto['Costo_Detencion_Base']

        df_compacto = df_compacto.merge(apertura_rio, on=['Central_Relacionada', 'Ciclo_ID_Relacionada'], how='left')
        df_compacto = df_compacto.merge(cierre_rio, on=['Central_Relacionada', 'Ciclo_ID_Relacionada'], how='left')

        df_compacto['Costo_Partida_Base'] = df_compacto['Costo_Partida_Base_Nuevo']
        df_compacto['Costo_Detencion_Base'] = df_compacto['Costo_Detencion_Base_Nuevo']
        df_compacto['Filtro_CostoCero_Partida'] = df_compacto['Filtro_CostoCero_Partida_Nuevo']
        df_compacto['Filtro_CostoCero_Detencion'] = df_compacto['Filtro_CostoCero_Detencion_Nuevo']
        df_compacto = df_compacto.drop(columns=['Costo_Partida_Base_Nuevo', 'Costo_Detencion_Base_Nuevo',
                                                'Filtro_CostoCero_Partida_Nuevo',
                                                'Filtro_CostoCero_Detencion_Nuevo'])

        # El filtro de configuracion deja de existir bajo este mecanismo.
        df_compacto['Filtro_Conf_Partida'] = 1
        df_compacto['Filtro_Conf_Detencion'] = 1

        delta_p = (df_compacto['Costo_Partida_Base'] - df_compacto['Costo_Partida_Base_Original']).sum()
        delta_d = (df_compacto['Costo_Detencion_Base'] - df_compacto['Costo_Detencion_Base_Original']).sum()
        n_sin_tarifa_p = int(df_compacto['Config_RIO_Sin_Tarifa_Partida'].sum())
        n_sin_tarifa_d = int(df_compacto['Config_RIO_Sin_Tarifa_Detencion'].sum())
        print(f"  Impacto bruto en costo de partida  : {delta_p:+,.0f} CLP")
        print(f"  Impacto bruto en costo de detencion: {delta_d:+,.0f} CLP")
        print(f"  Ciclos con config RIO sin tarifa (quedan para revision manual):")
        print(f"    Partida  : {n_sin_tarifa_p:,} de {len(df_compacto):,}")
        print(f"    Detencion: {n_sin_tarifa_d:,} de {len(df_compacto):,}")
    else:
        df_compacto['Config_RIO_Sin_Tarifa_Partida'] = False
        df_compacto['Config_RIO_Sin_Tarifa_Detencion'] = False

    # Empresa a nivel de ciclo (dominante por energia dentro de la relacionada)
    df_compacto['Empresa'] = df_compacto['Central_Relacionada'].map(empresa_por_relacionada) \
                                                              .fillna('Sin_Empresa')

    if FILTRAR_CICLOS_BAJA_GEN == 1:
        print("\n" + "=" * 78)
        print(f"  AUDITORIA: FILTRO DE RUIDO OPERATIVO (<= {UMBRAL_RUIDO_MWH} MWh)")
        print("=" * 78)
        mask_baja = df_compacto['Generacion_Suma_Ciclo'] <= UMBRAL_RUIDO_MWH
        eliminados = df_compacto[mask_baja]
        df_compacto = df_compacto[~mask_baja].copy()
        if not eliminados.empty:
            print(f"  Se eliminaron {len(eliminados):,} ciclos por generacion espuria "
                  f"({eliminados['Generacion_Suma_Ciclo'].sum():,.2f} MWh).")
        else:
            print("  Sin ciclos de generacion espuria.")

    gen_comp, rows_comp = audit_gen("4. df_compacto (ciclos)", df_compacto, col_gen='Generacion_Suma_Ciclo')

    # --- Busqueda relajada en el RIO alrededor de la partida / detencion ---
    if ACTIVAR_BUSQUEDA_RELAJADA == 1 and not df_compacto.empty:
        print(f"\n  Busqueda relajada en el RIO: +/- {VENTANA_CUARTOS_HORA * 15} minutos...")
        rio_search = rio[rio_cols].dropna(subset=['FECHA_HORA_RIO']).copy()
        rio_search = rio_search.rename(columns={'NOMBRE CONFIGURACIÓN': 'Conf_RIO'})
        for c in ['CONSIGNAS', 'MOTIVO', 'ESTADO OPERACIONAL']:
            rio_search[c] = rio_search[c].fillna('Sin_Registro_RIO')
        rio_search['COMENTARIO'] = rio_search['COMENTARIO'].fillna('')
        tol_seg = VENTANA_CUARTOS_HORA * 15 * 60
        por_central = {k: v for k, v in rio_search.groupby('Central_Relacionada_RIO')}

        def obtener_mejor_rio(row, tipo):
            objetivo = row['Inicio_Ciclo'] if tipo == 'Partida' else row['Termino_Ciclo']
            sub = por_central.get(row['Central_Relacionada'])
            if pd.isna(objetivo) or sub is None or sub.empty:
                return pd.Series([None] * 8)

            sub = sub.copy()
            sub['Diff'] = (sub['FECHA_HORA_RIO'] - objetivo).dt.total_seconds().abs()
            sub = sub[sub['Diff'] <= tol_seg]
            if sub.empty:
                return pd.Series([None] * 8)

            sub['Central'] = row['Central_Partida'] if tipo == 'Partida' else row['Central_Detencion']
            sub['Flag_Exencion'] = bool(row['Flag_Exencion'])
            fc, fd, fo = calcular_filtros(sub, 'Central', 'Conf_RIO', 'CONSIGNAS',
                                          'MOTIVO', 'ESTADO OPERACIONAL', 'COMENTARIO', 'Flag_Exencion')
            sub['Filtro_Conf'], sub['Filtro_Disp'], sub['Filtro_Op'] = fc, fd, fo
            sub['Suma'] = sub['Filtro_Conf'] + sub['Filtro_Disp'] + sub['Filtro_Op']
            best = sub.sort_values(by=['Suma', 'Diff'], ascending=[False, True]).iloc[0]
            return pd.Series([best['CONSIGNAS'], best['MOTIVO'], best['ESTADO OPERACIONAL'],
                              best['Filtro_Conf'], best['Filtro_Disp'], best['Filtro_Op'], True,
                              best['FECHA_HORA_RIO']])

        for prefijo in ['Partida', 'Detencion']:
            columna_confiable = f'_Confiable_{prefijo}'
            res = df_compacto.apply(lambda r: obtener_mejor_rio(r, prefijo), axis=1)
            validos = (res[6] == True) & (~df_compacto[columna_confiable])
            df_compacto[f'Fuente_Filtros_RIO_{prefijo}'] = pd.NaT
            if validos.any():
                destino = [f'Consigna_{prefijo}', f'Motivo_{prefijo}', f'Estado_Op_{prefijo}',
                           f'Filtro_Conf_{prefijo}', f'Filtro_Disp_{prefijo}', f'Filtro_Op_{prefijo}']
                for i, col in enumerate(destino):
                    df_compacto.loc[validos, col] = res.loc[validos, i]
                df_compacto.loc[validos, f'Fuente_Filtros_RIO_{prefijo}'] = res.loc[validos, 7]
            n_respetados = int(df_compacto[columna_confiable].sum())
            print(f"    {prefijo}: {int(validos.sum()):,} de {len(df_compacto):,} ciclos "
                  f"encontraron registro en la ventana "
                  f"({n_respetados:,} respetados de la reasignacion a config dominante).")


    for prefijo in ['Partida', 'Detencion']:
        fuente_filtros = f'Fuente_Filtros_RIO_{prefijo}'
        if fuente_filtros not in df_compacto:
            df_compacto[fuente_filtros] = pd.NaT
        ambas = (df_compacto[f'Fuente_Config_RIO_{prefijo}'].notna()
                 & df_compacto[fuente_filtros].notna())
        df_compacto[f'Diverge_Fuente_RIO_{prefijo}'] = (
            ambas & (df_compacto[f'Fuente_Config_RIO_{prefijo}'] != df_compacto[fuente_filtros]))

    for c in ['Filtro_Conf_Partida', 'Filtro_Disp_Partida', 'Filtro_Op_Partida',
              'Filtro_Conf_Detencion', 'Filtro_Disp_Detencion', 'Filtro_Op_Detencion']:
        df_compacto[c] = pd.to_numeric(df_compacto[c], errors='coerce').fillna(0).astype(int)

    # v6: el filtro de configuracion no existe bajo este mecanismo. Se reafirma
    # aqui porque la busqueda relajada de arriba pudo haberlo tocado de nuevo (a
    # proposito no se excluyo a estas filas de la busqueda relajada, para que
    # Disp/Op si se sigan pudiendo refinar).
    if USAR_TARIFA_RIO_INSTRUIDA == 1:
        df_compacto['Filtro_Conf_Partida'] = 1
        df_compacto['Filtro_Conf_Detencion'] = 1

    df_compacto = costos_clasicos(df_compacto)
    df_compacto['Costos_Totales_PD'] = df_compacto['Costo_Partida_Efectivo'] + df_compacto['Costo_Detencion_Efectivo']
    df_compacto['Total SC_PD'] = np.maximum(0, df_compacto['Costos_Totales_PD'] - df_compacto['Margen_Suma_Ciclo'])


    for prefijo in ['Partida', 'Detencion']:
        diverge = df_compacto[f'Diverge_Fuente_RIO_{prefijo}']
        monto = df_compacto.loc[diverge, f'Costo_{prefijo}_Efectivo'].sum()
        print(f"  Divergencia fuente RIO {prefijo.lower()}: {int(diverge.sum()):,} ciclos, "
              f"{monto:,.0f} CLP efectivos.")

        rescatada = df_compacto[f'Config_RIO_Rescatada_Ventana_{prefijo}']
        monto_rescatado = df_compacto.loc[rescatada, f'Costo_{prefijo}_Efectivo'].sum()
        print(f"  Configuracion RIO rescatada {prefijo.lower()}: {int(rescatada.sum()):,} ciclos, "
              f"{monto_rescatado:,.0f} CLP efectivos.")


    # ==========================================
    # 14.2 RENUMERACION DE CICLOS PARA EL REPORTE  [BUG 5]
    # ==========================================
    # El ID interno es continuo desde el mes anterior, porque un ciclo que cruza la
    # frontera mensual debe seguir siendo uno solo. Para el reporte se renumera
    # desde 1 por central relacionada, respetando el orden cronologico y
    # conservando la etiqueta original para trazabilidad.
    df_compacto['Etiqueta_Original'] = df_compacto['Etiqueta_Relacionada']

    if RENUMERAR_CICLOS_DEL_MES == 1:
        df_compacto = df_compacto.sort_values(['Central_Relacionada', 'Inicio_Ciclo']).reset_index(drop=True)
        df_compacto['Ciclo_Mes'] = df_compacto.groupby('Central_Relacionada').cumcount() + 1
        df_compacto['Etiqueta_Relacionada'] = (df_compacto['Central_Relacionada'].astype(str) + "&"
                                               + df_compacto['Ciclo_Mes'].astype(str))

        # La misma renumeracion se propaga al detalle de 15 min para que ambas
        # hojas del Excel usen la misma etiqueta.
        mapa_etiquetas = dict(zip(df_compacto['Etiqueta_Original'], df_compacto['Etiqueta_Relacionada']))
        resumen_relacionada['Etiqueta_Relacionada'] = (resumen_relacionada['Etiqueta_Relacionada']
                                                       .map(mapa_etiquetas)
                                                       .fillna(resumen_relacionada['Etiqueta_Relacionada']))
        print(f"\n  Ciclos renumerados desde 1 por central relacionada "
              f"(maximo por central: {int(df_compacto['Ciclo_Mes'].max())}).")
    else:
        df_compacto['Ciclo_Mes'] = df_compacto['Ciclo_ID_Relacionada']
        print("\n  Renumeracion desactivada: las etiquetas conservan el ID continuo.")


    # ==========================================
    # 14.3 AUDITORIA: LIMITES DE CICLOS
    # ==========================================
    df_lim = pd.DataFrame()
    if AUDITAR_LIMITES_CICLOS == 1 and not df_compacto.empty:
        print("\n" + "=" * 78)
        print("  AUDITORIA: LIMITES Y SUPERPOSICION DE CICLOS (+/- 15 min)")
        print("=" * 78)

        gen_bloque = resumen_relacionada.groupby(['Central_Relacionada', 'FECHA_HORA'])['GENERACION'].sum().to_dict()
        df_lim = df_compacto[['Etiqueta_Relacionada', 'Central_Relacionada', 'Inicio_Ciclo',
                              'Termino_Ciclo', 'Central_Partida']].copy() \
                            .sort_values(['Central_Relacionada', 'Inicio_Ciclo'])

        df_lim['Termino_Anterior'] = df_lim.groupby('Central_Relacionada')['Termino_Ciclo'].shift(1)
        df_lim['Minutos_Gap_Previo'] = (df_lim['Inicio_Ciclo'] - df_lim['Termino_Anterior']).dt.total_seconds() / 60.0
        df_lim['Minutos_Gap_Sig'] = df_lim.groupby('Central_Relacionada')['Minutos_Gap_Previo'].shift(-1)
        df_lim['Bloque_Previo'] = df_lim['Inicio_Ciclo'] - pd.Timedelta(minutes=MINUTOS_BLOQUE)
        df_lim['Bloque_Siguiente'] = df_lim['Termino_Ciclo'] + pd.Timedelta(minutes=MINUTOS_BLOQUE)
        df_lim['Gen_Previo'] = [gen_bloque.get((c, t), 0) for c, t in
                                zip(df_lim['Central_Relacionada'], df_lim['Bloque_Previo'])]
        df_lim['Gen_Sig'] = [gen_bloque.get((c, t), 0) for c, t in
                             zip(df_lim['Central_Relacionada'], df_lim['Bloque_Siguiente'])]

        mask_pegados = df_lim['Minutos_Gap_Previo'] <= MINUTOS_BLOQUE
        mask_h_prev = (df_lim['Gen_Previo'] > 0) & (df_lim['Minutos_Gap_Previo'].fillna(9999) > MINUTOS_BLOQUE)
        mask_h_sig = (df_lim['Gen_Sig'] > 0) & (df_lim['Minutos_Gap_Sig'].fillna(9999) > MINUTOS_BLOQUE)
        df_alertas = df_lim[mask_pegados.fillna(False) | mask_h_prev | mask_h_sig].copy()

        if df_alertas.empty:
            print("  OK: sin superposiciones ni cortes abruptos de energia.")
        else:
            print(f"  {len(df_alertas):,} anomalia(s) en las fronteras de ciclo. Primeras 25:")
            for _, row in df_alertas.head(25).iterrows():
                partes = []
                g = row['Minutos_Gap_Previo']
                if pd.notna(g) and g < 0:
                    partes.append(f"Superposicion ({abs(g):.0f} min)")
                elif pd.notna(g) and g == MINUTOS_BLOQUE:
                    partes.append("Ciclo pegado al anterior")
                if row['Gen_Previo'] > 0 and pd.notna(g) and g > MINUTOS_BLOQUE:
                    partes.append(f"{row['Gen_Previo']:.1f} MWh sueltos antes de la partida")
                if row['Gen_Sig'] > 0 and pd.notna(row['Minutos_Gap_Sig']) and row['Minutos_Gap_Sig'] > MINUTOS_BLOQUE:
                    partes.append(f"{row['Gen_Sig']:.1f} MWh sueltos tras la detencion")
                print(f"   [{row['Etiqueta_Relacionada']}] -> {' | '.join(partes)}")


    # ==========================================
    # 14.4 AUDITORIA: ENERGIA ENTRE CICLOS
    # ==========================================
    if AUDITAR_ENERGIA_INTER_CICLOS == 1 and not df_lim.empty:
        print("\n" + "=" * 78)
        print("  AUDITORIA: ENERGIA FISICA ENTRE CICLOS")
        print("=" * 78)
        gen_fisica = reporte.groupby(['Central', 'FECHA_HORA'])['GENERACION'].sum().to_dict()
        alertas_gap = []
        for _, row in df_lim.dropna(subset=['Termino_Anterior']).iterrows():
            if row['Minutos_Gap_Previo'] > MINUTOS_BLOQUE:
                rango = pd.date_range(start=row['Termino_Anterior'] + pd.Timedelta(minutes=MINUTOS_BLOQUE),
                                      end=row['Inicio_Ciclo'] - pd.Timedelta(minutes=MINUTOS_BLOQUE),
                                      freq=f'{MINUTOS_BLOQUE}min')
                energia = sum(gen_fisica.get((row['Central_Partida'], t), 0) for t in rango)
                if energia > 0:
                    alertas_gap.append({
                        'Ciclo_Siguiente': row['Etiqueta_Relacionada'],
                        'Horas_Apagada': round(row['Minutos_Gap_Previo'] / 60, 1),
                        'MWh_Ocultos': round(energia, 2)})
        if not alertas_gap:
            print("  OK: 0.00 MWh en los huecos entre ciclos. Agrupaciones hermeticas.")
        else:
            df_gap = pd.DataFrame(alertas_gap)
            print(f"  {df_gap['MWh_Ocultos'].sum():,.2f} MWh inyectados durante tiempos de 'Detencion'.")
            print("  (La maquina inyecto bajo otra configuracion, o un filtro previo la excluyo)")
            print(df_gap.sort_values('MWh_Ocultos', ascending=False).head(20).to_string(index=False))


    # ==========================================
    # 14.5 AUDITORIA: FRONTERA MENSUAL
    # ==========================================
    print("\n" + "=" * 78)
    print("  AUDITORIA: EMPALME DE FRONTERA MENSUAL")
    print("=" * 78)
    frontera = df_compacto[df_compacto['Estado_Ciclo_Mes'].str.contains('Viene del mes anterior', na=False)]
    if frontera.empty:
        print("  Sin ciclos inconclusos provenientes del mes anterior.")
        print("  (Si esperabas ciclos de frontera, revisa que RUTA_REPORTE_MES_PASADO exista.)")
    else:
        print(f"  {len(frontera):,} ciclos continuados desde el mes pasado "
              f"({frontera['Generacion_Suma_Ciclo'].sum():,.2f} MWh).")
        sin_po_front = frontera[frontera['Costo_Partida_Base'] == 0]
        if not sin_po_front.empty:
            print(f"  [!] {len(sin_po_front):,} de ellos no cruzaron tarifa de Partida. Verifica que")
            print("      el Costos_de_P-D del mes pasado contenga esas maquinas:")
            print(sin_po_front[['Etiqueta_Relacionada', 'Inicio_Ciclo']].head(20).to_string(index=False))

    n_exentos = int(df_compacto['Flag_Exencion'].astype(bool).sum())
    print(f"\n  Ciclos con exencion '{REGLA_EXENCION}' activa: {n_exentos:,} de {len(df_compacto):,}")


    # ==========================================
    # 14.5b AUDITORIA: CICLOS DE FRONTERA SIN INSTRUCCION RIO  [BUG 7]
    # ==========================================
    # Especifico para el problema que motivo el empalme del RIO: cuantos ciclos
    # que arrancaron ANTES de este mes siguen sin instruccion RIO en su apertura
    # incluso despues del empalme. Si RUTA_RIO_MES_PASADO no alcanza (por ejemplo,
    # porque el ciclo arranco hace 2+ meses), esto seguira apareciendo aqui.
    if USAR_TARIFA_RIO_INSTRUIDA == 1:
        print("\n" + "=" * 78)
        print("  AUDITORIA: CICLOS DE FRONTERA SIN INSTRUCCION RIO EN LA APERTURA")
        print("=" * 78)
        frontera_todo = df_compacto[df_compacto['Inicio_Ciclo'] < f_min_actual]
        if frontera_todo.empty:
            print("  Sin ciclos cuyo Inicio_Ciclo sea anterior al mes actual.")
        else:
            sin_rio_frontera = frontera_todo[frontera_todo['Config_RIO_Usada_Partida'] == 'Sin_Registro_RIO']
            print(f"  {len(frontera_todo):,} ciclos con Inicio_Ciclo anterior al mes actual.")
            print(f"  De esos, {len(sin_rio_frontera):,} SIGUEN sin instruccion RIO en la apertura "
                  f"(monto de referencia bajo metodo pre-v6: "
                  f"{sin_rio_frontera['Costo_Partida_Base_Original'].sum():,.0f} CLP).")
            if not sin_rio_frontera.empty:
                print("  Si RUTA_RIO_MES_PASADO esta activo y esto sigue > 0, el ciclo arranco")
                print("  mas de un mes atras, o el RIO del mes pasado tampoco tiene registro")
                print("  para ese instante. Revisar caso a caso:")
                print(sin_rio_frontera[['Etiqueta_Relacionada', 'Central_Relacionada', 'Inicio_Ciclo']]
                      .head(20).to_string(index=False))


    # ==========================================
    # 14.6 CASCADA FINANCIERA
    # ==========================================
    print("\n" + "=" * 78)
    print("  AUDITORIA FINANCIERA: IMPACTO DE FILTROS (CASCADA)")
    print("=" * 78)

    total_base = df_compacto['Costo_Partida_Base'].sum() + df_compacto['Costo_Detencion_Base'].sum()
    post_conf = ((df_compacto['Costo_Partida_Base'] * df_compacto['Filtro_Conf_Partida']).sum()
                 + (df_compacto['Costo_Detencion_Base'] * df_compacto['Filtro_Conf_Detencion']).sum())
    post_disp = ((df_compacto['Costo_Partida_Base'] * df_compacto['Filtro_Conf_Partida']
                  * df_compacto['Filtro_Disp_Partida']).sum()
                 + (df_compacto['Costo_Detencion_Base'] * df_compacto['Filtro_Conf_Detencion']
                    * df_compacto['Filtro_Disp_Detencion']).sum())
    post_op = df_compacto['Costos_Totales_PD'].sum()
    total_sc = df_compacto['Total SC_PD'].sum()

    df_auditoria_costos = pd.DataFrame({
        'Etapa_Financiera': [
            '1. Costo Base Potencial (Arranques + Paradas)',
            '   [-] Rechazo por Configuracion RIO distinta',
            '   [-] Rechazo por Estado de Pruebas (EP)',
            '   [-] Rechazo por Filtro Operacional (Sin Motivo / No SSCC)',
            '2. Costo Efectivo Validado a Recuperar',
            '   [-] Autocubierto por Margen de Venta (CMg > CV)',
            '3. PAGO FINAL DE SOBRECOSTO P-D'],
        'Monto (CLP)': [
            total_base, -(total_base - post_conf), -(post_conf - post_disp),
            -(post_disp - post_op), post_op, -(post_op - total_sc), total_sc]
    })
    for _, row in df_auditoria_costos.iterrows():
        print(f"  {row['Etapa_Financiera']:<60} : {row['Monto (CLP)']:>18,.0f} CLP")
        if row['Etapa_Financiera'][:2] in ('1.', '2.'):
            print("  " + "-" * 76)
    print("=" * 78)

    if total_base == 0:
        print("  [!] El costo base es CERO. Casi siempre significa que Llave_FHC no")
        print("      cruzo con Llave_Concatenada. Revisa el % de cruce de la seccion 5.")


    # ==========================================
    # 14.7 OBSERVACIONES POR CICLO
    # ==========================================
    # El diagnostico evalua primero los rechazos y solo despues la ausencia de
    # tarifa; al reves, un ciclo rechazado sin tarifa mostraba "Sin tarifa" y
    # ocultaba la causa real.
    df_compacto = marcar_sin_tarifa_rio(df_compacto, configuracion=None)

    df_compacto['Obs_Liquidacion_Final'] = np.select(
        [(df_compacto['Costos_Totales_PD'] > 0) & (df_compacto['Total SC_PD'] == 0),
         df_compacto['Costos_Totales_PD'] == 0,
         df_compacto['Total SC_PD'] > 0],
        ['Costo amortizado: Margen supero el costo P-D',
         'Costo nulo o anulado por filtros RIO/EP',
         'Sobrecosto validado a pago'], default='Sin Pago')

    columnas_finales = [
        'Etiqueta_Relacionada', 'Central_Relacionada', 'Empresa', 'Ciclo_Mes', 'Estado_Ciclo_Mes',
        'Inicio_Ciclo', 'Termino_Ciclo', 'Horas_Detenida_Ciclo',
        'Generacion_Suma_Ciclo', 'Margen_Suma_Ciclo',
        'Config_RIO_Rescatada_Ventana_Partida', 'Config_RIO_Rescatada_Ventana_Detencion',
        'Estado_Op_Partida', 'Consigna_Partida', 'Motivo_Partida', 'Costo_Partida_Efectivo', 'Obs_Partida',
        'Estado_Op_Detencion', 'Consigna_Detencion', 'Motivo_Detencion', 'Costo_Detencion_Efectivo', 'Obs_Detencion',
        'Costos_Totales_PD', 'Total SC_PD', 'Obs_Liquidacion_Final', 'Etiqueta_Original']
    if USAR_CONFIG_DOMINANTE == 1 and USAR_TARIFA_RIO_INSTRUIDA == 0:
        columnas_finales += ['Central_Partida', 'Central_Partida_Original',
                            'Central_Detencion', 'Central_Detencion_Original']
    if USAR_TARIFA_RIO_INSTRUIDA == 1:
        columnas_finales += ['Config_RIO_Usada_Partida', 'Config_RIO_Usada_Detencion',
                            'Costo_Partida_Base_Original', 'Costo_Detencion_Base_Original']
    df_compacto = df_compacto[columnas_finales]


    # ==========================================
    # 14.8 SOBRECOSTO POR EMPRESA
    # ==========================================
    df_empresa = df_compacto.groupby('Empresa', as_index=False).agg(
        Ciclos=('Etiqueta_Relacionada', 'count'),
        Centrales=('Central_Relacionada', 'nunique'),
        Generacion_MWh=('Generacion_Suma_Ciclo', 'sum'),
        Margen_CLP=('Margen_Suma_Ciclo', 'sum'),
        Costo_Partida_CLP=('Costo_Partida_Efectivo', 'sum'),
        Costo_Detencion_CLP=('Costo_Detencion_Efectivo', 'sum'),
        Costos_Totales_CLP=('Costos_Totales_PD', 'sum'),
        Total_SC_PD_CLP=('Total SC_PD', 'sum'),
    ).sort_values('Total_SC_PD_CLP', ascending=False)

    total_sc_emp = df_empresa['Total_SC_PD_CLP'].sum()
    if total_sc_emp:
        df_empresa['Participacion_%'] = (100 * df_empresa['Total_SC_PD_CLP'] / total_sc_emp).round(2)
    else:
        df_empresa['Participacion_%'] = 0.0

    print("\n" + "=" * 78)
    print("  SOBRECOSTO P-D POR EMPRESA")
    print("=" * 78)
    print(f"  {'Empresa':<32} {'Ciclos':>7} {'Gen (MWh)':>14} {'SC P-D (CLP)':>18} {'%':>7}")
    print("  " + "-" * 74)
    for _, f in df_empresa.iterrows():
        print(f"  {str(f['Empresa'])[:32]:<32} {f['Ciclos']:>7,} {f['Generacion_MWh']:>14,.0f} "
              f"{f['Total_SC_PD_CLP']:>18,.0f} {f['Participacion_%']:>6.1f}%")
    print("=" * 78)


    # ==========================================
    # 15. RECONCILIACION Y EXPORTACION
    # ==========================================
    detalle_mes = resumen_relacionada[resumen_relacionada['FECHA_HORA'] >= f_min_actual].copy()
    print_audit_summary()

    gen_csv_mes = reporte_actual['GENERACION'].sum()
    gen_detalle_mes = detalle_mes['GENERACION'].sum()
    print("\n" + "=" * 78)
    print("  RECONCILIACION (solo mes actual)")
    print(f"    CSV original          : {gen_csv_mes:>16,.2f} MWh")
    print(f"    Detalle en ciclos     : {gen_detalle_mes:>16,.2f} MWh "
          f"({100 * gen_detalle_mes / gen_csv_mes if gen_csv_mes else 0:.2f}%)")
    print(f"    Ciclos en el reporte  : {len(df_compacto):>16,}")
    print("  La diferencia corresponde a hidros/ERNC filtradas por Costo_Cero, centrales")
    print("  sin diccionario y bloques sin generacion. Revisa las auditorias de arriba.")
    print("=" * 78)

    print(f"\nExportando a: {RUTA_SALIDA} ...")
    with pd.ExcelWriter(RUTA_SALIDA, engine='xlsxwriter') as writer:
        hojas = {'Waterfall_Costos': df_auditoria_costos,
                 'SC_por_Empresa': df_empresa,
                 'Resumen_Ciclos_PD': df_compacto,
                 'Detalle_15Min': detalle_mes,
                 'Auditoria_Pasos': pd.DataFrame(_audit_log)}
        if AUDITAR_INSTRUCCION_RIO == 1:
            hojas['Cobertura_Instruccion_RIO'] = cobertura_export
        for nombre, df_h in hojas.items():
            df_h.to_excel(writer, sheet_name=nombre, index=False)
            ws = writer.sheets[nombre]
            for idx, col in enumerate(df_h.columns):
                largo_datos = df_h[col].map(lambda v: len(str(v))).max() if len(df_h) else 0
                ancho = max(int(largo_datos or 0), len(str(col))) + 2
                ws.set_column(idx, idx, min(ancho, 50))

    print("Listo. Proceso finalizado.")


if __name__ == "__main__":
    main({})
