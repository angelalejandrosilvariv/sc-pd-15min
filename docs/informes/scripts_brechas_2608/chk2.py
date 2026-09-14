import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
S = r"C:\Users\ANGEL~1.SIL\AppData\Local\Temp\claude\C--Kpi-SC-PD-5-a-6-Claude\993c7f16-aeaf-4559-9bdd-7f17479d2ac6\scratchpad"
SAL = r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Reporte_Sobrecostos_PD_Final.xlsx"
d = pd.read_excel(SAL, sheet_name="Detalle_15Min"); d["FECHA_HORA"] = pd.to_datetime(d["FECHA_HORA"])
v = d[(d["Central_Relacionada"] == "CMPCCORDILLERA") & (d["FECHA_HORA"] >= "2026-08-12 17:00") & (d["FECHA_HORA"] <= "2026-08-12 23:00")]
print(v.groupby(["Central", "CONSIGNAS"]).agg(bloques=("GENERACION", "size"), mwh=("GENERACION", "sum"), margen=("Margen", "sum")).to_string())
x2 = pd.read_excel(S + r"\xhyc_CMPCCORDILLERA.xlsx")
print("\nExcel CMPC configs y horas:", x2["central"].value_counts().to_dict())
m = d[d["Central_Relacionada"] == "CMPCCORDILLERA"].groupby("Central").agg(mwh=("GENERACION", "sum"), margen=("Margen", "sum"))
print("Motor CMPC por config:"); print(m.to_string())
c = pd.read_excel(r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Costos_de_P-D_Consolidado_2608.xlsx")
p = c[c["UNIDAD"] == "PENON_DIESEL"].groupby("DIA")["Partida_Fria"].agg(["min", "max"])
print("\nConsolidado 2608 PENON Partida_Fria por dia:"); print(p.to_string())
r = pd.read_excel(SAL, sheet_name="Resumen_Ciclos_PD")
print(r[r["Central_Relacionada"] == "PENON_DIESEL"][["Etiqueta_Relacionada", "Partida_Fria", "Config_RIO_Usada_Partida", "Costo_Partida_Base", "Costo_Partida_RIO_Instruida", "Costo_Partida_Base_Original"]].head(3).to_string(index=False))
