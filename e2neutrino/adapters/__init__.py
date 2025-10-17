"""
Adapter registry for ingestion.

Deutsch:
    Adapter-Registry für den Ingest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List

from ..models import Profile, TransponderScanEntry


@dataclass
class AdapterResult:
    profiles: List[Profile]
    scan_entries: List[TransponderScanEntry] = field(default_factory=list)
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


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

    def ingest_bundle(self, source_path: Path, config: Dict[str, object]) -> AdapterResult:
        profiles = self.ingest(source_path, config)
        return AdapterResult(profiles=profiles)


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
    for module in (
        "enigma2",
        "neutrino",
        "dvbsi",
        "m3u",
        "jsonapi",
        "provider_astra",
        "provider_ard",
        "provider_dvb_t2_de",
        "provider_simplitv_at",
        "provider_wilhelm_tel_de",
        "provider_vodafone_de",
    ):
        import_module(f"{package}.{module}")
