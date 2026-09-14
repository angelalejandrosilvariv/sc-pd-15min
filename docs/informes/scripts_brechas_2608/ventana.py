"""Excel (xHyC) vs motor (Detalle_15Min) en una ventana de tiempo para una central."""
import sys
import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
S = r"C:\Users\ANGEL~1.SIL\AppData\Local\Temp\claude\C--Kpi-SC-PD-5-a-6-Claude\993c7f16-aeaf-4559-9bdd-7f17479d2ac6\scratchpad"
SAL = r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Reporte_Sobrecostos_PD_Final.xlsx"
PATRON, T0, T1 = sys.argv[1], pd.Timestamp(sys.argv[2]), pd.Timestamp(sys.argv[3])
x = pd.read_excel(S + rf"\xhyc_{PATRON}.xlsx")
x["fh"] = pd.to_datetime(x["fecha"].astype(str), format="%y%m%d") + pd.to_timedelta(x["hora"].astype(int) - 1, unit="h")
w = x[(x["fh"] >= T0) & (x["fh"] <= T1)].sort_values(["fh", "central"])
print("EXCEL xHyC:")
print(w[["fh", "central", "generacion", "Generación_neta", "Ciclo de operación", "Partida", "Detencion", "CMg", "CV", "Margen", "Disponible (1) / Pruebas (0)"]].to_string(index=False))
d = pd.read_excel(SAL, sheet_name="Detalle_15Min")
d = d[d["Central_Relacionada"].str.contains(PATRON.split("_")[0])]
d["FECHA_HORA"] = pd.to_datetime(d["FECHA_HORA"])
v = d[(d["FECHA_HORA"] >= T0) & (d["FECHA_HORA"] <= T1)].sort_values(["FECHA_HORA", "Central"])
print("\nMOTOR Detalle_15Min:")
cols = [c for c in ["FECHA_HORA", "Central", "GENERACION", "Margen", "Etiqueta_Relacionada", "CONSIGNAS", "MOTIVO", "ESTADO OPERACIONAL", "Configuracion RIO"] if c in v.columns]
print(v[cols].to_string(index=False))
