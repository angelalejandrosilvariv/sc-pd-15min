#!/usr/bin/env python3
"""Construye la entrega CEN con la disposicion del Excel horario (spec 32)."""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from xlsxwriter.utility import xl_col_to_name

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src")) if str(RAIZ / "src") not in sys.path else None
import sc_pd_motor_v7 as motor  # noqa: E402

SHEETS = ["Menu", "Leeme", "Costos_de_P-D", "Pruebas", "Instrucciones RIO",
          "Central_Empresa", "Sobrecosto_PD xHyC", "PARTIDAS_DETENCIONES",
          "Sobrecosto_Ciclo", "RESUMEN", "Ciclos inconclusos",
          "xHyC mes anterior", "Diccionario"]
XHYC = ["Id", "fecha", "hora", "central", "generacion", "Remunerar", "Proceso_Partida",
        "horas_detenida", "proceso_detencion", "Ciclo de operación", "check01-PD", "con_costo_PD",
        "Costo_cero_PD", "Partida", "Detencion", "part_fria", "part_tibia_i", "part_tibia_f",
        "part_cal", "tipo_partida", "COSTO_PARTIDA [$]", "COSTO_DETENCION [$]", "CV", "CMg",
        "Diferencia Cmg-CV", "USD", "Generación_neta", "Margen", "Clave Ciclo", "Programación",
        "Disponible (1) / Pruebas (0)", "Combustible Partida", "Conf despachada RIO",
        "Politica vigente", "Empresa", "cuarto", "USD apertura ciclo", "USD cierre ciclo",
        "Filtro Costo_Cero partida", "Filtro Costo_Cero detención", "Conf despachada RIO detención",
        "Combustible Detención", "Tarifa partida USD", "Tarifa detención USD", "Central relacionada",
        "Clave relacionada", "FECHA_HORA", "Instrucción", "Operación", "Consigna", "Configuración RIO",
        "Comentario RIO", "Fuente RIO", "Vigencia RIO", "Filtro operacional", "Margen motor", "Check margen"]
PD = ["fecha", "hora", "central", "generacion", "Remunerar", "Proceso_Partida", "horas_detenida",
      "proceso_detencion", "Ciclo", "con_costo_PD", "Costo_cero_PD", "Costo PD", "Central relacionada",
      "Clave Ciclo", "Ciclo + fecha + hora", "Instrucción", "Operación", "Programación", "Monto Partidas",
      "Monto Detenciones", "Vacio", "N° Partidas", "Monto Partidas", "N° Detenciones", "Monto Detenciones",
      "Presta SSCC", "Bloque mes", "RIO PP", "RIO PS", "Revisar", "Exención sin historia", "Vigencia RIO",
      "Disponible (1) / Pruebas (0)", "Conf despachada RIO", "Filtro operacional motor", "Consigna", "cuarto",
      "FECHA_HORA", "Fuente RIO", "Antigüedad instrucción (min)", "Estado ciclo mes", "Empresa"]
COSTOS = ["id", "dia", "tipo", "Unidad", "Costo Partida fría", "Costo Partida tibia",
          "Costo Partida caliente", "Costo Detención", "Tiempo Partida fría", "Tiempo Partida tibia",
          "Tiempo Partida caliente", "Costo_Cero", "fria", "tibia_i", "tibia_f", "Caliente",
          "Costo Partida tibia 2", "Tiempo Partida tibia 2"]
RIO = ["Clave", "Clave relacionada", "Dia", "Hora", "E/S", "Central", "Sube", "Baja", "Queda",
       "COMENTARIO", "Configuración", "Estado Embalse", "Consigna", "MOTIVO", "Operación", "Neomante",
       "Relacionada", "Ciclo", "SSCC", "Ciclo Partida siguiente", "Clave Ciclo partida",
       "Combustible Partida", "FECHA_HORA_RIO", "Usada en", "Mes"]
CYCLE = ["Ciclo de operación", "Ciclo completo", "Total Costos Partida", "Total Costos Detención",
         "Total Margen", "Total Costos Partida ciclo inconcluso", "Margen ciclo inconcluso",
         "Total Sobrecosto_P-D", "Empresa", "Copia Ciclo", "Cuadro de pagos?", "", " ", "Verificadores",
         "PO", "SIF", "Ciclo", "Maximo ciclo", "SSCC", "Check SC", "Check partida", "Check detención", "Check margen"]

