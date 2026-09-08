"""Utilidades puras de integridad usadas por el motor y sus pruebas."""

import numpy as np
import pandas as pd


LLAVE_REPORTE = ['FECHA_HORA', 'UNIDAD GENERADORA', 'Central', 'CONFIGURACION']
LLAVE_RIO = ['FECHA_HORA_RIO', 'Central_Relacionada_RIO']


def empalmar_reportes(reporte_pasado, reporte_actual, audit_log=None):
    """Empalma reportes sin perder energia ante una colision de reloj.

    Los grupos completamente iguales son solapamientos reales. Cuando cambia
    GENERACION se conserva un bloque agregado: en particular, una hora DST
    repetida aporta la suma de ambos bloques fisicos.
    """
    audit_log = audit_log if audit_log is not None else []
    combinado = pd.concat([reporte_pasado, reporte_actual], ignore_index=True)
    repetidas = combinado.duplicated(LLAVE_REPORTE, keep=False)
    comparar = [c for c in ['GENERACION', 'CMg-CV', 'Dolar'] if c in combinado]
    sin_colision = combinado.loc[~repetidas]
    con_colision = combinado.loc[repetidas].copy()

    if con_colision.empty:
        reales = colisiones = con_colision
        resultado = sin_colision.copy()
    else:
        es_real = pd.Series(True, index=con_colision.index)
        agrupado = con_colision.groupby(LLAVE_REPORTE, sort=False, dropna=False)
        for columna in comparar:
            es_real &= agrupado[columna].transform('nunique', dropna=False).eq(1)

        reales = con_colision.loc[es_real]
        colisiones = con_colision.loc[~es_real].copy()
        reales_unicos = reales.drop_duplicates(LLAVE_REPORTE, keep='last')

        if colisiones.empty:
            colisiones_agregadas = colisiones
        else:
            colisiones['_GENERACION_NUMERICA'] = pd.to_numeric(
                colisiones['GENERACION'], errors='coerce')
            agregaciones = {c: 'last' for c in combinado.columns
                            if c not in LLAVE_REPORTE + ['GENERACION']}
            agregaciones['_GENERACION_NUMERICA'] = 'sum'
            colisiones_agregadas = (colisiones.groupby(
                LLAVE_REPORTE, as_index=False, sort=False, dropna=False)
                .agg(agregaciones)
                .rename(columns={'_GENERACION_NUMERICA': 'GENERACION'}))
            colisiones_agregadas = colisiones_agregadas[combinado.columns]

        resultado = pd.concat(
            [sin_colision, reales_unicos, colisiones_agregadas],
            ignore_index=True)[combinado.columns]

    def registrar(nombre, grupos):
        filas = len(grupos)
        mwh = pd.to_numeric(grupos['GENERACION'], errors='coerce').sum()
        audit_log.append({'paso': nombre, 'filas': filas, 'gen_MWh': round(mwh, 2),
                          'delta_gen': 0, 'pct_perdida': 0})

    registrar('1a. Duplicados reales del empalme', reales)
    registrar('1b. Colisiones distintas agregadas', colisiones)
    return resultado


def deduplicar_rio_priorizando_motivo(rio):
    """Conserva, para cada instante/central, una instruccion con MOTIVO."""
    df = rio.copy()
    df['_prio'] = df['MOTIVO'].notna().astype(int)
    return (df.sort_values(LLAVE_RIO + ['_prio'])
              .drop_duplicates(LLAVE_RIO, keep='last')
              .drop(columns='_prio').reset_index(drop=True))


def calcular_ciclos(df, grupo=('Central',), tolerancia_cortes=0,
                    nombre_columna_id=None):
    """Numera tramos positivos; con tolerancia cero todo micro-corte separa."""
    columnas_clave = [*grupo, 'FECHA_HORA']
    out = (df.groupby(columnas_clave, as_index=False)['GENERACION'].sum()
           .sort_values(columnas_clave).reset_index(drop=True))
    bruto = out['GENERACION'].fillna(0).gt(0)
    if tolerancia_cortes:
        generando = (bruto.replace(False, pd.NA).groupby([out[c] for c in grupo])
                     .ffill(limit=tolerancia_cortes).fillna(False).astype(bool))
    else:
        generando = bruto
    previo = generando.groupby([out[c] for c in grupo]).shift(fill_value=False).astype(bool)
    columna_id = nombre_columna_id or 'Ciclo_ID'
    out[columna_id] = (generando & ~previo).groupby(
        [out[c] for c in grupo]).cumsum()
    out.loc[~bruto, columna_id] = 0
    if nombre_columna_id:
        return out[columnas_clave + [columna_id]]
    activos = out[out[columna_id] > 0]
    ciclos = activos.groupby([*grupo, 'Ciclo_ID'], as_index=False).agg(
        Inicio_Ciclo=('FECHA_HORA', 'min'), Termino_Ciclo=('FECHA_HORA', 'max'))
    ciclos['Fin_Ciclo_Anterior'] = ciclos.groupby(list(grupo))['Termino_Ciclo'].shift()
    ciclos['Horas_Detenida_Ciclo'] = (
        (ciclos['Inicio_Ciclo'] - ciclos['Fin_Ciclo_Anterior']).dt.total_seconds() / 3600)
    return out, ciclos


def costos_clasicos(df):
    """Calcula costos efectivos con los tres filtros historicos."""
    out = df.copy()
    for tipo in ['Partida', 'Detencion']:
        out[f'Costo_{tipo}_Efectivo'] = (out[f'Costo_{tipo}_Base']
            * out[f'Filtro_Conf_{tipo}'] * out[f'Filtro_Disp_{tipo}']
            * out[f'Filtro_Op_{tipo}'])
    return out


def marcar_sin_tarifa_rio(df, configuracion='Configuracion RIO'):
    """Marca instrucciones inexistentes para revision manual, sin cobro."""
    out = df.copy()
    if configuracion in out:
        out['Config_RIO_Sin_Tarifa'] = out[configuracion].eq('Sin_Registro_RIO')
        out['Costo_Partida_Efectivo'] = np.where(out['Config_RIO_Sin_Tarifa'], 0,
                                                 out.get('Costo_Partida_Efectivo', 0))
        out['Obs_Partida'] = np.where(out['Config_RIO_Sin_Tarifa'],
                                      'Revisar manualmente: config RIO sin tarifa', '')
        return out

    for tipo in ['Partida', 'Detencion']:
        out[f'Obs_{tipo}'] = np.select(
            [out[f'Config_RIO_Sin_Tarifa_{tipo}'],
             out[f'Filtro_Conf_{tipo}'] == 0,
             out[f'Filtro_Disp_{tipo}'] == 0,
             out[f'Filtro_Op_{tipo}'] == 0,
             out[f'Costo_{tipo}_Base'] == 0],
            ['Revisar manualmente: config RIO sin tarifa',
             'Rechazo: Configuracion RIO distinta',
             'Rechazo: Maquina en Pruebas (EP)',
             'Rechazo: Sin Motivo ni SSCC en RIO',
             f'Sin tarifa de {tipo.lower()}'], default='Aprobado')
    return out
