"""
Schema resources bundled with the project.

Deutsch:
    Mitgelieferte JSON-Schemata für Validierungen.
"""

from __future__ import annotations

__all__ = ["load_schema"]

from importlib import resources
from json import load
from typing import Any, Dict


def load_schema(name: str) -> Dict[str, Any]:
    """
    Load a JSON schema from the local schema package.

    Deutsch:
        Lädt ein JSON-Schema aus dem Schema-Paket.
    """

    with resources.files(__name__).joinpath(name).open("r", encoding="utf-8") as fh:
        return load(fh)
