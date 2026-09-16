#!/usr/bin/env python3
"""Comparador oficial del motor v7 con el libro horario del CEN.

El modulo es deliberadamente importable: la lectura, el apareo y la
descomposicion se pueden probar sin ejecutar el programa ni usar datos reales.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
import pandas as pd

ALCANCE_MES = "Mes completo"
ALCANCE_PROPIO = "Solo ciclos del mes"
ENLASA = {"PENON_DIESEL", "TENO_DIESEL", "TRAPEN_DIESEL"}


def _numero(v: Any) -> float:
    return float(v) if isinstance(v, (int, float)) and not pd.isna(v) else 0.0


def _texto(v: Any) -> str:
    return "" if v is None or pd.isna(v) else str(v).strip()


def _fecha_hora(fecha: Any, hora: Any) -> pd.Timestamp | pd.NaT:
    """Convierte fecha AAMMDD y hora CEN 1..24 al inicio de la hora."""
    if isinstance(fecha, (pd.Timestamp, __import__("datetime").datetime, __import__("datetime").date)):
        dia = pd.Timestamp(fecha).normalize()
    else:
        s = _texto(fecha).split(".")[0].zfill(6)
        dia = pd.to_datetime(s, format="%y%m%d", errors="coerce")
    h = pd.to_numeric(hora, errors="coerce")
    if pd.isna(dia) or pd.isna(h) or not 1 <= int(h) <= 24:
        return pd.NaT
    return dia + pd.Timedelta(hours=int(h) - 1)


def _hoja(wb: openpyxl.Workbook, nombre: str) -> tuple[list[str], list[tuple]]:
    it = wb[nombre].iter_rows(values_only=True)
    encabezado = [_texto(x) for x in next(it)]
    return encabezado, list(it)


def leer_excel_horario(ruta: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Lee una sola vez el xlsm, siempre en modo read-only/data-only."""
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True, keep_links=False)
    try:
        hc, rc = _hoja(wb, "Sobrecosto_Ciclo")
        hx, rx = _hoja(wb, "Sobrecosto_PD xHyC")
        hp, rp = _hoja(wb, "PARTIDAS_DETENCIONES")
    finally:
        wb.close()
    ciclos = _sin_columnas_duplicadas(pd.DataFrame(rc, columns=hc))
    xhyc = _sin_columnas_duplicadas(pd.DataFrame(rx, columns=hx))
    pd_int = _sin_columnas_duplicadas(pd.DataFrame(rp, columns=hp))
    # El libro real trae en Sobrecosto_Ciclo columnas auxiliares 'Ciclo' y 'Copia Ciclo'
    # (columnas Q y J) que chocarian con el renombre de 'Ciclo de operacion' -> 'Ciclo'.
    ciclos = ciclos.drop(columns=[c for c in ("Ciclo", "Copia Ciclo") if c in ciclos.columns])
    return ciclos, xhyc, pd_int


def _sin_columnas_duplicadas(df: pd.DataFrame) -> pd.DataFrame:
    """Conserva la primera aparicion de cada encabezado (el libro real repite '' y nombres)."""
    return df.loc[:, ~df.columns.duplicated()]