# Public contract: templates use row/range placeholders and never structured references.
FORMULAS = {
    "Sobrecosto_PD xHyC": {
        "O": '=+I{r}', "U": '=IFERROR(IF(N{r}="SI",VLOOKUP(AH{r}&D{r},\'Costos_de_P-D\'!$A$2:$R${costos},IF(T{r}="fria",5,IF(T{r}="tibia",6,IF(T{r}="tibia_2",17,7))),FALSE)*AK{r}*AG{r}*AM{r},0),0)',
        "V": '=IFERROR(IF(O{r}="SI",VLOOKUP(AH{r}&D{r},\'Costos_de_P-D\'!$A$2:$R${costos},8,FALSE)*AL{r}*AO{r}*AN{r},0),0)',
        "Y": '=IF(X{r}-W{r}<0,0,X{r}-W{r})', "AA": '=E{r}', "AB": '=Z{r}*Y{r}*AA{r}',
        "AC": '=J{r}', "BE": '=ROUND(AB{r}-BD{r},0)'},
    "PARTIDAS_DETENCIONES": {
        "D": '=SUMIF(\'Sobrecosto_PD xHyC\'!$AT$2:$AT${N},O{r},\'Sobrecosto_PD xHyC\'!$E$2:$E${N})',
        "M": '=C{r}', "N": '=M{r}&"&"&I{r}', "O": '=A{r}&B{r}&"."&AK{r}&M{r}',
        "S": '=IFERROR(MAXIFS(\'Sobrecosto_PD xHyC\'!$U$2:$U${N},\'Sobrecosto_PD xHyC\'!$J$2:$J${N},N{r},\'Sobrecosto_PD xHyC\'!$G$2:$G${N},"SI")*IF(OR(P{r}="OM",Q{r}="PDO",AND(P{r}="OT",Z{r}=1),AND(AE{r}=1,P{r}="Sin_Registro_RIO")),1,0)*AF{r}*AG{r}*AH{r},0)',
        "T": '=IFERROR(MAXIFS(\'Sobrecosto_PD xHyC\'!$V$2:$V${N},\'Sobrecosto_PD xHyC\'!$J$2:$J${N},N{r},\'Sobrecosto_PD xHyC\'!$I$2:$I${N},"SI")*IF(OR(P{r}="OM",Q{r}="PDO",AND(P{r}="OT",Z{r}=1),AND(AE{r}=1,P{r}="Sin_Registro_RIO")),1,0)*AF{r}*AG{r}*AH{r},0)'},
    "Sobrecosto_Ciclo": {"C": '=SUMIF(PARTIDAS_DETENCIONES!$N$2:$N${M},A{r},PARTIDAS_DETENCIONES!$S$2:$S${M})',
        "D": '=SUMIF(PARTIDAS_DETENCIONES!$N$2:$N${M},A{r},PARTIDAS_DETENCIONES!$T$2:$T${M})',
        "E": '=SUMIF(\'Sobrecosto_PD xHyC\'!$AC$2:$AC${N},A{r},\'Sobrecosto_PD xHyC\'!$AB$2:$AB${N})'},
    "RESUMEN": {"C": '=SUMIF(Sobrecosto_Ciclo!$I$2:$I${C},A{r},Sobrecosto_Ciclo!$H$2:$H${C})'}
}

def interruptores_panel():
    return {n: v for n, v in vars(motor).items() if n.isupper() and not n.startswith("RUTA_")
            and n != "MINUTOS_BLOQUE" and isinstance(v, (str, int, float, bool))}

def _get(df, name, default=pd.NA):
    if name in df:
        return df[name]
    if isinstance(default, pd.Series):
        return default.reindex(df.index)
    return pd.Series([default] * len(df), index=df.index)

def _dates(df):
    return pd.to_datetime(_get(df, "FECHA_HORA"), errors="coerce")

def _aamm(c):
    if "Ciclo_Mes" in c and c.Ciclo_Mes.notna().any():
        m = re.search(r"(\d{2})\D?(\d{2})$", str(c.Ciclo_Mes.dropna().mode().iloc[0]))
        if m: return "".join(m.groups())
    d = pd.to_datetime(_get(c, "Inicio_Ciclo"), errors="coerce").dropna()
    if d.empty: raise ValueError("Resumen_Ciclos_PD no contiene fechas de ciclo válidas")
    return d.max().strftime("%y%m")

def _comb(x):
    try: return motor.combustible_configuracion(x)
    except Exception: return ""

