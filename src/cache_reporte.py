"""Caché Parquet opcional de las hojas del reporte del motor.

El Excel sigue siendo el artefacto contractual. El caché sólo se usa cuando
está completo, fue escrito después del libro y hay un motor Parquet disponible.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def carpeta_cache(reporte: str | Path) -> Path:
    ruta = Path(reporte)
    return ruta.with_name(f"{ruta.stem}_cache")


def escribir_cache(reporte: str | Path, hojas: dict[str, pd.DataFrame]) -> Path | None:
    """Escribe atómicamente un caché; devuelve ``None`` sin pyarrow/fastparquet."""
    destino = carpeta_cache(reporte)
    temporal = destino.with_name(destino.name + ".tmp")
    try:
        if temporal.exists():
            for archivo in temporal.iterdir():
                archivo.unlink()
        temporal.mkdir(parents=True, exist_ok=True)
        escritas = []
        for nombre, datos in hojas.items():
            try:
                datos.to_parquet(temporal / f"{nombre}.parquet", index=False)
                escritas.append(nombre)
            except (ValueError, TypeError, OverflowError):
                # Parametros_Motor, por ejemplo, mezcla strings y números en
                # una columna. No se fuerza su tipo: esa hoja usa el Excel.
                (temporal / f"{nombre}.parquet").unlink(missing_ok=True)
        if not escritas:
            raise ValueError("ninguna hoja admite serialización Parquet")
        (temporal / "manifest.json").write_text(
            json.dumps({"version": 1, "hojas": escritas}, ensure_ascii=False),
            encoding="utf-8",
        )
        if destino.exists():
            for archivo in destino.iterdir():
                archivo.unlink()
            destino.rmdir()
        temporal.replace(destino)
        return destino
    except (ImportError, ModuleNotFoundError, ValueError, OSError):
        if temporal.exists():
            for archivo in temporal.iterdir():
                archivo.unlink()
            temporal.rmdir()
        return None


def cache_vigente(reporte: str | Path) -> bool:
    reporte, cache = Path(reporte), carpeta_cache(reporte)
    manifest = cache / "manifest.json"
    return manifest.is_file() and cache.stat().st_mtime_ns >= reporte.stat().st_mtime_ns


def leer_hoja_cache(reporte: str | Path, nombre: str) -> pd.DataFrame | None:
    """Lee una hoja si el caché es vigente; cualquier incompatibilidad hace fallback."""
    archivo = carpeta_cache(reporte) / f"{nombre}.parquet"
    if not cache_vigente(reporte) or not archivo.is_file():
        return None
    try:
        return pd.read_parquet(archivo)
    except (ImportError, ModuleNotFoundError, ValueError, OSError):
        return None
