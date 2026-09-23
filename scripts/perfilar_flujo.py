"""Perfila de forma repetible motor v7 -> prorrateo -> entrega CEN."""
from __future__ import annotations

import argparse
import cProfile
import json
import os
import pstats
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "tests")]

import sc_pd_motor_v7 as motor  # noqa: E402
from generar_datos_volumen import generar  # noqa: E402
from generar_entrega_cen import generar_entrega  # noqa: E402
from resumen_salida import prorratear_salida  # noqa: E402


def medir(nombre, funcion, perfil_dir):
    perfil = cProfile.Profile()
    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    inicio = time.perf_counter()
    resultado = perfil.runcall(funcion)
    segundos = time.perf_counter() - inicio
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    perfil.dump_stats(perfil_dir / f"{nombre}.prof")
    with (perfil_dir / f"{nombre}_top30.txt").open("w") as out:
        pstats.Stats(perfil, stream=out).strip_dirs().sort_stats("cumulative").print_stats(30)
    return resultado, {"etapa": nombre, "segundos": segundos,
                       "rss_max_mib": rss / 1024, "incremento_rss_mib": (rss - rss0) / 1024}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--datos", type=Path, default=ROOT / ".perf-data")
    p.add_argument("--salida", type=Path, default=ROOT / ".perf-results")
    p.add_argument("--rapido", action="store_true")
    a = p.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    etapas = []
    rutas, metrica = medir("lectura_generacion_insumos", lambda: generar(
        a.datos, 8 if a.rapido else 300, 3 if a.rapido else 31), a.salida)
    etapas.append(metrica)
    reporte = a.salida / "Reporte_Sobrecostos_PD_Final.xlsx"
    config = {"RUTA_REPORTE_15MIN": str(rutas["reporte"]), "RUTA_REPORTE_MES_PASADO": str(rutas["reporte_anterior"]),
              "RUTA_RIO": str(rutas["rio"]), "RUTA_RIO_MES_PASADO": "", "RUTA_COSTOS_PD": str(rutas["costos"]),
              "RUTA_COSTOS_MES_PASADO": "", "RUTA_DICCIONARIO": str(rutas["diccionario"]),
              "RUTA_DICCIONARIO_EMPRESA": str(rutas["empresas"]), "RUTA_SALIDA": str(reporte)}
    # ``nulo`` evita que el conjunto sintético (sin historia operacional real)
    # convierta una cota inferior parcial en una clasificación de partida.
    _, metrica = medir("motor_v7_total", lambda: motor.main(
        config, {"HORAS_SIN_HISTORIA": "nulo"}), a.salida); etapas.append(metrica)
    _, metrica = medir("prorrateo_relectura_y_escritura", lambda: prorratear_salida(reporte, rutas["retiros"], a.salida), a.salida); etapas.append(metrica)
    _, metrica = medir("entrega_cen_lectura_excel_csv", lambda: generar_entrega(reporte, a.salida, retiros=rutas["retiros"]), a.salida); etapas.append(metrica)
    (a.salida / "metricas.json").write_text(json.dumps(etapas, indent=2), encoding="utf-8")
    for e in etapas: print(f"{e['etapa']:<38} {e['segundos']:>9.2f}s {e['rss_max_mib']:>10.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