def _xhyc(d, ciclos, panel):
    if d.empty: return pd.DataFrame(columns=XHYC)
    d = d.copy(); d["FECHA_HORA"] = _dates(d)
    d = d.sort_values(["Central", "FECHA_HORA"], kind="stable").reset_index(drop=True)
    cm = ciclos.set_index("Etiqueta_Relacionada", drop=False) if "Etiqueta_Relacionada" in ciclos else pd.DataFrame()
    out = pd.DataFrame(index=d.index, columns=XHYC); t = d.FECHA_HORA
    out["fecha"] = pd.to_numeric(t.dt.strftime("%y%m%d")); out["hora"] = t.dt.hour + 1; out["cuarto"] = t.dt.minute // 15 + 1
    out["central"] = _get(d,"Central",""); out["Id"] = out.fecha.astype("Int64").astype(str)+out.hora.astype(str)+"."+out.cuarto.astype(str)+out.central.astype(str)
    mapping={"generacion":"GENERACION","CV":"CV","CMg":"CMg","USD":"Dolar","Margen motor":"Margen","Ciclo de operación":"Etiqueta_Relacionada","Empresa":"Empresa","Central relacionada":"Central_Relacionada","FECHA_HORA":"FECHA_HORA","Instrucción":"MOTIVO","Operación":"ESTADO OPERACIONAL","Consigna":"CONSIGNAS","Configuración RIO":"Configuracion RIO","Comentario RIO":"COMENTARIO","Fuente RIO":"Fuente_Config_RIO","Vigencia RIO":"Vigencia_RIO","Filtro operacional":"Filtro_Operacional","Disponible (1) / Pruebas (0)":"Disponible (1) / Pruebas (0)","Tarifa partida USD":"Costo_Partida","Tarifa detención USD":"Costo_Detencion","Filtro Costo_Cero partida":"Filtro_CostoCero_Partida","Filtro Costo_Cero detención":"Filtro_CostoCero_Detencion"}
    for a,b in mapping.items(): out[a]=_get(d,b,"")
    grp=d.groupby(["Etiqueta_Relacionada","Central"],dropna=False)["FECHA_HORA"]
    first=grp.transform("min"); last=grp.transform("max")
    out["Proceso_Partida"]=t.eq(first).map({True:"SI",False:""}); out["proceso_detencion"]=t.eq(last).map({True:"SI",False:""})
    labels=_get(d,"Etiqueta_Relacionada",""); lookup=lambda col: labels.map(_get(ciclos,col).set_axis(_get(ciclos,"Etiqueta_Relacionada","")).to_dict()) if len(ciclos) else pd.Series("",index=d.index)
    hd=lookup("Horas_Detenida_Ciclo"); hc=lookup("Horas_Cota_Inferior"); out["horas_detenida"]=hd.where(hd.notna(),hc).where(t.eq(first),"")
    out["check01-PD"]=0; cp=pd.to_numeric(_get(d,"Costo_Partida"),errors="coerce"); cd=pd.to_numeric(_get(d,"Costo_Detencion",0),errors="coerce").fillna(0)
    out["con_costo_PD"]=pd.Series((cp.notna()|(cd>0)),index=d.index).map({True:"D",False:"NO"})
    out["Costo_cero_PD"]=_get(d,"Costo_Cero","No_Aplica").fillna("No_Aplica"); out["Partida"]=((out["Proceso_Partida"]=="SI")&(cp.fillna(0)>0)).map({True:"SI",False:0})
    out["Detencion"]=out.proceso_detencion; out["part_fria"]=_get(d,"Fria_Num1_M",""); out["part_tibia_i"]=_get(d,"Tibia_Num2_N",""); out["part_tibia_f"]=_get(d,"Tibia_Num1_O",""); out["part_cal"]=_get(d,"Caliente_Num1_P","")
    out["tipo_partida"]=_get(d,"Tipo_Partida","-").astype(str).str.lower().where(t.eq(first),"-")
    out["Diferencia Cmg-CV"]=(pd.to_numeric(out.CMg,errors="coerce")-pd.to_numeric(out.CV,errors="coerce")).clip(lower=0); out["Generación_neta"]=out.generacion
    out["Margen"]=out["Margen motor"]
    out["Clave Ciclo"]=labels; out["Politica vigente"]=_get(d,"Llave_FHC","").astype(str).str.rsplit("-",n=1).str[0]
    out["Combustible Partida"]=_get(d,"Configuracion RIO","").map(_comb); out["Combustible Detención"]=out["Combustible Partida"]
    out["Conf despachada RIO"]=_get(d,"pasa_combustible_partida",1); out["Conf despachada RIO detención"]=_get(d,"pasa_combustible_detencion",1)
    out["USD apertura ciclo"]=lookup("Valor_Dolar").fillna(_get(d,"Dolar")); out["USD cierre ciclo"]=out["USD apertura ciclo"]
    out["Clave relacionada"]=out.fecha.astype("Int64").astype(str)+out.hora.astype(str)+"."+out.cuarto.astype(str)+out["Central relacionada"].astype(str)
    for c in ["Remunerar","Programación"]: out[c]=""
    # pandas values equivalent to the workbook formulas.
    out["COSTO_PARTIDA [$]"]=cp.fillna(0)*pd.to_numeric(out["USD apertura ciclo"],errors="coerce").fillna(0)*pd.to_numeric(out["Conf despachada RIO"],errors="coerce").fillna(0)*pd.to_numeric(out["Filtro Costo_Cero partida"],errors="coerce").fillna(1)*(out["Proceso_Partida"]=="SI")
    out["COSTO_DETENCION [$]"]=cd*pd.to_numeric(out["USD cierre ciclo"],errors="coerce").fillna(0)*pd.to_numeric(out["Conf despachada RIO detención"],errors="coerce").fillna(0)*pd.to_numeric(out["Filtro Costo_Cero detención"],errors="coerce").fillna(1)*(out["proceso_detencion"]=="SI")
    out["Check margen"]=0
    return out[XHYC]

