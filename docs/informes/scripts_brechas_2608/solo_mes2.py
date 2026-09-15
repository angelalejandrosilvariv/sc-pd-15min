"""Agosto 2026, solo ciclos que inician y terminan en el mes, SIN herencia de julio.
Excel corregido: SC propio = MAX(0, partida + detencion - margen) de sus propias columnas
(se ignoran 'ciclo inconcluso'); se excluyen traspasados y ciclos que ya generaban a la hora 1.
Motor: Estado_Ciclo_Mes == 'Inicia y termina este mes'.
Aparea ciclo Excel <-> ciclo motor por central y traslape temporal y descompone la diferencia."""
import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.0f}")
S = r"C:\Users\ANGEL~1.SIL\AppData\Local\Temp\claude\C--Kpi-SC-PD-5-a-6-Claude\993c7f16-aeaf-4559-9bdd-7f17479d2ac6\scratchpad"
SAL = r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Reporte_Sobrecostos_PD_Final.xlsx"

ex = pd.read_pickle(S + r"\excel_fixed_fechas.pkl")
ex = ex[~ex.Traspasa & (ex["inicio"] > pd.Timestamp("2026-08-01 00:00"))].copy()
ex["SC_propio"] = (ex.Partida + ex.Detencion - ex.Margen).clip(lower=0)
ex["fin_h"] = ex["fin"] + pd.Timedelta(minutes=59)
mo = pd.read_excel(SAL, sheet_name="Resumen_Ciclos_PD")
mo["Empresa"] = mo["Empresa"].astype(str).str.strip()
mo = mo[mo["Estado_Ciclo_Mes"] == "Inicia y termina este mes"].copy()
for c in ("Inicio_Ciclo", "Termino_Ciclo"): mo[c] = pd.to_datetime(mo[c])

# ---- apareo por central + traslape ----
pares = []; usados = set()
for i, m in mo.iterrows():
    cand = ex[(ex.Central == m.Central_Relacionada) & (ex["inicio"] <= m.Termino_Ciclo) & (ex["fin_h"] >= m.Inicio_Ciclo) & ~ex.index.isin(usados)]
    if len(cand):
        j = cand.index[0]; usados.add(j); pares.append((i, j))
    else:
        pares.append((i, None))
sin_par_ex = ex[~ex.index.isin(usados)]

filas = []
for i, j in pares:
    m = mo.loc[i]; e = ex.loc[j] if j is not None else None
    filas.append({"Empresa": m.Empresa, "Central": m.Central_Relacionada, "Motor": m.Etiqueta_Relacionada,
                  "Excel": e.Ciclo if e is not None else "", "Inicio": m.Inicio_Ciclo,
                  "Mo_P": m.Costo_Partida_Efectivo, "Ex_P": e.Partida if e is not None else 0,
                  "Mo_D": m.Costo_Detencion_Efectivo, "Ex_D": e.Detencion if e is not None else 0,
                  "Mo_M": m.Margen_Suma_Ciclo, "Ex_M": e.Margen if e is not None else 0,
                  "Mo_SC": m["Total SC_PD"], "Ex_SC": e.SC_propio if e is not None else 0,
                  "Obs_P": m.Obs_Partida, "Obs_D": m.Obs_Detencion, "Config_Tarifa": m.Config_Tarifa_Partida,
                  "Config_RIO": m.Config_RIO_Usada_Partida, "Tipo": m.Tipo_Partida, "pareado": e is not None})
for j, e in sin_par_ex.iterrows():
    filas.append({"Empresa": e.Empresa, "Central": e.Central, "Motor": "", "Excel": e.Ciclo, "Inicio": e["inicio"],
                  "Mo_P": 0, "Ex_P": e.Partida, "Mo_D": 0, "Ex_D": e.Detencion, "Mo_M": 0, "Ex_M": e.Margen,
                  "Mo_SC": 0, "Ex_SC": e.SC_propio, "Obs_P": "", "Obs_D": "", "Config_Tarifa": "", "Config_RIO": "", "Tipo": "", "pareado": False})
