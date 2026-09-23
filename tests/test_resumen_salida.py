"""Resumen de la salida del motor para la interfaz y prorrateo desde el reporte."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from resumen_salida import (  # noqa: E402
    clasificar_ciclos, formato_clp, formato_mm, prorratear_salida, resumir_salida)

T0 = pd.Timestamp("2026-08-01 00:00")
Q = pd.Timedelta(minutes=15)


def _ciclo(etiqueta, empresa, estado, costos, total, obs="Aprobado"):
    return {"Etiqueta_Relacionada": etiqueta, "Empresa": empresa,
            "Estado_Ciclo_Mes": estado, "Tipo_Partida": "Fria", "Inicio_Ciclo": T0,
            "Costo_Partida_Efectivo": costos, "Costo_Detencion_Efectivo": 0.0,
            "Margen_Suma_Ciclo": costos - total, "Costos_Totales_PD": costos, "Total SC_PD": total,
            "Obs_Partida": obs}


@pytest.fixture
def salida(tmp_path):
    ciclos = pd.DataFrame([
        _ciclo("A&1", "E1", "Inicia y termina este mes", 100.0, 80.0),
        _ciclo("A&2", "E1", "Inicia y termina este mes", 50.0, 0.0),           # cubierto por margen
        _ciclo("B&1", "E2", "Inicia y termina este mes", 0.0, 0.0, "Revisar"),  # rechazado
        _ciclo("B&2", "E2", "Continua proximo mes", 0.0, 0.0),                  # diferido
        _ciclo("C&1", "E3", "Viene del mes anterior", 30.0, 20.0),
    ])
    ciclos["Ciclo_Mes"] = [1, 2, 1, 2, 1]
    detalle = pd.DataFrame({
        "Etiqueta_Relacionada": ["A&1", "A&1", "A&2", "B&2", "C&1"],
        "FECHA_HORA": [T0, T0 + Q, T0 + 2 * Q, T0 + 3 * Q, T0],
    })
    empresas = pd.DataFrame({"Empresa": ["E1", "E3", "E2"], "Ciclos": [2, 1, 2],
                             "Total_SC_PD_CLP": [80.0, 20.0, 0.0]})
    waterfall = pd.DataFrame({"Etapa_Financiera": ["1. Costo Base", "3. PAGO FINAL DE SOBRECOSTO P-D"],
                              "Monto (CLP)": [180.0, 100.0]})
    parametros = pd.DataFrame({"interruptor": ["PARTIDA_EN_PRUEBAS", "OTRO"], "valor": ["rechazar", 1]})
    ruta = tmp_path / "Reporte_Sobrecostos_PD_Final.xlsx"
    with pd.ExcelWriter(ruta) as w:
        ciclos.to_excel(w, sheet_name="Resumen_Ciclos_PD", index=False)
        detalle.to_excel(w, sheet_name="Detalle_15Min", index=False)
        empresas.to_excel(w, sheet_name="SC_por_Empresa", index=False)
        waterfall.to_excel(w, sheet_name="Waterfall_Costos", index=False)
        parametros.to_excel(w, sheet_name="Parametros_Motor", index=False)
    return ruta


def test_formatos_chilenos():
    assert formato_clp(939959962.4) == "$ 939.959.962"
    assert formato_mm(1008974072) == "1.009,0 MM"
    assert formato_mm(68_580_000) == "68,6 MM"


def test_clasificar_ciclos_en_palabras():
    df = pd.DataFrame({"Total SC_PD": [5, 0, 0, 0], "Costos_Totales_PD": [9, 9, 0, 0],
                       "Estado_Ciclo_Mes": ["x", "x", "x", "Continua todo el mes"]})
    assert list(clasificar_ciclos(df)) == ["Pagado", "Cubierto por el margen",
                                           "Sin costo o rechazado por filtros", "Diferido al próximo mes"]


def test_resumir_salida_indicadores_y_tablas(salida):
    r = resumir_salida(salida)
    assert r["total_sc"] == 100 and r["ciclos"] == 5 and r["mes"] == "2608"
    assert (r["pagados"], r["cubiertos"], r["rechazados"], r["diferidos"]) == (2, 1, 1, 1)
    assert r["empresas_con_pago"] == 2
    assert list(r["empresas"]["Empresa"]) == ["E1", "E3", "E2"]
    assert r["empresas"]["Participacion_%"].tolist() == [80.0, 20.0, 0.0]
    assert r["top_ciclos"]["Etiqueta_Relacionada"].iloc[0] == "A&1"
    assert r["waterfall"][-1] == ("3. PAGO FINAL DE SOBRECOSTO P-D", 100.0)
    assert r["parametros"] == {"PARTIDA_EN_PRUEBAS": "rechazar"}
    assert any("Revisar" in a for a in r["avisos"])


def test_resumir_salida_rechaza_un_archivo_que_no_es_del_motor(tmp_path):
    ruta = tmp_path / "otro.xlsx"
    pd.DataFrame({"a": [1]}).to_excel(ruta, index=False)
    with pytest.raises(ValueError, match="Resumen_Ciclos_PD"):
        resumir_salida(ruta)


def test_prorratear_salida_reparte_solo_ciclos_con_monto(salida, tmp_path):
    retiros = tmp_path / "retiros.csv"
    pd.DataFrame({"Cuarto de Hora": [1, 1, 2, 3, 4], "Suministrador": ["S1", "S2", "S1", "S2", "S2"],
                  "Medida_kWh": [-10, -30, -40, -99, -99]}).to_csv(retiros, index=False, sep=";")
    r = prorratear_salida(salida, retiros, tmp_path / "out")
    # A&1 (80) cruza cuartos 1-2: S1 50/80, S2 30/80; C&1 (20) el cuarto 1: S1 1/4, S2 3/4
    pagos = r["por_suministrador"].set_index("Suministrador")["Monetario"]
    assert pagos["S1"] == pytest.approx(80 * 50 / 80 + 20 * 10 / 40)
    assert pagos["S2"] == pytest.approx(80 * 30 / 80 + 20 * 30 / 40)
    assert r["total_repartido"] == pytest.approx(100) and r["delta_total"] == pytest.approx(0)
    # A&2 (cubierto) y B&2 (diferido) no se reparten ni generan avisos de "sin retiros"
    assert r["ciclos"] == 2 and r["ciclos_sin_retiros"] == [] and not r["mensajes"]
    assert r["excel"].exists() and r["csv"].exists()


@pytest.mark.parametrize("motor", ["turbina", "reglas"])
def test_salidas_alternativas_normalizan_etiqueta_y_prorratean(tmp_path, motor):
    ciclos = pd.DataFrame({
        "Empresa": ["E1"], "Inicio_Ciclo": [T0], "Total SC_PD": [100.0],
        "Costos_Totales_PD": [120.0], "Estado_Ciclo_Mes": ["Inicia y termina este mes"],
    })
    detalle = pd.DataFrame({"FECHA_HORA": [T0, T0 + Q]})
    if motor == "turbina":
        ciclos["Etiqueta_Turbina"] = "TG1&1"
        detalle["Etiqueta_Turbina"] = "TG1&1"
    else:
        ciclos["Etiqueta"] = "CEN&1"
        detalle["Central_Relacionada"] = "CEN"
        detalle["Ciclo_ID"] = 1

    salida_motor = tmp_path / f"salida_{motor}.xlsx"
    with pd.ExcelWriter(salida_motor) as w:
        ciclos.to_excel(w, sheet_name="Resumen_Ciclos_PD", index=False)
        detalle.to_excel(w, sheet_name="Detalle_15Min", index=False)
    retiros = tmp_path / f"retiros_{motor}.csv"
    pd.DataFrame({"Cuarto de Hora": [1, 2], "Suministrador": ["S1", "S1"],
                  "Medida_kWh": [-10, -20]}).to_csv(retiros, index=False, sep=";")

    reparto = prorratear_salida(salida_motor, retiros, tmp_path / f"out_{motor}")
    resumen = resumir_salida(salida_motor)
    etiqueta = "TG1&1" if motor == "turbina" else "CEN&1"
    assert reparto["delta_total"] == pytest.approx(0)
    assert reparto["total_repartido"] == pytest.approx(100)
    assert resumen["top_ciclos"]["Etiqueta_Relacionada"].tolist() == [etiqueta]