def preparar_ciclos_excel(ciclos: pd.DataFrame, xhyc: pd.DataFrame) -> pd.DataFrame:
    """Normaliza el resumen horario y deriva fechas exclusivamente desde xHyC."""
    c = ciclos.copy()
    ren = {"Ciclo de operación": "Ciclo", "Total Costos Partida": "Ex_P",
           "Total Costos Detención": "Ex_D", "Total Margen": "Ex_M",
           "Total Costos Partida ciclo inconcluso": "Herencia_P",
           "Margen ciclo inconcluso": "Herencia_M", "Total Sobrecosto_P-D": "Ex_SC",
           "Empresa": "Empresa", "SSCC": "SSCC"}
    c = c.rename(columns=ren)
    for col in ("Ex_P", "Ex_D", "Ex_M", "Herencia_P", "Herencia_M", "Ex_SC"):
        c[col] = pd.to_numeric(c.get(col, 0), errors="coerce").fillna(0.0)
    c["Ciclo"] = c["Ciclo"].map(_texto)
    # El libro real arrastra miles de filas vacias bajo la tabla (read_only las entrega).
    c = c[c["Ciclo"] != ""].copy()
    c["Central"] = c["Ciclo"].str.rsplit("&", n=1).str[0].str.strip()
    c["Empresa"] = c.get("Empresa", "").map(_texto)
    c["Traspasa"] = c["Empresa"].str.casefold().eq("se traspasa al proximo mes")
    c["SC_Propio"] = (c.Ex_P + c.Ex_D - c.Ex_M).clip(lower=0)

    x = xhyc.copy()
    x["Ciclo"] = x["Ciclo de operación"].map(_texto)
    x["Fecha_Hora"] = [_fecha_hora(f, h) for f, h in zip(x["fecha"], x["hora"])]
    x["generacion_n"] = pd.to_numeric(x["generacion"], errors="coerce").fillna(0)
    gen = x[(x.Ciclo != "") & (x.generacion_n > 0) & x.Fecha_Hora.notna()]
    fechas = gen.groupby("Ciclo").Fecha_Hora.agg(inicio="min", fin="max")
    c = c.merge(fechas, left_on="Ciclo", right_index=True, how="left")
    return c


def internos_excel(xhyc: pd.DataFrame, partidas: pd.DataFrame) -> pd.DataFrame:
    """Agrega los flags y costos internos utilizados por el diagnostico original."""
    filas: list[dict[str, Any]] = []
    for ciclo, g in xhyc.assign(_c=xhyc["Ciclo de operación"].map(_texto)).groupby("_c"):
        if not ciclo:
            continue
        pf = g["Partida"].map(_texto).str.upper().eq("SI")
        df = g["Detencion"].map(_texto).str.upper().eq("SI")
        num = lambda col: pd.to_numeric(g.get(col, 0), errors="coerce").fillna(0)
        filas.append({"Ciclo": ciclo, "p_flag": int(pf.sum()), "d_flag": int(df.sum()),
                      "U": float(num("COSTO_PARTIDA [$]")[pf].max()) if pf.any() else 0,
                      "V": float(num("COSTO_DETENCION [$]")[df].max()) if df.any() else 0,
                      "pruebas_p": int((pf & num("Disponible (1) / Pruebas (0)").eq(0)).sum()),
                      "conf_p": int((pf & num("Conf despachada RIO").eq(0)).sum())})
    out = pd.DataFrame(filas).set_index("Ciclo") if filas else pd.DataFrame()
    if not partidas.empty and "Clave Ciclo " in partidas:
        q = partidas.copy(); q["Ciclo"] = q["Clave Ciclo "].map(_texto)
        for col in ("Instrucción", "Presta SSCC"):
            if col not in q: q[col] = ""
        z = q.groupby("Ciclo").agg(Instruccion=("Instrucción", lambda s: "|".join(filter(None, map(_texto, s)))),
                                    Presta_SSCC=("Presta SSCC", "max"))
        out = out.join(z, how="outer")
    return out


def aparear_ciclos(motor: pd.DataFrame, excel: pd.DataFrame) -> pd.DataFrame:
    """Aparea por central y traslape; la hora Excel cubre hasta minuto 59."""
    usados: set[Any] = set(); filas = []
    for i, m in motor.sort_values("Inicio_Ciclo").iterrows():
        cand = excel[(excel.Central == _texto(m.Central_Relacionada)) &
                     (excel.inicio <= m.Termino_Ciclo) &
                     (excel.fin + pd.Timedelta(minutes=59) >= m.Inicio_Ciclo) &
                     ~excel.index.isin(usados)].sort_values("inicio")
        j = cand.index[0] if len(cand) else None
        if j is not None: usados.add(j)
        filas.append(_fila_par(m, excel.loc[j] if j is not None else None))
    for j, e in excel.loc[~excel.index.isin(usados)].iterrows():
        filas.append(_fila_par(None, e))
    return pd.DataFrame(filas)


