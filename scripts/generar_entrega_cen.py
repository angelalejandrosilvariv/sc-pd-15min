#!/usr/bin/env python3
"""Construye la entrega CEN con la disposicion del Excel horario (spec 32).

Lee la salida oficial del motor v7 (``Reporte_Sobrecostos_PD_Final.xlsx``) y escribe
``Entrega_SCPD_<AAMM>/`` con un libro cuyas hojas, encabezados y letras de columna son
las del ``Sobrecostos_PD_AAMM.xlsm`` del Coordinador, a resolucion de 15 minutos, mas
un CSV de valores por hoja. Las formulas entre hojas siguen la misma cadena del Excel
horario (``xHyC -> PARTIDAS_DETENCIONES -> Sobrecosto_Ciclo -> RESUMEN``); las columnas
que el Excel no tiene van a la derecha de la ultima suya.

Uso:  python scripts/generar_entrega_cen.py Reporte_Sobrecostos_PD_Final.xlsx
             [--salida CARPETA] [--entrada ARCHIVO ...] [--version Preliminar|Definitivo]
             [--retiros Retiros_15min.parquet]   # prorratea: llena RESUMEN!PAGA
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from xlsxwriter.utility import xl_col_to_name

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))
import sc_pd_motor_v7 as motor  # noqa: E402
from prorrateo_15min import (  # noqa: E402
    leer_retiros, prorratear_ciclos_motor, resumir_por_ciclo_suministrador)

SHEETS = ["Menu", "Leeme", "Costos_de_P-D", "Pruebas", "Instrucciones RIO",
          "Central_Empresa", "Sobrecosto_PD xHyC", "PARTIDAS_DETENCIONES",
          "Sobrecosto_Ciclo", "RESUMEN", "Ciclos inconclusos",
          "xHyC mes anterior", "Diccionario"]

# Encabezados en el orden exacto del Excel horario; lo que sigue a la ultima columna
# del Excel (marcada con el comentario) es propio del motor.
XHYC = ["Id", "fecha", "hora", "central", "generacion", "Remunerar", "Proceso_Partida",
        "horas_detenida", "proceso_detencion", "Ciclo de operación", "check01-PD", "con_costo_PD",
        "Costo_cero_PD", "Partida", "Detencion", "part_fria", "part_tibia_i", "part_tibia_f",
        "part_cal", "tipo_partida", "COSTO_PARTIDA [$]", "COSTO_DETENCION [$]", "CV", "CMg",
        "Diferencia Cmg-CV", "USD", "Generación_neta", "Margen", "Clave Ciclo", "Programación",
        "Disponible (1) / Pruebas (0)", "Combustible Partida", "Conf despachada RIO",
        "Politica vigente", "Empresa",  # <- AI, ultima del Excel
        "cuarto", "USD apertura ciclo", "USD cierre ciclo",
        "Filtro Costo_Cero partida", "Filtro Costo_Cero detención", "Conf despachada RIO detención",
        "Combustible Detención", "Tarifa partida USD", "Tarifa detención USD", "Central relacionada",
        "Clave relacionada", "FECHA_HORA", "Instrucción", "Operación", "Consigna", "Configuración RIO",
        "Comentario RIO", "Fuente RIO", "Vigencia RIO", "Filtro operacional", "Margen motor", "Check margen",
        "Unidades"]
PD = ["fecha", "hora", "central", "generacion", "Remunerar", "Proceso_Partida", "horas_detenida",
      "proceso_detencion", "Ciclo", "con_costo_PD", "Costo_cero_PD", "Costo PD", "Central relacionada",
      "Clave Ciclo", "Ciclo + fecha + hora", "Instrucción", "Operación", "Programación", "Monto Partidas",
      "Monto Detenciones", "Vacio", "N° Partidas", "Monto Partidas ciclo", "N° Detenciones",
      "Monto Detenciones ciclo", "Presta SSCC", "Bloque mes", "RIO PP", "RIO PS", "Revisar",  # <- AD
      "Exención sin historia", "Vigencia RIO", "Disponible (1) / Pruebas (0)", "Conf despachada RIO",
      "Filtro operacional motor", "Consigna", "cuarto", "FECHA_HORA", "Fuente RIO",
      "Antigüedad instrucción (min)", "Estado ciclo mes", "Empresa",
      # filtros de la detencion, para que T no dependa de los de la partida en un ciclo de un bloque
      "Instrucción detención", "Operación detención", "Consigna detención", "Presta SSCC detención",
      "Vigencia RIO detención", "Disponible (1) / Pruebas (0) detención", "Conf despachada RIO detención",
      "Filtro operacional motor detención", "Fuente RIO detención"]
COSTOS = ["id", "dia", "tipo", "Unidad", "Costo Partida fría", "Costo Partida tibia",
          "Costo Partida caliente", "Costo Detención", "Tiempo Partida fría", "Tiempo Partida tibia",
          "Tiempo Partida caliente", "Costo_Cero", "fria", "tibia_i", "tibia_f", "Caliente",
          "Costo Partida tibia 2", "Tiempo Partida tibia 2"]
COSTOS_ORIGEN = ["Llave_Concatenada", "DIA", "HORA", "UNIDAD", "Partida_Fria", "Partida_Tibia",
                 "Partida_Caliente", "Detencion", "Tiempo_Partida_Fria", "Tiempo_Partida_Tibia",
                 "Tiempo_Partida_Caliente", "Costo_Cero", "Fria_Num1_M", "Tibia_Num2_N", "Tibia_Num1_O",
                 "Caliente_Num1_P", "Partida_Tibia_2", "Tiempo_Partida_Tibia_2"]
RIO = ["Clave", "Clave relacionada", "Dia", "Hora", "E/S", "Central", "Sube", "Baja", "Queda",
       "COMENTARIO", "Configuración", "Estado Embalse", "Consigna", "MOTIVO", "Operación", "Neomante",
       "Relacionada", "Ciclo", "SSCC", "Ciclo Partida siguiente", "Clave Ciclo partida",
       "Combustible Partida",  # <- V, ultima del Excel
       "FECHA_HORA_RIO", "Usada en", "Mes"]
CICLO = ["Ciclo de operación", "Ciclo completo", "Total Costos Partida", "Total Costos Detención",
         "Total Margen", "Total Costos Partida ciclo inconcluso", "Margen ciclo inconcluso",
         "Total Sobrecosto_P-D", "Empresa", "Copia Ciclo", "Cuadro de pagos?", "", " ", "Verificadores",
         "PO", "SIF", "Ciclo", "Maximo ciclo", "SSCC",  # <- S, ultima del Excel
         "Check SC", "Check partida", "Check detención", "Check margen"]
INCONCLUSO_DER = ["Ciclo de operación", "Ciclo de operación", "Ciclo completo", "Total Costos Partida",
                  "Total Costos Detención", "Total Margen", "Total Costos Partida ciclo inconcluso",
                  "Margen ciclo inconcluso", "Total Sobrecosto_P-D", "Empresa", "Copia Ciclo",
                  "Cuadro de pagos?", "", " ", "Verificadores", "PO", "SIF"]
RESUMEN = ["Empresa", "PAGA", "RECIBE", "SALDO", "rep", "CHECK", "", "Motor Total_SC_PD_CLP", "Ciclos"]
# Hoja opcional (solo con archivo de retiros): quien paga cada ciclo y cuanto.
HOJA_PAGOS = "Cuadro de pagos"
PAGOS = ["Ciclo de operación", "Suministrador", "Retiro kWh ciclo", "Total kWh ciclo", "Prorrata",
         "Total Sobrecosto_P-D", "PAGA"]
PRUEBAS = ["Id", "fecha", "hora", "central", "Configuracion", "cuarto", "FECHA_HORA",
           "Central relacionada", "Fuente RIO"]

DIFERIDOS = ("Continua proximo mes", "Continua todo el mes")
SSCC_RE = "SSCC|CTF|CSF|CPF"
XH = "'Sobrecosto_PD xHyC'"
XA = "'xHyC mes anterior'"
RI = "'Instrucciones RIO'"
CI = "'Ciclos inconclusos'"
_FILTRO_OP = ('IF(OR({P}{r}="OM",{Q}{r}="PDO",AND({P}{r}="OT",{Z}{r}=1),'
              'AND(AE{r}=1,{P}{r}="Sin_Registro_RIO")),1,0)')

# Plantillas de formula por hoja y letra. {r} = fila; {N} ultima fila de xHyC, {M} de
# PARTIDAS_DETENCIONES, {C} de Sobrecosto_Ciclo, {K} de Ciclos inconclusos (tabla derecha),
# {F} de xHyC mes anterior, {R} de Instrucciones RIO, {E} de Central_Empresa, {Z} de RESUMEN,
# {costos} de Costos_de_P-D. Nunca referencias estructuradas.
FORMULAS = {
    "Sobrecosto_PD xHyC": {
        "O": "=+I{r}",
        "U": ("=IFERROR(IF(N{r}=\"SI\",VLOOKUP(AH{r}&D{r},'Costos_de_P-D'!$A$2:$R${costos},"
              "IF(T{r}=\"fria\",5,IF(T{r}=\"tibia\",6,IF(T{r}=\"tibia_2\",17,7))),FALSE)"
              "*AK{r}*AG{r}*AM{r},0),0)"),
        "V": ("=IFERROR(IF(O{r}=\"SI\",VLOOKUP(AH{r}&D{r},'Costos_de_P-D'!$A$2:$R${costos},8,FALSE)"
              "*AL{r}*AO{r}*AN{r},0),0)"),
        "Y": "=IF(X{r}-W{r}<0,0,X{r}-W{r})",
        "AA": "=E{r}",
        "AB": "=Z{r}*Y{r}*AA{r}",
        "AC": "=J{r}",
        "BE": "=ROUND(AB{r}-BD{r},0)",
    },
    "PARTIDAS_DETENCIONES": {
        "D": f"=SUMIF({XH}!$AT$2:$AT${{N}},O{{r}},{XH}!$E$2:$E${{N}})",
        "M": "=C{r}",
        "N": "=M{r}&\"&\"&I{r}",
        "O": "=A{r}&B{r}&M{r}",
        # solo en filas Proceso_Partida = SI
        "S": (f"=IFERROR(MAXIFS({XH}!$U$2:$U${{N}},{XH}!$J$2:$J${{N}},N{{r}},{XH}!$G$2:$G${{N}},\"SI\")"
              "*" + _FILTRO_OP.format(P="P", Q="Q", Z="Z", r="{r}") + "*AF{r}*AG{r}*AH{r},0)"),
        # solo en filas proceso_detencion = SI; usa los filtros de la detencion (AQ..)
        "T": (f"=IFERROR(MAXIFS({XH}!$V$2:$V${{N}},{XH}!$J$2:$J${{N}},N{{r}},{XH}!$I$2:$I${{N}},\"SI\")"
              "*" + _FILTRO_OP.format(P="AQ", Q="AR", Z="AT", r="{r}") + "*AU{r}*AV{r}*AW{r},0)"),
        "V": f"=COUNTIFS({XH}!$J$2:$J${{N}},N{{r}},{XH}!$G$2:$G${{N}},\"SI\")",
        "W": f"=SUMIFS({XH}!$U$2:$U${{N}},{XH}!$J$2:$J${{N}},N{{r}},{XH}!$G$2:$G${{N}},\"SI\")",
        "X": f"=COUNTIFS({XH}!$J$2:$J${{N}},N{{r}},{XH}!$I$2:$I${{N}},\"SI\")",
        "Y": f"=SUMIFS({XH}!$V$2:$V${{N}},{XH}!$J$2:$J${{N}},N{{r}},{XH}!$I$2:$I${{N}},\"SI\")",
        "AB": f"=COUNTIFS({RI}!$B$2:$B${{R}},O{{r}},{RI}!$M$2:$M${{R}},\"PP\")",
        "AC": f"=COUNTIFS({RI}!$B$2:$B${{R}},O{{r}},{RI}!$M$2:$M${{R}},\"PS\")",
        "AD": "=IF(AB{r}+AC{r}>1,1,0)",
    },
    "Sobrecosto_Ciclo": {
        "C": "=SUMIF(PARTIDAS_DETENCIONES!$N$2:$N${M},A{r},PARTIDAS_DETENCIONES!$S$2:$S${M})",
        "D": "=SUMIF(PARTIDAS_DETENCIONES!$N$2:$N${M},A{r},PARTIDAS_DETENCIONES!$T$2:$T${M})",
        "E": f"=SUMIF({XH}!$AC$2:$AC${{N}},A{{r}},{XH}!$AB$2:$AB${{N}})",
        "F": (f"=SUMIF({CI}!$S$3:$S${{K}},A{{r}},{CI}!$V$3:$V${{K}})"
              f"+SUMIF({CI}!$S$3:$S${{K}},A{{r}},{CI}!$W$3:$W${{K}})"),
        "G": f"=SUMIF({CI}!$S$3:$S${{K}},A{{r}},{CI}!$X$3:$X${{K}})",
        "H": "=IF(C{r}+D{r}+F{r}>E{r}+G{r},C{r}+D{r}+F{r}-E{r}-G{r},0)",
        "I": "=IF(B{r}=1,VLOOKUP(Q{r},Central_Empresa!$A$2:$B${E},2,0),\"Se traspasa al proximo mes\")",
        "J": "=A{r}",
        "K": "=IFERROR(VLOOKUP(I{r},RESUMEN!$A$2:$A${Z},1,0),\"Falta en cuadro de pagos\")",
        "Q": "=LEFT(A{r},FIND(\"&\",A{r},1)-1)",
        "R": "=MAXIFS(PARTIDAS_DETENCIONES!$I$2:$I${M},PARTIDAS_DETENCIONES!$C$2:$C${M},Q{r})",
        "S": f"=SUMIF({RI}!$R$2:$R${{R}},A{{r}},{RI}!$S$2:$S${{R}})",
        # los ciclos diferidos (B = 0) tienen Costo_*_Efectivo = 0 en el motor y su margen
        # no se liquida; los checks solo aplican a los ciclos completos
        "T": "=ROUND((H{r}-{col_sc}{r})*B{r},0)",
        "U": "=ROUND((C{r}+F{r}-{col_partida}{r})*B{r},0)",
        "V": "=ROUND((D{r}-{col_detencion}{r})*B{r},0)",
        "W": "=ROUND((E{r}+G{r}-{col_margen}{r})*B{r},0)",
    },
    "RESUMEN": {
        # "B" (PAGA) solo se escribe con prorrateo: ver FORMULA_PAGA
        "C": "=SUMIF(Sobrecosto_Ciclo!$I$2:$I${C},A{r},Sobrecosto_Ciclo!$H$2:$H${C})",
        "D": "=+C{r}-B{r}",
        "E": "=+COUNTIF($A$2:$A${Z},A{r})",
        "F": "=ROUND(C{r}-H{r},0)",
        "I": "=COUNTIFS(Sobrecosto_Ciclo!$I$2:$I${C},A{r})",
    },
    HOJA_PAGOS: {
        "E": "=IF(D{r}=0,0,C{r}/D{r})",
        # el precio del ciclo es el mismo H que liquida Sobrecosto_Ciclo (solo ciclos completos)
        "F": "=SUMIFS(Sobrecosto_Ciclo!$H$2:$H${C},Sobrecosto_Ciclo!$A$2:$A${C},A{r},Sobrecosto_Ciclo!$B$2:$B${C},1)",
        "G": "=E{r}*F{r}",
    },
    "Ciclos inconclusos": {
        # tabla izquierda (Proximo mes), filas desde la 3
        "C": "=SUMIF(PARTIDAS_DETENCIONES!$N$2:$N${M},A{r},PARTIDAS_DETENCIONES!$S$2:$S${M})",
        "D": "=SUMIF(PARTIDAS_DETENCIONES!$N$2:$N${M},A{r},PARTIDAS_DETENCIONES!$T$2:$T${M})",
        "E": f"=SUMIF({XH}!$AC$2:$AC${{N}},A{{r}},{XH}!$AB$2:$AB${{N}})",
        "Q": "=LEFT(A{r},FIND(\"&\",A{r},1)-1)",
        # tabla derecha (Mes anterior)
        "S": "=T{r}",
        "X": f"=SUMIF({XA}!$AC$2:$AC${{F}},T{{r}},{XA}!$AB$2:$AB${{F}})",
    },
}
FORMULA_PAGA = f"=SUMIF('{HOJA_PAGOS}'!$B$2:$B${{P}},A{{r}},'{HOJA_PAGOS}'!$G$2:$G${{P}})"


# --------------------------------------------------------------------------- utilidades
def interruptores_panel() -> dict:
    return {n: v for n, v in vars(motor).items() if n.isupper() and not n.startswith("RUTA_")
            and n != "MINUTOS_BLOQUE" and isinstance(v, (str, int, float, bool))}


def _col(df: pd.DataFrame, nombre: str, default=None) -> pd.Series:
    """Columna del DataFrame o una serie constante con el mismo indice."""
    if nombre in df.columns:
        return df[nombre]
    return pd.Series([default] * len(df), index=df.index, dtype=object)


def _num(serie, default=0.0) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce").fillna(default)


def _letra(indice: int) -> str:
    return xl_col_to_name(indice)


def _indice(letra: str) -> int:
    n = 0
    for ch in letra:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _aamm(ciclos: pd.DataFrame) -> str:
    if "Ciclo_Mes" in ciclos and ciclos["Ciclo_Mes"].notna().any():
        m = re.search(r"(\d{2})\D?(\d{2})$", str(ciclos["Ciclo_Mes"].dropna().mode().iloc[0]))
        if m:
            return "".join(m.groups())
    fechas = pd.to_datetime(_col(ciclos, "Inicio_Ciclo"), errors="coerce").dropna()
    if fechas.empty:
        raise ValueError("Resumen_Ciclos_PD no contiene fechas de ciclo válidas")
    return fechas.max().strftime("%y%m")


def _combustible(serie: pd.Series) -> pd.Series:
    return motor.combustible_configuracion(serie.fillna("").astype(str)).astype(str)


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    h.update(ruta.read_bytes())
    return h.hexdigest()


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True).strip()
    except Exception:
        return "no disponible"


def _politica(llave_fhc: pd.Series, central: pd.Series) -> pd.Series:
    """'260818-1AGUASBLANCAS-AGB_DIESEL' -> '260818-1' (la central puede traer guiones)."""
    llave = llave_fhc.fillna("").astype(str)
    cen = central.fillna("").astype(str)
    return pd.Series([l[:-len(c)] if c and l.endswith(c) else l for l, c in zip(llave, cen)],
                     index=llave.index)


def _si(mask: pd.Series) -> pd.Series:
    return mask.map({True: "SI", False: ""})


# --------------------------------------------------------------------------- hojas
def _atributos_ciclo(detalle_total: pd.DataFrame) -> pd.DataFrame:
    """Dolar y combustible instruido en la apertura y el cierre de cada ciclo.

    Se calculan sobre el detalle COMPLETO (mes + frontera): la apertura de un ciclo
    que viene del mes anterior esta en la frontera. Es la misma valorizacion de
    ``tarifa_valorizada_al_extremo`` (spec 25 §7).
    """
    if detalle_total.empty:
        return pd.DataFrame(columns=["USD apertura ciclo", "USD cierre ciclo",
                                     "Combustible Partida", "Combustible Detención"])
    d = detalle_total.copy()
    d["FECHA_HORA"] = pd.to_datetime(d["FECHA_HORA"], errors="coerce")
    d = d.sort_values("FECHA_HORA", kind="stable")
    dolar = _num(_col(d, "Valor_Dolar", np.nan), np.nan)
    d["_dolar"] = dolar.where(dolar.notna(), _num(_col(d, "Dolar", np.nan), np.nan))
    d["_comb"] = _combustible(_col(d, "Configuracion RIO", ""))
    g = d.groupby("Etiqueta_Relacionada")
    return pd.DataFrame({"USD apertura ciclo": g["_dolar"].first(),
                         "USD cierre ciclo": g["_dolar"].last(),
                         "Combustible Partida": g["_comb"].first(),
                         "Combustible Detención": g["_comb"].last()})


def _por_bloque_configuracion(detalle: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (ciclo, configuracion, bloque): el motor trae una por unidad generadora.

    Generacion y margen se suman; el resto de los campos es comun a las unidades de
    una misma configuracion (CMg, dolar, tarifas, RIO). Las unidades quedan listadas.
    """
    d = detalle.copy()
    d["FECHA_HORA"] = pd.to_datetime(d["FECHA_HORA"], errors="coerce")
    llave = ["Etiqueta_Relacionada", "Central", "FECHA_HORA"]
    if not all(c in d.columns for c in llave):
        d["Unidades"] = _col(d, "UNIDAD GENERADORA", "")
        return d
    unidad = _col(d, "UNIDAD GENERADORA", "").fillna("").astype(str)
    d["Unidades"] = unidad
    if not d.duplicated(llave).any():
        return d
    agregaciones = {c: "first" for c in d.columns if c not in llave}
    for c in ("GENERACION", "Margen"):
        if c in d.columns:
            agregaciones[c] = "sum"
    agregaciones["Unidades"] = lambda s: "+".join(dict.fromkeys(v for v in s if v))
    if "CV" in d.columns and "GENERACION" in d.columns:
        # CV ponderado por generacion, para que USD x MAX(0, CMg-CV) x generacion siga cerrando
        d["_cv_g"] = _num(d["CV"]) * _num(d["GENERACION"])
        agregaciones["_cv_g"] = "sum"
    out = d.groupby(llave, as_index=False, sort=False).agg(agregaciones)
    if "_cv_g" in out.columns:
        gen = _num(out["GENERACION"])
        out["CV"] = (out["_cv_g"] / gen.where(gen != 0)).where(gen != 0, _num(out["CV"]))
        out = out.drop(columns="_cv_g")
    return out