p = pd.DataFrame(filas)
p["dSC"] = p.Mo_SC - p.Ex_SC

def causa(r):
    if r.Motor == "": return "ciclo solo en Excel"
    if not r.pareado: return "ciclo solo en motor"
    if abs(r.dSC) < 1: return "identico"
    c = []
    if (r.Mo_P == 0) != (r.Ex_P == 0): c.append("filtro partida")
    elif abs(r.Mo_P - r.Ex_P) > 1: c.append("tarifa partida")
    if (r.Mo_D == 0) != (r.Ex_D == 0): c.append("filtro detencion")
    elif abs(r.Mo_D - r.Ex_D) > 1: c.append("tarifa detencion")
    if abs(r.Mo_M - r.Ex_M) > 1: c.append("margen")
    return " + ".join(c) if c else "otro"
p["Causa"] = p.apply(causa, axis=1)

print(f"Excel solo mes (sin herencia): {len(ex)} ciclos, SC propio {ex.SC_propio.sum():,.0f}  (SC publicado {ex.SC.sum():,.0f})")
print(f"Motor solo mes: {len(mo)} ciclos, SC {mo['Total SC_PD'].sum():,.0f}   delta {mo['Total SC_PD'].sum() - ex.SC_propio.sum():+,.0f} "
      f"({100*(mo['Total SC_PD'].sum()/ex.SC_propio.sum()-1):+.1f}%)")
print(f"pares: {int(p.pareado.sum())} | solo motor: {int(((p.Motor != '') & ~p.pareado).sum())} | solo Excel: {int((p.Motor == '').sum())}")
print(f"suma |dSC| por ciclo: {p.dSC.abs().sum():,.0f}")

print("\nPOR CAUSA (todas las empresas):")
g = p.groupby("Causa").agg(ciclos=("dSC", "size"), delta=("dSC", "sum"), abs_delta=("dSC", lambda s: s.abs().sum())).sort_values("abs_delta", ascending=False)
print(g.to_string())

print("\nPOR EMPRESA:")
e = p.groupby("Empresa").agg(Ex_SC=("Ex_SC", "sum"), Mo_SC=("Mo_SC", "sum"), delta=("dSC", "sum")).sort_values("delta", key=abs, ascending=False)
e["pct"] = (e.delta / e.Ex_SC.where(e.Ex_SC > 0) * 100)
print(e.to_string(formatters={"pct": lambda v: "n/a" if pd.isna(v) else f"{v:+.0f}%"}))

print("\nPOR EMPRESA x CAUSA (|delta| > 300 k):")
ec = p.groupby(["Empresa", "Causa"]).agg(ciclos=("dSC", "size"), delta=("dSC", "sum")).reset_index()
ec = ec[ec.delta.abs() > 300000].sort_values(["Empresa", "delta"], key=lambda s: s if s.name == "Empresa" else s.abs(), ascending=[True, False])
print(ec.to_string(index=False))

print("\nTOP 30 CICLOS POR |dSC|:")
cols = ["Empresa", "Motor", "Excel", "Inicio", "Ex_P", "Mo_P", "Ex_D", "Mo_D", "Ex_M", "Mo_M", "Ex_SC", "Mo_SC", "dSC", "Causa", "Obs_P", "Tipo"]
print(p.sort_values("dSC", key=abs, ascending=False)[cols].head(30).to_string(index=False))
with pd.ExcelWriter(S + r"\SoloMes_2608_pares.xlsx", engine="xlsxwriter") as w:
    p.sort_values(["Empresa", "Central", "Inicio"]).to_excel(w, sheet_name="Pares", index=False)
    e.reset_index().to_excel(w, sheet_name="Por_Empresa", index=False)
    ec.to_excel(w, sheet_name="Empresa_x_Causa", index=False)
p.to_pickle(S + r"\pares_solo_mes.pkl")
