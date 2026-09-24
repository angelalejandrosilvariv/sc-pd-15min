"""Regenera deliberadamente la referencia compacta de punta a punta.

Uso desde la raíz del repositorio::

    python tests/regenerar_huellas.py
"""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "tests")]

COMBINACIONES = {
    "panel_por_defecto": {},
    "margen_hora": {"RESOLUCION_MARGEN": "hora"},
    "orden_om_fallida": {"PARTIDA_EN_PRUEBAS": "validar_orden_om_fallida"},
    "sin_diferir": {"DIFERIR_CICLOS_SIN_TERMINAR": 0},
}


def _valor(valor):
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ["na"]
    if isinstance(valor, (float,)):  # repr es parte explícita del contrato golden
        return ["float", repr(valor)]
    if isinstance(valor, pd.Timestamp):
        return ["fecha", valor.isoformat()]
    return [type(valor).__name__, str(valor)]


def huella(df: pd.DataFrame) -> str:
    contenido = [[_valor(c) for c in df.columns]]
    contenido.extend([_valor(v) for v in fila] for fila in df.itertuples(index=False, name=None))
    normalizado = json.dumps(contenido, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(normalizado.encode("utf-8")).hexdigest()


def _ejecutar(argumentos):
    nombre, panel, base = argumentos
    base = Path(base) / nombre
    datos, salida = base / "datos", base / "salida"
    salida.mkdir(parents=True)

    import sc_pd_motor_v7 as motor
    from generar_datos_volumen import generar
    from generar_entrega_cen import generar_entrega
    from resumen_salida import prorratear_salida

    motor = importlib.reload(motor)
    rutas = generar(datos, configuraciones=8, dias=3)
    reporte = salida / "Reporte_Sobrecostos_PD_Final.xlsx"
    entradas = {
        "RUTA_REPORTE_15MIN": str(rutas["reporte"]),
        "RUTA_REPORTE_MES_PASADO": str(rutas["reporte_anterior"]),
        "RUTA_RIO": str(rutas["rio"]), "RUTA_RIO_MES_PASADO": "",
        "RUTA_COSTOS_PD": str(rutas["costos"]), "RUTA_COSTOS_MES_PASADO": "",
        "RUTA_DICCIONARIO": str(rutas["diccionario"]),
        "RUTA_DICCIONARIO_EMPRESA": str(rutas["empresas"]),
        "RUTA_SALIDA": str(reporte),
    }
    motor.main(entradas, panel)
    prorrateo = prorratear_salida(reporte, rutas["retiros"], salida)
    entrega = generar_entrega(reporte, salida, panel=panel, retiros=rutas["retiros"])

    xl = pd.ExcelFile(reporte)
    hojas = {hoja: huella(pd.read_excel(xl, sheet_name=hoja)) for hoja in xl.sheet_names}
    csv = {}
    for ruta in sorted(entrega.glob("*.csv")):
        nombre_csv = ruta.name.split("_", 2)[-1]
        if nombre_csv == "parametros.csv":
            continue
        csv[nombre_csv] = huella(pd.read_csv(ruta, encoding="utf-8-sig"))

    ciclos = pd.read_excel(reporte, sheet_name="Resumen_Ciclos_PD")
    resumen = next(entrega.glob("*_RESUMEN.csv"))
    saldo = pd.to_numeric(pd.read_csv(resumen, encoding="utf-8-sig")["SALDO"], errors="coerce").sum()
    metricas = {
        "total_sc_pd": repr(float(pd.to_numeric(ciclos["Total SC_PD"], errors="coerce").sum())),
        "ciclos_pagados": int((pd.to_numeric(ciclos["Total SC_PD"], errors="coerce") > 0).sum()),
        "total_repartido": repr(float(prorrateo["total_repartido"])),
        "saldo_resumen": repr(float(saldo)),
    }
    estados = ciclos["Obs_Liquidacion_Final"].fillna("").astype(str)
    cobertura = {
        "pagados": int(estados.str.contains("pago").sum()),
        "cubiertos": int(estados.str.contains("amortizado").sum()),
        "diferidos": int(estados.str.contains("Diferido").sum()),
        "rechazados": int(estados.str.contains("nulo|anulado", case=False, regex=True).sum()),
    }
    partidas = pd.read_csv(next(entrega.glob("*_PARTIDAS_DETENCIONES.csv")), encoding="utf-8-sig")
    return nombre, {"xlsx": hojas, "csv": csv, "metricas": metricas,
                    "cobertura": cobertura,
                    "hay_sscc": bool((partidas["Presta SSCC"] == 1).any())}


def generar_referencia(base: str | Path) -> dict:
    tareas = [(nombre, panel, str(base)) for nombre, panel in COMBINACIONES.items()]
    with ProcessPoolExecutor(max_workers=4) as ejecutor:
        return dict(ejecutor.map(_ejecutar, tareas))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="scpd-huellas-") as temporal:
        referencia = generar_referencia(temporal)
    destino = ROOT / "tests" / "golden" / "huellas.json"
    destino.write_text(json.dumps(referencia, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(f"Referencia escrita en {destino} ({destino.stat().st_size} bytes)")
