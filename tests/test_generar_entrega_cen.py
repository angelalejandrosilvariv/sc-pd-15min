from pathlib import Path
import sys

import openpyxl
import pandas as pd

ROOT = Path(__file__).parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import sc_pd_motor_v7 as motor  # noqa: E402
from generar_entrega_cen import generar_entrega, interruptores_panel  # noqa: E402


def _salida(tmp_path):
    ruta = tmp_path / "Reporte_Sobrecostos_PD_Final.xlsx"
    ciclos = []
    bloques = []
    for n, (empresa, central, p, d) in enumerate((("E1","A",100,20),("E1","B",50,10),("E2","C",30,5)), 1):
        etiqueta=f"{central} &{n}"; inicio=pd.Timestamp(f"2026-08-0{n} 00:00")
        margen=4*10
        ciclos.append({"Etiqueta_Relacionada":etiqueta,"Central_Relacionada":central,"Empresa":empresa,
            "Estado_Ciclo_Mes":"Inicia y termina este mes","Inicio_Ciclo":inicio,"Termino_Ciclo":inicio+pd.Timedelta(minutes=45),
            "Costo_Partida_Base":p,"Filtro_Conf_Partida":1,"Filtro_Disp_Partida":1,"Filtro_Op_Partida":1,"Filtro_CostoCero_Partida":1,
            "Costo_Detencion_Base":d,"Filtro_Conf_Detencion":1,"Filtro_Disp_Detencion":1,"Filtro_Op_Detencion":1,"Filtro_CostoCero_Detencion":1,
            "Costo_Partida_Efectivo":p,"Costo_Detencion_Efectivo":d,"Margen_Suma_Ciclo":margen,"Total SC_PD":max(0,p+d-margen)})
        for q in range(4):
            bloques.append({"Etiqueta_Relacionada":etiqueta,"Central_Relacionada":central,"Central":central+"_GN",
                "Ciclo_ID_Relacionada":n,"FECHA_HORA":inicio+pd.Timedelta(minutes=15*q),"GENERACION":1,"CMg":20,"CV":10,
                "Dolar":1,"Margen":10,"Fuente_Config_RIO":inicio-pd.Timedelta(minutes=10),"CONSIGNAS":"PP","MOTIVO":"OM",
                "ESTADO OPERACIONAL":"PDO","COMENTARIO":"","Configuracion RIO":central+"_GN","Filtro_Operacional":1,"Vigencia_RIO":1,
                "Costo_Partida_ML":p,"Costo_Detencion_ML":d,"Filtro_CostoCero_Partida":1,"Filtro_CostoCero_Detencion":1})
    ciclos=pd.DataFrame(ciclos); detalle=pd.DataFrame(bloques)
    cand=motor.candidatas_tarifa_configuracion(detalle)
    empresas=pd.DataFrame({"Empresa":["E1","E2"],"Total_SC_PD_CLP":[sum(x["Total SC_PD"] for x in ciclos.to_dict("records")[:2]),ciclos.iloc[2]["Total SC_PD"]]})
    guia=pd.DataFrame({"Columna":["Total SC_PD","GENERACION"],"Que significa":["Sobrecosto final","Energia del bloque"]})
    with pd.ExcelWriter(ruta,engine="openpyxl") as w:
        ciclos.to_excel(w,sheet_name="Resumen_Ciclos_PD",index=False); detalle.to_excel(w,sheet_name="Detalle_15Min",index=False)
        empresas.to_excel(w,sheet_name="SC_por_Empresa",index=False); guia.to_excel(w,sheet_name="Guia_Lectura",index=False)
        cand.to_excel(w,sheet_name="Candidatas_Tarifa",index=False)
    return ruta,ciclos,detalle


def test_genera_siete_archivos_checks_diccionario_y_panel(tmp_path):
    reporte,ciclos,bloques=_salida(tmp_path)
    destino=generar_entrega(reporte,{},tmp_path/"entrega",tablas_dinamicas=True)
    assert len(list(destino.iterdir())) == 7
    nombres={p.name for p in destino.iterdir()}; assert any(n.endswith("_Auditoria.xlsx") for n in nombres)
    parametros=pd.read_csv(next(destino.glob("*_parametros.csv")))
    assert set(interruptores_panel(motor)) <= set(parametros.interruptor)
    assert {"motor_version","fecha_corrida"} <= set(parametros.interruptor)
    dic=pd.read_csv(next(destino.glob("*_diccionario.csv")))
    for csv in destino.glob("*.csv"):
        if "diccionario" not in csv.name:
            assert set(pd.read_csv(csv).columns) <= set(dic.loc[dic.archivo.eq(csv.name),"columna"])
    # Las mismas formulas, recalculadas en pandas, cierran en cero.
    margen=bloques.assign(r=lambda x:(x.CMg-x.CV).clip(lower=0)*x.Dolar*x.GENERACION).groupby("Etiqueta_Relacionada").r.sum()
    assert (ciclos.set_index("Etiqueta_Relacionada").Margen_Suma_Ciclo-margen).abs().max() == 0
    sc=(ciclos.Costo_Partida_Base+ciclos.Costo_Detencion_Base-ciclos.Margen_Suma_Ciclo).clip(lower=0)
    assert (sc-ciclos["Total SC_PD"]).abs().max() == 0
    wb=openpyxl.load_workbook(next(destino.glob("*_Auditoria.xlsx")),read_only=False,data_only=False)
    assert {"Leeme","Parametros","Ciclos","Bloques","Candidatas","Empresas","Resumen_Empresa","Resumen_Central","Diccionario"} <= set(wb.sheetnames)
    assert "SUMIFS" in " ".join(str(c.value) for row in wb["Ciclos"] for c in row if c.value)