def _fila_par(m: pd.Series | None, e: pd.Series | None) -> dict[str, Any]:
    getm = lambda k, d=0: d if m is None or pd.isna(m.get(k, d)) else m.get(k, d)
    gete = lambda k, d=0: d if e is None or pd.isna(e.get(k, d)) else e.get(k, d)
    return {"Empresa": _texto(getm("Empresa", gete("Empresa", ""))),
            "Central": _texto(getm("Central_Relacionada", gete("Central", ""))),
            "Motor": _texto(getm("Etiqueta_Relacionada", "")), "Excel": _texto(gete("Ciclo", "")),
            "Inicio_Motor": getm("Inicio_Ciclo", pd.NaT), "Fin_Motor": getm("Termino_Ciclo", pd.NaT),
            "Inicio_Excel": gete("inicio", pd.NaT), "Fin_Excel": gete("fin", pd.NaT),
            "Mo_P": _numero(getm("Costo_Partida_Efectivo")), "Ex_P": _numero(gete("P_Comparacion", gete("Ex_P"))),
            "Mo_D": _numero(getm("Costo_Detencion_Efectivo")), "Ex_D": _numero(gete("Ex_D")),
            "Mo_M": _numero(getm("Margen_Suma_Ciclo")), "Ex_M": _numero(gete("M_Comparacion", gete("Ex_M"))),
            "Mo_SC": _numero(getm("Total SC_PD")), "Ex_SC": _numero(gete("SC_Comparacion", gete("Ex_SC"))),
            "Obs_P": _texto(getm("Obs_Partida", "")), "Obs_D": _texto(getm("Obs_Detencion", "")),
            "Config_Tarifa": _texto(getm("Config_Tarifa_Partida", "")),
            "Config_RIO": _texto(getm("Config_RIO_Usada_Partida", "")), "Tipo": _texto(getm("Tipo_Partida", "")),
            "Vigencia_P": getm("Vigencia_RIO_Partida", np.nan), "Vigencia_D": getm("Vigencia_RIO_Detencion", np.nan),
            "pareado": m is not None and e is not None}


def _sc(p: float, d: float, margen: float) -> float:
    return max(0.0, p + d - margen)


def descomponer_efectos(pares: pd.DataFrame) -> pd.DataFrame:
    """Sustitucion P, luego D, luego M, respetando MAX(0,...)."""
    p = pares.copy(); p["dSC"] = p.Mo_SC - p.Ex_SC
    solo_e = p.Motor.eq(""); solo_m = ~p.pareado & ~solo_e
    p["Efecto_P"] = [_sc(r.Mo_P, r.Ex_D, r.Ex_M)-_sc(r.Ex_P, r.Ex_D, r.Ex_M) for r in p.itertuples()]
    p["Efecto_D"] = [_sc(r.Mo_P, r.Mo_D, r.Ex_M)-_sc(r.Mo_P, r.Ex_D, r.Ex_M) for r in p.itertuples()]
    p["Efecto_M"] = [_sc(r.Mo_P, r.Mo_D, r.Mo_M)-_sc(r.Mo_P, r.Mo_D, r.Ex_M) for r in p.itertuples()]
    p.loc[solo_e, ["Efecto_P", "Efecto_D", "Efecto_M"]] = np.c_[np.zeros(solo_e.sum()), np.zeros(solo_e.sum()), -p.loc[solo_e, "Ex_SC"]]
    p.loc[solo_m, ["Efecto_P", "Efecto_D", "Efecto_M"]] = np.c_[p.loc[solo_m, "Mo_SC"], np.zeros(solo_m.sum()), np.zeros(solo_m.sum())]
    if not np.allclose(p.Efecto_P + p.Efecto_D + p.Efecto_M, p.dSC, atol=2):
        raise AssertionError("La suma de efectos no reproduce el delta SC")
    return p


def _rechazo_motor(obs: str, vigencia: Any) -> str:
    o = obs.casefold()
    if "sin motivo" in o: return "R5 sin motivo"
    if "pruebas (ep)" in o or " dice ep" in o: return "R5 EP"
    if "fuera de vigencia" in o or (not pd.isna(vigencia) and _numero(vigencia) == 0): return "R5 fuera de vigencia"
    if "sin historia" in o or "sin tarifa" in o: return "R5 sin historia"
    return "R5 motor rechaza por RIO"


