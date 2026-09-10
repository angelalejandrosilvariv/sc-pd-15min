#!/usr/bin/env python3
"""Consolida los archivos de politicas PO. Debe existir una subcarpeta
"Politicas PO" dentro de esta misma carpeta, con los archivos PO*.xls*."""

from __future__ import annotations

import os
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))

from consolidar_politicas import consolidar_politicas  # noqa: E402


def main() -> None:
    os.chdir(CARPETA)
    consolidar_politicas()


if __name__ == "__main__":
    main()
