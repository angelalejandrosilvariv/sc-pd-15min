#!/usr/bin/env python3
"""Genera el paquete autocontenido de auditoria SC-PD para el CEN."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SPECS = {
    "VIGENCIA_INSTRUCCION_RIO_MIN": "spec 27", "HORAS_SIN_HISTORIA": "spec 28",
    "TARIFA_CONFIGURACION": "spec 25", "MARGEN_NETEADO_POR_CICLO": "spec 23",
    "DIFERIR_CICLOS_SIN_TERMINAR": "spec 17", "CALCULAR_MARGEN_EN_EL_MOTOR": "spec 22",
}
RUTAS_PANEL = ("RUTA_REPORTE_15MIN", "RUTA_REPORTE_MES_PASADO", "RUTA_RIO",
                "RUTA_RIO_MES_PASADO", "RUTA_COSTOS_PD", "RUTA_COSTOS_MES_PASADO",
                "RUTA_DICCIONARIO", "RUTA_DICCIONARIO_EMPRESA")


def sha256_archivo(ruta: str | Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""): h.update(bloque)
    return h.hexdigest()


def interruptores_panel(motor: Any) -> dict[str, Any]:
    """Lista reproducible de constantes editables del panel, sin rutas/salidas."""
    omitir = {"PATRONES_PO", "TARIFAS_CONFIGURACION_VALIDAS"}
    return {n: v for n, v in vars(motor).items()
            if n.isupper() and not n.startswith("RUTA_") and n not in omitir
            and isinstance(v, (str, int, float, bool, list, tuple))}


def _commit(raiz: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=raiz,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        return "no disponible"


def tabla_parametros(motor: Any, rutas: dict[str, str], raiz: Path,
                     ahora: datetime | None = None) -> pd.DataFrame:
    filas = [{"interruptor": k, "valor": json.dumps(v, ensure_ascii=False) if isinstance(v, (list, tuple)) else v,
              "spec": SPECS.get(k, "panel v7")} for k, v in interruptores_panel(motor).items()]
    filas += [{"interruptor":"motor_version", "valor":_commit(raiz), "spec":"git"},
              {"interruptor":"fecha_corrida", "valor":(ahora or datetime.now(timezone.utc)).isoformat(), "spec":"UTC"}]
    for clave, valor in rutas.items():
        if not valor: continue
        p = Path(valor)
        filas.append({"interruptor":f"archivo_entrada/{clave}/nombre", "valor":p.name, "spec":"archivo_entrada"})
        filas.append({"interruptor":f"archivo_entrada/{clave}/sha256",
                      "valor":sha256_archivo(p) if p.is_file() else "no encontrado", "spec":"archivo_entrada"})
    return pd.DataFrame(filas)


def _col(df: pd.DataFrame, nombre: str, defecto: Any = "") -> pd.Series:
    return df[nombre] if nombre in df else pd.Series(defecto, index=df.index)


def preparar_tablas(libro: str | Path, motor: Any) -> dict[str, pd.DataFrame]:
    x = pd.ExcelFile(libro)
    ciclos = pd.read_excel(x, "Resumen_Ciclos_PD")
    bloques0 = pd.read_excel(x, "Detalle_15Min")
    empresas = pd.read_excel(x, "SC_por_Empresa")
    guia = pd.read_excel(x, "Guia_Lectura")
    etiquetas = set(ciclos["Etiqueta_Relacionada"].dropna().astype(str))
    bloques0["Etiqueta_Relacionada"] = _col(bloques0, "Etiqueta_Relacionada").astype(str)
    bloques0 = bloques0[bloques0.Etiqueta_Relacionada.isin(etiquetas)].copy()
    columnas_b = ["Etiqueta_Relacionada", "Central_Relacionada", "Central", "FECHA_HORA",
                  "GENERACION", "CMg", "CV", "Dolar", "Margen", "Fuente_Config_RIO",
                  "CONSIGNAS", "MOTIVO", "ESTADO OPERACIONAL", "COMENTARIO",
                  "Configuracion RIO", "Filtro_Operacional", "Vigencia_RIO"]
    bloques = pd.DataFrame({c: _col(bloques0, c, np.nan if c in {"GENERACION","CMg","CV","Dolar","Margen"} else "")
                            for c in columnas_b})
    bloques["FECHA_HORA"] = pd.to_datetime(bloques.FECHA_HORA, errors="coerce")
    bloques["Fuente_Config_RIO"] = pd.to_datetime(bloques.Fuente_Config_RIO, errors="coerce")
    fuente = bloques.groupby("Etiqueta_Relacionada").Fuente_Config_RIO.agg(Partida="first", Detencion="last")
    ciclos["Inicio_Ciclo"] = pd.to_datetime(ciclos.Inicio_Ciclo, errors="coerce")
    ciclos["Termino_Ciclo"] = pd.to_datetime(ciclos.Termino_Ciclo, errors="coerce")
    ciclos = ciclos.merge(fuente, left_on="Etiqueta_Relacionada", right_index=True, how="left")
    ciclos["Antiguedad_Instruccion_Partida_min"] = (ciclos.Inicio_Ciclo-ciclos.Partida).dt.total_seconds()/60
    ciclos["Antiguedad_Instruccion_Detencion_min"] = (ciclos.Termino_Ciclo-ciclos.Detencion).dt.total_seconds()/60
    ciclos = ciclos.drop(columns=["Partida", "Detencion"])
    if "Candidatas_Tarifa" in x.sheet_names:
        candidatas = pd.read_excel(x, "Candidatas_Tarifa")
    else:
        candidatas = motor.candidatas_tarifa_configuracion(bloques0)
    return {"ciclos":ciclos, "bloques":bloques, "candidatas":candidatas,
            "empresas":empresas, "guia":guia}


def _diccionario(csvs: dict[str, pd.DataFrame], guia: pd.DataFrame) -> pd.DataFrame:
    gl = {}
    if {"Columna", "Que significa"}.issubset(guia.columns):
        gl = dict(zip(guia.Columna.astype(str), guia["Que significa"].astype(str)))
    filas = []
    unidades = {"GENERACION":"MWh", "CMg":"USD/MWh", "CV":"USD/MWh", "Dolar":"CLP/USD",
                "Margen":"CLP", "Total SC_PD":"CLP"}
    for archivo, df in csvs.items():
        for c in df.columns:
            filas.append({"archivo":archivo, "columna":c,
                          "significado":gl.get(c, c.replace("_", " ")),
                          "unidad":unidades.get(c, "min" if "min" in c else ""),
                          "origen":"Guia_Lectura" if c in gl else "salida del motor o formula spec 31"})
    return pd.DataFrame(filas)


def _agregar_tabla(writer, hoja: str, df: pd.DataFrame, nombre: str, formulas=None):
    df.to_excel(writer, sheet_name=hoja, index=False)
    ws = writer.sheets[hoja]; filas, cols = df.shape
    opciones = []
    formulas = formulas or {}
    for c in df.columns:
        item = {"header": c}
        if c in formulas: item["formula"] = formulas[c]
        opciones.append(item)
    if cols and filas:
        ws.add_table(0, 0, filas, cols-1, {"name":nombre, "columns":opciones, "style":"Table Style Medium 2"})
    ws.freeze_panes(1, 0)
    fecha = writer.book.add_format({"num_format":"dd-mm-yyyy hh:mm"})
    numero = writer.book.add_format({"num_format":"#,##0.00"})
    for i, c in enumerate(df.columns):
        ws.set_column(i, i, min(45, max(12, len(c)+2)), fecha if "FECHA" in c or "Ciclo" in c and c.startswith(("Inicio","Termino")) else numero if pd.api.types.is_numeric_dtype(df[c]) else None)


def _resumen_sumifs(ciclos: pd.DataFrame, campo: str) -> pd.DataFrame:
    valores = sorted(ciclos[campo].fillna("(vacio)").astype(str).unique())
    return pd.DataFrame({campo:valores, "Ciclos":0, "Costo_Partida":0., "Costo_Detencion":0., "Margen":0., "SC":0.})


def escribir_auditoria(ruta: Path, tablas: dict[str,pd.DataFrame], parametros: pd.DataFrame,
                       diccionario: pd.DataFrame, interruptores: dict[str,Any]) -> None:
    b = tablas["bloques"].copy(); c = tablas["ciclos"].copy(); cand = tablas["candidatas"].copy()
    b["Margen_recalc"] = 0.; c["Margen_recalc"] = 0.; c["Costo_Partida_recalc"] = 0.
    c["Costo_Detencion_recalc"] = 0.; c["SC_recalc"] = 0.; c["Check_SC"] = 0.; c["Check_Margen"] = 0.
    cand["Tarifa_max_recalc"] = 0.
    formulas_b = {}
    if not interruptores.get("MARGEN_NETEADO_POR_CICLO", 0) and interruptores.get("RESOLUCION_MARGEN", "bloque") != "hora":
        formulas_b["Margen_recalc"] = "=MAX(0,[@CMg]-[@CV])*[@Dolar]*[@GENERACION]"
    formulas_c = {
        "Margen_recalc":'=SUMIFS(Bloques[Margen_recalc],Bloques[Etiqueta_Relacionada],[@Etiqueta_Relacionada])',
        "Costo_Partida_recalc":'=[@Costo_Partida_Base]*[@Filtro_Conf_Partida]*[@Filtro_Disp_Partida]*[@Filtro_Op_Partida]*[@Filtro_CostoCero_Partida]',
        "Costo_Detencion_recalc":'=[@Costo_Detencion_Base]*[@Filtro_Conf_Detencion]*[@Filtro_Disp_Detencion]*[@Filtro_Op_Detencion]*[@Filtro_CostoCero_Detencion]',
        "SC_recalc":'=MAX(0,[@Costo_Partida_recalc]+[@Costo_Detencion_recalc]-[@Margen_Suma_Ciclo])',
        "Check_SC":'=[@SC_recalc]-[@[Total SC_PD]]', "Check_Margen":'=[@Margen_recalc]-[@Margen_Suma_Ciclo]'}
    formulas_cand = {"Tarifa_max_recalc":'=MAXIFS(Candidatas[Costo_Partida_ML],Candidatas[Etiqueta_Relacionada],[@Etiqueta_Relacionada],Candidatas[pasa_combustible],1,Candidatas[pasa_costo_cero],1)'}
    with pd.ExcelWriter(ruta, engine="xlsxwriter") as w:
        leeme = pd.DataFrame({"LEEME":["Paquete de auditoria SC-PD del Coordinador",
            "Los CSV son la fuente abierta para replicar este libro.",
            "SC = MAX(0, Costo Partida + Costo Detencion - Margen)",
            "Margen_recalc por bloque queda sin formula si el margen se netea por ciclo o usa resolucion hora.",
            "Interruptores:"] + [f"{k} = {v}" for k,v in interruptores.items()]})
        leeme.to_excel(w, sheet_name="Leeme", index=False); parametros.to_excel(w, sheet_name="Parametros", index=False)
        _agregar_tabla(w,"Ciclos",c,"Ciclos",formulas_c); _agregar_tabla(w,"Bloques",b,"Bloques",formulas_b)
        _agregar_tabla(w,"Candidatas",cand,"Candidatas",formulas_cand); _agregar_tabla(w,"Empresas",tablas["empresas"],"Empresas")
        for hoja, campo in (("Resumen_Empresa","Empresa"),("Resumen_Central","Central_Relacionada")):
            r = _resumen_sumifs(c, campo); _agregar_tabla(w,hoja,r,hoja)
            ws=w.sheets[hoja]
            ws.write(0, 7, "Filtro"); ws.data_validation(1,7,1,7,{"validate":"list","source":r[campo].tolist()})
            for fila in range(2,len(r)+2):
                clave=f"${xlsx_col(0)}{fila}"
                ws.write_formula(fila-1,1,f'=COUNTIF(Ciclos[{campo}],{clave})')
                for col, origen in enumerate(("Costo_Partida_Efectivo","Costo_Detencion_Efectivo","Margen_Suma_Ciclo","Total SC_PD"),2):
                    ws.write_formula(fila-1,col,f'=SUMIFS(Ciclos[{origen}],Ciclos[{campo}],{clave})')
        diccionario.to_excel(w,sheet_name="Diccionario",index=False)


def xlsx_col(n: int) -> str:
    s=""
    while True:
        n,r=divmod(n,26); s=chr(65+r)+s
        if n==0:return s
        n-=1


def generar_entrega(reporte: str | Path, rutas_entrada: dict[str,str] | None=None,
                    carpeta_salida: str | Path | None=None, tablas_dinamicas: bool=False,
                    panel: dict[str,Any] | None=None) -> Path:
    raiz=Path(__file__).resolve().parents[1]
    import sys
    if str(raiz/"src") not in sys.path: sys.path.insert(0,str(raiz/"src"))
    import sc_pd_motor_v7 as motor
    tablas=preparar_tablas(reporte,motor); ciclos=tablas["ciclos"]
    mes=pd.to_datetime(ciclos.Inicio_Ciclo,errors="coerce").dropna().min().strftime("%y%m")
    destino=Path(carpeta_salida) if carpeta_salida else Path(reporte).parent/f"Entrega_SCPD_{mes}"
    destino.mkdir(parents=True,exist_ok=True)
    ints=interruptores_panel(motor); ints.update(panel or {})
    rutas = dict(rutas_entrada) if rutas_entrada is not None else {
        nombre: str(getattr(motor, nombre, "")) for nombre in RUTAS_PANEL}
    # La salida del motor es asimismo la entrada principal de este empaquetador.
    rutas["REPORTE_MOTOR"] = str(reporte)
    parametros=tabla_parametros(type("Panel",(),{**vars(motor),**ints}),rutas,raiz)
    csvs={f"SCPD_{mes}_parametros.csv":parametros, f"SCPD_{mes}_bloques.csv":tablas["bloques"],
          f"SCPD_{mes}_ciclos.csv":tablas["ciclos"], f"SCPD_{mes}_candidatas_tarifa.csv":tablas["candidatas"],
          f"SCPD_{mes}_empresas.csv":tablas["empresas"]}
    dic=_diccionario(csvs,tablas["guia"]); csvs[f"SCPD_{mes}_diccionario.csv"]=dic
    for nombre,df in csvs.items(): df.to_csv(destino/nombre,index=False,encoding="utf-8-sig")
    auditoria=destino/f"SCPD_{mes}_Auditoria.xlsx"; escribir_auditoria(auditoria,tablas,parametros,dic,ints)
    if tablas_dinamicas:
        try:
            import win32com.client  # type: ignore
            _crear_tablas_dinamicas(auditoria, win32com.client)
        except Exception as exc:
            print(f"AVISO: no fue posible crear tablas dinamicas ({exc}); se conservan los resumenes SUMIFS.")
    print(f"Entrega creada en: {destino}")
    return destino


def _crear_tablas_dinamicas(ruta: Path, cliente: Any) -> None:
    """Reemplaza los resúmenes por pivots equivalentes cuando Excel está disponible."""
    excel = cliente.DispatchEx("Excel.Application"); excel.Visible = False
    libro = None
    try:
        libro = excel.Workbooks.Open(str(ruta.resolve()))
        origen = libro.Worksheets("Ciclos").ListObjects("Ciclos").Range
        cache = libro.PivotCaches().Create(1, origen)  # xlDatabase
        for hoja, campo in (("Resumen_Empresa", "Empresa"), ("Resumen_Central", "Central_Relacionada")):
            ws = libro.Worksheets(hoja); ws.Cells.Clear()
            pt = cache.CreatePivotTable(ws.Range("A3"), "Pivot" + hoja)
            pt.PivotFields(campo).Orientation = 1  # xlRowField
            for nombre, titulo in (("Costo_Partida_Efectivo","Costo Partida"),
                                   ("Costo_Detencion_Efectivo","Costo Detencion"),
                                   ("Margen_Suma_Ciclo","Margen"),("Total SC_PD","SC")):
                pt.AddDataField(pt.PivotFields(nombre), titulo, -4157)  # xlSum
            pt.PivotFields(campo).EnableMultiplePageItems = True
        libro.Save()
        print("Tablas dinamicas creadas con Excel; reemplazan los resumenes SUMIFS.")
    finally:
        if libro is not None: libro.Close(SaveChanges=True)
        excel.Quit()


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("reporte"); p.add_argument("--salida"); p.add_argument("--tablas-dinamicas",action="store_true")
    a=p.parse_args(); generar_entrega(a.reporte,carpeta_salida=a.salida,tablas_dinamicas=a.tablas_dinamicas)


if __name__=="__main__": main()
