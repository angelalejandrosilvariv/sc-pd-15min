from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from comparar_con_excel_horario import (  # noqa: E402
    aparear_ciclos, asignar_causas, descomponer_efectos,
    leer_excel_horario, preparar_ciclos_excel,
)


def _libro_horario(tmp_path):
    ruta = tmp_path / "horario.xlsx"
    ciclos = pd.DataFrame([
        ["A&1", 100, 20, 10, 999, 999, 110, "EMP", 0],
        ["B&1", 30, 0, 50, 0, 0, 0, "EMP", 0],
        ["C&1", 5, 0, 0, 0, 0, 5, "Se traspasa al proximo mes", 0],
    ], columns=["Ciclo de operación", "Total Costos Partida", "Total Costos Detención",
                "Total Margen", "Total Costos Partida ciclo inconcluso",
                "Margen ciclo inconcluso", "Total Sobrecosto_P-D", "Empresa", "SSCC"])
    x = pd.DataFrame([
        [260801, 1, "A_CFG", 1, "A&1", "SI", 0, 100, 0, 1, 1, 1, 10, 1, 1],
        [260801, 2, "A_CFG", 1, "A&1", 0, "SI", 0, 20, 1, 1, 1, 0, 1, 1],
        [260802, 3, "B_CFG", 1, "B&1", "SI", 0, 30, 0, 1, 1, 1, 50, 1, 1],
    ], columns=["fecha", "hora", "central", "generacion", "Ciclo de operación", "Partida",
                "Detencion", "COSTO_PARTIDA [$]", "COSTO_DETENCION [$]", "CMg", "CV", "USD",
                "Margen", "Disponible (1) / Pruebas (0)", "Conf despachada RIO"])
    pdx = pd.DataFrame([["A&1", "P", "D", "", "", 1, 100, 20]], columns=[
        "Clave Ciclo ", "Proceso_Partida", "proceso_detencion", "Instrucción", "Operación",
        "Presta SSCC", "Monto Partidas", "Monto Detenciones"])
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        ciclos.to_excel(w, sheet_name="Sobrecosto_Ciclo", index=False)
        x.to_excel(w, sheet_name="Sobrecosto_PD xHyC", index=False)
        pdx.to_excel(w, sheet_name="PARTIDAS_DETENCIONES", index=False)
    return ruta


def test_lee_fechas_y_recalcula_sc_sin_herencia(tmp_path):
    c, x, _ = leer_excel_horario(_libro_horario(tmp_path))
    c = preparar_ciclos_excel(c, x).set_index("Ciclo")
    assert c.loc["A&1", "inicio"] == pd.Timestamp("2026-08-01 00:00")
    assert c.loc["A&1", "fin"] == pd.Timestamp("2026-08-01 01:00")
    assert c.loc["A&1", "SC_Propio"] == 110  # ignora 999 + 999 heredados
    assert c.loc["B&1", "SC_Propio"] == 0  # MAX(0, ...) activo
    assert bool(c.loc["C&1", "Traspasa"])


def test_apareo_traslape_exclusivos_y_descomposicion_exacta(tmp_path):
    c, x, _ = leer_excel_horario(_libro_horario(tmp_path)); ex = preparar_ciclos_excel(c, x)
    ex = ex[ex.Ciclo.isin(["A&1", "B&1"])].copy(); ex["SC_Comparacion"] = ex.SC_Propio
    mo = pd.DataFrame([
        {"Etiqueta_Relacionada":"A_m", "Central_Relacionada":"A", "Empresa":"EMP",
         "Inicio_Ciclo":pd.Timestamp("2026-08-01 01:30"), "Termino_Ciclo":pd.Timestamp("2026-08-01 01:45"),
         "Costo_Partida_Efectivo":40, "Costo_Detencion_Efectivo":20, "Margen_Suma_Ciclo":100,
         "Total SC_PD":0},  # traslapa por los 59 minutos y activa MAX
        {"Etiqueta_Relacionada":"D_m", "Central_Relacionada":"D", "Empresa":"EMP",
         "Inicio_Ciclo":pd.Timestamp("2026-08-03"), "Termino_Ciclo":pd.Timestamp("2026-08-03 01:00"),
         "Costo_Partida_Efectivo":7, "Costo_Detencion_Efectivo":0, "Margen_Suma_Ciclo":0,
         "Total SC_PD":7},
    ])
    p = descomponer_efectos(aparear_ciclos(mo, ex))
    assert set(p.Motor) == {"A_m", "D_m", ""}
    assert p.loc[p.Motor.eq("A_m"), "pareado"].item()
    assert not p.loc[p.Motor.eq("D_m"), "pareado"].item()
    assert (p.Efecto_P + p.Efecto_D + p.Efecto_M - p.dSC).abs().max() < 1


