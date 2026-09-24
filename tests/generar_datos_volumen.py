"""Generador reproducible de insumos de volumen para perfilar el flujo SC-PD.

El tamaño por defecto representa un mes de 31 días y 300 configuraciones
(892.800 filas). ``--rapido`` crea el mismo conjunto de casos en una muestra
pequeña, apropiada para desarrollo y regresión.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEMILLA = 35015


def generar(destino: str | Path, configuraciones: int = 300, dias: int = 31) -> dict[str, Path]:
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEMILLA)
    fechas = pd.date_range("2026-08-01", periods=dias * 96, freq="15min")
    cfg = np.array([f"CENTRAL_{i:03d}_CFG{i % 3 + 1}" for i in range(configuraciones)])
    centrales = np.array([f"CENTRAL_{i:03d}" for i in range(configuraciones)])
    n = len(fechas) * configuraciones
    generacion = rng.gamma(2, 6, n)
    # Paradas periódicas producen ciclos, ciclos sin instrucción y costo cero.
    bloque = np.tile(np.arange(len(fechas)), configuraciones)
    generacion[(bloque % 97) < 8] = 0
    reporte = pd.DataFrame({
        "FECHA_HORA": np.tile(fechas, configuraciones),
        "UNIDAD GENERADORA": np.repeat(centrales, len(fechas)),
        "Central": np.repeat(cfg, len(fechas)),
        "CONFIGURACION": np.repeat(cfg, len(fechas)),
        "GENERACION": generacion,
        # Un margen acotado permite combinar ciclos pagados y amortizados sin
        # depender de valores extremos aleatorios.
        "CMg": rng.uniform(65, 105, n), "CV": rng.uniform(45, 75, n),
        "Dolar": np.full(n, 920.0), "CMg-CV": np.zeros(n), "Tipo": "C.Frec",
    })
    actual = destino / "Reporte_PD_15min_2608.csv"
    reporte.to_csv(actual, index=False)
    # Un día previo permite ciclos que cruzan la frontera mensual.
    pasado = reporte.iloc[: configuraciones * 96].copy()
    pasado["FECHA_HORA"] = pd.to_datetime(pasado["FECHA_HORA"]) - pd.Timedelta(days=1)
    ruta_pasado = destino / "Reporte_PD_15min_2607.csv"
    pasado.to_csv(ruta_pasado, index=False)

    diccionario = pd.DataFrame({"Central": cfg, "Relacionada": centrales})
    dic = destino / "Diccionario_central_config.xlsx"
    diccionario.to_excel(dic, index=False)
    emp = destino / "Diccionario_configuracion_empresa.xlsx"
    pd.DataFrame({"Central": centrales, "Empresa": [f"EMP_{i % 12:02d}" for i in range(configuraciones)]}).to_excel(emp, index=False)

    dias_costos = pd.date_range("2026-07-31", periods=dias + 1)
    costos = []
    for fecha in dias_costos:
        for i, unidad in enumerate(cfg):
            # Cinco centrales tienen dos ciclos completos cuyo costo supera con
            # holgura el margen (10 pagos); las restantes ejercitan margen y
            # filtros. CENTRAL_000 conserva el caso explícito de costo cero.
            tarifa_partida = 250000 if 1 <= i <= 5 else 30000
            tarifa_detencion = 50000 if 1 <= i <= 5 else 5000
            costos.append({"Llave_Concatenada": f"{fecha:%y%m%d}-1{unidad}", "UNIDAD": unidad,
                           "Fria_Num1_M": 24, "Tibia_Num1_O": 8, "Tibia_Num2_N": 16,
                           "Caliente_Num1_P": 4, "Partida_Fria": tarifa_partida + i,
                           "Partida_Tibia": tarifa_partida + i,
                           "Partida_Tibia_2": tarifa_partida + i,
                           "Partida_Caliente": tarifa_partida + i,
                           "Detencion": tarifa_detencion + i,
                           "Costo_Cero": "SI" if i == 0 else "NO"})
    costos_df = pd.DataFrame(costos)
    costos_path = destino / "Costos_de_P-D_Consolidado.xlsx"
    costos_df.to_excel(costos_path, index=False)

    # Encabezado real del RIO comienza en fila 5 (skiprows=4).
    rio_rows = []
    # Sólo hacen falta instrucciones en los extremos de los ciclos. Mantener el
    # RIO compacto acelera tanto el cruce como la entrega sin perder cobertura.
    extremos = {8, 96, 105, 193, 202}
    for bloque_i in sorted(extremos & set(range(len(fechas)))):
        instante = fechas[bloque_i]
        for c in range(configuraciones):
            motivo, comentario = "OM", ""
            # Una detención OT con SSCC y otra sin SSCC cubren las dos ramas.
            if c == 6 and bloque_i == 96:
                motivo, comentario = "OT", "Presta SSCC"
            elif c == 6 and bloque_i == 193:
                motivo = "OT"
            # Un ciclo completo rechazado por una instrucción EP.
            elif c == 7 and 8 <= bloque_i <= 96:
                motivo = "EP"
            estado = "N" if (c == 7 and 8 <= bloque_i <= 96) or (c == 6 and bloque_i == 193) else "PDO"
            rio_rows.append({"FECHA": instante.date(), "HORA": instante.strftime("%H:%M"),
                             "NOMBRE CONFIGURACIÓN": cfg[c], "CON": "", "MOT": motivo,
                             "EO": estado, "COMENTARIO": comentario})
    rio_path = destino / "RIO_08_2026.xlsx"
    with pd.ExcelWriter(rio_path) as writer:
        pd.DataFrame(rio_rows).to_excel(writer, index=False, startrow=4)

    retiros_path = destino / "Retiros_15min.csv"
    cuartos = np.arange(1, len(fechas) + 1)
    suministradores = [f"SUM_{i:02d}" for i in range(80)]
    retiros = pd.DataFrame({"Cuarto de Hora": np.repeat(cuartos, 80),
                            "Suministrador": np.tile(suministradores, len(cuartos)),
                            "Medida_kWh": -rng.uniform(100, 10000, len(cuartos) * 80)})
    retiros.to_csv(retiros_path, index=False)
    return {"reporte": actual, "reporte_anterior": ruta_pasado, "rio": rio_path,
            "costos": costos_path, "diccionario": dic, "empresas": emp, "retiros": retiros_path}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("destino", nargs="?", default=".perf-data")
    p.add_argument("--rapido", action="store_true")
    a = p.parse_args()
    rutas = generar(a.destino, configuraciones=8 if a.rapido else 300, dias=3 if a.rapido else 31)
    print("\n".join(f"{k}: {v}" for k, v in rutas.items()))
