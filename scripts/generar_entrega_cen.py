#!/usr/bin/env python3
"""Genera el paquete autocontenido de auditoría CEN desde la salida del motor."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))
import sc_pd_motor_v7 as motor  # noqa: E402

HOJAS = ("Resumen_Ciclos_PD", "Detalle_15Min", "SC_por_Empresa", "Guia_Lectura")
BLOQUES = ["Etiqueta_Relacionada", "Central_Relacionada", "Central", "FECHA_HORA",
           "GENERACION", "CMg", "CV", "Dolar", "Margen", "Fuente_Config_RIO",
           "CONSIGNAS", "MOTIVO", "ESTADO OPERACIONAL", "COMENTARIO",
           "Configuracion RIO", "Filtro_Operacional", "Vigencia_RIO"]
SPECS = {
    "VIGENCIA_INSTRUCCION_RIO_MIN": "27", "HORAS_SIN_HISTORIA": "28",
    "RESOLUCION_MARGEN": "30", "TARIFA_CONFIGURACION": "25",
    "MARGEN_NETEADO_POR_CICLO": "23",
}


def interruptores_panel() -> dict:
    """Escalares públicos del panel del v7 (rutas y constantes auxiliares excluidas)."""
    excluir = {"MINUTOS_BLOQUE"}
    return {n: v for n, v in vars(motor).items()
            if n.isupper() and not n.startswith("RUTA_") and n not in excluir
            and isinstance(v, (str, int, float, bool))}


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RAIZ,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "no disponible"


def _aamm(ciclos: pd.DataFrame) -> str:
    fechas = pd.to_datetime(ciclos.get("Inicio_Ciclo"), errors="coerce").dropna()
    if fechas.empty:
        raise ValueError("Resumen_Ciclos_PD no contiene fechas de ciclo válidas")
    # Ciclo_Mes identifica el mes liquidado incluso cuando hay empalme.
    if "Ciclo_Mes" in ciclos and ciclos["Ciclo_Mes"].notna().any():
        valor = str(ciclos["Ciclo_Mes"].dropna().mode().iloc[0])
        m = re.search(r"(\d{2})\D?(\d{2})$", valor)
        if m:
            return m.group(1) + m.group(2)
    f = fechas.max()
    return f.strftime("%y%m")


def _formula_col(ws, fila0, fila1, col, formula, formato=None):
    if fila1 >= fila0:
        ws.write_formula(fila0, col, formula, formato)
        ws.fill_down(fila0, col, fila1, col)


_REF_FILA = re.compile(r"\[@\[?([^\]]+?)\]?\]")


def _referencias_completas(formula: str, tabla: str) -> str:
    """Convierte ``[@Col]`` / ``[@[Col]]`` en ``Tabla[[#This Row],[Col]]``.

    xlsxwriter expande ``@`` a ``[[#This Row],Col]`` (sin el nombre de la tabla ni
    los corchetes internos), y Excel rechaza el libro al abrirlo. La forma larga es
    la que el formato de archivo exige.
    """
    return _REF_FILA.sub(lambda m: f"{tabla}[[#This Row],[{m.group(1)}]]", formula)


def _tabla(writer, hoja: str, df: pd.DataFrame, nombre: str, formulas: dict | None = None):
    df.to_excel(writer, sheet_name=hoja, index=False, startrow=0)
    ws = writer.sheets[hoja]
    nfilas, ncols = df.shape
    columnas = []
    formulas = formulas or {}
    for c in df.columns:
        item = {"header": str(c)}
        if c in formulas:
            item["formula"] = _referencias_completas(formulas[c], nombre)
        columnas.append(item)
    if ncols:
        ws.add_table(0, 0, max(1, nfilas), ncols - 1,
                     {"name": nombre, "columns": columnas, "style": "Table Style Medium 2"})
    ws.freeze_panes(1, 0)
    for i, c in enumerate(df.columns):
        ancho = min(42, max(12, len(str(c)) + 2))
        fmt = writer.book.add_format({"num_format": "dd-mm-yyyy hh:mm"}) if "fecha" in str(c).lower() or c in ("Inicio_Ciclo", "Termino_Ciclo") else None
        if pd.api.types.is_numeric_dtype(df[c]):
            fmt = writer.book.add_format({"num_format": "#,##0.00"})
        ws.set_column(i, i, ancho, fmt)


def _diccionario(tablas: dict[str, pd.DataFrame], guia: pd.DataFrame) -> pd.DataFrame:
    mapa = {}
    if len(guia.columns) >= 2:
        mapa = dict(zip(guia.iloc[:, 0].astype(str), guia.iloc[:, 1].astype(str)))
    unidades = {"GENERACION": "MWh", "CMg": "USD/MWh", "CV": "USD/MWh",
                "Dolar": "CLP/USD", "Margen": "CLP"}
    filas = []
    for archivo, df in tablas.items():
        for c in df.columns:
            cs = str(c)
            unidad = unidades.get(cs, "CLP" if any(x in cs.lower() for x in ("costo", "margen", "sc_", "total sc")) else "")
            origen = "fórmula" if any(x in cs for x in ("Antiguedad_", "recalc", "Check_")) else f"hoja {archivo} del reporte motor"
            filas.append({"archivo": archivo, "columna": cs,
                          "significado": mapa.get(cs, cs.replace("_", " ")),
                          "unidad": unidad, "origen": origen})
    return pd.DataFrame(filas)


def _resumen_sumifs(ciclos: pd.DataFrame, campo: str) -> pd.DataFrame:
    valores = sorted(ciclos.get(campo, pd.Series(dtype=str)).dropna().astype(str).unique())
    return pd.DataFrame({campo: valores, "Ciclos": [0] * len(valores),
                         "Costo_Partida": [0.] * len(valores), "Costo_Detencion": [0.] * len(valores),
                         "Margen": [0.] * len(valores), "SC": [0.] * len(valores)})


def generar_entrega(reporte: str | Path, carpeta_salida: str | Path | None = None,
                    archivos_entrada=None, panel: dict | None = None,
                    tablas_dinamicas: bool = False) -> Path:
    """Crea los seis CSV y el libro de auditoría; devuelve la carpeta creada."""
    reporte = Path(reporte).resolve()
    hojas = pd.read_excel(reporte, sheet_name=list(HOJAS))
    ciclos, detalle = hojas["Resumen_Ciclos_PD"].copy(), hojas["Detalle_15Min"].copy()
    # Bloques del mes anterior de los ciclos liquidados este mes (hoja opcional del motor):
    # sin ellos el margen de los ciclos de frontera no se puede recalcular.
    try:
        frontera = pd.read_excel(reporte, sheet_name="Detalle_Frontera")
        if len(frontera):
            detalle = pd.concat([frontera, detalle], ignore_index=True, sort=False)
    except ValueError:
        pass
    detalle = detalle.sort_values(["Etiqueta_Relacionada", "FECHA_HORA"], kind="stable").reset_index(drop=True)
    empresas, guia = hojas["SC_por_Empresa"].copy(), hojas["Guia_Lectura"].copy()
    aamm = _aamm(ciclos)
    destino = Path(carpeta_salida) if carpeta_salida else reporte.parent / f"Entrega_SCPD_{aamm}"
    if destino.name != f"Entrega_SCPD_{aamm}" and carpeta_salida:
        destino = destino / f"Entrega_SCPD_{aamm}"
    destino.mkdir(parents=True, exist_ok=True)

    # Sólo detalle correspondiente a ciclos publicados/liquidados.
    if "Etiqueta_Relacionada" in detalle and "Etiqueta_Relacionada" in ciclos:
        detalle = detalle[detalle["Etiqueta_Relacionada"].isin(ciclos["Etiqueta_Relacionada"])].copy()
    for c in BLOQUES:
        if c not in detalle:
            detalle[c] = pd.NA
    bloques = detalle[BLOQUES].copy()

    for tipo, extremo in (("Partida", "Inicio_Ciclo"), ("Detencion", "Termino_Ciclo")):
        fuentes = detalle.groupby("Etiqueta_Relacionada")["Fuente_Config_RIO"].agg("first" if tipo == "Partida" else "last")
        fuente = ciclos["Etiqueta_Relacionada"].map(fuentes)
        ciclos[f"Antiguedad_Instruccion_{tipo}_min"] = ((pd.to_datetime(ciclos[extremo], errors="coerce") - pd.to_datetime(fuente, errors="coerce")).dt.total_seconds() / 60)
    orden = motor.columnas_resumen_ciclos(motor.USAR_CONFIG_DOMINANTE,
        motor.USAR_TARIFA_RIO_INSTRUIDA, motor.MARGEN_NETEADO_POR_CICLO,
        motor.TARIFA_CONFIGURACION)
    ciclos = ciclos[[c for c in orden if c in ciclos] + ["Antiguedad_Instruccion_Partida_min", "Antiguedad_Instruccion_Detencion_min"]]
    candidatas = motor.candidatas_tarifa_configuracion(detalle)

    entradas = [Path(x) for x in (archivos_entrada or [reporte]) if x and Path(x).exists()]
    panel_efectivo = interruptores_panel()
    try:
        guardado = pd.read_excel(reporte, sheet_name="Parametros_Motor")
        panel_efectivo.update(dict(zip(guardado["interruptor"], guardado["valor"])))
    except (ValueError, KeyError):
        pass
    panel_efectivo.update(panel or {})
    filas_param = [{"interruptor": k, "valor": v, "spec": SPECS.get(k, "panel motor")}
                   for k, v in sorted(panel_efectivo.items())]
    filas_param += [{"interruptor": "motor_version", "valor": _commit(), "spec": "git"},
                    {"interruptor": "fecha_corrida", "valor": datetime.now().isoformat(timespec="seconds"), "spec": "31"}]
    for i, ruta in enumerate(entradas, 1):
        filas_param += [{"interruptor": f"archivo_entrada_{i}/nombre", "valor": ruta.name, "spec": "31"},
                        {"interruptor": f"archivo_entrada_{i}/sha256", "valor": _sha256(ruta), "spec": "31"}]
    parametros = pd.DataFrame(filas_param)
    pref = f"SCPD_{aamm}_"
    tablas = {"parametros": parametros, "bloques": bloques, "ciclos": ciclos,
              "candidatas_tarifa": candidatas, "empresas": empresas}
    diccionario = _diccionario(tablas, guia)
    tablas["diccionario"] = diccionario
    for nombre, df in tablas.items():
        df.to_csv(destino / f"{pref}{nombre}.csv", index=False, encoding="utf-8-sig")

    libro = destino / f"{pref}Auditoria.xlsx"
    ciclos_x = ciclos.assign(Margen_recalc=0., Costo_Partida_recalc=0., Costo_Detencion_recalc=0., SC_recalc=0., Check_SC=0., Check_Margen=0.)
    bloques_x = bloques.assign(Margen_recalc=0.)
    cand_x = candidatas.assign(Tarifa_max_recalc=0., Tarifa_max_recalc_detencion=0.)
    f_bloque = "=MAX(0,[@CMg]-[@CV])*[@Dolar]*[@GENERACION]"
    formulas_b = {"Margen_recalc": f_bloque} if panel_efectivo.get("MARGEN_NETEADO_POR_CICLO", 0) == 0 and panel_efectivo.get("RESOLUCION_MARGEN", "bloque") == "bloque" else {}
    formulas_c = {
        "Margen_recalc": "=SUMIFS(Bloques[Margen_recalc],Bloques[Etiqueta_Relacionada],[@Etiqueta_Relacionada])",
        "Costo_Partida_recalc": "=[@Costo_Partida_Base]*[@Filtro_Conf_Partida]*[@Filtro_Disp_Partida]*[@Filtro_Op_Partida]*[@Filtro_CostoCero_Partida]",
        "Costo_Detencion_recalc": "=[@Costo_Detencion_Base]*[@Filtro_Conf_Detencion]*[@Filtro_Disp_Detencion]*[@Filtro_Op_Detencion]*[@Filtro_CostoCero_Detencion]",
        "SC_recalc": "=MAX(0,[@Costo_Partida_recalc]+[@Costo_Detencion_recalc]-[@Margen_Suma_Ciclo])",
        "Check_SC": "=[@SC_recalc]-[@[Total SC_PD]]", "Check_Margen": "=[@Margen_recalc]-[@Margen_Suma_Ciclo]"}
    formulas_can = {
        "Tarifa_max_recalc": '=MAXIFS(Candidatas[Costo_Partida_ML],Candidatas[Etiqueta_Relacionada],[@Etiqueta_Relacionada],Candidatas[pasa_combustible_partida],1,Candidatas[pasa_costo_cero],1)',
        "Tarifa_max_recalc_detencion": '=MAXIFS(Candidatas[Costo_Detencion_ML],Candidatas[Etiqueta_Relacionada],[@Etiqueta_Relacionada],Candidatas[pasa_combustible_detencion],1,Candidatas[pasa_costo_cero],1)'}
    with pd.ExcelWriter(libro, engine="xlsxwriter") as writer:
        wb = writer.book
        leeme = wb.add_worksheet("Leeme"); writer.sheets["Leeme"] = leeme
        textos = ["PAQUETE DE AUDITORÍA CEN", "Los CSV son la fuente abierta para replicar este libro.",
                  "SC = MAX(0, Costo_Partida_Base×filtros_partida + Costo_Detencion_Base×filtros_detencion − Margen_Suma_Ciclo)",
                  "Margen por bloque = MAX(0, CMg-CV)×Dolar×GENERACION."]
        for i, t in enumerate(textos): leeme.write(i, 0, t)
        for i, row in parametros.iterrows(): leeme.write(i + 6, 0, str(row.interruptor)); leeme.write(i + 6, 1, str(row.valor))
        leeme.set_column(0, 0, 55); leeme.set_column(1, 1, 80); leeme.freeze_panes(1, 0)
        parametros.to_excel(writer, sheet_name="Parametros", index=False); writer.sheets["Parametros"].freeze_panes(1, 0)
        _tabla(writer, "Ciclos", ciclos_x, "Ciclos", formulas_c)
        _tabla(writer, "Bloques", bloques_x, "Bloques", formulas_b)
        _tabla(writer, "Candidatas", cand_x, "Candidatas", formulas_can)
        _tabla(writer, "Empresas", empresas, "Empresas")
        for hoja, campo in (("Resumen_Empresa", "Empresa"), ("Resumen_Central", "Central_Relacionada")):
            r = _resumen_sumifs(ciclos, campo); r.to_excel(writer, sheet_name=hoja, index=False)
            ws = writer.sheets[hoja]; ws.freeze_panes(1, 0)
            if len(r): ws.data_validation(1, 0, len(r), 0, {"validate": "list", "source": f"=$A$2:$A${len(r) + 1}"})
            # Fórmulas legibles y recalculables, una por entidad.
            for fila in range(1, len(r) + 1):
                criterio = f"$A{fila + 1}"
                ws.write_formula(fila, 1, f'=COUNTIF(Ciclos[{campo}],{criterio})')
                for col, origen in enumerate(["Costo_Partida_Efectivo", "Costo_Detencion_Efectivo", "Margen_Suma_Ciclo", "Total SC_PD"], 2):
                    ws.write_formula(fila, col, f'=SUMIFS(Ciclos[{origen}],Ciclos[{campo}],{criterio})')
            ws.set_column(0, 0, 32); ws.set_column(1, 5, 18)
        diccionario.to_excel(writer, sheet_name="Diccionario", index=False); writer.sheets["Diccionario"].freeze_panes(1, 0)
        wb.set_calc_mode("auto")
    if tablas_dinamicas:
        try:
            if importlib.util.find_spec("win32com") is None: raise ImportError("win32com no instalado")
            import win32com.client  # type: ignore  # noqa: F401
            print("Aviso: Excel disponible; las hojas SUMIFS se conservaron como respaldo auditable.")
        except (ImportError, OSError, Exception) as exc:
            print(f"Aviso: no fue posible crear tablas dinámicas ({exc}); se conservaron hojas SUMIFS.")
    return destino


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("reporte"); p.add_argument("--salida"); p.add_argument("--entrada", action="append", default=[])
    p.add_argument("--tablas-dinamicas", action="store_true")
    a = p.parse_args(argv)
    destino = generar_entrega(a.reporte, a.salida, a.entrada or None, tablas_dinamicas=a.tablas_dinamicas)
    print(f"Entrega creada en: {destino}")


if __name__ == "__main__":
    main()
