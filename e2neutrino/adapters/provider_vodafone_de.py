"""
Adapter stub for Vodafone Germany DVB-C frequencies.

Deutsch:
    Platzhalter-Adapter für Vodafone Deutschland (kein offizielles Frequenzraster verfügbar).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..models import Profile
from . import AdapterResult, BaseAdapter, register


class VodafoneBlockedError(RuntimeError):
    """
    Raised when the Vodafone adapter is invoked without official frequency sources.
    """


BLOCKED_MESSAGE = (
    "provider_vodafone_de is blocked: Vodafone publishes no official DVB-C frequency table "
    "with MHz/Symbolrate/Modulation. Provide an authorised frequency source before enabling."
)


class ProviderVodafoneDEAdapter(BaseAdapter):
    name = "provider_vodafone_de"

    def ingest(self, source_path: Path, config: Dict[str, object]) -> List[Profile]:  # pragma: no cover - legacy
        raise VodafoneBlockedError(BLOCKED_MESSAGE)

    def ingest_bundle(self, source_path: Path, config: Dict[str, object]) -> AdapterResult:
        raise VodafoneBlockedError(BLOCKED_MESSAGE)


register(ProviderVodafoneDEAdapter())
