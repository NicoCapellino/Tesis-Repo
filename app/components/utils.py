"""
Utilidades compartidas para las páginas del dashboard.
"""

from __future__ import annotations

import re


def slugify(label: str) -> str:
    """Convertir un label de capa USGS a un slug válido para nombres de variables y columnas."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