def _costos(df):
    out=pd.DataFrame(index=df.index,columns=COSTOS)
    names=["Llave_Concatenada","DIA","HORA","UNIDAD","Partida_Fria","Partida_Tibia","Partida_Caliente","Detencion","Tiempo_Partida_Fria","Tiempo_Partida_Tibia","Tiempo_Partida_Caliente","Costo_Cero","Fria_Num1_M","Tibia_Num2_N","Tibia_Num1_O","Caliente_Num1_P","Partida_Tibia_2","Tiempo_Partida_Tibia_2"]
    for a,b in zip(COSTOS,names): out[a]=_get(df,b,"")
    return out

def _rio(df,ciclos):
    out=pd.DataFrame(index=df.index,columns=RIO); t=pd.to_datetime(_get(df,"FECHA_HORA_RIO"),errors="coerce"); q=t.dt.minute//15+1; fecha=t.dt.strftime("%y%m%d"); hora=t.dt.hour+1
    cfg=_get(df,"NOMBRE CONFIGURACIÓN",_get(df,"Configuracion RIO","")); rel=_get(df,"Central_Relacionada_RIO","")
    out["Clave"]=fecha+hora.astype("Int64").astype(str)+"."+q.astype("Int64").astype(str)+cfg.astype(str); out["Clave relacionada"]=fecha+hora.astype("Int64").astype(str)+"."+q.astype("Int64").astype(str)+rel.astype(str)
    for a,b in {"Dia":"DIA","Central":"U. GENERADORA","Sube":"POTENCIA MÁXIMA","Baja":"POTENCIA MÍNIMA","Queda":"POTENCIA INSTRUIDA","COMENTARIO":"COMENTARIO","Configuración":"NOMBRE CONFIGURACIÓN","Estado Embalse":"ESTADO DE EMBALSE","Consigna":"CONSIGNAS","MOTIVO":"MOTIVO","Operación":"ESTADO OPERACIONAL","Relacionada":"Central_Relacionada_RIO","FECHA_HORA_RIO":"FECHA_HORA_RIO","Mes":"Mes"}.items(): out[a]=_get(df,b,"")
    out["Hora"]=t.dt.strftime("%H:%M"); out["SSCC"]=_get(df,"COMENTARIO","").astype(str).str.contains("SSCC|CTF|CSF|CPF",case=False,regex=True).astype(int)
    # Match cycle endpoints to the instruction timestamp and related plant.
    out["Ciclo"]="No encontrado"; out["Usada en"]=""
    for _,c in ciclos.iterrows():
        lab=c.get("Etiqueta_Relacionada",""); cr=c.get("Central_Relacionada","")
        uses=[]
        for typ,col in (("Partida","Fuente_Config_RIO_Partida"),("Detencion","Fuente_Config_RIO_Detencion")):
            src=c.get(col,c.get("Fuente_Config_RIO",pd.NaT)); mask=t.eq(pd.to_datetime(src,errors="coerce")) & rel.eq(cr)
            out.loc[mask,"Ciclo"]=lab; uses.append((mask,typ))
        for mask,typ in uses: out.loc[mask,"Usada en"]=out.loc[mask,"Usada en"].map(lambda x: typ if not x else "Partida y Detencion")
    out["Clave Ciclo partida"]=out["Ciclo"].where(out.MOTIVO.isin(["PP","PMT"]),""); out["Combustible Partida"]=out["Configuración"].map(_comb)
    for c in ["E/S","Neomante","Ciclo Partida siguiente"]: out[c]=""
    return out[RIO]

