"""Diagnostico de causa raiz, ciclo a ciclo, agosto 2026, solo ciclos que inician y terminan en el mes.
Descompone dSC exactamente en efecto partida / detencion / margen (sustitucion secuencial) y
asigna cada efecto a una causa raiz usando los internos del Excel (flags de xHyC) y del motor (Obs)."""
import openpyxl, pandas as pd, numpy as np
pd.set_option("display.width", 260); pd.set_option("display.float_format", lambda v: f"{v:,.0f}")
S = r"C:\Users\ANGEL~1.SIL\AppData\Local\Temp\claude\C--Kpi-SC-PD-5-a-6-Claude\993c7f16-aeaf-4559-9bdd-7f17479d2ac6\scratchpad"
NEW = r"C:\Kpi SC_PD\5 a 6\Sobrecostos_PD_2608 pre fixed.xlsm"

# ---- internos del Excel por ciclo (xHyC completo) ----
wb = openpyxl.load_workbook(NEW, read_only=True, data_only=True, keep_links=False)
ws = wb["Sobrecosto_PD xHyC"]; it = ws.iter_rows(values_only=True); hdr = list(next(it)); ix = {h: i for i, h in enumerate(hdr) if h}
n = lambda v: float(v) if isinstance(v, (int, float)) else 0.0
acc = {}
for r in it:
    c = r[ix["Ciclo de operación"]]
    if c is None: continue
    a = acc.setdefault(str(c), {"p_flag": 0, "d_flag": 0, "U": 0.0, "V": 0.0, "pruebas_p": 0, "conf_p": 0, "configs_p": set()})
    if r[ix["Partida"]] == "SI":
        a["p_flag"] += 1; a["U"] = max(a["U"], n(r[ix["COSTO_PARTIDA [$]"]])); a["configs_p"].add(str(r[ix["central"]]))
        if n(r[ix["Disponible (1) / Pruebas (0)"]]) == 0: a["pruebas_p"] += 1
        if n(r[ix["Conf despachada RIO"]]) == 0: a["conf_p"] += 1
    if r[ix["Detencion"]] == "SI":
        a["d_flag"] += 1; a["V"] = max(a["V"], n(r[ix["COSTO_DETENCION [$]"]]))
wb.close()
xi = pd.DataFrame.from_dict(acc, orient="index"); xi["configs_p"] = xi["configs_p"].map(len)

p = pd.read_pickle(S + r"\pares_solo_mes.pkl")
p = p.merge(xi, left_on="Excel", right_index=True, how="left")
ENLASA = {"PENON_DIESEL", "TENO_DIESEL", "TRAPEN_DIESEL"}
sc = lambda P, D, M: max(0.0, P + D - M)

def diag(r):
    """Devuelve (efecto_P, causa_P, efecto_D, causa_D, efecto_M, causa_M)."""
    if r.Motor == "": return (0, "", 0, "", -r.Ex_SC, "R1b ciclo solo en Excel (apareo)")
    if not r.pareado: return (r.Mo_SC, "R1 parada corta: ciclo solo en el motor", 0, "", 0, "")
    eP = sc(r.Mo_P, r.Ex_D, r.Ex_M) - sc(r.Ex_P, r.Ex_D, r.Ex_M)
    eD = sc(r.Mo_P, r.Mo_D, r.Ex_M) - sc(r.Mo_P, r.Ex_D, r.Ex_M)
    eM = sc(r.Mo_P, r.Mo_D, r.Mo_M) - sc(r.Mo_P, r.Mo_D, r.Ex_M)
    obsP, obsD = str(r.Obs_P), str(r.Obs_D)
    # --- partida ---
    if abs(r.Mo_P - r.Ex_P) <= 1: cP = ""
    elif r.Ex_P == 0:
        if r.p_flag == 0: cP = "R2 Excel no marca la partida"
        elif r.U == 0 and r.pruebas_p > 0: cP = "R4 Excel anula por lista Pruebas"
        elif r.U == 0 and r.conf_p > 0: cP = "R4b Excel anula por combustible"
        else: cP = "R3 Excel no asocia la instruccion RIO al ciclo (factor 0)"
    elif r.Mo_P == 0:
        if "Sin Motivo" in obsP: cP = "R5 motor rechaza: RIO sin motivo (Excel paga por &1 / hora exacta)"
        elif "Pruebas (EP)" in obsP: cP = "R5b motor rechaza: RIO dice EP"
        elif "Sin tarifa" in obsP: cP = "R8 motor sin historia (horas nulas)"
        else: cP = "R5c motor rechaza: " + obsP[:30]
    else:
        cP = "R7 tarifa: politica PO de mitad de mes" if r.Central in ENLASA else "R6 tarifa: configuracion elegida (max Excel vs combustible instruido)"
    # --- detencion ---
    if abs(r.Mo_D - r.Ex_D) <= 1: cD = ""
    elif r.Ex_D == 0:
        if r.d_flag == 0: cD = "R2 Excel no marca la detencion"
        elif r.V == 0: cD = "R4 Excel anula la detencion (Pruebas/combustible)"
        else: cD = "R3 Excel no asocia la instruccion RIO al ciclo (factor 0)"
    elif r.Mo_D == 0:
        if "Sin Motivo" in obsD: cD = "R5 motor rechaza: RIO sin motivo (Excel paga por &1 / hora exacta)"
        elif "Pruebas (EP)" in obsD: cD = "R5b motor rechaza: RIO dice EP"
        elif "Sin tarifa" in obsD: cD = "R8b motor sin tarifa de detencion"
        else: cD = "R5c motor rechaza: " + obsD[:30]
    else:
        cD = "R7 tarifa: politica PO de mitad de mes" if r.Central in ENLASA else "R6 tarifa: configuracion elegida (max Excel vs combustible instruido)"
    # --- margen ---
    if abs(r.Mo_M - r.Ex_M) <= 1: cM = ""
    else: cM = "R9 margen: truncado por bloque (motor) vs por hora (Excel)" if r.Mo_M > r.Ex_M else "R9b margen: Excel acredita mas"
    return (eP, cP, eD, cD, eM, cM)

