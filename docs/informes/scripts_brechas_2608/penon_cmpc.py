import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
S = r"C:\Users\ANGEL~1.SIL\AppData\Local\Temp\claude\C--Kpi-SC-PD-5-a-6-Claude\993c7f16-aeaf-4559-9bdd-7f17479d2ac6\scratchpad"
SAL = r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Reporte_Sobrecostos_PD_Final.xlsx"
x = pd.read_excel(S + r"\xhyc_PENON_DIESEL.xlsx")
p = x[x["Partida"] == "SI"][["fecha", "hora", "central", "part_fria", "part_tibia_i", "part_tibia_f", "part_cal", "tipo_partida", "COSTO_PARTIDA [$]", "USD", "Politica vigente"]]
print("EXCEL PENON partidas:"); print(p.head(6).to_string(index=False))
r = pd.read_excel(SAL, sheet_name="Resumen_Ciclos_PD")
m = r[r["Central_Relacionada"] == "PENON_DIESEL"][["Etiqueta_Relacionada", "Inicio_Ciclo", "Horas_Detenida_Ciclo", "Tipo_Partida", "Fria_Num1_M", "Tibia_Num2_N", "Caliente_Num1_P", "Partida_Fria", "Partida_Tibia", "Partida_Caliente", "Costo_Partida_Base", "Detencion_Tarifa"]]
print("\nMOTOR PENON:"); print(m.head(6).to_string(index=False))
c = pd.read_excel(r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Costos_de_P-D_Consolidado_2608.xlsx")
print("\nCostos consolidado 2608 PENON:"); print(c[c["UNIDAD"].astype(str).str.contains("PENON")].head(4).to_string(index=False))
# CMPC margen
x2 = pd.read_excel(S + r"\xhyc_CMPCCORDILLERA.xlsx")
x2["fh"] = pd.to_datetime(x2["fecha"].astype(str), format="%y%m%d") + pd.to_timedelta(x2["hora"].astype(int) - 1, unit="h")
w = x2[(x2["fh"] >= "2026-08-12 08:00") & (x2["fh"] <= "2026-08-12 23:00")][["fh", "generacion", "CMg", "CV", "USD", "Margen", "Ciclo de operación"]]
print("\nEXCEL CMPC Aug 12:"); print(w.to_string(index=False))
d = pd.read_excel(SAL, sheet_name="Detalle_15Min"); d["FECHA_HORA"] = pd.to_datetime(d["FECHA_HORA"])
v = d[(d["Central_Relacionada"] == "CMPCCORDILLERA") & (d["FECHA_HORA"] >= "2026-08-12 08:00") & (d["FECHA_HORA"] <= "2026-08-12 23:00")]
cols = [c for c in ["FECHA_HORA", "Central", "GENERACION", "CMg", "CV", "Dolar", "Margen"] if c in v.columns]
print("\nMOTOR CMPC Aug 12 (resumen por hora):")
v = v.assign(h=v["FECHA_HORA"].dt.floor("h")).groupby("h").agg(gen=("GENERACION", "sum"), margen=("Margen", "sum"), **({"cmg": ("CMg", "mean"), "cv": ("CV", "mean")} if "CMg" in v.columns else {}))
print(v.to_string())
