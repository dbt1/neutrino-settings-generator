"""
Adapter for Austria's simpliTV DVB-T2 antenna channel list (official PDF).

Deutsch:
    Adapter für die simpliTV-Senderliste (DVB-T2, Österreich).
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

STAND_PATTERN_MONTH = re.compile(r"Stand:\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})")
CHANNEL_PATTERN = re.compile(r"\d{2}")

MONTH_LOOKUP = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}


class ProviderSimpliTVATAdapter(BaseAdapter):
    name = "provider_simplitv_at"

    def ingest(self, source_path: Path, config: Dict[str, object]) -> List[Profile]:  # pragma: no cover - legacy
        log.info("provider_simplitv_at emits scan entries only; no Enigma2 profile is produced")
        return []

    def ingest_bundle(self, source_path: Path, config: Dict[str, object]) -> AdapterResult:
        pdf_files = sorted(Path(source_path).glob("*.pdf"))
        if not pdf_files:
            raise FileNotFoundError(f"no PDF payloads found in {source_path}")

        entries: List[TransponderScanEntry] = []
        sources: List[str] = []
        default_last_seen = datetime.now(timezone.utc).isoformat()

        for pdf_path in pdf_files:
            text = extract_text(pdf_path)
            last_seen = _extract_last_seen(text) or default_last_seen
            sources.append(pdf_path.name)
            for record in _parse_records(text):
                region_code = _build_region_code(record.state_code, record.site_name)
                for mux, channels in record.mux_channels.items():
                    for channel in channels:
                        frequency_hz = _channel_to_frequency(channel)
                        if frequency_hz is None:
                            continue
                        extras = {
                            "mux": mux,
                            "channel": str(channel),
                            "bundesland_programme": record.programme or "",
                            "site": record.site_name,
                            "source_pdf": pdf_path.name,
                        }
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
                            country="AT",
                            provider="simpliTV",
                            region=region_code,
                            last_seen=last_seen,
                            source_provenance=str(pdf_path),
                            extras=extras,
                        )
                        entries.append(entry)

        metadata = {
            "regions": str(len({entry.region for entry in entries if entry.region})),
            "entry_count": str(len(entries)),
            "sources": sources,
        }
        return AdapterResult(profiles=[], scan_entries=entries, extra_metadata=metadata)


class _Record:
    __slots__ = ("state_code", "site_name", "programme", "mux_channels")

    def __init__(self, state_code: str, site_name: str, programme: str) -> None:
        self.state_code = state_code
        self.site_name = site_name
        self.programme = programme
        self.mux_channels: Dict[str, List[int]] = {"A": [], "B": [], "C": [], "D": [], "E": [], "F": []}


def _parse_records(text: str) -> Iterable[_Record]:
    records: List[_Record] = []
    current_state: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("simpliTV Kanalliste") or line.startswith("Bundesland-"):
            continue
        if "MUX A" in line and "MUX F" in line:
            continue
        if line.strip() in {"MUX A", "MUX B", "MUX C", "MUX D", "MUX E", "MUX F"}:
            continue

        state_field = line[0:6].strip()
        site_field = line[6:45].strip()
        programme_field = line[45:75].strip()
        mux_a_field = line[75:90].strip()
        mux_b_field = line[90:105].strip()
        mux_c_field = line[105:120].strip()
        mux_d_field = line[120:135].strip()
        mux_e_field = line[135:150].strip()
        mux_f_field = line[150:].strip()

        if state_field and len(state_field) <= 4 and not site_field:
            current_state = state_field
            continue

        if not site_field:
            continue

        state_code = state_field or current_state or ""
        record = _Record(state_code, site_field, programme_field)

        _populate_mux(record, "A", mux_a_field)
        _populate_mux(record, "B", mux_b_field)
        _populate_mux(record, "C", mux_c_field)
        _populate_mux(record, "D", mux_d_field)
        _populate_mux(record, "E", mux_e_field)
        _populate_mux(record, "F", mux_f_field)

        if any(record.mux_channels.values()):
            records.append(record)

    return records


def _populate_mux(record: _Record, mux: str, raw_field: str) -> None:
    if not raw_field or raw_field == "-":
        return
    channels: List[int] = []
    for match in CHANNEL_PATTERN.finditer(raw_field):
        try:
            channels.append(int(match.group(0)))
        except ValueError:
            continue
    if not channels:
        return
    record.mux_channels[mux].extend(channels)


def _channel_to_frequency(channel: int) -> Optional[int]:
    if channel < 21 or channel > 60:
        return None
    frequency_mhz = 306 + 8 * channel
    return frequency_mhz * 1_000_000


def _build_region_code(state_code: str, site_name: str) -> str:
    state_slug = _slugify(state_code or "AT")
    site_slug = _slugify(site_name)
    if site_slug:
        return f"AT-{state_slug}-{site_slug}"
    return f"AT-{state_slug}"


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("ö", "oe").replace("ä", "ae").replace("ü", "ue").replace("ß", "ss")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _extract_last_seen(text: str) -> Optional[str]:
    match = STAND_PATTERN_MONTH.search(text)
    if not match:
        return None
    month_name = match.group(1).lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    year = int(match.group(2))
    month = MONTH_LOOKUP.get(month_name)
    if not month:
        return None
    dt = datetime(year, month, 1, tzinfo=timezone.utc)
    return dt.isoformat()


register(ProviderSimpliTVATAdapter())
