"""Contrato entre las plantillas CEN y el preprocesamiento de XlsxWriter."""
import sys
from pathlib import Path

from xlsxwriter.worksheet import Worksheet

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from generar_entrega_cen import FORMULAS, WorksheetFormulasPreparadas  # noqa: E402


def test_preparacion_rapida_equivale_a_xlsxwriter_para_todas_las_plantillas():
    valores = dict(r=2, N=101, M=102, C=103, K=104, F=105, R=106, E=107,
                   Z=108, costos=109, col_sc="AA", col_partida="AB",
                   col_detencion="AC", col_margen="AD")
    original = Worksheet()
    original.use_future_functions = True
    rapida = WorksheetFormulasPreparadas()

    for hoja, formulas in FORMULAS.items():
        for columna, plantilla in formulas.items():
            formula = plantilla.format(**valores)
            sin_prefijo = formula.replace("_xlfn.", "")
            esperado = Worksheet._prepare_formula(original, sin_prefijo)
            obtenido = rapida._prepare_formula(formula)
            assert obtenido == esperado, f"{hoja}!{columna}: {formula}"
