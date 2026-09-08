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
    reales = []
    colisiones = []
    salida = []
    for _, grupo in combinado.groupby(LLAVE_REPORTE, sort=False, dropna=False):
        if len(grupo) == 1:
            salida.append(grupo.iloc[-1].copy())
        elif all(grupo[c].nunique(dropna=False) == 1 for c in comparar):
            reales.append(grupo)
            salida.append(grupo.iloc[-1].copy())
        else:
            colisiones.append(grupo)
            fila = grupo.iloc[-1].copy()
            fila['GENERACION'] = pd.to_numeric(grupo['GENERACION'], errors='coerce').sum()
            salida.append(fila)
    resultado = pd.DataFrame(salida, columns=combinado.columns).reset_index(drop=True)

    def registrar(nombre, grupos):
        filas = sum(len(g) for g in grupos)
        mwh = sum(pd.to_numeric(g['GENERACION'], errors='coerce').sum() for g in grupos)
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


def calcular_ciclos(df, grupo=('Central',), tolerancia_cortes=0):
    """Numera tramos positivos; con tolerancia cero todo micro-corte separa."""
    out = df.sort_values([*grupo, 'FECHA_HORA']).copy()
    bruto = out['GENERACION'].fillna(0).gt(0)
    if tolerancia_cortes:
        generando = (bruto.replace(False, pd.NA).groupby([out[c] for c in grupo])
                     .ffill(limit=tolerancia_cortes).fillna(False).astype(bool))
    else:
        generando = bruto
    previo = generando.groupby([out[c] for c in grupo]).shift(fill_value=False).astype(bool)
    out['Ciclo_ID'] = (generando & ~previo).groupby([out[c] for c in grupo]).cumsum()
    out.loc[~bruto, 'Ciclo_ID'] = 0
    activos = out[out['Ciclo_ID'] > 0]
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
    out['Config_RIO_Sin_Tarifa'] = out[configuracion].eq('Sin_Registro_RIO')
    out['Costo_Partida_Efectivo'] = np.where(out['Config_RIO_Sin_Tarifa'], 0,
                                             out.get('Costo_Partida_Efectivo', 0))
    out['Obs_Partida'] = np.where(out['Config_RIO_Sin_Tarifa'],
                                  'Revisar manualmente: config RIO sin tarifa', '')
    return out