def _pd(x,ciclos,rio):
    if x.empty:return pd.DataFrame(columns=PD)
    keys=["Central relacionada","FECHA_HORA","Ciclo de operación"]
    base=x.sort_values(keys).groupby(keys,dropna=False,as_index=False).first(); out=pd.DataFrame(index=base.index,columns=PD)
    for a,b in {"fecha":"fecha","hora":"hora","central":"Central relacionada","Ciclo":"Ciclo de operación","Empresa":"Empresa","cuarto":"cuarto","FECHA_HORA":"FECHA_HORA","Fuente RIO":"Fuente RIO"}.items():out[a]=base[b]
    out["generacion"]=base.groupby(level=0)["generacion"].sum(); out["Central relacionada"]=out.central; out["Clave Ciclo"]=out.central.astype(str)+"&"+out.Ciclo.astype(str).str.rsplit("&",n=1).str[-1]
    out["Ciclo + fecha + hora"]=out.fecha.astype("Int64").astype(str)+out.hora.astype(str)+"."+out.cuarto.astype(str)+out.central.astype(str)
    cmap=ciclos.set_index("Etiqueta_Relacionada").to_dict("index") if len(ciclos) else {}
    for i,row in out.iterrows():
        c=cmap.get(row.Ciclo,{ }); dt=row.FECHA_HORA; start=pd.to_datetime(c.get("Inicio_Ciclo"),errors="coerce"); end=pd.to_datetime(c.get("Termino_Ciclo"),errors="coerce"); deferred=str(c.get("Estado_Ciclo_Mes","")) in ("Continua proximo mes","Continua todo el mes")
        p=dt==start; e=dt==end and not deferred; out.at[i,"Proceso_Partida"]="SI" if p else ""; out.at[i,"proceso_detencion"]="SI" if e else ""
        out.at[i,"horas_detenida"]=c.get("Horas_Detenida_Ciclo",c.get("Horas_Cota_Inferior","")) if p else ""
        suffix="Partida" if p else "Detencion" if e else None
        out.at[i,"Instrucción"]=c.get(f"Motivo_{suffix}",base.at[i,"Instrucción"]) if suffix else base.at[i,"Instrucción"]
        out.at[i,"Operación"]=c.get(f"Estado_Op_{suffix}",base.at[i,"Operación"]) if suffix else base.at[i,"Operación"]
        out.at[i,"Consigna"]=c.get(f"Consigna_{suffix}",base.at[i,"Consigna"]) if suffix else base.at[i,"Consigna"]
        out.at[i,"Vigencia RIO"]=c.get(f"Vigencia_RIO_{suffix}",1) if suffix else base.at[i,"Vigencia RIO"]
        out.at[i,"Disponible (1) / Pruebas (0)"]=c.get(f"Filtro_Disp_{suffix}",1) if suffix else base.at[i,"Disponible (1) / Pruebas (0)"]
        out.at[i,"Conf despachada RIO"]=c.get(f"Filtro_Conf_{suffix}",1) if suffix else 1; out.at[i,"Filtro operacional motor"]=c.get(f"Filtro_Op_{suffix}",1) if suffix else base.at[i,"Filtro operacional"]
        out.at[i,"Estado ciclo mes"]=c.get("Estado_Ciclo_Mes",""); out.at[i,"Exención sin historia"]=c.get("Flag_Exencion",0)
    out["Monto Partidas"]=out.Ciclo.map(ciclos.set_index("Etiqueta_Relacionada").get("Costo_Partida_Efectivo",pd.Series(dtype=float))).fillna(0).where(out.Proceso_Partida=="SI",0)
    out["Monto Detenciones"]=out.Ciclo.map(ciclos.set_index("Etiqueta_Relacionada").get("Costo_Detencion_Efectivo",pd.Series(dtype=float))).fillna(0).where(out.proceso_detencion=="SI",0)
    out["Presta SSCC"]=(out["Instrucción"].astype(str)+out["Consigna"].astype(str)).str.contains("SSCC|CTF|CSF|CPF",case=False).astype(int); out["Bloque mes"]=(pd.to_datetime(out.FECHA_HORA).dt.day-1)*96+(out.hora-1)*4+out.cuarto
    for c in ["Remunerar","con_costo_PD","Programación","Vacio"]:out[c]=""
    out["Costo PD"]=1; out["Costo_cero_PD"]="NO"; out["RIO PP"]=0; out["RIO PS"]=0; out["Revisar"]=0
    return out[PD]

