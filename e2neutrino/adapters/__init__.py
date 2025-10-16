"""
Adapter registry for ingestion.

Deutsch:
    Adapter-Registry für den Ingest.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Dict, List

from ..models import Profile


class BaseAdapter:
    """
    Base class for all ingestion adapters.

    Deutsch:
        Basisklasse für alle Ingest-Adapter.
    """

    name = "base"

    def ingest(self, source_path: Path, config: Dict[str, object]) -> List[Profile]:  # pragma: no cover - abstract
        raise NotImplementedError

    def default_profile_id(self, source_path: Path) -> str:
        return Path(source_path).name


_REGISTRY: Dict[str, BaseAdapter] = {}
_BOOTSTRAPPED = False


def register(adapter: BaseAdapter) -> None:
    _REGISTRY[adapter.name] = adapter


def get_adapter(name: str) -> BaseAdapter:
    global _BOOTSTRAPPED
    if not _BOOTSTRAPPED:
        _bootstrap()
        _BOOTSTRAPPED = True
    adapter = _REGISTRY.get(name)
    if not adapter:
        raise KeyError(f"adapter {name} not registered")
    return adapter


def list_adapters() -> List[str]:
    if not _BOOTSTRAPPED:
        _bootstrap()
    return sorted(_REGISTRY.keys())


def _bootstrap() -> None:
    # Import modules to trigger registration side effects.
    package = __name__
    for module in ("enigma2", "neutrino", "dvbsi", "m3u", "jsonapi"):
        import_module(f"{package}.{module}")
