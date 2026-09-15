"""Ciclos del Excel con fechas (desde xHyC extraido) vs ciclos del motor, para una central."""
import sys
import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.1f}")
S = r"C:\Users\ANGEL~1.SIL\AppData\Local\Temp\claude\C--Kpi-SC-PD-5-a-6-Claude\993c7f16-aeaf-4559-9bdd-7f17479d2ac6\scratchpad"
SAL = r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo\Reporte_Sobrecostos_PD_Final.xlsx"
PATRON = sys.argv[1]
x = pd.read_excel(S + rf"\xhycF_{PATRON}.xlsx")
x["fh"] = pd.to_datetime(x["fecha"].astype(str), format="%y%m%d") + pd.to_timedelta(x["hora"].astype(int) - 1, unit="h")
x = x[x["generacion"].fillna(0) > 0]
g = (x.groupby("Ciclo de operación")
      .agg(inicio=("fh", "min"), fin=("fh", "max"), horas=("fh", "size"), configs=("central", "nunique"),
           gen=("generacion", "sum"), partida=("COSTO_PARTIDA [$]", "max"), detencion=("COSTO_DETENCION [$]", "max"),
           margen=("Margen", "sum"), pruebas0=("Disponible (1) / Pruebas (0)", lambda s: int((s == 0).sum())))
      .sort_values("inicio"))
print("EXCEL:"); print(g.to_string())
m = pd.read_excel(SAL, sheet_name="Resumen_Ciclos_PD")
m = m[m["Central_Relacionada"].str.contains(PATRON.split("_")[0])]
print("\nMOTOR:")
print(m[["Etiqueta_Relacionada", "Inicio_Ciclo", "Termino_Ciclo", "Generacion_Suma_Ciclo", "Margen_Suma_Ciclo",
         "Costo_Partida_Efectivo", "Obs_Partida", "Costo_Detencion_Efectivo", "Obs_Detencion", "Total SC_PD"]]
      .sort_values("Inicio_Ciclo").to_string(index=False))
d = pd.read_excel(SAL, sheet_name="Detalle_15Min")
d = d[d["Central_Relacionada"].str.contains(PATRON.split("_")[0])]
print("\nDETALLE motor (bloques):", len(d), "| columnas:", [c for c in d.columns][:30])
