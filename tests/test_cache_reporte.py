import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from cache_reporte import cache_vigente, carpeta_cache, escribir_cache, leer_hoja_cache


def test_cache_parquet_roundtrip_y_control_de_vigencia(tmp_path, monkeypatch):
    """El caché sólo puede reemplazar la lectura si es posterior al XLSX."""
    reporte = tmp_path / "Reporte.xlsx"
    reporte.write_bytes(b"xlsx")
    monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda self, path, index=False: self.to_pickle(path))
    monkeypatch.setattr(pd, "read_parquet", pd.read_pickle)
    esperado = pd.DataFrame({"A": [1, 2], "Fecha": pd.to_datetime(["2026-08-01", "2026-08-02"])})
    assert escribir_cache(reporte, {"Detalle_15Min": esperado}) == carpeta_cache(reporte)
    assert cache_vigente(reporte)
    pd.testing.assert_frame_equal(leer_hoja_cache(reporte, "Detalle_15Min"), esperado)

    futuro = time.time() + 2
    os.utime(reporte, (futuro, futuro))
    assert not cache_vigente(reporte)
    assert leer_hoja_cache(reporte, "Detalle_15Min") is None


def test_sin_motor_parquet_no_impide_exportar(tmp_path, monkeypatch):
    reporte = tmp_path / "Reporte.xlsx"
    reporte.write_bytes(b"xlsx")

    def sin_motor(*args, **kwargs):
        raise ImportError("pyarrow no instalado")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", sin_motor)
    assert escribir_cache(reporte, {"Hoja": pd.DataFrame({"x": [1]})}) is None
    assert not carpeta_cache(reporte).exists()