def hoja_xhyc(detalle: pd.DataFrame, ciclos: pd.DataFrame, atributos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por bloque x configuracion, con los valores que las formulas reproducen."""
    if detalle.empty:
        return pd.DataFrame(columns=XHYC)
    d = _por_bloque_configuracion(detalle)
    d = d.sort_values(["Central", "FECHA_HORA"], kind="stable").reset_index(drop=True)
    t = d["FECHA_HORA"]
    etiqueta = _col(d, "Etiqueta_Relacionada", "").astype(str)
    central = _col(d, "Central", "").astype(str)
    cic = ciclos.drop_duplicates("Etiqueta_Relacionada").set_index("Etiqueta_Relacionada") \
        if "Etiqueta_Relacionada" in ciclos else pd.DataFrame()

    def del_ciclo(col, default=np.nan):
        if col in cic.columns:
            return etiqueta.map(cic[col])
        return pd.Series(default, index=d.index)

    def atributo(col):
        if col in atributos.columns:
            return etiqueta.map(atributos[col])
        return pd.Series(np.nan, index=d.index)

    out = pd.DataFrame(index=d.index)
    out["fecha"] = t.dt.strftime("%y%m%d").astype(int)
    out["hora"] = t.dt.strftime("%H:%M")  # inicio del bloque; el Excel usa 1..24
    out["cuarto"] = t.dt.minute // 15 + 1
    out["central"] = central
    out["Id"] = out["fecha"].astype(str) + out["hora"] + central
    out["generacion"] = _num(_col(d, "GENERACION"))
    out["Remunerar"] = ""
    grupo_cfg = d.groupby([etiqueta, central])["FECHA_HORA"]
    es_primero = t.eq(grupo_cfg.transform("min"))
    es_ultimo = t.eq(grupo_cfg.transform("max"))
    out["Proceso_Partida"] = _si(es_primero)
    horas = del_ciclo("Horas_Detenida_Ciclo")
    horas = horas.where(horas.notna(), del_ciclo("Horas_Cota_Inferior"))
    out["horas_detenida"] = horas.where(es_primero, np.nan)
    out["proceso_detencion"] = _si(es_ultimo)
    out["Ciclo de operación"] = etiqueta
    out["check01-PD"] = 0
    tarifa_p = _num(_col(d, "Costo_Partida", np.nan), np.nan)
    tarifa_d = _num(_col(d, "Costo_Detencion"))
    out["con_costo_PD"] = central.where(tarifa_p.notna() | (tarifa_d > 0), "NO")
    out["Costo_cero_PD"] = _col(d, "Costo_Cero", "No_Aplica").fillna("No_Aplica")
    out["Partida"] = (es_primero & (tarifa_p.fillna(0) > 0)).map({True: "SI", False: 0})
    out["Detencion"] = out["proceso_detencion"]
    out["part_fria"] = _col(d, "Fria_Num1_M", np.nan)
    out["part_tibia_i"] = _col(d, "Tibia_Num2_N", np.nan)
    out["part_tibia_f"] = _col(d, "Tibia_Num1_O", np.nan)
    out["part_cal"] = _col(d, "Caliente_Num1_P", np.nan)
    tipo = _col(d, "Tipo_Partida", "-").fillna("-").astype(str).str.lower()
    out["tipo_partida"] = tipo.where(es_primero, "-")
    # filtros por configuracion (columna AG del horario) y dolar del extremo del ciclo
    comb_propio = _combustible(central)
    comb_p = atributo("Combustible Partida").fillna("").astype(str)
    comb_d = atributo("Combustible Detención").fillna("").astype(str)
    out["Combustible Partida"] = comb_p
    out["Combustible Detención"] = comb_d
    out["Conf despachada RIO"] = ((comb_p == "") | (comb_propio == comb_p)).astype(int)
    out["Conf despachada RIO detención"] = ((comb_d == "") | (comb_propio == comb_d)).astype(int)
    dolar_bloque = _num(_col(d, "Dolar", np.nan), np.nan)
    out["USD apertura ciclo"] = _num(atributo("USD apertura ciclo"), np.nan).where(lambda s: s.notna(), dolar_bloque)
    out["USD cierre ciclo"] = _num(atributo("USD cierre ciclo"), np.nan).where(lambda s: s.notna(), dolar_bloque)
    out["Filtro Costo_Cero partida"] = _num(_col(d, "Filtro_CostoCero_Partida", 1), 1).astype(int)
    out["Filtro Costo_Cero detención"] = _num(_col(d, "Filtro_CostoCero_Detencion", 1), 1).astype(int)
    # valores que reproducen las formulas U y V (candidatas de tarifa_configuracion_maxima)
    out["COSTO_PARTIDA [$]"] = (tarifa_p.fillna(0) * out["USD apertura ciclo"].fillna(0)
                                * out["Conf despachada RIO"] * out["Filtro Costo_Cero partida"]
                                * (out["Partida"] == "SI"))
    out["COSTO_DETENCION [$]"] = (tarifa_d * out["USD cierre ciclo"].fillna(0)
                                  * out["Conf despachada RIO detención"] * out["Filtro Costo_Cero detención"]
                                  * es_ultimo)
    out["CV"] = _num(_col(d, "CV", np.nan), np.nan)
    out["CMg"] = _num(_col(d, "CMg", np.nan), np.nan)
    out["Diferencia Cmg-CV"] = (out["CMg"].fillna(0) - out["CV"].fillna(0)).clip(lower=0)
    out["USD"] = dolar_bloque
    out["Generación_neta"] = out["generacion"]
    out["Margen motor"] = _num(_col(d, "Margen"))
    out["Margen"] = out["Margen motor"]
    out["Clave Ciclo"] = etiqueta
    out["Programación"] = ""
    out["Disponible (1) / Pruebas (0)"] = _num(_col(d, "Disponible (1) / Pruebas (0)", 1), 1).astype(int)
    out["Politica vigente"] = _politica(_col(d, "Llave_FHC", ""), central)
    out["Empresa"] = _col(d, "Empresa", "")
    out["Tarifa partida USD"] = tarifa_p
    out["Tarifa detención USD"] = tarifa_d
    out["Central relacionada"] = _col(d, "Central_Relacionada", "").astype(str)
    out["Clave relacionada"] = out["fecha"].astype(str) + out["hora"] + out["Central relacionada"]
    out["FECHA_HORA"] = t
    out["Instrucción"] = _col(d, "MOTIVO", "")
    out["Operación"] = _col(d, "ESTADO OPERACIONAL", "")
    out["Consigna"] = _col(d, "CONSIGNAS", "")
    out["Configuración RIO"] = _col(d, "Configuracion RIO", "")
    out["Comentario RIO"] = _col(d, "COMENTARIO", "").fillna("")
    out["Fuente RIO"] = pd.to_datetime(_col(d, "Fuente_Config_RIO", pd.NaT), errors="coerce")
    out["Vigencia RIO"] = _num(_col(d, "Vigencia_RIO", 1), 1).astype(int)
    out["Filtro operacional"] = _num(_col(d, "Filtro_Operacional", 0)).astype(int)
    out["Check margen"] = 0.0
    out["Unidades"] = _col(d, "Unidades", "")
    return out[XHYC]


def _filtro_op_formula(motivo: pd.Series, eo: pd.Series, sscc: pd.Series, exencion: pd.Series) -> pd.Series:
    """Replica en pandas del IF(OR(...)) de PARTIDAS_DETENCIONES!S/T."""
    motivo = motivo.fillna("").astype(str)
    eo = eo.fillna("").astype(str)
    return ((motivo == "OM") | (eo == "PDO") | ((motivo == "OT") & (sscc == 1))
            | ((exencion == 1) & (motivo == "Sin_Registro_RIO"))).astype(int)


def hoja_partidas_detenciones(x: pd.DataFrame, ciclos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por bloque x central relacionada; los extremos traen los filtros del ciclo."""
    if x.empty:
        return pd.DataFrame(columns=PD)
    llaves = ["Central relacionada", "FECHA_HORA"]
    base = x.sort_values(llaves + ["central"], kind="stable")
    agg = base.groupby(llaves, as_index=False, sort=True).agg(
        fecha=("fecha", "first"), hora=("hora", "first"), cuarto=("cuarto", "first"),
        generacion=("generacion", "sum"), Etiqueta=("Ciclo de operación", "first"),
        Empresa=("Empresa", "first"), Instruccion=("Instrucción", "first"),
        Operacion=("Operación", "first"), Consigna=("Consigna", "first"),
        Comentario=("Comentario RIO", "first"), Fuente=("Fuente RIO", "first"),
        Vigencia=("Vigencia RIO", "first"), Disponible=("Disponible (1) / Pruebas (0)", "first"),
        FiltroOp=("Filtro operacional", "first"),
        MaxU=("COSTO_PARTIDA [$]", "max"), MaxV=("COSTO_DETENCION [$]", "max"))
    etiqueta = agg["Etiqueta"].astype(str)
    cic = ciclos.drop_duplicates("Etiqueta_Relacionada").set_index("Etiqueta_Relacionada") \
        if "Etiqueta_Relacionada" in ciclos else pd.DataFrame()

    def del_ciclo(col, default=np.nan):
        if col in cic.columns:
            return etiqueta.map(cic[col])
        return pd.Series(default, index=agg.index)

    t = agg["FECHA_HORA"]
    inicio = pd.to_datetime(del_ciclo("Inicio_Ciclo"), errors="coerce")
    termino = pd.to_datetime(del_ciclo("Termino_Ciclo"), errors="coerce")
    estado = del_ciclo("Estado_Ciclo_Mes", "").fillna("").astype(str)
    diferido = estado.isin(DIFERIDOS)
    es_partida = t.eq(inicio)
    es_detencion = t.eq(termino) & ~diferido

    out = pd.DataFrame(index=agg.index)
    out["fecha"] = agg["fecha"]
    out["hora"] = agg["hora"]
    out["central"] = agg["Central relacionada"].astype(str)
    out["generacion"] = agg["generacion"]
    out["Remunerar"] = ""
    out["Proceso_Partida"] = _si(es_partida)
    horas = del_ciclo("Horas_Detenida_Ciclo")
    horas = horas.where(horas.notna(), del_ciclo("Horas_Cota_Inferior"))
    out["horas_detenida"] = horas.where(es_partida, np.nan)
    out["proceso_detencion"] = _si(es_detencion)
    out["Ciclo"] = _num(etiqueta.str.rsplit("&", n=1).str[-1], 0).astype(int)
    out["con_costo_PD"] = ""
    out["Costo_cero_PD"] = _num(del_ciclo("Filtro_CostoCero_Partida", 1), 1).map(lambda v: "NO" if v == 1 else "SI")
    out["Costo PD"] = 1
    out["Central relacionada"] = out["central"]
    out["Clave Ciclo"] = etiqueta
    out["cuarto"] = agg["cuarto"]
    out["Ciclo + fecha + hora"] = out["fecha"].astype(str) + out["hora"].astype(str) + out["central"]

    def extremo(col_ciclo, col_bloque, mask, default=None):
        """Valor del ciclo en el extremo indicado, el del bloque en el resto."""
        v = del_ciclo(col_ciclo, np.nan)
        bloque = agg[col_bloque] if col_bloque else pd.Series(default, index=agg.index)
        return v.where(mask & v.notna(), bloque)

    # Partida (o bloque) -> columnas del Excel; detencion -> columnas propias al final
    out["Instrucción"] = extremo("Motivo_Partida", "Instruccion", es_partida)
    out["Operación"] = extremo("Estado_Op_Partida", "Operacion", es_partida)
    out["Consigna"] = extremo("Consigna_Partida", "Consigna", es_partida)
    # en una fila que es solo detencion, las columnas del Excel muestran la detencion
    solo_det = es_detencion & ~es_partida
    out["Instrucción"] = out["Instrucción"].where(~solo_det, extremo("Motivo_Detencion", "Instruccion", es_detencion))
    out["Operación"] = out["Operación"].where(~solo_det, extremo("Estado_Op_Detencion", "Operacion", es_detencion))
    out["Consigna"] = out["Consigna"].where(~solo_det, extremo("Consigna_Detencion", "Consigna", es_detencion))
    out["Programación"] = ""
    comentario_p = extremo("Comentario_Partida", "Comentario", es_partida).fillna("").astype(str)
    comentario_d = extremo("Comentario_Detencion", "Comentario", es_detencion).fillna("").astype(str)
    out["Presta SSCC"] = comentario_p.str.contains(SSCC_RE, case=False, regex=True).astype(int)
    out["Presta SSCC"] = out["Presta SSCC"].where(
        ~solo_det, comentario_d.str.contains(SSCC_RE, case=False, regex=True).astype(int))
    exencion = _num(del_ciclo("Flag_Exencion", 0).map(
        lambda v: 1 if str(v).strip().lower() in ("1", "true", "1.0") else 0), 0).astype(int)
    out["Exención sin historia"] = exencion
    out["Vigencia RIO"] = _num(extremo("Vigencia_RIO_Partida", "Vigencia", es_partida), 1).astype(int)
    out["Disponible (1) / Pruebas (0)"] = _num(extremo("Filtro_Disp_Partida", "Disponible", es_partida), 1).astype(int)
    out["Conf despachada RIO"] = _num(extremo("Filtro_Conf_Partida", None, es_partida, 1), 1).astype(int)
    out["Filtro operacional motor"] = _num(extremo("Filtro_Op_Partida", "FiltroOp", es_partida), 0).astype(int)
    fuente_p = extremo("Fuente_Filtros_RIO_Partida", "Fuente", es_partida)
    fuente_p = fuente_p.where(fuente_p.notna(), extremo("Fuente_Config_RIO_Partida", "Fuente", es_partida))
    out["Fuente RIO"] = pd.to_datetime(fuente_p, errors="coerce")
    out["Instrucción detención"] = extremo("Motivo_Detencion", "Instruccion", es_detencion)
    out["Operación detención"] = extremo("Estado_Op_Detencion", "Operacion", es_detencion)
    out["Consigna detención"] = extremo("Consigna_Detencion", "Consigna", es_detencion)
    out["Presta SSCC detención"] = comentario_d.str.contains(SSCC_RE, case=False, regex=True).astype(int)
    out["Vigencia RIO detención"] = _num(extremo("Vigencia_RIO_Detencion", "Vigencia", es_detencion), 1).astype(int)
    out["Disponible (1) / Pruebas (0) detención"] = _num(extremo("Filtro_Disp_Detencion", "Disponible", es_detencion), 1).astype(int)
    out["Conf despachada RIO detención"] = _num(extremo("Filtro_Conf_Detencion", None, es_detencion, 1), 1).astype(int)
    out["Filtro operacional motor detención"] = _num(extremo("Filtro_Op_Detencion", "FiltroOp", es_detencion), 0).astype(int)
    fuente_d = extremo("Fuente_Filtros_RIO_Detencion", "Fuente", es_detencion)
    fuente_d = fuente_d.where(fuente_d.notna(), extremo("Fuente_Config_RIO_Detencion", "Fuente", es_detencion))
    out["Fuente RIO detención"] = pd.to_datetime(fuente_d, errors="coerce")

    # Valores que reproducen S y T: MAXIFS por ciclo (todas las configuraciones) x filtros
    max_u = x.groupby("Ciclo de operación")["COSTO_PARTIDA [$]"].max()
    max_v = x.groupby("Ciclo de operación")["COSTO_DETENCION [$]"].max()
    fop_p = _filtro_op_formula(out["Instrucción"], out["Operación"], out["Presta SSCC"], exencion)
    fop_d = _filtro_op_formula(out["Instrucción detención"], out["Operación detención"],
                               out["Presta SSCC detención"], exencion)
    out["Monto Partidas"] = (etiqueta.map(max_u).fillna(0) * fop_p * out["Vigencia RIO"]
                             * out["Disponible (1) / Pruebas (0)"] * out["Conf despachada RIO"]
                             ).where(es_partida, 0.0)
    out["Monto Detenciones"] = (etiqueta.map(max_v).fillna(0) * fop_d * out["Vigencia RIO detención"]
                                * out["Disponible (1) / Pruebas (0) detención"]
                                * out["Conf despachada RIO detención"]).where(es_detencion, 0.0)
    out["Vacio"] = ""
    n_p = x[x["Proceso_Partida"] == "SI"].groupby("Ciclo de operación").agg(
        n=("Proceso_Partida", "size"), s=("COSTO_PARTIDA [$]", "sum"))
    n_d = x[x["proceso_detencion"] == "SI"].groupby("Ciclo de operación").agg(
        n=("proceso_detencion", "size"), s=("COSTO_DETENCION [$]", "sum"))
    extremos = es_partida | es_detencion
    out["N° Partidas"] = etiqueta.map(n_p["n"]).where(extremos, np.nan)
    out["Monto Partidas ciclo"] = etiqueta.map(n_p["s"]).where(extremos, np.nan)
    out["N° Detenciones"] = etiqueta.map(n_d["n"]).where(extremos, np.nan)
    out["Monto Detenciones ciclo"] = etiqueta.map(n_d["s"]).where(extremos, np.nan)
    out["Bloque mes"] = (t.dt.day - 1) * 96 + t.dt.hour * 4 + t.dt.minute // 15 + 1
    out["RIO PP"] = 0
    out["RIO PS"] = 0
    out["Revisar"] = 0
    out["FECHA_HORA"] = t
    out["Antigüedad instrucción (min)"] = (t - out["Fuente RIO"]).dt.total_seconds() / 60
    out["Estado ciclo mes"] = estado
    out["Empresa"] = agg["Empresa"]
    out["_es_partida"] = es_partida
    out["_es_detencion"] = es_detencion
    return out


def _conteo_rio(pdv: pd.DataFrame, rio: pd.DataFrame) -> pd.DataFrame:
    """Valores de RIO PP / RIO PS / Revisar (las formulas van solo en los extremos)."""
    if rio.empty or pdv.empty:
        return pdv
    for col, consigna in (("RIO PP", "PP"), ("RIO PS", "PS")):
        conteo = rio.loc[rio["Consigna"].astype(str) == consigna, "Clave relacionada"].value_counts()
        pdv[col] = pdv["Ciclo + fecha + hora"].map(conteo).fillna(0).astype(int)
    pdv["Revisar"] = ((pdv["RIO PP"] + pdv["RIO PS"]) > 1).astype(int)
    return pdv


def hoja_costos(costos: pd.DataFrame) -> pd.DataFrame:
    if costos.empty:
        return pd.DataFrame(columns=COSTOS)
    # misma tabla que uso el motor: una fila por llave, gana la ultima (df_costos_pd)
    c = costos.drop_duplicates(subset=["Llave_Concatenada"], keep="last").reset_index(drop=True) \
        if "Llave_Concatenada" in costos else costos.reset_index(drop=True)
    out = pd.DataFrame(index=c.index)
    for destino, origen in zip(COSTOS, COSTOS_ORIGEN):
        out[destino] = _col(c, origen, np.nan)
    return out[COSTOS]


def hoja_rio(rio_usado: pd.DataFrame, ciclos: pd.DataFrame) -> pd.DataFrame:
    if rio_usado.empty:
        return pd.DataFrame(columns=RIO)
    r = rio_usado.reset_index(drop=True)
    t = pd.to_datetime(_col(r, "FECHA_HORA_RIO", pd.NaT), errors="coerce")
    fecha = t.dt.strftime("%y%m%d").fillna("")
    # la llave usa el bloque de 15 min que contiene la instruccion, como xHyC!Id
    hora = t.dt.floor("15min").dt.strftime("%H:%M").fillna("")
    config = _col(r, "NOMBRE CONFIGURACIÓN", "").fillna("").astype(str)
    relacionada = _col(r, "Central_Relacionada_RIO", "").fillna("").astype(str)
    out = pd.DataFrame(index=r.index)
    out["Clave"] = fecha + hora + config
    out["Clave relacionada"] = fecha + hora + relacionada
    out["Dia"] = t.dt.day
    out["Hora"] = t.dt.strftime("%H:%M")
    out["E/S"] = ""
    out["Central"] = _col(r, "U. GENERADORA", "")
    out["Sube"] = _col(r, "POTENCIA MÁXIMA", np.nan)
    out["Baja"] = _col(r, "POTENCIA MÍNIMA", np.nan)
    out["Queda"] = _col(r, "POTENCIA INSTRUIDA", np.nan)
    comentario = _col(r, "COMENTARIO", "").fillna("").astype(str)
    out["COMENTARIO"] = comentario
    out["Configuración"] = config
    out["Estado Embalse"] = _col(r, "ESTADO DE EMBALSE", "")
    out["Consigna"] = _col(r, "CONSIGNAS", "")
    out["MOTIVO"] = _col(r, "MOTIVO", "")
    out["Operación"] = _col(r, "ESTADO OPERACIONAL", "")
    out["Neomante"] = ""
    out["Relacionada"] = relacionada
    # Que ciclo uso este registro: apertura (configuracion o filtros) y cierre
    out["Ciclo"] = "No encontrado"
    out["Usada en"] = ""
    if not ciclos.empty and "Etiqueta_Relacionada" in ciclos:
        for tipo, cols in (("Partida", ("Fuente_Config_RIO_Partida", "Fuente_Filtros_RIO_Partida")),
                           ("Detencion", ("Fuente_Config_RIO_Detencion", "Fuente_Filtros_RIO_Detencion"))):
            usados = []
            for col in cols:
                if col in ciclos:
                    usados.append(pd.DataFrame({
                        "_t": pd.to_datetime(ciclos[col], errors="coerce"),
                        "_rel": ciclos["Central_Relacionada"].astype(str),
                        "_et": ciclos["Etiqueta_Relacionada"].astype(str)}).dropna(subset=["_t"]))
            if not usados:
                continue
            tabla = pd.concat(usados).drop_duplicates(["_t", "_rel"])
            cruce = pd.DataFrame({"_t": t, "_rel": relacionada}).merge(tabla, on=["_t", "_rel"], how="left")
            hay = cruce["_et"].notna().values
            out.loc[hay, "Ciclo"] = cruce.loc[hay, "_et"].values
            previo = out.loc[hay, "Usada en"]
            out.loc[hay, "Usada en"] = np.where(previo.eq(""), tipo, "Partida y Detencion")
    out["SSCC"] = comentario.str.contains(SSCC_RE, case=False, regex=True).astype(int)
    out["Ciclo Partida siguiente"] = ""
    out["Clave Ciclo partida"] = out["Ciclo"].where(out["MOTIVO"].astype(str).isin(["PP", "PMT"]), "")
    out["Combustible Partida"] = _combustible(config)
    out["FECHA_HORA_RIO"] = t
    out["Mes"] = _col(r, "Mes", "")
    return out[RIO]


def hoja_pruebas(x_total: pd.DataFrame) -> pd.DataFrame:
    if x_total.empty:
        return pd.DataFrame(columns=PRUEBAS)
    p = x_total[_num(x_total["Disponible (1) / Pruebas (0)"], 1).eq(0)]
    return pd.DataFrame({"Id": p["Id"], "fecha": p["fecha"], "hora": p["hora"], "central": p["central"],
                         "Configuracion": p["central"], "cuarto": p["cuarto"], "FECHA_HORA": p["FECHA_HORA"],
                         "Central relacionada": p["Central relacionada"], "Fuente RIO": p["Fuente RIO"]}
                        ).reset_index(drop=True)[PRUEBAS]


def hoja_inconclusos(ciclos: pd.DataFrame, pdv: pd.DataFrame, x: pd.DataFrame, xf: pd.DataFrame):
    """Tablas 'Proximo mes' (diferidos) y 'Mes anterior' (herencia), como en el Excel."""
    estado = _col(ciclos, "Estado_Ciclo_Mes", "").fillna("").astype(str)
    etiqueta = _col(ciclos, "Etiqueta_Relacionada", "").astype(str)
    izq_src = ciclos[estado.isin(DIFERIDOS)]
    der_src = ciclos[estado.eq("Viene del mes anterior")]

    s_por_ciclo = pdv.groupby("Clave Ciclo")["Monto Partidas"].sum() if len(pdv) else pd.Series(dtype=float)
    t_por_ciclo = pdv.groupby("Clave Ciclo")["Monto Detenciones"].sum() if len(pdv) else pd.Series(dtype=float)
    e_por_ciclo = x.groupby("Clave Ciclo")["Margen"].sum() if len(x) else pd.Series(dtype=float)
    izq = pd.DataFrame(index=range(len(izq_src)), columns=CICLO[:16])
    et = etiqueta[izq_src.index].values
    izq["Ciclo de operación"] = et
    izq["Ciclo completo"] = 0
    izq["Total Costos Partida"] = pd.Series(et).map(s_por_ciclo).fillna(0).values
    izq["Total Costos Detención"] = pd.Series(et).map(t_por_ciclo).fillna(0).values
    izq["Total Margen"] = pd.Series(et).map(e_por_ciclo).fillna(0).values
    izq["Total Costos Partida ciclo inconcluso"] = 0
    izq["Margen ciclo inconcluso"] = 0
    izq["Total Sobrecosto_P-D"] = 0
    izq["Empresa"] = "Se traspasa al proximo mes"
    izq["Copia Ciclo"] = et
    izq["Cuadro de pagos?"] = "Falta en cuadro de pagos"
    izq["PO"] = 0
    izq["SIF"] = 0
    izq["Ciclo"] = pd.Series(et).str.rsplit("&", n=1).str[0].values
    for c in ("", " ", "Verificadores"):
        izq[c] = ""

    margen_front = xf.groupby("Clave Ciclo")["Margen"].sum() if len(xf) else pd.Series(dtype=float)
    der = pd.DataFrame(index=range(len(der_src)), columns=INCONCLUSO_DER)
    et = etiqueta[der_src.index].values
    der.iloc[:, 0] = et
    der.iloc[:, 1] = et
    der.iloc[:, 2] = 1
    der.iloc[:, 3] = _num(_col(der_src, "Costo_Partida_Efectivo")).values
    der.iloc[:, 4] = 0
    der.iloc[:, 5] = pd.Series(et).map(margen_front).fillna(0).values
    der.iloc[:, 6] = 0
    der.iloc[:, 7] = 0
    der.iloc[:, 8] = np.nan
    der.iloc[:, 9] = _col(der_src, "Empresa", "").values
    der.iloc[:, 10] = et
    der.iloc[:, 11] = ""
    der.iloc[:, 12] = ""
    der.iloc[:, 13] = ""
    der.iloc[:, 14] = ""
    der.iloc[:, 15] = 0
    der.iloc[:, 16] = 0
    return izq, der


def hoja_ciclo(ciclos: pd.DataFrame, pdv: pd.DataFrame, x: pd.DataFrame, der: pd.DataFrame,
               rio: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Sobrecosto_Ciclo: A..S del Excel, checks T..W y luego todo Resumen_Ciclos_PD."""
    out = pd.DataFrame(index=ciclos.index)
    etiqueta = _col(ciclos, "Etiqueta_Relacionada", "").astype(str)
    estado = _col(ciclos, "Estado_Ciclo_Mes", "").fillna("").astype(str)
    completo = (~estado.isin(DIFERIDOS)).astype(int)
    s_por_ciclo = pdv.groupby("Clave Ciclo")["Monto Partidas"].sum() if len(pdv) else pd.Series(dtype=float)
    t_por_ciclo = pdv.groupby("Clave Ciclo")["Monto Detenciones"].sum() if len(pdv) else pd.Series(dtype=float)
    e_por_ciclo = x.groupby("Clave Ciclo")["Margen"].sum() if len(x) else pd.Series(dtype=float)
    her_p = pd.Series(der.iloc[:, 3].values, index=der.iloc[:, 0].values) if len(der) else pd.Series(dtype=float)
    her_d = pd.Series(der.iloc[:, 4].values, index=der.iloc[:, 0].values) if len(der) else pd.Series(dtype=float)
    her_m = pd.Series(der.iloc[:, 5].values, index=der.iloc[:, 0].values) if len(der) else pd.Series(dtype=float)
    out["Ciclo de operación"] = etiqueta
    out["Ciclo completo"] = completo
    out["Total Costos Partida"] = etiqueta.map(s_por_ciclo).fillna(0).astype(float)
    out["Total Costos Detención"] = etiqueta.map(t_por_ciclo).fillna(0).astype(float)
    out["Total Margen"] = etiqueta.map(e_por_ciclo).fillna(0).astype(float)
    out["Total Costos Partida ciclo inconcluso"] = _num(etiqueta.map(her_p)) + _num(etiqueta.map(her_d))
    out["Margen ciclo inconcluso"] = _num(etiqueta.map(her_m))
    bruto = (out["Total Costos Partida"] + out["Total Costos Detención"]
             + out["Total Costos Partida ciclo inconcluso"] - out["Total Margen"] - out["Margen ciclo inconcluso"])
    out["Total Sobrecosto_P-D"] = bruto.clip(lower=0)
    empresa = _col(ciclos, "Empresa", "").astype(str)
    out["Empresa"] = empresa.where(completo == 1, "Se traspasa al proximo mes")
    out["Copia Ciclo"] = etiqueta
    out["Cuadro de pagos?"] = out["Empresa"].where(completo == 1, "Falta en cuadro de pagos")
    out[""] = ""
    out[" "] = ""
    out["Verificadores"] = ""
    out["PO"] = 0
    out["SIF"] = 0
    out["Ciclo"] = _col(ciclos, "Central_Relacionada", "").astype(str)
    ciclo_id = _num(_col(ciclos, "Ciclo_ID_Relacionada", np.nan), np.nan)
    ciclo_id = ciclo_id.where(ciclo_id.notna(), _num(etiqueta.str.rsplit("&", n=1).str[-1], 0))
    out["Maximo ciclo"] = ciclo_id.groupby(out["Ciclo"]).transform("max").astype(int)
    sscc = rio.groupby("Ciclo")["SSCC"].sum() if len(rio) else pd.Series(dtype=float)
    out["SSCC"] = etiqueta.map(sscc).fillna(0).astype(int)
    out["Check SC"] = ((out["Total Sobrecosto_P-D"] - _num(_col(ciclos, "Total SC_PD"))) * completo).round(0)
    out["Check partida"] = ((out["Total Costos Partida"] + out["Total Costos Partida ciclo inconcluso"]
                             - _num(_col(ciclos, "Costo_Partida_Efectivo"))) * completo).round(0)
    out["Check detención"] = ((out["Total Costos Detención"]
                               - _num(_col(ciclos, "Costo_Detencion_Efectivo"))) * completo).round(0)
    out["Check margen"] = ((out["Total Margen"] + out["Margen ciclo inconcluso"]
                            - _num(_col(ciclos, "Margen_Suma_Ciclo"))) * completo).round(0)
    # las columnas del motor que chocan con las del Excel (p. ej. Empresa) se renombran
    columnas_motor = [c if c not in CICLO else f"{c} (motor)" for c in ciclos.columns]
    motor_df = ciclos.copy()
    motor_df.columns = columnas_motor
    out = pd.concat([out, motor_df.set_index(out.index)], axis=1)
    return out, columnas_motor


def hoja_pagos(detalle_prorrateo: pd.DataFrame) -> pd.DataFrame:
    """Cuadro de pagos: una fila por ciclo y suministrador que retiro en sus cuartos."""
    por_ciclo = resumir_por_ciclo_suministrador(detalle_prorrateo)
    out = pd.DataFrame({
        "Ciclo de operación": por_ciclo["Ciclo"].astype(str), "Suministrador": por_ciclo["Suministrador"].astype(str),
        "Retiro kWh ciclo": por_ciclo["Medida_kWh_Ciclo"], "Total kWh ciclo": por_ciclo["Total_kWh_Ciclo"],
        "Prorrata": por_ciclo["Prorrata"], "Total Sobrecosto_P-D": por_ciclo["Precio_Ciclo"],
        "PAGA": por_ciclo["Monetario"]})
    return out[PAGOS].reset_index(drop=True)


def hoja_resumen(ciclo: pd.DataFrame, empresas: pd.DataFrame, pagos: pd.DataFrame | None = None) -> pd.DataFrame:
    """RESUMEN: RECIBE por empresa generadora y, con prorrateo, PAGA por suministrador.

    Los suministradores que no reciben se agregan al final; el cruce es por nombre exacto.
    """
    paga = (pagos.groupby("Suministrador")["PAGA"].sum() if pagos is not None and len(pagos)
            else pd.Series(dtype=float))
    orden = list(dict.fromkeys(list(_col(empresas, "Empresa", "").dropna().astype(str))
                               + [e for e in ciclo["Empresa"].astype(str).unique()
                                  if e != "Se traspasa al proximo mes"]
                               + list(paga.sort_values(ascending=False).index.astype(str))))
    out = pd.DataFrame({"Empresa": orden})
    out["PAGA"] = out["Empresa"].map(paga).fillna(0).astype(float)
    recibe = ciclo.groupby("Empresa")["Total Sobrecosto_P-D"].sum()
    out["RECIBE"] = out["Empresa"].map(recibe).fillna(0).astype(float)
    out["SALDO"] = out["RECIBE"] - out["PAGA"]
    out["rep"] = 1
    motor_total = dict(zip(_col(empresas, "Empresa", "").astype(str), _num(_col(empresas, "Total_SC_PD_CLP"))))
    out["Motor Total_SC_PD_CLP"] = out["Empresa"].map(motor_total).fillna(0).astype(float)
    out["CHECK"] = (out["RECIBE"] - out["Motor Total_SC_PD_CLP"]).round(0)
    out[""] = ""
    out["Ciclos"] = out["Empresa"].map(ciclo["Empresa"].value_counts()).fillna(0).astype(int)
    return out[RESUMEN]


# --------------------------------------------------------------------------- diccionario y leeme
_SIGNIFICADOS = {
    "Id": "fecha & hora & central; llave del bloque (igual que el Excel, con hora HH:MM)",
    "fecha": "AAMMDD", "hora": "inicio del bloque de 15 min, HH:MM (el Excel trae 1..24)", "cuarto": "1..4 dentro de la hora",
    "central": "configuracion que genero", "generacion": "MWh del bloque",
    "Proceso_Partida": "SI en el primer bloque de la configuracion dentro del ciclo",
    "proceso_detencion": "SI en el ultimo bloque de la configuracion dentro del ciclo",
    "horas_detenida": "horas detenida antes del ciclo (o cota inferior)",
    "Ciclo de operación": "Etiqueta_Relacionada del motor (relacionada&numero)",
    "COSTO_PARTIDA [$]": "tarifa de la configuracion segun tramo x dolar de apertura x combustible instruido x Costo_Cero",
    "COSTO_DETENCION [$]": "tarifa de detencion x dolar de cierre x combustible instruido al cierre x Costo_Cero",
    "Margen": "USD x MAX(0, CMg-CV) x generacion, bloque a bloque",
    "Monto Partidas": "MAXIFS de COSTO_PARTIDA del ciclo x filtro operacional x vigencia x pruebas x configuracion",
    "Monto Detenciones": "idem con COSTO_DETENCION y los filtros de la detencion",
    "Presta SSCC": "1 si el comentario de la instruccion contiene SSCC/CTF/CSF/CPF",
    "Total Sobrecosto_P-D": "MAX(0, C + D + F - E - G), identica al Excel horario",
    "Ciclo completo": "1 = se liquida este mes; 0 = se traspasa (diferido)",
}


def hoja_diccionario(frames: dict[str, pd.DataFrame], formulas: dict) -> pd.DataFrame:
    filas = []
    for hoja, df in frames.items():
        f = formulas.get(hoja, {})
        for i, col in enumerate(df.columns):
            letra = _letra(i)
            filas.append({"hoja": hoja, "columna": col, "letra": letra,
                          "significado": _SIGNIFICADOS.get(col, str(col).replace("_", " ")),
                          "fórmula o valor": f.get(letra, "valor")})
    return pd.DataFrame(filas)


LEEME = [
    "PAQUETE DE AUDITORIA CEN - formato del Excel horario a resolucion de 15 minutos (spec 32).",
    "Cada hoja replica la homonima del Sobrecostos_PD_AAMM.xlsm: mismos encabezados y letras de columna;",
    "las columnas a la derecha de la ultima del Excel son del motor y no existen en el horario.",
    "Solo hay filas para los bloques de 15 min que pertenecen a un ciclo del mes; no se rellenan horas sin generacion.",
    "La columna hora trae el inicio del bloque de 15 min (HH:MM) en vez del 1..24 del horario; Id y las llaves siguen siendo fecha & hora & central.",
    "",
    "CADENA DE FORMULAS (igual que el horario):",
    "  RESUMEN!C = SUMIF(Sobrecosto_Ciclo!I, empresa, Sobrecosto_Ciclo!H)",
    "  Sobrecosto_Ciclo!C/D = SUMIF(PARTIDAS_DETENCIONES!N, ciclo, S/T);  E = SUMIF(xHyC!AC, ciclo, xHyC!AB)",
    "  Sobrecosto_Ciclo!F/G = herencia del mes anterior desde 'Ciclos inconclusos' (tabla derecha)",
    "  Sobrecosto_Ciclo!H = IF(C+D+F > E+G, C+D+F-E-G, 0)",
    "  PARTIDAS_DETENCIONES!S = MAXIFS(xHyC!U del ciclo con Proceso_Partida=SI) x filtro operacional x vigencia x pruebas x configuracion",
    "  xHyC!U = VLOOKUP(politica&central, Costos_de_P-D, tramo) x USD apertura ciclo x Conf despachada RIO x Costo_Cero",
    "  xHyC!AB = USD x MAX(0, CMg-CV) x generacion",
    "",
    "DIFERENCIAS DE REGLA FRENTE AL EXCEL HORARIO (decisiones 14/15/16-09-2026):",
    "  1. Tarifa al dolar del extremo: xHyC!U usa 'USD apertura ciclo' (AK), no el dolar del bloque (Z). Spec 25 §7.",
    "  2. Pruebas (EP) y filtro operacional se evaluan en la instruccion de apertura/cierre del ciclo (PARTIDAS_DETENCIONES!AG, S);",
    "     por eso multiplican en PARTIDAS_DETENCIONES!S/T y no en xHyC!U/V. xHyC!AE queda informativo.",
    "  3. Vigencia +/-30 min de la instruccion RIO (PARTIDAS_DETENCIONES!AF). Spec 27.",
    "  4. Presta SSCC (PARTIDAS_DETENCIONES!Z) sale del COMENTARIO de la instruccion del ciclo (1/0); el ISNUMBER del Excel siempre da 1.",
    "  5. Exencion 'sin historia' (PARTIDAS_DETENCIONES!AE): reemplaza la regla RIGHT(N,2)='&1' y P='' del Excel.",
    "  6. En un ciclo de un solo bloque la fila es partida y detencion a la vez: T usa los filtros de la detencion (AQ..AY).",
    "",
    "OTRAS NOTAS:",
    "  Generacion_neta (xHyC!AA) = generacion: el reporte de 15 min ya viene neto de consumos propios.",
    "  Margen (xHyC!AB) es formula solo con RESOLUCION_MARGEN=bloque, MARGEN_NETEADO_POR_CICLO=0 y CALCULAR_MARGEN_EN_EL_MOTOR=1;",
    "  con otra combinacion se escribe el valor del motor. 'Margen motor' (BD) y 'Check margen' (BE) lo contrastan.",
    "  IFERROR en xHyC!U/V cubre politicas sin tarifa en Costos_de_P-D (tampoco tienen tarifa en el motor).",
    "  Las formulas pesadas (S, T, V..Y, AB..AD de PARTIDAS_DETENCIONES) solo estan en las filas de partida/detencion; el resto son valores.",
    "  Los ciclos diferidos (Ciclo completo = 0) muestran C/D/E de este mes pero H se excluye del RESUMEN (I = 'Se traspasa al proximo mes').",
    "  Costos_de_P-D trae una fila por llave (gana la ultima), igual que la tabla que uso el motor, y solo las configuraciones con ciclos en el mes.",
    "  Los CSV de la carpeta son estas mismas hojas volcadas como valores (donde hay formula, el valor calculado en Python).",
    "  Los checks (Sobrecosto_Ciclo!T:W, RESUMEN!F, xHyC!BE) deben ser 0; 'Check SC' compara H x B con Total SC_PD del motor.",
]
LEEME_PAGOS = [
    "",
    "PRORRATEO DE PAGOS (spec 11, con archivo de retiros a 15 minutos):",
    "  'Cuadro de pagos' reparte cada ciclo liquidado entre los suministradores que retiraron energia en sus cuartos de hora.",
    "  Cuadro de pagos!E (Prorrata) = retiro del suministrador en el ciclo / retiro total en el ciclo.",
    "  Cuadro de pagos!F = SUMIFS(Sobrecosto_Ciclo!H, ciclo, Ciclo completo = 1);  G (PAGA) = E x F.",
    "  RESUMEN!B (PAGA) = SUMIF(Cuadro de pagos!B, empresa, Cuadro de pagos!G);  D (SALDO) = RECIBE - PAGA.",
    "  RESUMEN!G1 = SUM(SALDO) debe ser 0: lo que se paga iguala lo que se recibe (salvo ciclos sin retiros, que avisa la consola).",
    "  Los suministradores se cruzan con las empresas por nombre exacto; los que solo pagan aparecen al final del RESUMEN.",
    "  El detalle cuarto a cuarto esta en SCPD_<AAMM>_Prorrateo_Detalle_15min.csv.",
]


# --------------------------------------------------------------------------- escritura
def _celdas(df: pd.DataFrame) -> list[list]:
    """Filas como listas de valores nativos; NaN/NaT -> None (celda vacia)."""
    obj = df.astype(object).where(pd.notna(df), None)
    return obj.values.tolist()


def _cacheado(valor):
    """Valor que se guarda junto a la formula: Excel recalcula al abrir (fullCalcOnLoad)."""
    if valor is None or valor == "":
        return 0  # un <v></v> vacio deja el libro ilegible
    if isinstance(valor, (pd.Timestamp, np.datetime64, datetime)):
        return str(valor)
    if isinstance(valor, (np.integer, np.floating)):
        return valor.item()
    return valor


def _escribir(wb, ws, df: pd.DataFrame, formulas: dict | None = None, ctx: dict | None = None,
              solo_filas: dict | None = None, fila_inicio: int = 0, col_inicio: int = 0,
              formatos: dict | None = None, filas_extra: dict | None = None):
    """Escribe encabezado, valores y formulas (con su valor cacheado) fila a fila.

    Se escribe en orden de filas para poder usar ``constant_memory`` de xlsxwriter (mucho
    mas rapido y liviano que ``DataFrame.to_excel``). ``formulas`` = {letra: plantilla};
    ``solo_filas`` = {letra: mascara booleana} restringe una formula a ciertas filas;
    ``filas_extra`` = {fila_0based: [(col, valor), ...]} celdas adicionales en la fila del
    encabezado (valor None = la formula G1 de RESUMEN). ``fila_inicio`` es la fila del
    encabezado.
    """
    ctx = ctx or {}
    negrita = wb.add_format({"bold": True})
    columnas = list(df.columns)
    ws.write_row(fila_inicio, col_inicio, [str(c) for c in columnas], negrita)
    for col, valor in (filas_extra or {}).get(fila_inicio, []):
        if valor is None:  # RESUMEN!G1 = SUM(D:D), igual que el Excel horario
            ws.write_formula(fila_inicio, col, "=SUM(D:D)", None,
                             float(_num(df.iloc[:, 3]).sum()) if len(df) else 0)
        else:
            ws.write(fila_inicio, col, valor)
    plantillas = {}
    for letra, plantilla in (formulas or {}).items():
        ci = _indice(letra) - col_inicio
        if 0 <= ci < len(columnas):
            mascara = solo_filas.get(letra) if solo_filas else None
            plantillas[ci] = (plantilla, None if mascara is None else np.asarray(mascara, dtype=bool))
    for i, fila in enumerate(_celdas(df)):
        r = fila_inicio + 1 + i
        ws.write_row(r, col_inicio, fila)
        for ci, (plantilla, mascara) in plantillas.items():
            if mascara is not None and not mascara[i]:
                continue
            ws.write_formula(r, col_inicio + ci, plantilla.format(r=r + 1, **ctx), None, _cacheado(fila[ci]))
    for i, col in enumerate(columnas):
        fmt = (formatos or {}).get(col)
        ws.set_column(col_inicio + i, col_inicio + i, min(40, max(11, len(str(col)) + 2)), fmt)
    return ws


def _escribir_lado_a_lado(wb, ws, izq: pd.DataFrame, der: pd.DataFrame, f_izq: dict, f_der: dict,
                          ctx: dict, col_der: int, formatos: dict | None = None):
    """Dos tablas en la misma hoja (Ciclos inconclusos), escritas fila a fila."""
    negrita = wb.add_format({"bold": True})
    ws.write(0, 0, "Próximo mes", negrita)
    ws.write(0, col_der, "Mes anterior", negrita)
    ws.write_row(1, 0, [str(c) for c in izq.columns], negrita)
    ws.write_row(1, col_der, [str(c) for c in der.columns], negrita)
    celdas_izq, celdas_der = _celdas(izq), _celdas(der)
    pl_izq = {_indice(k): v for k, v in f_izq.items() if _indice(k) < len(izq.columns)}
    pl_der = {_indice(k) - col_der: v for k, v in f_der.items()
              if 0 <= _indice(k) - col_der < len(der.columns)}
    for i in range(max(len(celdas_izq), len(celdas_der))):
        r = 2 + i
        for celdas, plantillas, col0 in ((celdas_izq, pl_izq, 0), (celdas_der, pl_der, col_der)):
            if i >= len(celdas):
                continue
            ws.write_row(r, col0, celdas[i])
            for ci, plantilla in plantillas.items():
                ws.write_formula(r, col0 + ci, plantilla.format(r=r + 1, **ctx), None, _cacheado(celdas[i][ci]))
    for i, col in enumerate(izq.columns):
        ws.set_column(i, i, min(40, max(11, len(str(col)) + 2)), (formatos or {}).get(col))
    for i, col in enumerate(der.columns):
        ws.set_column(col_der + i, col_der + i, min(40, max(11, len(str(col)) + 2)), (formatos or {}).get(col))
    return ws


def generar_entrega(reporte: str | Path, carpeta_salida: str | Path | None = None,
                    archivos_entrada=None, panel: dict | None = None,
                    version: str = "Preliminar", retiros: str | Path | None = None) -> Path:
    """Crea la carpeta Entrega_SCPD_<AAMM> con el libro y los CSV; devuelve la carpeta.

    Con ``retiros`` (CSV o Parquet de retiros a 15 minutos) prorratea el sobrecosto de cada
    ciclo entre los suministradores (spec 11): agrega la hoja ``Cuadro de pagos`` y llena
    ``RESUMEN!PAGA``. Sin retiros, PAGA queda en 0 como en la spec 32.
    """
    reporte = Path(reporte).resolve()
    # calamine lee el reporte del motor (~350k filas) en segundos; openpyxl tarda minutos
    try:
        xl = pd.ExcelFile(reporte, engine="calamine")
    except (ImportError, ValueError):
        xl = pd.ExcelFile(reporte)

    def leer(nombre, columnas=None):
        if nombre in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=nombre)
            for c in df.columns:
                if "FECHA" in str(c).upper() or str(c).startswith("Fuente_") or str(c) in ("Inicio_Ciclo", "Termino_Ciclo"):
                    df[c] = pd.to_datetime(df[c], errors="coerce")
            return df
        print(f"Aviso: el reporte no trae la hoja {nombre}; se genera vacía.")
        return pd.DataFrame(columns=columnas or [])

    ciclos = leer("Resumen_Ciclos_PD")
    detalle = leer("Detalle_15Min")
    frontera = leer("Detalle_Frontera", list(detalle.columns))
    empresas = leer("SC_por_Empresa", ["Empresa", "Total_SC_PD_CLP"])
    costos_usados = leer("Costos_PD_Usados")
    rio_usado = leer("RIO_Usado")
    central_empresa = leer("Central_Empresa", ["Central", "Empresa"])
    if "Etiqueta_Relacionada" in detalle and "Etiqueta_Relacionada" in ciclos:
        publicados = set(ciclos["Etiqueta_Relacionada"])
        detalle = detalle[detalle["Etiqueta_Relacionada"].isin(publicados)].copy()
        if len(frontera):
            frontera = frontera[frontera["Etiqueta_Relacionada"].isin(publicados)].copy()

    aamm = _aamm(ciclos)
    destino = Path(carpeta_salida) if carpeta_salida else reporte.parent / f"Entrega_SCPD_{aamm}"
    if carpeta_salida and destino.name != f"Entrega_SCPD_{aamm}":
        destino = destino / f"Entrega_SCPD_{aamm}"
    destino.mkdir(parents=True, exist_ok=True)
    if not retiros:
        # Una segunda corrida en la misma carpeta no debe conservar pagos de
        # una corrida anterior que si recibio el archivo de retiros.
        for nombre in ("Cuadro_de_pagos.csv", "Prorrateo_Detalle_15min.csv"):
            (destino / f"SCPD_{aamm}_{nombre}").unlink(missing_ok=True)
    entradas = [Path(x) for x in (archivos_entrada or [reporte]) if x and Path(x).exists()]
    if retiros and Path(retiros).resolve() not in {e.resolve() for e in entradas}:
        entradas.append(Path(retiros))

    # panel efectivo: motor + hoja Parametros_Motor del reporte + lo que pase el llamador
    panel_efectivo = interruptores_panel()
    try:
        guardado = pd.read_excel(xl, sheet_name="Parametros_Motor")
        panel_efectivo.update(dict(zip(guardado["interruptor"], guardado["valor"])))
    except (ValueError, KeyError):
        pass
    panel_efectivo.update(panel or {})
    filas_param = [{"interruptor": k, "valor": v, "spec": "panel motor"} for k, v in sorted(panel_efectivo.items())]
    filas_param += [{"interruptor": "motor_version", "valor": _commit(), "spec": "git"},
                    {"interruptor": "fecha_corrida", "valor": datetime.now().isoformat(timespec="seconds"), "spec": "32"},
                    {"interruptor": "version_entrega", "valor": version, "spec": "32"}]
    for i, ruta in enumerate(entradas, 1):
        filas_param += [{"interruptor": f"archivo_entrada_{i}/nombre", "valor": ruta.name, "spec": "32"},
                        {"interruptor": f"archivo_entrada_{i}/sha256", "valor": _sha256(ruta), "spec": "32"}]
    parametros = pd.DataFrame(filas_param)

    # hojas
    detalle_total = pd.concat([frontera, detalle], ignore_index=True, sort=False) if len(frontera) else detalle
    atributos = _atributos_ciclo(detalle_total)
    x = hoja_xhyc(detalle, ciclos, atributos)
    xf = hoja_xhyc(frontera, ciclos, atributos)
    costos = hoja_costos(costos_usados)
    if len(costos) and len(x) and "Unidad" in costos:
        # el Excel horario trae todas las unidades; aqui solo las configuraciones con ciclos,
        # que son las llaves que xHyC!U/V buscan (Leeme lo declara)
        con_ciclo = set(x["central"].astype(str)) | set(xf["central"].astype(str))
        costos = costos[costos["Unidad"].astype(str).isin(con_ciclo)].reset_index(drop=True)
    rio = hoja_rio(rio_usado, ciclos)
    if len(rio) and "Mes" in rio.columns:
        # del mes anterior solo interesan las instrucciones que algun ciclo uso
        rio = rio[(rio["Mes"].astype(str) != "anterior") | (rio["Usada en"].astype(str) != "")].reset_index(drop=True)
    pruebas = hoja_pruebas(pd.concat([xf, x], ignore_index=True) if len(xf) else x)
    pdv = _conteo_rio(hoja_partidas_detenciones(x, ciclos), rio)
    izq, der = hoja_inconclusos(ciclos, pdv, x, xf)
    ciclo, columnas_motor = hoja_ciclo(ciclos, pdv, x, der, rio)
    pagos = detalle_prorrateo = None
    if retiros:
        # solo ciclos con monto: un diferido o amortizado no tiene nada que repartir
        con_monto = ciclos[_num(_col(ciclos, "Total SC_PD")) != 0]
        detalle_prorrateo, auditoria_pagos = prorratear_ciclos_motor(detalle, con_monto, leer_retiros(retiros))
        pagos = hoja_pagos(detalle_prorrateo)
        print(f"Prorrateo: {auditoria_pagos['total_repartido']:,.0f} de {auditoria_pagos['total_original']:,.0f} CLP "
              f"repartidos entre {pagos['Suministrador'].nunique()} suministradores.")
        for mensaje in auditoria_pagos["mensajes"]:
            print(mensaje)
    resumen = hoja_resumen(ciclo, empresas, pagos)
    central_empresa = central_empresa[[c for c in ["Central", "Empresa"] if c in central_empresa]].copy()
    if len(central_empresa) and "Central_Relacionada" in ciclos and "Empresa" in ciclos:
        # El motor rescata la empresa por configuracion cuando la relacionada no esta en el
        # diccionario (asignar_empresas). Sobrecosto_Ciclo!I busca por relacionada, asi que
        # esas parejas se agregan aqui, marcadas, para que el VLOOKUP reproduzca al motor.
        central_empresa["Origen"] = "diccionario"
        faltan = ciclos[~ciclos["Central_Relacionada"].astype(str).isin(central_empresa["Central"].astype(str))]
        rescate = (faltan[["Central_Relacionada", "Empresa"]].dropna().drop_duplicates("Central_Relacionada")
                   .rename(columns={"Central_Relacionada": "Central"}))
        rescate = rescate[rescate["Empresa"].astype(str) != "Sin_Empresa"]
        rescate["Origen"] = "rescate por configuracion (motor)"
        central_empresa = pd.concat([central_empresa, rescate], ignore_index=True)

    margen_formula = (int(panel_efectivo.get("CALCULAR_MARGEN_EN_EL_MOTOR", 1)) == 1
                      and str(panel_efectivo.get("RESOLUCION_MARGEN", "bloque")) == "bloque"
                      and int(panel_efectivo.get("MARGEN_NETEADO_POR_CICLO", 0)) == 0)
    f_xhyc = dict(FORMULAS["Sobrecosto_PD xHyC"])
    if not margen_formula:
        f_xhyc.pop("AB", None)
    if len(rio) == 0:
        # sin RIO no hay contra que contar; se dejan los valores (0)
        f_pd = {k: v for k, v in FORMULAS["PARTIDAS_DETENCIONES"].items() if k not in ("AB", "AC")}
        f_ciclo = {k: v for k, v in FORMULAS["Sobrecosto_Ciclo"].items() if k != "S"}
    else:
        f_pd = dict(FORMULAS["PARTIDAS_DETENCIONES"])
        f_ciclo = dict(FORMULAS["Sobrecosto_Ciclo"])
    if len(central_empresa) == 0:
        f_ciclo.pop("I", None)
    es_p, es_d = pdv["_es_partida"], pdv["_es_detencion"]
    extremos = es_p | es_d
    solo_pd = {"S": es_p, "T": es_d, "V": extremos, "W": extremos, "X": extremos, "Y": extremos,
               "AB": extremos, "AC": extremos, "AD": extremos}
    pdv_x = pdv[PD]
    # letras de las columnas del motor que usan los checks de Sobrecosto_Ciclo
    base = len(CICLO)
    letra_motor = {c: _letra(base + i) for i, c in enumerate(columnas_motor)}
    ctx = {"N": max(2, len(x) + 1), "M": max(2, len(pdv_x) + 1), "C": max(2, len(ciclo) + 1),
           "K": max(3, len(der) + 2), "F": max(2, len(xf) + 1), "R": max(2, len(rio) + 1),
           "E": max(2, len(central_empresa) + 1), "Z": max(2, len(resumen) + 1),
           "P": max(2, len(pagos) + 1) if pagos is not None else 2,
           "costos": max(2, len(costos) + 1),
           "col_sc": letra_motor.get("Total SC_PD", "H"), "col_partida": letra_motor.get("Costo_Partida_Efectivo", "C"),
           "col_detencion": letra_motor.get("Costo_Detencion_Efectivo", "D"),
           "col_margen": letra_motor.get("Margen_Suma_Ciclo", "E")}

    frames = {"Costos_de_P-D": costos, "Pruebas": pruebas, "Instrucciones RIO": rio,
              "Central_Empresa": central_empresa, "Sobrecosto_PD xHyC": x, "PARTIDAS_DETENCIONES": pdv_x,
              "Sobrecosto_Ciclo": ciclo, "RESUMEN": resumen, "xHyC mes anterior": xf}
    f_resumen = dict(FORMULAS["RESUMEN"])
    if pagos is not None:
        frames[HOJA_PAGOS] = pagos
        f_resumen["B"] = FORMULA_PAGA
    formulas_doc = dict(FORMULAS)
    formulas_doc["RESUMEN"] = f_resumen
    formulas_doc["xHyC mes anterior"] = FORMULAS["Sobrecosto_PD xHyC"]
    diccionario = hoja_diccionario(frames, formulas_doc)
    frames["Diccionario"] = diccionario

    # CSV: una hoja por archivo, valores
    def seguro(s):
        return re.sub(r"[^\w-]+", "_", s, flags=re.UNICODE).strip("_")
    for hoja, df in frames.items():
        df.to_csv(destino / f"SCPD_{aamm}_{seguro(hoja)}.csv", index=False, encoding="utf-8-sig",
                  date_format="%Y-%m-%d %H:%M:%S")
    der_csv = der.copy()
    der_csv.columns = [f"{c}_{i + 1}" if list(der.columns).count(c) > 1 else c for i, c in enumerate(der.columns)]
    inconclusos_csv = pd.concat([izq.assign(tabla="Próximo mes"), der_csv.assign(tabla="Mes anterior")],
                                ignore_index=True, sort=False)
    inconclusos_csv.to_csv(destino / f"SCPD_{aamm}_Ciclos_inconclusos.csv", index=False, encoding="utf-8-sig")
    parametros.to_csv(destino / f"SCPD_{aamm}_parametros.csv", index=False, encoding="utf-8-sig")
    if detalle_prorrateo is not None:
        detalle_prorrateo.to_csv(destino / f"SCPD_{aamm}_Prorrateo_Detalle_15min.csv", index=False,
                                 encoding="utf-8-sig")

    # libro
    libro = destino / f"SCPD_{aamm}_Auditoria.xlsx"
    import xlsxwriter
    wb = xlsxwriter.Workbook(str(libro), {"constant_memory": True, "default_date_format": "yyyy-mm-dd hh:mm",
                                          "nan_inf_to_errors": True, "strings_to_formulas": False,
                                          "use_future_functions": True})  # MAXIFS necesita _xlfn.
    try:
        clp = wb.add_format({"num_format": "#,##0"})
        dec = wb.add_format({"num_format": "0.00"})
        f_clp = {c: clp for c in ("COSTO_PARTIDA [$]", "COSTO_DETENCION [$]", "Margen", "Margen motor",
                                  "Monto Partidas", "Monto Detenciones", "Monto Partidas ciclo", "Monto Detenciones ciclo",
                                  "Total Costos Partida", "Total Costos Detención", "Total Margen",
                                  "Total Costos Partida ciclo inconcluso", "Margen ciclo inconcluso",
                                  "Total Sobrecosto_P-D", "RECIBE", "SALDO", "PAGA", "Motor Total_SC_PD_CLP",
                                  "Check SC", "Check partida", "Check detención", "Check margen", "CHECK",
                                  "Retiro kWh ciclo", "Total kWh ciclo")}
        f_dec = {c: dec for c in ("generacion", "Generación_neta", "CV", "CMg", "Diferencia Cmg-CV", "USD",
                                  "Tarifa partida USD", "Tarifa detención USD", "USD apertura ciclo", "USD cierre ciclo")}
        formatos = {**f_clp, **f_dec, "Prorrata": wb.add_format({"num_format": "0.0000%"})}
        nombres = list(SHEETS)
        if pagos is not None:
            nombres.insert(nombres.index("RESUMEN") + 1, HOJA_PAGOS)
        hojas = {nombre: wb.add_worksheet(nombre) for nombre in nombres}

        ws = hojas["Menu"]
        ws.write_row(0, 0, ["DIA", "Mes", "", "Version"])
        ws.write_row(1, 0, [int(aamm + "01"), aamm, "", version])
        ws.write_row(3, 0, ["ARCHIVO", "SHA-256", "", "Interruptor", "Valor", "Spec"])
        for i in range(max(len(entradas), len(parametros))):
            if i < len(entradas):
                ws.write(4 + i, 0, entradas[i].name)
                ws.write(4 + i, 1, _sha256(entradas[i]))
            if i < len(parametros):
                fila = parametros.iloc[i]
                ws.write(4 + i, 3, str(fila["interruptor"]))
                ws.write(4 + i, 4, str(fila["valor"]))
                ws.write(4 + i, 5, str(fila["spec"]))
        ws.set_column(0, 1, 40)
        ws.set_column(3, 4, 44)
        ws.freeze_panes(1, 0)

        ws = hojas["Leeme"]
        leeme = LEEME + ([] if pagos is None else LEEME_PAGOS)
        for i, linea in enumerate(leeme):
            ws.write(i, 0, linea)
        ws.set_column(0, 0, 150)

        _escribir(wb, hojas["Costos_de_P-D"], costos, formatos=formatos).freeze_panes(1, 0)
        _escribir(wb, hojas["Pruebas"], pruebas).freeze_panes(1, 0)
        _escribir(wb, hojas["Instrucciones RIO"], rio).freeze_panes(1, 0)
        _escribir(wb, hojas["Central_Empresa"], central_empresa).freeze_panes(1, 0)
        _escribir(wb, hojas["Sobrecosto_PD xHyC"], x, f_xhyc, ctx, formatos=formatos).freeze_panes(1, 0)
        _escribir(wb, hojas["PARTIDAS_DETENCIONES"], pdv_x, f_pd, ctx, solo_pd, formatos=formatos).freeze_panes(1, 0)
        _escribir(wb, hojas["Sobrecosto_Ciclo"], ciclo, f_ciclo, ctx, formatos=formatos).freeze_panes(1, 0)
        _escribir(wb, hojas["RESUMEN"], resumen, f_resumen, ctx, formatos=formatos,
                  filas_extra={0: [(6, None)]}).freeze_panes(1, 0)
        if pagos is not None:
            _escribir(wb, hojas[HOJA_PAGOS], pagos, FORMULAS[HOJA_PAGOS], ctx, formatos=formatos).freeze_panes(1, 0)
        f_inc = FORMULAS["Ciclos inconclusos"]
        _escribir_lado_a_lado(wb, hojas["Ciclos inconclusos"], izq, der,
                              {k: v for k, v in f_inc.items() if k in ("C", "D", "E", "Q")},
                              {k: v for k, v in f_inc.items() if k in ("S", "X")}, ctx, 18, formatos)
        hojas["Ciclos inconclusos"].freeze_panes(2, 0)
        _escribir(wb, hojas["xHyC mes anterior"], xf, f_xhyc, ctx, formatos=formatos).freeze_panes(1, 0)
        _escribir(wb, hojas["Diccionario"], diccionario).freeze_panes(1, 0)
        wb.set_calc_mode("auto")
    finally:
        wb.close()

    # verificacion en pandas de lo que los checks del libro deben dar en Excel
    for nombre, col in (("Check SC", "Check SC"), ("Check partida", "Check partida"),
                        ("Check detención", "Check detención"), ("Check margen", "Check margen")):
        n = int((ciclo[col].abs() > 1).sum())
        if n:
            print(f"Aviso: {nombre} distinto de 0 en {n} ciclo(s); revise Sobrecosto_Ciclo.")
    n_res = int((resumen["CHECK"].abs() > 1).sum())
    if n_res:
        print(f"Aviso: RESUMEN!CHECK distinto de 0 en {n_res} empresa(s).")
    return destino


def main(argv=None):
    p = argparse.ArgumentParser(description="Entrega CEN con el formato del Excel horario (spec 32).")
    p.add_argument("reporte", help="Reporte_Sobrecostos_PD_Final.xlsx del motor v7")
    p.add_argument("--salida", help="carpeta donde crear Entrega_SCPD_<AAMM>")
    p.add_argument("--entrada", action="append", default=[], help="archivo de entrada a registrar (repetible)")
    p.add_argument("--version", default="Preliminar", help="Preliminar | Definitivo")
    p.add_argument("--retiros", help="retiros 15 min (.csv o .parquet): llena PAGA y agrega 'Cuadro de pagos'")
    a = p.parse_args(argv)
    carpeta = generar_entrega(a.reporte, a.salida, a.entrada or None, version=a.version, retiros=a.retiros)
    print(f"Entrega creada en: {carpeta}")


if __name__ == "__main__":
    main()
