"""
Adapter for German DVB-T2 HD multiplex information (official PDF).

Deutsch:
    Adapter für die offizielle DVB-T2-HD-Standortliste (Deutschland).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from pdfminer.high_level import extract_text

from ..models import Profile, TransponderScanEntry
from . import AdapterResult, BaseAdapter, register

log = logging.getLogger(__name__)

STATE_PATTERN = re.compile(r"^[A-Z]{2}(?:\s*\([A-Z]+\))?")
STAND_PATTERN = re.compile(r"Stand:\s*(\d{2}\.\d{2}\.\d{4})")
CHANNEL_PATTERN = re.compile(r"\d{2}")


class ProviderDVBT2DEAdapter(BaseAdapter):
    name = "provider_dvb_t2_de"

    def ingest(self, source_path: Path, config: Dict[str, object]) -> List[Profile]:  # pragma: no cover - legacy
        log.info("provider_dvb_t2_de emits scan entries only; no Enigma2 profile is produced")
        return []

    def ingest_bundle(self, source_path: Path, config: Dict[str, object]) -> AdapterResult:
        pdf_files = sorted(Path(source_path).glob("*.pdf"))
        if not pdf_files:
            raise FileNotFoundError(f"no PDF payloads found in {source_path}")

        entries: List[TransponderScanEntry] = []
        last_seen_global = datetime.now(timezone.utc).isoformat()
        provenance_sources: List[str] = []
        for pdf_path in pdf_files:
            text = extract_text(pdf_path)
            last_seen = _extract_last_seen(text) or last_seen_global
            provenance_sources.append(pdf_path.name)
            for record in _parse_records(text):
                region_code = _build_region_code(record.state, record.site)
                for channel in record.channels:
                    frequency_hz = _channel_to_frequency(channel)
                    if frequency_hz is None:
                        continue
                    extras = {
                        "channel": str(channel),
                        "network": record.network,
                        "site": record.site,
                        "row_index": str(record.index),
                        "source_pdf": pdf_path.name,
                    }
                    if record.polarisation:
                        extras["polarisation_hint"] = record.polarisation
                    entry = TransponderScanEntry(
                        delivery_system="DVB-T2",
                        system="DVB-T2",
                        frequency_hz=frequency_hz,
                        symbol_rate=None,
                        bandwidth_hz=8_000_000,
                        modulation="COFDM",
                        fec=None,
                        polarization=None,
                        plp_id=None,
                        country="DE",
                        provider=record.network or "DVB-T2",
                        region=region_code,
                        last_seen=last_seen,
                        source_provenance=str(pdf_path),
                        extras=extras,
                    )
                    entries.append(entry)

        metadata = {
            "regions": str(len({entry.region for entry in entries if entry.region})),
            "entry_count": str(len(entries)),
            "sources": provenance_sources,
        }
        return AdapterResult(profiles=[], scan_entries=entries, extra_metadata=metadata)


def _extract_last_seen(text: str) -> Optional[str]:
    match = STAND_PATTERN.search(text)
    if not match:
        return None
    try:
        dt = datetime.strptime(match.group(1), "%d.%m.%Y")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


class _Record:
    __slots__ = ("index", "state", "network", "site", "polarisation", "channels")

    def __init__(self, index: int, state: str, network: str, site: str) -> None:
        self.index = index
        self.state = state
        self.network = network
        self.site = site
        self.polarisation: Optional[str] = None
        self.channels: List[int] = []


def _parse_records(text: str) -> Iterable[_Record]:
    records: List[_Record] = []
    current: Optional[_Record] = None
    lines = text.splitlines()
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line or line.startswith("DVB-T2") or line.startswith("Kanal-/Multiplexbelegung"):
            continue
        if set(line) == {" "} or set(line) == {"\x0c"}:
            continue
        state_field = line[0:12].strip()
        network_field = line[12:24].strip()
        site_field = line[24:60].strip()
        pol_field = line[60:68].strip()
        channel_field = line[68:].strip()

        if state_field:
            current = _Record(len(records), state_field, network_field, site_field)
            records.append(current)
        elif site_field and current is not None and site_field not in {"H", "V", "H/V"}:
            current.site = (current.site + " " + site_field).strip()

        if current is None:
            continue

        if pol_field:
            current.polarisation = pol_field

        if channel_field:
            for match in CHANNEL_PATTERN.finditer(channel_field):
                value = int(match.group(0))
                if value not in current.channels:
                    current.channels.append(value)
    return records


def _channel_to_frequency(channel: int) -> Optional[int]:
    if channel < 21 or channel > 60:
        return None
    frequency_mhz = 306 + 8 * channel
    return frequency_mhz * 1_000_000


def _build_region_code(state: str, site: str) -> str:
    state_clean = _slugify(state.upper())
    site_slug = _slugify(site)
    return f"DE-{state_clean}-{site_slug}" if site_slug else f"DE-{state_clean}"


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


register(ProviderDVBT2DEAdapter())