def test_familias_de_causa_raiz():
    base = {"Empresa":"E", "Central":"X", "Motor":"m", "Excel":"e", "pareado":True,
            "Mo_P":10., "Ex_P":0., "Mo_D":0., "Ex_D":0., "Mo_M":0., "Ex_M":0.,
            "Mo_SC":10., "Ex_SC":0., "Obs_P":"", "Obs_D":"", "Vigencia_P":1,
            "Vigencia_D":1, "Config_Tarifa":"", "Config_RIO":"", "Tipo":""}
    rows = []
    # R2, R3, R4, R5, R6, R7, R9, más R1/R1b.
    for central, ex_p, mo_p, obs, mo_m, ex_m in [
        ("X",0,10,"",0,0), ("Y",0,10,"",0,0), ("Z",0,10,"",0,0),
        ("W",10,0,"Rechazo: instruccion RIO fuera de vigencia",0,0),
        ("Q",5,10,"",0,0), ("PENON_DIESEL",5,10,"",0,0), ("M",10,10,"",10,5)]:
        r = dict(base, Central=central, Excel=central, Ex_P=float(ex_p), Mo_P=float(mo_p),
                 Obs_P=obs, Mo_M=float(mo_m), Ex_M=float(ex_m))
        r["Mo_SC"] = max(0, mo_p-mo_m); r["Ex_SC"] = max(0, ex_p-ex_m); rows.append(r)
    rows += [dict(base, Central="SM", Excel="", pareado=False, Mo_SC=10),
             dict(base, Central="SE", Motor="", Mo_P=0, Ex_P=10, Mo_SC=0, Ex_SC=10, pareado=False)]
    p = descomponer_efectos(pd.DataFrame(rows))
    ints = pd.DataFrame({"p_flag":[0,1,1,1,1,1,1], "U":[0,10,0,10,5,5,10],
                         "pruebas_p":[0,0,1,0,0,0,0], "conf_p":[0]*7,
                         "d_flag":[0]*7, "V":[0]*7, "Instruccion":["","","","I","I","I","I"]},
                        index=["X","Y","Z","W","Q","PENON_DIESEL","M"])
    _, efectos = asignar_causas(p, ints)
    causas = " ".join(efectos.Causa)
    for codigo in ("R1 ", "R1b", "R2 ", "R3 ", "R4 ", "R5 ", "R6 ", "R7 ", "R9 "):
        assert codigo in causas


# --- forma real del libro del CEN (hallada al correr con datos): columnas repetidas, filas vacias,
# --- herencia del mes anterior y empalme con el mes anterior en la salida del motor ---------------

def _libro_real(tmp_path):
    """Como el libro real: 'Sobrecosto_Ciclo' trae ademas 'Copia Ciclo' y 'Ciclo', encabezados
    vacios repetidos y filas en blanco bajo la tabla; un &1 hereda partida y margen de julio."""
    ruta = tmp_path / "horario_real.xlsx"
    ciclos = pd.DataFrame([
        ["A&1", 1, 100, 20, 10, 40, 500, 0, "EMP", "A&1", "EMP", None, None, "A", 0],
        ["A&2", 1, 100, 20, 10, 0, 0, 110, "EMP", "A&2", "EMP", None, None, "A", 0],
        [None, None, None, None, None, None, None, None, None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None, None, None, None, None, None, None],
    ], columns=["Ciclo de operación", "Ciclo completo", "Total Costos Partida", "Total Costos Detención",
                "Total Margen", "Total Costos Partida ciclo inconcluso", "Margen ciclo inconcluso",
                "Total Sobrecosto_P-D", "Empresa", "Copia Ciclo", "Cuadro de pagos?", None, None, "Ciclo", "SSCC"])
    x = pd.DataFrame([
        [260801, 1, "A_CFG", 1, "A&1", "SI", 0, 100, 0, 1, 1, 1, 10, 1, 1],
        [260805, 3, "A_CFG", 1, "A&2", "SI", 0, 100, 0, 1, 1, 1, 10, 1, 1],
        [260805, 4, "A_CFG", 1, "A&2", 0, "SI", 0, 20, 1, 1, 1, 0, 1, 1],
    ], columns=["fecha", "hora", "central", "generacion", "Ciclo de operación", "Partida",
                "Detencion", "COSTO_PARTIDA [$]", "COSTO_DETENCION [$]", "CMg", "CV", "USD",
                "Margen", "Disponible (1) / Pruebas (0)", "Conf despachada RIO"])
    pdx = pd.DataFrame([["A&2", "P", "D", "OM", "", 1, 100, 20]], columns=[
        "Clave Ciclo ", "Proceso_Partida", "proceso_detencion", "Instrucción", "Operación",
        "Presta SSCC", "Monto Partidas", "Monto Detenciones"])
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        ciclos.to_excel(w, sheet_name="Sobrecosto_Ciclo", index=False)
        x.to_excel(w, sheet_name="Sobrecosto_PD xHyC", index=False)
        pdx.to_excel(w, sheet_name="PARTIDAS_DETENCIONES", index=False)
    return ruta


