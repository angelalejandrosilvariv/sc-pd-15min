"""Filas hora-central del Excel (Sobrecosto_PD xHyC) para una central: ciclos con fechas."""
import sys
import openpyxl
import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.0f}")
XLSM = r"C:\Kpi SC_PD\5 a 6\Sobrecostos_PD_2608 pre fixed.xlsm"
PATRON = sys.argv[1]
wb = openpyxl.load_workbook(XLSM, read_only=True, data_only=True, keep_links=False)
ws = wb["Sobrecosto_PD xHyC"]
rows = ws.iter_rows(values_only=True)
hdr = list(next(rows))
print({i: h for i, h in enumerate(hdr) if h is not None})
data = [r for r in rows if r and any(isinstance(v, str) and PATRON in v for v in r[:6])]
wb.close()
df = pd.DataFrame(data, columns=[h if h else f"c{i}" for i, h in enumerate(hdr)][:len(data[0])])
out = r"C:\Users\ANGEL~1.SIL\AppData\Local\Temp\claude\C--Kpi-SC-PD-5-a-6-Claude\993c7f16-aeaf-4559-9bdd-7f17479d2ac6\scratchpad\xhycF_" + PATRON.replace("/", "_") + ".xlsx"
df.to_excel(out, index=False)
print(len(df), "filas ->", out)
print(df.head(3).T.to_string())
