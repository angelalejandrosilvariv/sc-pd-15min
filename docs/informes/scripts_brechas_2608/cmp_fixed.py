"""Excel original vs Excel 'fixed' vs motor (agosto), por empresa y por central."""
from collections import defaultdict
import json, openpyxl, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.0f}")
OLD = r"C:\Kpi SC_PD\5 a 6\Claude\Sobrecostos_PD_2608 pre.xlsm"
NEW = r"C:\Kpi SC_PD\5 a 6\Sobrecostos_PD_2608 pre fixed.xlsm"
SAL = r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Reporte_Sobrecostos_PD_Final.xlsx"

def leer(xlsm):
    wb = openpyxl.load_workbook(xlsm, read_only=True, data_only=True, keep_links=False)
    ws = wb["Sobrecosto_Ciclo"]; rows = []
    for f in ws.iter_rows(min_row=2, values_only=True):
        if f[0] is None: continue
        n = lambda v: float(v) if isinstance(v, (int, float)) else 0.0
        ciclo, completo, c_p, c_d, margen, f_i, g_i, sc, emp = f[:9]
        rows.append({"Ciclo": str(ciclo), "Central": str(ciclo).split("&")[0], "Partida": n(c_p)+n(f_i),
                     "Detencion": n(c_d), "Margen": n(margen)+n(g_i), "SC": n(sc),
                     "Empresa": emp if isinstance(emp, str) else "",
                     "Traspasa": isinstance(emp, str) and emp.startswith("Se traspasa")})
    wb.close(); return pd.DataFrame(rows)

o, n = leer(OLD), leer(NEW)
print("hojas fixed:", openpyxl.load_workbook(NEW, read_only=True, keep_links=False).sheetnames)
print(f"ciclos: original {len(o)}  fixed {len(n)} | traspasados {o.Traspasa.sum()} / {n.Traspasa.sum()}")
print(f"TOTAL SC: original {o.SC.sum():,.0f}   fixed {n.SC.sum():,.0f}   delta {n.SC.sum()-o.SC.sum():+,.0f}")
m = pd.read_excel(SAL, sheet_name="SC_por_Empresa")[["Empresa","Total_SC_PD_CLP"]]
m["Empresa"] = m["Empresa"].str.strip()
e = pd.concat([o.groupby("Empresa").SC.sum().rename("Excel_orig"), n.groupby("Empresa").SC.sum().rename("Excel_fixed"),
               m.set_index("Empresa")["Total_SC_PD_CLP"].rename("Motor")], axis=1).fillna(0)
e = e[e.index != ""]
e["d_fixed_vs_orig"] = e.Excel_fixed - e.Excel_orig; e["d_motor_vs_fixed"] = e.Motor - e.Excel_fixed
e = e[e.abs().sum(axis=1) > 0].sort_values("Excel_fixed", ascending=False)
print(e.to_string()); print(f"\nsuma |motor-orig| {(e.Motor-e.Excel_orig).abs().sum():,.0f}   suma |motor-fixed| {e.d_motor_vs_fixed.abs().sum():,.0f}")
c = pd.concat([o.groupby("Central").agg(o_ciclos=("SC","size"), o_SC=("SC","sum"), o_margen=("Margen","sum"), o_partida=("Partida","sum"), o_det=("Detencion","sum")),
               n.groupby("Central").agg(n_ciclos=("SC","size"), n_SC=("SC","sum"), n_margen=("Margen","sum"), n_partida=("Partida","sum"), n_det=("Detencion","sum"))], axis=1).fillna(0)
c["dSC"] = c.n_SC - c.o_SC
c = c[(c.dSC.abs() > 1) | (c.o_ciclos != c.n_ciclos)].sort_values("dSC", key=abs, ascending=False)
print("\nCENTRALES QUE CAMBIAN ENTRE ORIGINAL Y FIXED:"); print(c.to_string())
n.to_pickle("excel_fixed_ciclos.pkl"); o.to_pickle("excel_orig_ciclos.pkl")