def _salida_motor_con_empalme(tmp_path):
    ruta = tmp_path / "motor.xlsx"
    motor = pd.DataFrame([
        # ciclo de julio que cierra en agosto: no debe fijar el mes de comparacion
        ["A&1", "A", "EMP", "Viene del mes anterior", "2026-07-30 10:00", "2026-08-01 02:00",
         100, 20, 10, 110, "Aprobado", "Aprobado", "A_CFG", "A_CFG", "Fria", 1, 1],
        ["A&2", "A", "EMP", "Inicia y termina este mes", "2026-08-05 02:15", "2026-08-05 03:30",
         100, 20, 10, 110, "Aprobado", "Aprobado", "A_CFG", "A_CFG", "Fria", 1, 1],
    ], columns=["Etiqueta_Relacionada", "Central_Relacionada", "Empresa", "Estado_Ciclo_Mes", "Inicio_Ciclo",
                "Termino_Ciclo", "Costo_Partida_Efectivo", "Costo_Detencion_Efectivo", "Margen_Suma_Ciclo",
                "Total SC_PD", "Obs_Partida", "Obs_Detencion", "Config_Tarifa_Partida", "Config_RIO_Usada_Partida",
                "Tipo_Partida", "Vigencia_RIO_Partida", "Vigencia_RIO_Detencion"])
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        motor.to_excel(w, sheet_name="Resumen_Ciclos_PD", index=False)
    return ruta


def test_libro_real_columnas_repetidas_y_filas_vacias(tmp_path):
    c, x, _ = leer_excel_horario(_libro_real(tmp_path))
    e = preparar_ciclos_excel(c, x)

    assert list(e.Ciclo) == ["A&1", "A&2"]            # sin filas vacias
    assert e.columns.is_unique                        # 'Ciclo' ya no choca con la columna auxiliar
    assert e.set_index("Ciclo").loc["A&1", "Herencia_M"] == 500


def test_comparar_usa_el_mes_de_los_ciclos_propios_y_cierra_la_herencia(tmp_path):
    from comparar_con_excel_horario import comparar
    hojas = comparar(_salida_motor_con_empalme(tmp_path), _libro_real(tmp_path), tmp_path / "cmp.xlsx")
    r = hojas["Resumen"].set_index("Alcance")

    # El mes es agosto (los ciclos propios), no julio (minimo de Inicio_Ciclo del empalme).
    assert r.loc["Solo ciclos del mes", "Ciclos_Excel"] == 1
    assert r.loc["Solo ciclos del mes", "Ciclos_Motor"] == 1
    assert r.loc["Solo ciclos del mes", "Delta"] == 0
    # Mes completo: el SC publicado del &1 es 0 por el margen heredado (100+20+40-10-500 < 0);
    # la descomposicion debe cerrar contra ese SC, no contra las columnas propias.
    assert r.loc["Mes completo", "SC_Excel"] == 110
    pares = hojas["Pares"]; fila = pares[(pares.Alcance == "Mes completo") & (pares.Excel == "A&1")].iloc[0]
    assert fila.Ex_SC == 0 and fila.Ex_P == 140 and fila.Ex_M == 510
    assert abs(fila.Efecto_P + fila.Efecto_D + fila.Efecto_M - fila.dSC) < 2
