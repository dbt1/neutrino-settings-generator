"""
Adapter for ARD Empfangsparameter (HD) page.

Deutsch:
    Adapter für die ARD-HD-Empfangsparameter (Astra 19.2E).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from ..models import Profile, TransponderScanEntry
from . import AdapterResult, BaseAdapter, register

log = logging.getLogger(__name__)

TRANSPONDER_PATTERN = re.compile(
    r"Transponder\s*(?P<tp>\d+)\s*/\s*Downlink-Frequenz\s*\(GHz\)\s*:\s*(?P<freq>[\d,\.]+)",
    re.IGNORECASE,
)
POLARISATION_PATTERN = re.compile(r"Polarisation\s*:\s*(?P<pol>[a-z]+)", re.IGNORECASE)
SYMBOL_RATE_PATTERN = re.compile(
    r"Symbolrate\s*\(MSym/s\)\s*:\s*(?P<sr>[\d,\.]+)", re.IGNORECASE
)
FEC_PATTERN = re.compile(r"Fehlerschutz\s*\(FEC\)\s*:\s*(?P<fec>[0-9/]+)", re.IGNORECASE)
MODULATION_PATTERN = re.compile(r"Modulation\s*:\s*(?P<mod>[\w\- ]+)", re.IGNORECASE)


class ProviderArdAdapter(BaseAdapter):
    name = "provider_ard"

    def ingest(self, source_path: Path, config: Dict[str, object]) -> List[Profile]:  # pragma: no cover - legacy
        log.info("provider_ard emits scan entries only; no Enigma2 profile is produced")
        return []

    def ingest_bundle(self, source_path: Path, config: Dict[str, object]) -> AdapterResult:
        html_files = sorted(Path(source_path).glob("*.html"))
        if not html_files:
            raise FileNotFoundError(f"no HTML payloads found in {source_path}")

        provider_name = str(config.get("provider_name") or "ARD HD (Astra 19.2E)")
        delivery_system = str(config.get("delivery_system") or "DVB-S")
        region = str(config.get("region") or "DE-ARD-HD")
        source_url = str(config.get("url") or "")
        timestamp = datetime.now(timezone.utc).isoformat()

        entries: List[TransponderScanEntry] = []
        for html_path in html_files:
            soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
            for paragraph in soup.find_all("p"):
                text = paragraph.get_text(separator=" ", strip=True)
                entry = _parse_paragraph(
                    text,
                    provider=provider_name,
                    region=region,
                    delivery_system=delivery_system,
                    last_seen=timestamp,
                    source_url=source_url or html_path.as_uri(),
                )
                if entry:
                    entries.append(entry)

        metadata = {
            "provider": provider_name,
            "region": region,
            "entry_count": str(len(entries)),
            "source_url": source_url,
        }

        return AdapterResult(profiles=[], scan_entries=entries, extra_metadata=metadata)


def _parse_paragraph(
    text: str,
    *,
    provider: str,
    region: str,
    delivery_system: str,
    last_seen: str,
    source_url: str,
) -> Optional[TransponderScanEntry]:
    if "Transponder" not in text:
        return None

    tp_match = TRANSPONDER_PATTERN.search(text)
    pol_match = POLARISATION_PATTERN.search(text)
    sr_match = SYMBOL_RATE_PATTERN.search(text)
    fec_match = FEC_PATTERN.search(text)
    mod_match = MODULATION_PATTERN.search(text)

    if not tp_match:
        return None

    try:
        frequency_ghz = float(tp_match.group("freq").replace(",", "."))
    except ValueError:
        log.debug("provider_ard: invalid frequency in paragraph %s", text)
        return None

    frequency_hz = int(frequency_ghz * 1_000_000_000)
    symbol_rate = None
    if sr_match:
        try:
            symbol_rate = int(float(sr_match.group("sr").replace(",", ".")) * 1_000_000)
        except ValueError:
            symbol_rate = None

    fec_value = fec_match.group("fec") if fec_match else None
    modulation_raw = mod_match.group("mod") if mod_match else None
    system = delivery_system
    modulation = None
    if modulation_raw:
        parts = modulation_raw.upper().split()
        if parts and parts[0].startswith("DVB-"):
            system = parts[0]
            modulation = " ".join(parts[1:]) if len(parts) > 1 else None
        else:
            modulation = modulation_raw.upper()

    extras: Dict[str, str] = {}
    if tp_match and tp_match.group("tp"):
        extras["transponder_number"] = tp_match.group("tp")

    return TransponderScanEntry(
        delivery_system=delivery_system,
        system=system,
        frequency_hz=frequency_hz,
        symbol_rate=symbol_rate,
        bandwidth_hz=None,
        modulation=modulation,
        fec=fec_value,
        polarization=_coerce_polarisation(pol_match.group("pol") if pol_match else None),
        plp_id=None,
        country="DE",
        provider=provider,
        region=region,
        last_seen=last_seen,
        source_provenance=source_url,
        extras=extras,
    )


def _coerce_polarisation(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    value = raw.strip().upper()
    if value.startswith("H"):
        return "H"
    if value.startswith("V"):
        return "V"
    if value.startswith("L"):
        return "L"
    if value.startswith("R"):
        return "R"
    return value


register(ProviderArdAdapter())