def asignar_causas(pares: pd.DataFrame, internos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = pares.merge(internos, left_on="Excel", right_index=True, how="left") if not internos.empty else pares.copy()
    causas = []
    for r in p.itertuples():
        if not r.Motor: cp, cd, cm = "", "", "R1b ciclo solo en el Excel"
        elif not r.pareado: cp, cd, cm = "R1 ciclo solo en el motor", "", ""
        else:
            pf, df = _numero(getattr(r, "p_flag", 0)), _numero(getattr(r, "d_flag", 0))
            instr = _texto(getattr(r, "Instruccion", ""))
            if abs(r.Mo_P-r.Ex_P) <= 1: cp = ""
            elif r.Ex_P == 0:
                if pf == 0: cp = "R2 Excel no marca la partida"
                elif _numero(getattr(r, "U", 0)) == 0 and _numero(getattr(r, "pruebas_p", 0)) > 0: cp = "R4 anulada por Pruebas"
                elif _numero(getattr(r, "U", 0)) == 0 and _numero(getattr(r, "conf_p", 0)) > 0: cp = "R4 anulada por combustible"
                elif not instr: cp = "R3 Excel no asocia la instruccion"
                else: cp = "R3 Excel no asocia la instruccion"
            elif r.Mo_P == 0: cp = _rechazo_motor(r.Obs_P, r.Vigencia_P)
            elif r.Central in ENLASA: cp = "R7 tarifa por politica PO"
            else: cp = "R6 tarifa por configuracion"
            if abs(r.Mo_D-r.Ex_D) <= 1: cd = ""
            elif r.Ex_D == 0:
                if df == 0: cd = "R2 Excel no marca la detencion"
                elif _numero(getattr(r, "V", 0)) == 0: cd = "R4 anulada por Pruebas/combustible"
                elif not instr: cd = "R3 Excel no asocia la instruccion"
                else: cd = "R3 Excel no asocia la instruccion"
            elif r.Mo_D == 0: cd = _rechazo_motor(r.Obs_D, r.Vigencia_D)
            elif r.Central in ENLASA: cd = "R7 tarifa por politica PO"
            else: cd = "R6 tarifa por configuracion"
            cm = "" if abs(r.Mo_M-r.Ex_M) <= 1 else "R9 margen por bloque vs hora"
        causas.append((cp, cd, cm))
    p[["Causa_P", "Causa_D", "Causa_M"]] = causas
    piezas = []
    for ef, ca in (("Efecto_P", "Causa_P"), ("Efecto_D", "Causa_D"), ("Efecto_M", "Causa_M")):
        z = p[["Empresa", "Central", "Motor", "Excel", ef, ca]].rename(columns={ef:"Efecto", ca:"Causa"})
        piezas.append(z[(z.Causa != "") & (z.Efecto.abs() > .5)])
    return p, pd.concat(piezas, ignore_index=True)


def _resumen(alcance: str, motor: pd.DataFrame, excel: pd.DataFrame) -> dict[str, Any]:
    mo, ex = motor["Total SC_PD"].sum(), excel.SC_Comparacion.sum()
    return {"Alcance": alcance, "Ciclos_Motor": len(motor), "Ciclos_Excel": len(excel),
            "SC_Motor": mo, "SC_Excel": ex, "Delta": mo-ex, "Delta_pct": (mo/ex-1)*100 if ex else np.nan}


def comparar(ruta_motor: str | Path, ruta_excel: str | Path, ruta_salida: str | Path) -> dict[str, pd.DataFrame]:
    motor = pd.read_excel(ruta_motor, sheet_name="Resumen_Ciclos_PD")
    for col in ("Inicio_Ciclo", "Termino_Ciclo"): motor[col] = pd.to_datetime(motor[col], errors="coerce")
    ciclos0, xhyc, pd_int = leer_excel_horario(ruta_excel)
    excel = preparar_ciclos_excel(ciclos0, xhyc)
    # El mes liquidado es el de los ciclos que inician y terminan en el; el minimo de
    # Inicio_Ciclo apuntaria al mes anterior cuando hay empalme.
    propios = motor.loc[motor.Estado_Ciclo_Mes.eq("Inicia y termina este mes"), "Inicio_Ciclo"].dropna()
    mes = (propios.min() if len(propios) else motor.Termino_Ciclo.dropna().max()).to_period("M")
    inicio_mes, fin_mes = mes.start_time, mes.end_time
    excel_mes = excel[~excel.Traspasa].copy(); excel_mes["SC_Comparacion"] = excel_mes.Ex_SC
    # El SC publicado del libro es MAX(0, C + D + F - E - G): la partida y el margen heredados
    # del mes anterior entran a la partida y al margen para que la descomposicion cierre.
    excel_mes["P_Comparacion"] = excel_mes.Ex_P + excel_mes.Herencia_P
    excel_mes["M_Comparacion"] = excel_mes.Ex_M + excel_mes.Herencia_M
    motor_mes = motor[(motor.Inicio_Ciclo <= fin_mes) & (motor.Termino_Ciclo >= inicio_mes)].copy()
    excel_propio = excel_mes[(excel_mes.inicio > inicio_mes) & (excel_mes.inicio <= fin_mes)].copy()
    excel_propio["SC_Comparacion"] = excel_propio.SC_Propio
    excel_propio["P_Comparacion"] = excel_propio.Ex_P; excel_propio["M_Comparacion"] = excel_propio.Ex_M
    motor_propio = motor[motor.Estado_Ciclo_Mes.eq("Inicia y termina este mes")].copy()
    ints = internos_excel(xhyc, pd_int)
    todos = []; res = []
    for nombre, mo, ex in ((ALCANCE_MES, motor_mes, excel_mes), (ALCANCE_PROPIO, motor_propio, excel_propio)):
        q = descomponer_efectos(aparear_ciclos(mo, ex)); q, ef = asignar_causas(q, ints)
        q.insert(0, "Alcance", nombre); ef.insert(0, "Alcance", nombre); todos.append((q, ef)); res.append(_resumen(nombre, mo, ex))
    pares = pd.concat([x[0] for x in todos], ignore_index=True); efectos = pd.concat([x[1] for x in todos], ignore_index=True)
    resumen = pd.DataFrame(res)
    empresa = pares.groupby(["Alcance", "Empresa"], dropna=False).agg(SC_Motor=("Mo_SC","sum"), SC_Excel=("Ex_SC","sum"), Delta=("dSC","sum")).reset_index()
    empresa["Delta_pct"] = empresa.Delta / empresa.SC_Excel.replace(0, np.nan) * 100
    causa = efectos.groupby(["Alcance","Causa"]).agg(n=("Efecto","size"), Neto=("Efecto","sum"), Bruto=("Efecto",lambda s:s.abs().sum())).reset_index().sort_values(["Alcance","Bruto"], ascending=[True,False])
    causa_emp = efectos.groupby(["Alcance","Empresa","Causa"]).agg(n=("Efecto","size"), Neto=("Efecto","sum"), Bruto=("Efecto",lambda s:s.abs().sum())).reset_index()
    frontera_m = motor[~motor.Estado_Ciclo_Mes.eq("Inicia y termina este mes")].copy(); frontera_m.insert(0,"Origen","Motor fuera del mes")
    frontera_e = excel[excel.Ciclo.str.endswith("&1")].copy(); frontera_e.insert(0,"Origen","Excel &1 con herencia")
    frontera = pd.concat([frontera_m, frontera_e], ignore_index=True, sort=False)
    hojas = {"Resumen":resumen, "Por_Empresa":empresa, "Pares":pares, "Causa_Raiz":causa,
             "Causa_x_Empresa":causa_emp, "Ciclos_Excel":excel, "Frontera":frontera}
    with pd.ExcelWriter(ruta_salida, engine="xlsxwriter") as w:
        for nombre, tabla in hojas.items(): tabla.to_excel(w, sheet_name=nombre, index=False)
    for nombre in ("Resumen", "Por_Empresa", "Causa_Raiz"):
        print(f"\n{nombre}\n{hojas[nombre].to_string(index=False)}")
    return hojas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("motor"); ap.add_argument("excel_horario"); ap.add_argument("salida")
    a = ap.parse_args(); comparar(a.motor, a.excel_horario, a.salida)


if __name__ == "__main__": main()