def _cycle(c, pdv, xv, empresas, incon_last):
    motor_cols=list(c.columns); out=pd.DataFrame(index=c.index,columns=CYCLE+motor_cols)
    out["Ciclo de operación"]=_get(c,"Etiqueta_Relacionada",""); state=_get(c,"Estado_Ciclo_Mes",""); out["Ciclo completo"]=state.isin(["Inicia y termina este mes","Viene del mes anterior"]).astype(int)
    out["Total Costos Partida"]=_get(c,"Costo_Partida_Efectivo",0); out["Total Costos Detención"]=_get(c,"Costo_Detencion_Efectivo",0); out["Total Margen"]=_get(c,"Margen_Suma_Ciclo",0)
    out["Total Costos Partida ciclo inconcluso"]=0; out["Margen ciclo inconcluso"]=0; out["Total Sobrecosto_P-D"]=_get(c,"Total SC_PD",0); out["Empresa"]=_get(c,"Empresa",""); out["Copia Ciclo"]=out["Ciclo de operación"]
    out["Cuadro de pagos?"]=""; out["Verificadores"]=""; out["PO"]=0; out["SIF"]=0; out["Ciclo"]=_get(c,"Central_Relacionada",""); out["Maximo ciclo"]=_get(c,"Ciclo_ID_Relacionada",0); out["SSCC"]=0
    for q in ["Check SC","Check partida","Check detención","Check margen"]: out[q]=0
    for q in motor_cols: out[q]=c[q].values
    return out

def _inconclusos(c, xfront):
    nxt=c[_get(c,"Estado_Ciclo_Mes","").isin(["Continua proximo mes","Continua todo el mes"])].copy(); prev=c[_get(c,"Estado_Ciclo_Mes","").eq("Viene del mes anterior")].copy()
    left=pd.DataFrame(index=range(len(nxt)),columns=CYCLE[:16]); left["Ciclo de operación"]=_get(nxt,"Etiqueta_Relacionada","").values; left["Ciclo completo"]=0; left["Empresa"]="Se traspasa al proximo mes"
    right_headers=["Ciclo de operación","Ciclo de operación","Ciclo completo","Total Costos Partida","Total Costos Detención","Total Margen","Total Costos Partida ciclo inconcluso","Margen ciclo inconcluso","Total Sobrecosto_P-D","Empresa","Copia Ciclo","Cuadro de pagos?","","","Verificadores","PO","SIF"]
    right=pd.DataFrame(index=range(len(prev)),columns=right_headers); labs=_get(prev,"Etiqueta_Relacionada","").values
    right.iloc[:,0]=labs; right.iloc[:,1]=labs; right.iloc[:,2]=1; right.iloc[:,3]=_get(prev,"Costo_Partida_Efectivo",0).values; right.iloc[:,4]=0
    margins=xfront.groupby("Clave Ciclo")["Margen"].sum() if len(xfront) else pd.Series(dtype=float); right.iloc[:,5]=pd.Series(labs).map(margins).fillna(0); right.iloc[:,6:8]=0; right.iloc[:,9]=_get(prev,"Empresa","").values
    return left,right

def _sha(path):
    h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()

def _params(reporte, inputs, panel):
    p=interruptores_panel(); p.update(panel or {})
    try:
        saved=pd.read_excel(reporte,sheet_name="Parametros_Motor"); p.update(dict(zip(saved.interruptor,saved.valor)))
    except (ValueError,KeyError): pass
    rows=[{"interruptor":k,"valor":v,"spec":"panel motor"} for k,v in sorted(p.items())]
    try: commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=RAIZ,text=True).strip()
    except Exception: commit="no disponible"
    rows += [{"interruptor":"motor_version","valor":commit,"spec":"git"},{"interruptor":"fecha_corrida","valor":datetime.now().isoformat(timespec="seconds"),"spec":"32"}]
    for i,f in enumerate(inputs,1): rows += [{"interruptor":f"archivo_entrada_{i}/nombre","valor":f.name,"spec":"32"},{"interruptor":f"archivo_entrada_{i}/sha256","valor":_sha(f),"spec":"32"}]
    return pd.DataFrame(rows),p

def _dict(frames):
    rows=[]
    for sh,df in frames.items():
        for i,col in enumerate(df.columns): rows.append({"hoja":sh,"columna":col,"letra":xl_col_to_name(i),"significado":str(col).replace("_"," "),"origen motor":sh,"fórmula o valor":"fórmula o valor según spec 32"})
    return pd.DataFrame(rows)