d = p.apply(lambda r: pd.Series(diag(r), index=["eP", "cP", "eD", "cD", "eM", "cM"]), axis=1)
p = pd.concat([p, d], axis=1)
assert (abs(p.eP + p.eD + p.eM - p.dSC) < 1).all()

ef = pd.concat([p[["Empresa", "Central", "Motor", "Excel", "eP", "cP"]].rename(columns={"eP": "efecto", "cP": "causa"}),
                p[["Empresa", "Central", "Motor", "Excel", "eD", "cD"]].rename(columns={"eD": "efecto", "cD": "causa"}),
                p[["Empresa", "Central", "Motor", "Excel", "eM", "cM"]].rename(columns={"eM": "efecto", "cM": "causa"})])
ef = ef[(ef.causa != "") & (ef.efecto.abs() > 0.5)]
print(f"dSC total {p.dSC.sum():+,.0f} | suma efectos {ef.efecto.sum():+,.0f} | |efectos| {ef.efecto.abs().sum():,.0f}")
print("\nCAUSA RAIZ (efecto exacto sobre el SC, todas las empresas):")
g = ef.groupby("causa").agg(n=("efecto", "size"), neto=("efecto", "sum"), bruto=("efecto", lambda s: s.abs().sum())).sort_values("bruto", ascending=False)
print(g.to_string())
print("\nCAUSA RAIZ x EMPRESA (|efecto| > 250 k):")
ge = ef.groupby(["Empresa", "causa"]).agg(n=("efecto", "size"), neto=("efecto", "sum")).reset_index()
ge = ge[ge.neto.abs() > 250000].sort_values(["Empresa", "neto"], key=lambda s: s if s.name == "Empresa" else s.abs(), ascending=[True, False])
print(ge.to_string(index=False))
print("\nCAUSA RAIZ x CENTRAL (|efecto| > 1 MM):")
gc = ef.groupby(["Central", "causa"]).agg(n=("efecto", "size"), neto=("efecto", "sum")).reset_index()
gc = gc[gc.neto.abs() > 1e6].sort_values("neto", key=abs, ascending=False)
print(gc.to_string(index=False))
with pd.ExcelWriter(S + r"\Diagnostico_2608.xlsx", engine="xlsxwriter") as w:
    g.reset_index().to_excel(w, sheet_name="Causa_raiz", index=False)
    ge.to_excel(w, sheet_name="Causa_x_Empresa", index=False)
    gc.to_excel(w, sheet_name="Causa_x_Central", index=False)
    ef.sort_values("efecto", key=abs, ascending=False).to_excel(w, sheet_name="Efectos", index=False)
    p.to_excel(w, sheet_name="Pares", index=False)
p.to_pickle(S + r"\pares_diag.pkl")
