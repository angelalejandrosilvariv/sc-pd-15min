"""Prueba integrada pequeña del paquete de auditoría de la spec 31."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generar_entrega_cen import generar_entrega, interruptores_panel


def test_genera_siete_archivos_y_diccionario_completo(tmp_path):
    ciclos = pd.DataFrame({
        "Etiqueta_Relacionada": [f"C{i}&1" for i in range(3)],
        "Central_Relacionada": [f"C{i}" for i in range(3)], "Empresa": ["E1", "E1", "E2"],
        "Ciclo_Mes": ["2608"] * 3, "Inicio_Ciclo": pd.date_range("2026-08-01", periods=3),
        "Termino_Ciclo": pd.date_range("2026-08-01 00:45", periods=3),
        "Margen_Suma_Ciclo": [4.] * 3, "Costo_Partida_Base": [10.] * 3,
        "Costo_Detencion_Base": [2.] * 3, "Total SC_PD": [8.] * 3,
    })
    for tipo in ("Partida", "Detencion"):
        for filtro in ("Conf", "Disp", "Op", "CostoCero"):
            ciclos[f"Filtro_{filtro}_{tipo}"] = 1
        ciclos[f"Costo_{tipo}_Efectivo"] = ciclos[f"Costo_{tipo}_Base"]
    filas = []
    for i in range(3):
        for j in range(4):
            filas.append({"Etiqueta_Relacionada": f"C{i}&1", "Central_Relacionada": f"C{i}",
                "Ciclo_ID_Relacionada": 1, "Central": f"C{i}_GN", "FECHA_HORA": pd.Timestamp("2026-08-01") + pd.Timedelta(days=i, minutes=15*j),
                "GENERACION": 1., "CMg": 3., "CV": 2., "Dolar": 1., "Margen": 1.,
                "Fuente_Config_RIO": pd.Timestamp("2026-08-01") + pd.Timedelta(days=i),
                "CONSIGNAS": "PP", "MOTIVO": "OM", "ESTADO OPERACIONAL": "PDO",
                "COMENTARIO": "", "Configuracion RIO": f"C{i}_GN", "Filtro_Operacional": 1,
                "Vigencia_RIO": 1, "Costo_Partida_ML": 10., "Costo_Detencion_ML": 2.,
                "Filtro_CostoCero_Partida": 1, "Filtro_CostoCero_Detencion": 1})
    detalle = pd.DataFrame(filas)
    reporte = tmp_path / "Reporte_Sobrecostos_PD_Final.xlsx"
    with pd.ExcelWriter(reporte) as writer:
        ciclos.to_excel(writer, sheet_name="Resumen_Ciclos_PD", index=False)
        detalle.to_excel(writer, sheet_name="Detalle_15Min", index=False)
        pd.DataFrame({"Empresa": ["E1", "E2"], "Total_SC_PD_CLP": [16., 8.]}).to_excel(writer, sheet_name="SC_por_Empresa", index=False)
        pd.DataFrame({"Columna": ["Margen"], "Que significa": ["Margen de venta"]}).to_excel(writer, sheet_name="Guia_Lectura", index=False)
    destino = generar_entrega(reporte, tablas_dinamicas=True)
    assert len(list(destino.iterdir())) == 7
    params = pd.read_csv(destino / "SCPD_2608_parametros.csv")
    assert set(interruptores_panel()).issubset(set(params["interruptor"]))
    dic = pd.read_csv(destino / "SCPD_2608_diccionario.csv")
    for nombre in ("parametros", "bloques", "ciclos", "candidatas_tarifa", "empresas"):
        df = pd.read_csv(destino / f"SCPD_2608_{nombre}.csv")
        assert set(df.columns).issubset(set(dic.loc[dic.archivo == nombre, "columna"]))


# --- hallazgos de la verificacion con datos reales (16-09) -----------------------------------

def test_referencias_estructuradas_completas():
    """xlsxwriter expande [@Col] a [[#This Row],Col] y Excel no abre el libro: hay que
    escribir Tabla[[#This Row],[Col]]."""
    from generar_entrega_cen import _referencias_completas
    assert (_referencias_completas("=[@SC_recalc]-[@[Total SC_PD]]", "Ciclos")
            == "=Ciclos[[#This Row],[SC_recalc]]-Ciclos[[#This Row],[Total SC_PD]]")
    assert (_referencias_completas("=SUMIFS(Bloques[Margen_recalc],Bloques[Etiqueta_Relacionada],[@Etiqueta_Relacionada])", "Ciclos")
            == "=SUMIFS(Bloques[Margen_recalc],Bloques[Etiqueta_Relacionada],Ciclos[[#This Row],[Etiqueta_Relacionada]])")


def test_libro_no_contiene_referencias_cortas(tmp_path):
    import zipfile, re
    test_genera_siete_archivos_y_diccionario_completo(tmp_path)
    libro = next(tmp_path.rglob("SCPD_2608_Auditoria.xlsx"))
    with zipfile.ZipFile(libro) as z:
        xml = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.startswith("xl/"))
    assert "[[#This Row]," in xml
    assert not re.search(r"(?<![A-Za-z\]])\[\[#This Row\],", xml), "referencia sin nombre de tabla"


def test_bloques_del_mes_anterior_entran_desde_detalle_frontera(tmp_path):
    """Los ciclos que vienen del mes anterior traen su margen completo: sin los bloques de
    ese mes (hoja Detalle_Frontera) el recalculo por bloque no cierra."""
    test_genera_siete_archivos_y_diccionario_completo(tmp_path)
    reporte = tmp_path / "Reporte_Sobrecostos_PD_Final.xlsx"
    hojas = pd.read_excel(reporte, sheet_name=None)
    frontera = hojas["Detalle_15Min"].head(2).copy()
    frontera["FECHA_HORA"] = pd.Timestamp("2026-07-31 23:30"); frontera["Etiqueta_Relacionada"] = "C0&1"
    with pd.ExcelWriter(reporte) as w:
        for nombre, df in hojas.items():
            df.to_excel(w, sheet_name=nombre, index=False)
        frontera.to_excel(w, sheet_name="Detalle_Frontera", index=False)
    destino = generar_entrega(reporte, tmp_path / "salida2")
    bloques = pd.read_csv(destino / "SCPD_2608_bloques.csv")
    assert (pd.to_datetime(bloques.FECHA_HORA) < "2026-08-01").sum() == 2
    assert bloques.groupby("Etiqueta_Relacionada").size()["C0&1"] == 6
