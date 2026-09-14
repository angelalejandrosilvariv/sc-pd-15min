import pandas as pd
S = r"C:\Users\ANGEL~1.SIL\AppData\Local\Temp\claude\C--Kpi-SC-PD-5-a-6-Claude\993c7f16-aeaf-4559-9bdd-7f17479d2ac6\scratchpad"
SAL = r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Reporte_Sobrecostos_PD_Final.xlsx"
d = pd.read_excel(SAL, sheet_name="Detalle_15Min")
d = d[d["Central_Relacionada"] == "MEJILLONES-CTM3_TG1+TV1"].copy()
d["FECHA_HORA"] = pd.to_datetime(d["FECHA_HORA"])
for t0, t1 in [("2026-08-06 14:00", "2026-08-06 23:00"), ("2026-08-17 09:00", "2026-08-17 16:00"),
               ("2026-08-26 16:00", "2026-08-27 06:00"), ("2026-08-27 14:00", "2026-08-28 06:00"), ("2026-08-28 15:00", "2026-08-29 06:00")]:
    v = d[(d["FECHA_HORA"] >= t0) & (d["FECHA_HORA"] <= t1)]
    g = v.groupby(["Central", "CONSIGNAS"]).agg(bloques=("GENERACION", "size"), mwh=("GENERACION", "sum"), desde=("FECHA_HORA", "min"), hasta=("FECHA_HORA", "max"))
    print(f"\n{t0} -> {t1}"); print(g.to_string())
