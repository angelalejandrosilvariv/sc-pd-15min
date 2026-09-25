"""Regresión real motor -> prorrateo -> entrega sobre el juego rápido."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path[:0] = [str(Path(__file__).parent), str(Path(__file__).parents[1] / "scripts")]
from generar_entrega_cen import generar_entrega  # noqa: E402
from regenerar_huellas import generar_referencia  # noqa: E402
from test_generar_entrega_cen import reporte as fixture_reporte  # noqa: E402

GOLDEN = Path(__file__).parent / "golden" / "huellas.json"


@pytest.fixture(scope="session")
def corrida_punta_a_punta(tmp_path_factory):
    return generar_referencia(tmp_path_factory.mktemp("punta_a_punta"))


def test_huellas_compactas_de_todo_el_flujo(corrida_punta_a_punta):
    esperado = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual = corrida_punta_a_punta
    assert actual.keys() == esperado.keys()
    for combinacion in esperado:
        for artefacto in ("xlsx", "csv"):
            assert actual[combinacion][artefacto].keys() == esperado[combinacion][artefacto].keys()
            for hoja, hash_esperado in esperado[combinacion][artefacto].items():
                assert actual[combinacion][artefacto][hoja] == hash_esperado, (
                    f"Cambió {artefacto} '{hoja}' en la combinación '{combinacion}'")
        metricas_actuales = actual[combinacion]["metricas"]
        metricas_esperadas = esperado[combinacion]["metricas"]
        assert metricas_actuales.keys() == metricas_esperadas.keys()
        assert metricas_actuales["ciclos_pagados"] == metricas_esperadas["ciclos_pagados"]
        for metrica in metricas_esperadas.keys() - {"ciclos_pagados"}:
            assert float(metricas_actuales[metrica]) == pytest.approx(
                float(metricas_esperadas[metrica]), rel=1e-12, abs=1e-6)
        cobertura = actual[combinacion]["cobertura"]
        assert cobertura["pagados"] >= 10
        assert cobertura["cubiertos"] > 0 and cobertura["rechazados"] > 0
        if combinacion != "sin_diferir":
            assert cobertura["diferidos"] > 0


def test_comentario_de_ciclo_vacio_usa_sscc_del_bloque(tmp_path):
    """El comentario agregado puede faltar; el bloque sigue siendo la evidencia."""
    reporte = fixture_reporte.__wrapped__(tmp_path)
    hojas = pd.read_excel(reporte, sheet_name=None)
    ciclo = hojas["Resumen_Ciclos_PD"]["Etiqueta_Relacionada"].eq("C&1")
    hojas["Resumen_Ciclos_PD"].loc[ciclo, "Comentario_Partida"] = pd.NA
    detalle = hojas["Detalle_15Min"]
    primer_bloque = detalle["Etiqueta_Relacionada"].eq("C&1") & detalle["FECHA_HORA"].eq(detalle["FECHA_HORA"].min())
    detalle.loc[primer_bloque, "COMENTARIO"] = "Presta SSCC"
    with pd.ExcelWriter(reporte) as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre, index=False)

    carpeta = generar_entrega(reporte, tmp_path / "entrega")
    partidas = pd.read_csv(next(carpeta.glob("*_PARTIDAS_DETENCIONES.csv")), encoding="utf-8-sig")
    fila = partidas[(partidas["Clave Ciclo"] == "C&1") & (partidas["Proceso_Partida"] == "SI")]
    assert fila["Presta SSCC"].tolist() == [1]