def _write_df(writer,name,df,formulas=None,ctx=None,startrow=0,header=True):
    df.to_excel(writer,sheet_name=name,index=False,startrow=startrow,header=header)
    ws=writer.sheets[name]; ws.freeze_panes(1 if startrow==0 else 2,0); ctx=ctx or {}
    if formulas:
        for letter,tpl in formulas.items():
            ci=ord(letter)-65 if len(letter)==1 else (ord(letter[0])-64)*26+ord(letter[1])-65
            if ci>=len(df.columns): continue
            for i in range(len(df)):
                r=startrow+i+2; formula=tpl.format(r=r,**ctx)
                value=df.iloc[i,ci] if pd.notna(df.iloc[i,ci]) else 0
                ws.write_formula(startrow+i+1,ci,formula,None,value)
    for i,col in enumerate(df.columns): ws.set_column(i,i,min(42,max(12,len(str(col))+2)))

def generar_entrega(reporte: str|Path, carpeta_salida: str|Path|None=None,
                    archivos_entrada=None, panel:dict|None=None, version:str="Preliminar") -> Path:
    reporte=Path(reporte).resolve(); xl=pd.ExcelFile(reporte)
    def read(name,cols=None):
        if name in xl.sheet_names:return pd.read_excel(xl,sheet_name=name)
        print(f"Aviso: falta la hoja {name}; se generará vacía")
        return pd.DataFrame(columns=cols or [])
    c=read("Resumen_Ciclos_PD"); d=read("Detalle_15Min"); front=read("Detalle_Frontera"); emp=read("SC_por_Empresa"); costs=read("Costos_PD_Usados"); rio0=read("RIO_Usado"); cent=read("Central_Empresa",["Central","Empresa"])
    aamm=_aamm(c); destino=Path(carpeta_salida) if carpeta_salida else reporte.parent/f"Entrega_SCPD_{aamm}"
    if carpeta_salida and destino.name!=f"Entrega_SCPD_{aamm}":destino/=f"Entrega_SCPD_{aamm}"
    destino.mkdir(parents=True,exist_ok=True); inputs=[Path(x) for x in (archivos_entrada or [reporte]) if Path(x).exists()]; params,panel_eff=_params(reporte,inputs,panel)
    x=_xhyc(d,c,panel_eff); xf=_xhyc(front,c,panel_eff); costos=_costos(costs); rio=_rio(rio0,c)
    pruebas=x[pd.to_numeric(x["Disponible (1) / Pruebas (0)"],errors="coerce").eq(0)].copy(); pruebas=pd.DataFrame({"Id":pruebas.Id,"fecha":pruebas.fecha,"hora":pruebas.hora,"central":pruebas.central,"Configuracion":pruebas.central,"cuarto":pruebas.cuarto,"FECHA_HORA":pruebas.FECHA_HORA,"Central relacionada":pruebas["Central relacionada"],"Fuente RIO":pruebas["Fuente RIO"]})
    pdv=_pd(x,c,rio); cyc=_cycle(c,pdv,x,emp,2); left,right=_inconclusos(c,xf)
    names=list(dict.fromkeys(list(_get(emp,"Empresa","").dropna())+list(_get(c,"Empresa","").dropna())))
    resumen=pd.DataFrame({"Empresa":names,"PAGA":0}); totals=dict(zip(_get(emp,"Empresa",""),_get(emp,"Total_SC_PD_CLP",0))); resumen["RECIBE"]=resumen.Empresa.map(totals).fillna(0); resumen["SALDO"]=resumen.RECIBE; resumen["rep"]=1; resumen["CHECK"]=0; resumen[""]=0; resumen["Motor Total_SC_PD_CLP"]=resumen.RECIBE; resumen["Ciclos"]=resumen.Empresa.map(_get(c,"Empresa","").value_counts()).fillna(0)
    frames={"Costos_de_P-D":costos,"Pruebas":pruebas,"Instrucciones RIO":rio,"Central_Empresa":cent[[q for q in ["Central","Empresa"] if q in cent]],"Sobrecosto_PD xHyC":x,"PARTIDAS_DETENCIONES":pdv,"Sobrecosto_Ciclo":cyc,"RESUMEN":resumen,"xHyC mes anterior":xf}
    dic=_dict(frames); frames["Diccionario"]=dic
    safe=lambda s:re.sub(r"[^\w-]+","_",s,flags=re.UNICODE).strip("_")
    for sh,df in frames.items(): df.to_csv(destino/f"SCPD_{aamm}_{safe(sh)}.csv",index=False,encoding="utf-8-sig",date_format="%Y-%m-%d %H:%M:%S")
    # CSV apilado: los dos encabezados homónimos de la tabla derecha se
    # desambiguan sólo en el formato plano (en Excel conservan el original).
    right_csv=right.copy(); right_csv.columns=[f"{v}_{i+1}" if list(right.columns).count(v)>1 else v for i,v in enumerate(right.columns)]
    inc=pd.concat([left.assign(tabla="Próximo mes"),right_csv.assign(tabla="Mes anterior")],ignore_index=True); inc.to_csv(destino/f"SCPD_{aamm}_Ciclos_inconclusos.csv",index=False,encoding="utf-8-sig")
    params.to_csv(destino/f"SCPD_{aamm}_parametros.csv",index=False,encoding="utf-8-sig")
    book=destino/f"SCPD_{aamm}_Auditoria.xlsx"; ctx={"N":max(2,len(x)+1),"M":max(2,len(pdv)+1),"C":max(2,len(cyc)+1),"costos":max(2,len(costos)+1)}
    with pd.ExcelWriter(book,engine="xlsxwriter") as w:
        menu=pd.DataFrame([[int(aamm+"01"),aamm,"",version],["","","",""]],columns=["DIA","Mes","","Version"]); _write_df(w,"Menu",menu)
        ws=w.sheets["Menu"]; ws.write(3,0,"ARCHIVO");ws.write(3,1,"SHA-256");ws.write(3,3,"Interruptor");ws.write(3,4,"Valor");ws.write(3,5,"Spec")
        for i,f in enumerate(inputs,4):ws.write(i,0,f.name);ws.write(i,1,_sha(f))
        for i,row in params.iterrows():ws.write(i+4,3,row.interruptor);ws.write(i+4,4,str(row.valor));ws.write(i+4,5,row.spec)
        leeme=["Paquete de auditoría CEN con el formato del Excel horario.","Los CSV son estas hojas volcadas como valores.","RESUMEN!C = SUMIF(Sobrecosto_Ciclo!I, H).", "Sobrecosto_Ciclo!C/D = SUMIF(PARTIDAS_DETENCIONES!N, S/T); E = SUMIF(xHyC!AC, AB).", "PARTIDAS_DETENCIONES!S usa MAXIFS(xHyC!U por ciclo y Proceso_Partida) y filtros del ciclo.","La tarifa usa el dólar del extremo; Pruebas/EP y el filtro operacional se evalúan en la instrucción del extremo.","La instrucción RIO tiene vigencia ±30 min; Presta SSCC procede de su COMENTARIO.","Exención sin historia reemplaza la regla histórica del Excel.","Generación_neta es generación: el reporte ya viene neto.","Margen es fórmula sólo con RESOLUCION_MARGEN=bloque y MARGEN_NETEADO_POR_CICLO=0.","Las columnas a la derecha de las originales son campos de auditoría del motor.","IFERROR en tarifa representa políticas inexistentes, que tampoco tienen tarifa en el motor."]
        _write_df(w,"Leeme",pd.DataFrame({"Leeme":leeme}))
        for sh in ["Costos_de_P-D","Pruebas","Instrucciones RIO","Central_Empresa","Sobrecosto_PD xHyC","PARTIDAS_DETENCIONES","Sobrecosto_Ciclo","RESUMEN"]:_write_df(w,sh,frames[sh],FORMULAS.get(sh),ctx)
        ws=w.book.add_worksheet("Ciclos inconclusos");w.sheets["Ciclos inconclusos"]=ws; ws.write(0,0,"Próximo mes");ws.write(0,18,"Mes anterior")
        left.to_excel(w,sheet_name="Ciclos inconclusos",index=False,startrow=1,startcol=0);right.to_excel(w,sheet_name="Ciclos inconclusos",index=False,startrow=1,startcol=18)
        for i in range(len(right)): ws.write_formula(i+2,18,f"=T{i+3}",None,right.iloc[i,0]); ws.write_formula(i+2,23,f"=SUMIF('xHyC mes anterior'!$AC$2:$AC${max(2,len(xf)+1)},T{i+3},'xHyC mes anterior'!$AB$2:$AB${max(2,len(xf)+1)})",None,right.iloc[i,5])
        ws.freeze_panes(2,0); _write_df(w,"xHyC mes anterior",xf,FORMULAS["Sobrecosto_PD xHyC"],ctx);_write_df(w,"Diccionario",dic)
        w.book.set_calc_mode("auto")
    return destino

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("reporte");p.add_argument("--salida");p.add_argument("--entrada",action="append",default=[]);p.add_argument("--version",default="Preliminar")
    a=p.parse_args(argv);print(f"Entrega creada en: {generar_entrega(a.reporte,a.salida,a.entrada or None,version=a.version)}")

if __name__=="__main__":main()
