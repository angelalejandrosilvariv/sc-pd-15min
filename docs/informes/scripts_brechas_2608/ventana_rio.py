"""Impacto de restringir la busqueda del RIO a +/- W minutos alrededor de la partida/detencion.
Usa el RIO de agosto (local) y la salida del motor; solo ciclos que inician y terminan en agosto."""
import pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.0f}")
W = r"C:\Kpi SC_PD\5 a 6\Claude\sc-pd-15min-main\Carpeta_de_Trabajo"
SAL = W + r"\Reporte_Sobrecostos_PD_Final.xlsx"
dic = pd.read_excel(W + r"\Diccionario_central_config.xlsx", sheet_name=0)
dic = dict(zip(dic.iloc[:, 0].astype(str).str.strip(), dic.iloc[:, 1].astype(str).str.strip()))
rio = pd.read_excel(W + r"\RIO_08_2026.xlsx", skiprows=4)
rio.columns = [str(c).strip().upper() for c in rio.columns]
rio = rio.rename(columns={"CON": "CONSIGNAS", "MOT": "MOTIVO", "EO": "ESTADO OPERACIONAL"})
rio["FECHA"] = pd.to_datetime(rio["FECHA"], errors="coerce"); h = rio["HORA"].astype(str).str.strip()
rio["T"] = pd.to_datetime(rio["FECHA"].dt.strftime("%Y-%m-%d") + " " + h.str.replace("24:00", "00:00", regex=False), errors="coerce")
rio.loc[h.str.startswith("24:00"), "T"] += pd.Timedelta(days=1)
rio["REL"] = rio["NOMBRE CONFIGURACIÓN"].astype(str).str.strip().map(dic).fillna(rio["NOMBRE CONFIGURACIÓN"].astype(str).str.strip())
for c in ("CONSIGNAS", "MOTIVO", "ESTADO OPERACIONAL"): rio[c] = rio[c].astype(str).str.strip().replace({"nan": "", "-": ""})
rio["COMENTARIO"] = rio["COMENTARIO"].astype(str).replace({"nan": ""})
rio = rio.dropna(subset=["T"]).sort_values("T")
def pasa(row):
    sscc = bool(pd.Series([row.COMENTARIO]).str.contains("SSCC|CTF|CSF|CPF", case=False).iloc[0])
    return (row.MOTIVO == "OM") or (row["ESTADO OPERACIONAL"] == "PDO") or (row.MOTIVO == "OT" and sscc)
def mejor_en_ventana(rel, t, atras, adelante):
    sub = rio[(rio.REL == rel) & (rio["T"] >= t - pd.Timedelta(minutes=atras)) & (rio["T"] <= t + pd.Timedelta(minutes=adelante))]
    if sub.empty: return None, None
    ok = sub[sub.apply(pasa, axis=1) & (sub.CONSIGNAS != "EP")]
    if len(ok): return True, ok.iloc[0]
    return False, sub.iloc[-1]
r = pd.read_excel(SAL, sheet_name="Resumen_Ciclos_PD")
m = r[r.Estado_Ciclo_Mes == "Inicia y termina este mes"].copy()
m["Inicio_Ciclo"] = pd.to_datetime(m.Inicio_Ciclo); m["Termino_Ciclo"] = pd.to_datetime(m.Termino_Ciclo)
ap = m[(m.Obs_Partida == "Aprobado") & (m.Costo_Partida_Efectivo > 0)]
ad = m[(m.Obs_Detencion == "Aprobado") & (m.Costo_Detencion_Efectivo > 0)]
print(f"Partidas aprobadas con costo: {len(ap)} ({ap.Costo_Partida_Efectivo.sum():,.0f}); detenciones: {len(ad)} ({ad.Costo_Detencion_Efectivo.sum():,.0f})")
print(f"\n{'ventana':>16} | {'partidas que caen':>17} {'CLP':>14} | {'detenciones que caen':>20} {'CLP':>14}")
res = {}
for atras in (30, 60, 120, 180, 240):
    fp = [i for i, x in ap.iterrows() if mejor_en_ventana(x.Central_Relacionada, x.Inicio_Ciclo, atras, 30)[0] is not True]
    fd = [i for i, x in ad.iterrows() if mejor_en_ventana(x.Central_Relacionada, x.Termino_Ciclo, atras, 30)[0] is not True]
    res[atras] = (fp, fd)
    print(f"-{atras:>4} / +30 min | {len(fp):>17} {ap.loc[fp].Costo_Partida_Efectivo.sum():>14,.0f} | {len(fd):>20} {ad.loc[fd].Costo_Detencion_Efectivo.sum():>14,.0f}")
fp, fd = res[30]
print("\nPARTIDAS sin instruccion valida en -30/+30 min (que hoy se aprueban con la ultima instruccion vigente):")
rows = []
for i in fp:
    x = ap.loc[i]; ok, reg = mejor_en_ventana(x.Central_Relacionada, x.Inicio_Ciclo, 24*60, 30)
    rows.append({"ciclo": x.Etiqueta_Relacionada, "inicio": x.Inicio_Ciclo, "instr_usada": reg["T"] if reg is not None else None,
                 "min_antes": (x.Inicio_Ciclo - reg["T"]).total_seconds()/60 if reg is not None else None,
                 "consigna": reg.CONSIGNAS if reg is not None else "", "motivo": reg.MOTIVO if reg is not None else "", "costo": x.Costo_Partida_Efectivo, "SC": x["Total SC_PD"]})
print(pd.DataFrame(rows).sort_values("costo", ascending=False).to_string(index=False))
print("\nDETENCIONES sin instruccion valida en -30/+30 min:")
rows = []
for i in fd:
    x = ad.loc[i]; ok, reg = mejor_en_ventana(x.Central_Relacionada, x.Termino_Ciclo, 24*60, 30)
    rows.append({"ciclo": x.Etiqueta_Relacionada, "fin": x.Termino_Ciclo, "instr_usada": reg["T"] if reg is not None else None,
                 "min_antes": (x.Termino_Ciclo - reg["T"]).total_seconds()/60 if reg is not None else None,
                 "consigna": reg.CONSIGNAS if reg is not None else "", "motivo": reg.MOTIVO if reg is not None else "", "costo": x.Costo_Detencion_Efectivo, "SC": x["Total SC_PD"]})
print(pd.DataFrame(rows).sort_values("costo", ascending=False).to_string(index=False))
