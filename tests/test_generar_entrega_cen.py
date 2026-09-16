"""Pruebas sintéticas de la entrega con formato horario (spec 32)."""
import sys
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from generar_entrega_cen import FORMULAS, SHEETS, generar_entrega


def _reporte(tmp_path):
    ciclos=pd.DataFrame({"Etiqueta_Relacionada":["C&1","D&1","A&1"],"Central_Relacionada":["C","D","A"],"Empresa":["E1","E2","E1"],"Ciclo_Mes":["2608"]*3,"Inicio_Ciclo":pd.to_datetime(["2026-08-01","2026-08-02","2026-07-31 23:45"],format="mixed"),"Termino_Ciclo":pd.to_datetime(["2026-08-01 00:15",None,"2026-08-01"],format="mixed"),"Estado_Ciclo_Mes":["Inicia y termina este mes","Continua proximo mes","Viene del mes anterior"],"Costo_Partida_Efectivo":[20.,10.,5.],"Costo_Detencion_Efectivo":[2.,0.,1.],"Margen_Suma_Ciclo":[2.,1.,1.],"Total SC_PD":[20.,0.,5.]})
    rows=[]
    for lab,rel,day in [("C&1","C",1),("D&1","D",2),("A&1","A",1)]:
      for j in range(2):
       for config,tarifa in ((rel+"_1",10.),(rel+"_2",20.)) if rel=="C" else ((rel+"_1",10.),):
        rows.append({"Etiqueta_Relacionada":lab,"Central_Relacionada":rel,"Central":config,"FECHA_HORA":pd.Timestamp(2026,8,day)+pd.Timedelta(minutes=15*j),"GENERACION":1.,"CMg":2.,"CV":1.,"Dolar":1.,"Margen":1.,"Costo_Partida":tarifa,"Costo_Detencion":1.,"MOTIVO":"OM","ESTADO OPERACIONAL":"PDO","Disponible (1) / Pruebas (0)":1})
    d=pd.DataFrame(rows); front=d.iloc[:1].copy();front["Etiqueta_Relacionada"]="A&1";front["Central_Relacionada"]="A";front["FECHA_HORA"]=pd.Timestamp("2026-07-31 23:45")
    p=tmp_path/"Reporte.xlsx"
    with pd.ExcelWriter(p) as w:
      ciclos.to_excel(w,sheet_name="Resumen_Ciclos_PD",index=False);d.to_excel(w,sheet_name="Detalle_15Min",index=False);front.to_excel(w,sheet_name="Detalle_Frontera",index=False)
      pd.DataFrame({"Empresa":["E1","E2"],"Total_SC_PD_CLP":[25,0]}).to_excel(w,sheet_name="SC_por_Empresa",index=False)
    return p


def test_paquete_hojas_formulas_y_frontera(tmp_path):
    out=generar_entrega(_reporte(tmp_path),version="Definitivo")
    assert len(list(out.glob("*.csv")))==12
    book=next(out.glob("*.xlsx")); wb=load_workbook(book,data_only=False)
    assert wb.sheetnames==SHEETS
    assert wb["Menu"]["A2"].value==260801 and wb["Menu"]["D2"].value=="Definitivo"
    assert wb["Sobrecosto_PD xHyC"]["A2"].value.startswith("2608011.1")
    assert wb["Sobrecosto_PD xHyC"]["U2"].value.startswith("=IFERROR")
    assert wb["Sobrecosto_Ciclo"]["C2"].value.startswith("=SUMIF")
    assert wb["Ciclos inconclusos"]["S3"].value=="=T3"
    assert "'xHyC mes anterior'" in wb["Ciclos inconclusos"]["X3"].value


def test_formulas_sin_referencias_estructuradas_y_rangos_acotados():
    text=" ".join(FORMULAS["PARTIDAS_DETENCIONES"].values())
    assert "$U$2:$U${N}" in text
    assert "[@" not in text and "[[#This Row]" not in text


def test_sin_rio_se_degrada_a_encabezados(tmp_path):
    out=generar_entrega(_reporte(tmp_path)); wb=load_workbook(next(out.glob("*.xlsx")))
    assert wb["Instrucciones RIO"].max_row==1
