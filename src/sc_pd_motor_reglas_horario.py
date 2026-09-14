# -*- coding: utf-8 -*-
"""
MOTOR SC P-D "REGLAS DEL HORARIO" - tercer modelo, independiente del v7 y del turbina.

Aplica sobre el reporte de 15 minutos las reglas del modelo horario tal como se
leyeron en sus formulas y macros (docs/informes/Reglas_Modelo_Horario.md). No
pretende ser mejor: pretende ser FIEL. Sirve para dos cosas:

  - contra el Excel horario aisla el efecto puro de la RESOLUCION (misma regla,
    distinto dato);
  - contra el v7 sobre el mismo reporte aisla el efecto puro de la REGLA (mismo
    dato, distinta regla).

Cada paso cita la regla del documento (R0.a, R4, R5...). Donde el Excel usa un
insumo que el proyecto no tiene (hoja Pruebas, Ciclos inconclusos), se dice que
se sustituye y por que.

Diferencias deliberadas respecto del v7, todas por fidelidad al Excel:
  - NO empalma el mes anterior (R0.b): las horas detenidas del primer ciclo son
    un piso desde el primer bloque de la central en los datos.
  - NO exime por 'sin_historia': el primer ciclo se cobra con ese piso, y si no
    tiene instruccion RIO se cobra igual (R6, excepcion &1).
  - Tramo con bordes INCLUSIVOS y SIN Tibia 2 (R4).
  - Partida y detencion del ciclo = MAXIMO entre las configuraciones presentes
    (R5): la mezcla de configuraciones hermanas, reproducida a proposito.
  - Filtro de configuracion instruida SOLO por combustible (R8).
  - Filtro operacional: OM, o PDO, o (OT y SSCC), o (&1 sin instruccion) (R6).
  - Frontera: se traspasa si es el ultimo ciclo y la central genera en el ultimo
    bloque del mes (R11). Sin hoja 'Ciclos inconclusos' de entrada.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fase1_integridad import (calcular_ciclos, deduplicar_rio_priorizando_motivo,  # noqa: E402
                              filtro_costo_cero)
from sc_pd_motor_v7 import (asignar_empresas, calcular_margen_bloques,  # noqa: E402
                            leer_reporte)

# ==========================================
# 0. PANEL
# ==========================================
RUTA_REPORTE_15MIN       = r"Reporte_PD_15min_2606.csv"
RUTA_RIO                 = r"RIO_06_2026.xlsx"
RUTA_COSTOS_PD           = r"Costos_de_P-D_Consolidado.xlsx"
RUTA_DICCIONARIO         = r"Diccionario_central_config.xlsx"
RUTA_DICCIONARIO_EMPRESA = r"Diccionario_central_empresa.xlsx"
RUTA_SALIDA              = r"Reporte_Sobrecostos_PD_ReglasHorario.xlsx"
# Se aceptan por compatibilidad con los runners, pero se IGNORAN (R0.b).
RUTA_REPORTE_MES_PASADO = RUTA_RIO_MES_PASADO = RUTA_COSTOS_MES_PASADO = ""

CALCULAR_MARGEN_EN_EL_MOTOR = 1     # R9: (CMg - CV) x Dolar, truncado por bloque
TOLERANCIA_RIO_HORAS        = 24    # busqueda hacia atras del registro RIO, igual que el v7
CODIGOS_SSCC                = ('SSCC', 'CTF', 'CSF', 'CPF')   # R6/R8: Instrucciones RIO!S

PATRONES_PO = [(r'^(\d{8})-(\d{1,2})', '%Y%m%d'), (r'^(\d{6})-(\d{1,2})', '%y%m%d')]
MAPA_RIO = {'CON': 'CONSIGNAS', 'MOT': 'MOTIVO', 'EO': 'ESTADO OPERACIONAL',
            'NOMBRE CONFIGURACION': 'NOMBRE CONFIGURACIÓN'}
REQ_RIO = ['CONSIGNAS', 'MOTIVO', 'ESTADO OPERACIONAL', 'NOMBRE CONFIGURACIÓN',
           'COMENTARIO', 'FECHA', 'HORA']


# ==========================================
# REGLAS COMO FUNCIONES (testeables)
# ==========================================
def marcar_partidas_detenciones(df, grupo):
    """R0.a: partida = gen != 0 y bloque anterior del mismo grupo == 0;
    detencion = gen != 0 y bloque siguiente == 0. Sin tolerancia. La primera fila
    del grupo nunca es partida (la macro compara con una fila anterior que no existe).
    Usa != 0, no > 0, como la macro."""
    d = df.sort_values([grupo, 'FECHA_HORA']).copy()
    gen = pd.to_numeric(d['GENERACION'], errors='coerce').fillna(0)
    mismo_ant = d[grupo].eq(d[grupo].shift(1))
    mismo_sig = d[grupo].eq(d[grupo].shift(-1))
    gen_ant = gen.shift(1).fillna(0)
    gen_sig = gen.shift(-1).fillna(0)
    d['Partida_Flag'] = (gen.ne(0) & gen_ant.eq(0) & mismo_ant).astype(int)
    d['Detencion_Flag'] = (gen.ne(0) & gen_sig.eq(0) & mismo_sig).astype(int)
    return d


def horas_detenidas_con_piso(ciclos):
    """R0.b: horas desde la detencion anterior de la MISMA relacionada; si no la
    hay, desde el primer bloque de esa relacionada en los datos (piso al inicio
    del mes). Nunca nulo."""
    c = ciclos.sort_values(['Central_Relacionada', 'Inicio_Ciclo']).copy()
    fin_ant = c.groupby('Central_Relacionada')['Termino_Ciclo'].shift(1)
    ref = fin_ant.fillna(c['Primer_Bloque_Central'])
    c['Horas_Detenida_Ciclo'] = (c['Inicio_Ciclo'] - ref).dt.total_seconds() / 3600.0
    c['Historia'] = np.where(fin_ant.notna(), 'detencion anterior', 'piso inicio mes')
    return c


def tramo_horario(horas, umbral_fria, umbral_cal):
    """R4: caliente si h <= cal; fria si h >= fria; tibia en otro caso. Bordes
    inclusivos. Si umbral fria == 0 -> siempre fria. Sin Tibia 2."""
    h = pd.to_numeric(horas, errors='coerce').fillna(0)
    uf = pd.to_numeric(umbral_fria, errors='coerce').fillna(0)
    uc = pd.to_numeric(umbral_cal, errors='coerce').fillna(0)
    return np.where(uf.eq(0), 'fria',
                    np.where(h.le(uc), 'caliente', np.where(h.ge(uf), 'fria', 'tibia')))


def sufijo_combustible(config):
    """R8: lo que sigue a '_GN' o '_DIESEL' (p. ej. 'GNL_B', 'DIESEL'); '' si no hay."""
    s = str(config)
    for marca in ('_GN', '_DIESEL'):
        pos = s.find(marca)
        if pos >= 0:
            return s[pos + 1:]
    return ''


def factor_operacional(motivo, eo, presta_sscc, es_primer_ciclo):
    """R6: paga si OM, o PDO, o (OT y SSCC), o (primer ciclo del mes sin instruccion)."""
    motivo = '' if pd.isna(motivo) else str(motivo).strip()
    eo = '' if pd.isna(eo) else str(eo).strip()
    if motivo == 'OM' or eo == 'PDO' or (motivo == 'OT' and presta_sscc):
        return 1
    if es_primer_ciclo and motivo == '':
        return 1
    return 0


# ==========================================
# MAIN
# ==========================================
def main(rutas: dict, panel: dict | None = None):
    globals().update(rutas or {})
    globals().update(panel or {})

    print("\n" + "=" * 78)
    print("  MOTOR 'REGLAS DEL HORARIO' SOBRE DATO DE 15 MINUTOS")
    print("=" * 78)
    if any((RUTA_REPORTE_MES_PASADO, RUTA_RIO_MES_PASADO, RUTA_COSTOS_MES_PASADO)):
        print("  [R0.b] Rutas de mes anterior recibidas y DELIBERADAMENTE ignoradas:")
        print("         el horario no empalma el mes anterior en ningun nivel.")

    # ---- 1. Reporte del mes (sin empalme) ----
    rep = leer_reporte(RUTA_REPORTE_15MIN, "Mes actual")
    rep['GENERACION'] = pd.to_numeric(rep['GENERACION'], errors='coerce').fillna(0)
    f_ini, f_fin = rep['FECHA_HORA'].min(), rep['FECHA_HORA'].max()
    print(f"  Reporte: {len(rep):,} filas, {rep['GENERACION'].sum():,.2f} MWh, {f_ini} -> {f_fin}")
    tiene_gen = rep.groupby(['UNIDAD GENERADORA', 'Central', 'CONFIGURACION'])['GENERACION'] \
                   .transform(lambda s: (s != 0).any())
    rep = rep[tiene_gen.astype(bool)].copy()

    # ---- 2. Margen por bloque (R9) ----
    rep['Margen'] = calcular_margen_bloques(rep, CALCULAR_MARGEN_EN_EL_MOTOR, 0)

    # ---- 3. Politicas y tarifas (R2) ----
    ext = pd.read_excel(RUTA_COSTOS_PD, sheet_name=0)
    ext['UNIDAD'] = ext['UNIDAD'].astype(str).str.strip()
    ext['Llave_Concatenada'] = ext['Llave_Concatenada'].astype(str).str.strip()
    cols_c = ['Llave_Concatenada', 'UNIDAD', 'Partida_Fria', 'Partida_Tibia', 'Partida_Caliente',
              'Detencion', 'Costo_Cero', 'Fria_Num1_M', 'Caliente_Num1_P']
    costos = ext[cols_c].drop_duplicates('Llave_Concatenada', keep='last')
    for c in ('Partida_Fria', 'Partida_Tibia', 'Partida_Caliente', 'Detencion',
              'Fria_Num1_M', 'Caliente_Num1_P'):
        costos[c] = pd.to_numeric(costos[c], errors='coerce').fillna(0)

    llaves = costos['Llave_Concatenada']
    extr, fmt = None, None
    for patron, f in PATRONES_PO:
        p = llaves.str.extract(patron)
        if p[0].notna().sum() > 0:
            extr, fmt = p, f
            break
    if extr is None:
        sys.exit("ERROR: no se reconoce Llave_Concatenada")
    pol = extr.dropna().drop_duplicates().rename(columns={0: 'FECHA_TXT', 1: 'Hora'})
    h24 = pol['Hora'].astype(str).eq('24')
    pol['Fecha_PO'] = pd.to_datetime(pol['FECHA_TXT'] + ' ' + pol['Hora'].astype(str).where(~h24, '0') + ':00',
                                     format=fmt + ' %H:%M', errors='coerce')
    pol.loc[h24, 'Fecha_PO'] += pd.Timedelta(days=1)
    pol['Llave_PO_Base'] = pol['FECHA_TXT'] + '-' + pol['Hora'].astype(str)
    pol = pol[['Fecha_PO', 'Llave_PO_Base']].dropna().sort_values('Fecha_PO')
    print(f"  Politicas PO: {len(pol):,} ({pol['Fecha_PO'].min()} -> {pol['Fecha_PO'].max()})")

    rep = rep.sort_values('FECHA_HORA').reset_index(drop=True)
    rep = pd.merge_asof(rep, pol, left_on='FECHA_HORA', right_on='Fecha_PO', direction='backward')
    rep['Llave_FHC'] = rep['Llave_PO_Base'].fillna('SinFecha-1') + rep['Central'].astype(str).str.strip()
    rep = rep.merge(costos, left_on='Llave_FHC', right_on='Llave_Concatenada', how='left')
    print(f"  Cruce de tarifas: {100*rep['Llave_Concatenada'].notna().mean():.1f}% de los bloques.")

    # ---- 4. Costo cero y COGEN ----
    # El Excel no tiene la exclusion de COGEN en sus formulas, pero su salida
    # tiene CERO ciclos para SANTAFE_BL1_COGEN y ESCUADRON_COGEN: las excluye
    # aguas arriba, al decidir que filas entran a 'Sobrecosto_PD xHyC'. Ser fiel
    # al Excel es reproducir su resultado, no solo sus formulas: se aplica la
    # misma regla que el v7 (filtro_costo_cero cubre Costo_Cero == SI y COGEN).
    rep['Filtro_CostoCero'] = filtro_costo_cero(rep['Costo_Cero'].fillna('NO'), rep['Central'])
    unidades_con_costo = set(costos.loc[costos['Costo_Cero'].astype(str).str.upper().ne('SI'), 'UNIDAD'])
    rep = rep[rep['Central'].astype(str).str.strip().isin(unidades_con_costo)
              & rep['Filtro_CostoCero'].eq(1)].copy()
    print(f"  Tras Costo_Cero y COGEN: {len(rep):,} bloques, {rep['GENERACION'].sum():,.2f} MWh")

    # ---- 5. Relacionada (R1) ----
    dic = pd.read_excel(RUTA_DICCIONARIO, sheet_name=0)
    k, v = dic.columns[0], dic.columns[1]
    mapa = dict(zip(dic[k].astype(str).str.strip(), dic[v].astype(str).str.strip()))
    rep['Central'] = rep['Central'].astype(str).str.strip()
    rep['Central_Relacionada'] = rep['Central'].map(mapa).fillna(rep['Central'])

    # ---- 6. RIO ----
    rio = pd.read_excel(RUTA_RIO, skiprows=4)
    rio.columns = [str(c).strip().upper() for c in rio.columns]
    rio = rio.rename(columns={a: b for a, b in MAPA_RIO.items() if a in rio.columns})
    rio = rio.loc[:, ~rio.columns.duplicated()]
    faltan = [c for c in REQ_RIO if c not in rio.columns]
    if faltan:
        sys.exit(f"ERROR: faltan columnas en el RIO: {faltan}")
    rio['FECHA'] = pd.to_datetime(rio['FECHA'], errors='coerce')
    hs = rio['HORA'].astype(str).str.strip()
    rio['FECHA_HORA_RIO'] = pd.to_datetime(rio['FECHA'].dt.strftime('%Y-%m-%d') + ' '
                                           + hs.str.replace('24:00', '00:00', regex=False), errors='coerce')
    rio.loc[hs.str.startswith('24:00'), 'FECHA_HORA_RIO'] += pd.Timedelta(days=1)
    rio['NOMBRE CONFIGURACIÓN'] = rio['NOMBRE CONFIGURACIÓN'].astype(str).str.strip()
    rio['Central_Relacionada_RIO'] = rio['NOMBRE CONFIGURACIÓN'].map(mapa).fillna(rio['NOMBRE CONFIGURACIÓN'])
    for c in ('CONSIGNAS', 'MOTIVO', 'ESTADO OPERACIONAL'):
        rio[c] = rio[c].astype(str).str.strip().replace({'nan': np.nan, '-': np.nan, '': np.nan})
    rio['COMENTARIO'] = rio['COMENTARIO'].astype(str).replace({'nan': ''})
    rio = rio.dropna(subset=['FECHA_HORA_RIO']).sort_values('FECHA_HORA_RIO')
    rio_sub = deduplicar_rio_priorizando_motivo(
        rio[['FECHA_HORA_RIO', 'Central_Relacionada_RIO', 'CONSIGNAS', 'MOTIVO',
             'ESTADO OPERACIONAL', 'NOMBRE CONFIGURACIÓN', 'COMENTARIO']]).sort_values('FECHA_HORA_RIO')
    print(f"  RIO: {len(rio_sub):,} registros")

    # Registro RIO vigente por bloque (hacia atras, misma relacionada)
    rep = rep.sort_values('FECHA_HORA').reset_index(drop=True)
    rep = pd.merge_asof(rep, rio_sub, left_on='FECHA_HORA', right_on='FECHA_HORA_RIO',
                        left_by='Central_Relacionada', right_by='Central_Relacionada_RIO',
                        direction='backward', tolerance=pd.Timedelta(hours=TOLERANCIA_RIO_HORAS))

    # ---- 7. Flags de partida/detencion por CONFIGURACION (R0.a) ----
    rep = marcar_partidas_detenciones(rep, 'Central')

    # ---- 8. Ciclos por RELACIONADA (R0.c) y horas detenidas con piso (R0.b) ----
    ciclos_rel = calcular_ciclos(rep, grupo=['Central_Relacionada'], tolerancia_cortes=0,
                                 nombre_columna_id='Ciclo_ID')
    rep = rep.merge(ciclos_rel, on=['Central_Relacionada', 'FECHA_HORA'], how='left')
    activos = rep[rep['Ciclo_ID'] > 0].copy()
    ciclos = (activos.groupby(['Central_Relacionada', 'Ciclo_ID'], as_index=False)
              .agg(Inicio_Ciclo=('FECHA_HORA', 'min'), Termino_Ciclo=('FECHA_HORA', 'max'),
                   Generacion_Suma_Ciclo=('GENERACION', 'sum'), Margen_Suma_Ciclo=('Margen', 'sum')))
    primer = rep.groupby('Central_Relacionada')['FECHA_HORA'].min().rename('Primer_Bloque_Central')
    ciclos = ciclos.merge(primer, left_on='Central_Relacionada', right_index=True)
    ciclos = horas_detenidas_con_piso(ciclos)
    ciclos['Etiqueta'] = ciclos['Central_Relacionada'] + '&' + ciclos['Ciclo_ID'].astype(int).astype(str)
    print(f"  Ciclos: {len(ciclos):,} en {ciclos['Central_Relacionada'].nunique()} relacionadas "
          f"({int(ciclos['Historia'].eq('piso inicio mes').sum())} con piso al inicio del mes)")

    # ---- 9. Costo horario por bloque-configuracion (R4, R5, R7) ----
    activos = activos.merge(ciclos[['Central_Relacionada', 'Ciclo_ID', 'Horas_Detenida_Ciclo']],
                            on=['Central_Relacionada', 'Ciclo_ID'], how='left')
    activos['Tipo_Partida'] = tramo_horario(activos['Horas_Detenida_Ciclo'],
                                            activos['Fria_Num1_M'], activos['Caliente_Num1_P'])
    tarifa_partida = np.select(
        [activos['Tipo_Partida'].eq('fria'), activos['Tipo_Partida'].eq('caliente')],
        [activos['Partida_Fria'], activos['Partida_Caliente']], activos['Partida_Tibia'])
    dolar = pd.to_numeric(activos['Dolar'], errors='coerce').fillna(0)
    activos['Filtro_EP'] = np.where(activos['ESTADO OPERACIONAL'].astype(str).str.strip().eq('EP'), 0, 1)
    # R5 + condicion H>0: hay partida solo si horas detenidas > 0
    hay_partida = activos['Partida_Flag'].eq(1) & activos['Horas_Detenida_Ciclo'].gt(0)
    activos['Costo_Partida_Bloque'] = np.where(hay_partida, tarifa_partida * dolar * activos['Filtro_EP'], 0.0)
    activos['Costo_Detencion_Bloque'] = np.where(activos['Detencion_Flag'].eq(1),
                                                 activos['Detencion'] * dolar * activos['Filtro_EP'], 0.0)

    # ---- 10. Filtro combustible por ciclo (R8) ----
    pp = rio_sub[rio_sub['CONSIGNAS'].isin(['PP', 'PMT'])][
        ['FECHA_HORA_RIO', 'Central_Relacionada_RIO', 'NOMBRE CONFIGURACIÓN']].copy()
    pp['Comb_Instruido'] = pp['NOMBRE CONFIGURACIÓN'].map(sufijo_combustible)
    comb = {}
    for _, c in ciclos.iterrows():
        m = pp[(pp['Central_Relacionada_RIO'] == c['Central_Relacionada'])
               & (pp['FECHA_HORA_RIO'] >= c['Inicio_Ciclo'] - pd.Timedelta(hours=1))
               & (pp['FECHA_HORA_RIO'] <= c['Termino_Ciclo'])]
        comb[(c['Central_Relacionada'], c['Ciclo_ID'])] = m['Comb_Instruido'].iloc[0] if not m.empty else ''
    activos['Comb_Instruido'] = [comb.get((r, i), '') for r, i in
                                 zip(activos['Central_Relacionada'], activos['Ciclo_ID'])]
    activos['Comb_Propio'] = activos['Central'].map(sufijo_combustible)
    activos['Filtro_Comb'] = np.where(activos['Comb_Instruido'].eq(''), 1,
                                      np.where(activos['Comb_Propio'].eq(activos['Comb_Instruido']), 1, 0))
    activos['Costo_Partida_Bloque'] *= activos['Filtro_Comb']
    activos['Costo_Detencion_Bloque'] *= activos['Filtro_Comb']

    # ---- 11. MAXIMO por ciclo (R5) ----
    mx = (activos.groupby(['Central_Relacionada', 'Ciclo_ID'])
          .agg(Costo_Partida_Max=('Costo_Partida_Bloque', 'max'),
               Costo_Detencion_Max=('Costo_Detencion_Bloque', 'max'),
               Configs_En_Ciclo=('Central', 'nunique'),
               Config_Partida_Max=('Central', lambda s: s.iloc[
                   activos.loc[s.index, 'Costo_Partida_Bloque'].values.argmax()] if len(s) else ''),
               Tipo_Partida=('Tipo_Partida', 'first'))
          .reset_index())
    ciclos = ciclos.merge(mx, on=['Central_Relacionada', 'Ciclo_ID'], how='left')

    # ---- 12. Filtro operacional por ciclo (R6) ----
    ini = activos.sort_values('FECHA_HORA').groupby(['Central_Relacionada', 'Ciclo_ID']).first()
    ciclos = ciclos.merge(ini[['MOTIVO', 'ESTADO OPERACIONAL']].reset_index(),
                          on=['Central_Relacionada', 'Ciclo_ID'], how='left')
    sscc = {}
    for _, c in ciclos.iterrows():
        m = rio_sub[(rio_sub['Central_Relacionada_RIO'] == c['Central_Relacionada'])
                    & (rio_sub['FECHA_HORA_RIO'] >= c['Inicio_Ciclo'])
                    & (rio_sub['FECHA_HORA_RIO'] <= c['Termino_Ciclo'])]
        sscc[(c['Central_Relacionada'], c['Ciclo_ID'])] = bool(
            m['COMENTARIO'].astype(str).str.upper().str.contains('|'.join(CODIGOS_SSCC)).any())
    ciclos['Presta_SSCC'] = [sscc.get((r, i), False) for r, i in
                             zip(ciclos['Central_Relacionada'], ciclos['Ciclo_ID'])]
    ciclos['Factor_Operacional'] = [
        factor_operacional(m, e, s, i == 1) for m, e, s, i in
        zip(ciclos['MOTIVO'], ciclos['ESTADO OPERACIONAL'], ciclos['Presta_SSCC'], ciclos['Ciclo_ID'])]
    ciclos['Costo_Partida'] = ciclos['Costo_Partida_Max'].fillna(0) * ciclos['Factor_Operacional']
    ciclos['Costo_Detencion'] = ciclos['Costo_Detencion_Max'].fillna(0) * ciclos['Factor_Operacional']

    # ---- 13. Frontera (R11) ----
    ultimo = ciclos.groupby('Central_Relacionada')['Ciclo_ID'].transform('max').eq(ciclos['Ciclo_ID'])
    gen_fin = rep[rep['FECHA_HORA'] == f_fin].groupby('Central_Relacionada')['GENERACION'].sum()
    genera_al_cierre = ciclos['Central_Relacionada'].map(gen_fin).fillna(0).ne(0)
    ciclos['Se_Traspasa'] = ultimo & genera_al_cierre

    # ---- 14. Liquidacion (R10) y empresa (R12) ----
    ciclos['Costos_Totales_PD'] = ciclos['Costo_Partida'] + ciclos['Costo_Detencion']
    ciclos['Total SC_PD'] = np.maximum(0, ciclos['Costos_Totales_PD'] - ciclos['Margen_Suma_Ciclo'])
    emp = {}
    if RUTA_DICCIONARIO_EMPRESA and os.path.exists(RUTA_DICCIONARIO_EMPRESA):
        de = pd.read_excel(RUTA_DICCIONARIO_EMPRESA, sheet_name=0)
        emp = dict(zip(de.iloc[:, 0].astype(str).str.strip(), de.iloc[:, 1].astype(str).str.strip()))
    ciclos['Central'] = ciclos['Config_Partida_Max'].fillna('')
    ciclos = asignar_empresas(ciclos, emp)
    ciclos['Empresa'] = ciclos['Empresa'].fillna(ciclos['Central_Relacionada'].map(emp))

    liquidados = ciclos[~ciclos['Se_Traspasa']]
    traspasados = ciclos[ciclos['Se_Traspasa']]

    print("\n" + "=" * 78)
    print("  RESULTADO (reglas del horario sobre 15 min)")
    print("=" * 78)
    print(f"  Ciclos liquidados      : {len(liquidados):,}   traspasados: {len(traspasados):,}")
    print(f"  Costo partida          : {liquidados['Costo_Partida'].sum():>16,.0f} CLP")
    print(f"  Costo detencion        : {liquidados['Costo_Detencion'].sum():>16,.0f} CLP")
    print(f"  Margen                 : {liquidados['Margen_Suma_Ciclo'].sum():>16,.0f} CLP")
    print(f"  PAGO FINAL SC P-D      : {liquidados['Total SC_PD'].sum():>16,.0f} CLP")
    print(f"  Ciclos con >1 configuracion (mezcla activa): "
          f"{int(liquidados['Configs_En_Ciclo'].gt(1).sum()):,}")

    por_emp = (liquidados.groupby('Empresa', dropna=False)
               .agg(Ciclos=('Total SC_PD', 'size'), Costo_Partida_CLP=('Costo_Partida', 'sum'),
                    Costo_Detencion_CLP=('Costo_Detencion', 'sum'), Margen_CLP=('Margen_Suma_Ciclo', 'sum'),
                    Total_SC_PD_CLP=('Total SC_PD', 'sum'))
               .reset_index().sort_values('Total_SC_PD_CLP', ascending=False))

    cols = ['Etiqueta', 'Central_Relacionada', 'Empresa', 'Ciclo_ID', 'Inicio_Ciclo', 'Termino_Ciclo',
            'Horas_Detenida_Ciclo', 'Historia', 'Tipo_Partida', 'Configs_En_Ciclo', 'Config_Partida_Max',
            'MOTIVO', 'ESTADO OPERACIONAL', 'Presta_SSCC', 'Factor_Operacional',
            'Costo_Partida', 'Costo_Detencion', 'Generacion_Suma_Ciclo', 'Margen_Suma_Ciclo',
            'Costos_Totales_PD', 'Total SC_PD', 'Se_Traspasa']
    print(f"\nExportando a: {RUTA_SALIDA} ...")
    with pd.ExcelWriter(RUTA_SALIDA, engine='xlsxwriter') as w:
        por_emp.to_excel(w, sheet_name='SC_por_Empresa', index=False)
        liquidados[cols].to_excel(w, sheet_name='Resumen_Ciclos_PD', index=False)
        traspasados[cols].to_excel(w, sheet_name='Traspasados', index=False)
        activos[['Central_Relacionada', 'Ciclo_ID', 'Central', 'FECHA_HORA', 'GENERACION', 'Margen',
                 'Partida_Flag', 'Detencion_Flag', 'Tipo_Partida', 'Filtro_EP', 'Filtro_Comb',
                 'Costo_Partida_Bloque', 'Costo_Detencion_Bloque']].to_excel(
            w, sheet_name='Detalle_15Min', index=False)
    print("Listo.")
    return liquidados, traspasados, por_emp


if __name__ == '__main__':
    main({})
