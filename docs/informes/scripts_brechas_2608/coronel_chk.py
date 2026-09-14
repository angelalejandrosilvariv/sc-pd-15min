import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
S = r"C:\Users\ANGEL~1.SIL\AppData\Local\Temp\claude\C--Kpi-SC-PD-5-a-6-Claude\993c7f16-aeaf-4559-9bdd-7f17479d2ac6\scratchpad"
SAL = r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Reporte_Sobrecostos_PD_Final.xlsx"
d = pd.read_excel(SAL, sheet_name="Detalle_15Min"); d["FECHA_HORA"] = pd.to_datetime(d["FECHA_HORA"])
cols = ["FECHA_HORA", "Central", "GENERACION", "CONSIGNAS", "MOTIVO", "ESTADO OPERACIONAL", "Fuente_Config_RIO", "Filtro_Operacional"]
print("CORONEL cierre Aug 6 (Excel det=0, motor paga):")
print(d[(d["Central_Relacionada"] == "CORONEL") & (d["FECHA_HORA"] >= "2026-08-06 19:00") & (d["FECHA_HORA"] <= "2026-08-06 20:45")][cols].to_string(index=False))
print("\nCORONEL cierre Aug 7 21:00 (Excel &7 det=0):")
print(d[(d["Central_Relacionada"] == "CORONEL") & (d["FECHA_HORA"] >= "2026-08-07 19:30") & (d["FECHA_HORA"] <= "2026-08-07 21:00")][cols].to_string(index=False))
x = pd.read_excel(S + r"\xhyc_CORONEL.xlsx")
x["fh"] = pd.to_datetime(x["fecha"].astype(str), format="%y%m%d") + pd.to_timedelta(x["hora"].astype(int) - 1, unit="h")
print("\nExcel CORONEL Aug 6 17:00-20:00 / Aug 7 17:00-20:00:")
print(x[(x["fh"] >= "2026-08-06 17:00") & (x["fh"] <= "2026-08-06 20:00") | (x["fh"] >= "2026-08-07 17:00") & (x["fh"] <= "2026-08-07 20:00")][["fh", "generacion", "Ciclo de operación", "Partida", "Detencion", "COSTO_DETENCION [$]", "Programación", "Disponible (1) / Pruebas (0)"]].to_string(index=False))
print("\nExcel CORONEL Aug 13 22:00 - Aug 14 08:00 (motor ve parada 00:00-06:45):")
print(x[(x["fh"] >= "2026-08-13 22:00") & (x["fh"] <= "2026-08-14 08:00")][["fh", "generacion", "Generación_neta", "Ciclo de operación", "Partida", "Detencion"]].to_string(index=False))
