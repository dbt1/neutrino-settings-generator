"""
Adapter for the ASTRA channel finder JSON endpoint.

Deutsch:
    Adapter für die ASTRA-Senderübersicht (Channel Finder API).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..models import Profile, TransponderScanEntry
from . import AdapterResult, BaseAdapter, register

log = logging.getLogger(__name__)

DEFAULT_URL = (
    "https://astra.de/channel-finder/listing"
    "?filter%5Blanguage%5D=german"
    "&filter%5Borbital_position%5D=19.20"
    "&filter%5Bpay_model%5D=free"
    "&layout=list"
    "&more_filters=no"
    "&tv=on"
    "&items_per_page=500"
)


class ProviderAstraAdapter(BaseAdapter):
    """
    Ingest ASTRA channel metadata and emit scanfile transponder entries.
    """

    name = "provider_astra"

    def ingest(self, source_path: Path, config: Dict[str, object]) -> List[Profile]:  # pragma: no cover - legacy
        log.info("provider_astra emits scan entries only; no Enigma2 profile is produced")
        return []

    def ingest_bundle(self, source_path: Path, config: Dict[str, object]) -> AdapterResult:
        payloads = list(_load_payloads(source_path))
        if not payloads:
            raise FileNotFoundError(f"no JSON payloads found in {source_path}")

        provider_name = str(config.get("provider_name") or config.get("position") or "ASTRA 19.2E")
        delivery_system = str(config.get("delivery_system") or "DVB-S")
        orbital_position = str(config.get("orbital_position") or "19.2E")
        source_url = str(config.get("url") or DEFAULT_URL)

        entries: List[TransponderScanEntry] = []
        timestamp = datetime.now(timezone.utc).isoformat()

        for payload in payloads:
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict) and "data" in payload:
                rows = payload["data"]
            else:
                log.warning("provider_astra: unsupported payload type %s", type(payload))
                continue
            for row in rows:
                entry = _coerce_entry(
                    row,
                    provider_name=provider_name,
                    delivery_system=delivery_system,
                    orbital_position=orbital_position,
                    last_seen=timestamp,
                    source_url=source_url,
                )
                if entry:
                    entries.append(entry)

        metadata = {
            "provider": provider_name,
            "orbital_position": orbital_position,
            "delivery_system": delivery_system,
            "entry_count": str(len(entries)),
            "source_url": source_url,
        }
        return AdapterResult(profiles=[], scan_entries=entries, extra_metadata=metadata)


def _load_payloads(source_path: Path) -> Iterable[Any]:
    base = Path(source_path)
    json_files = sorted(base.glob("*.json"))
    if json_files:
        for json_path in json_files:
            try:
                yield json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                log.error("provider_astra: failed to parse %s: %s", json_path, exc)
        return

    # Fallback to parse inline JSON within HTML if the fetch was not configured correctly.
    for html_path in sorted(base.glob("*.html")):
        text = html_path.read_text(encoding="utf-8", errors="replace")
        start = text.find("window.__CHANNEL_FINDER__")
        if start == -1:
            continue
        start = text.find("{", start)
        end = text.find("</script>", start)
        if start == -1 or end == -1:
            continue
        snippet = text[start:end]
        try:
            payload = json.loads(snippet)
        except json.JSONDecodeError:
            continue
        data = payload.get("channels") or payload.get("data")
        if isinstance(data, list):
            yield data


def _coerce_entry(
    row: Dict[str, Any],
    *,
    provider_name: str,
    delivery_system: str,
    orbital_position: str,
    last_seen: str,
    source_url: str,
) -> Optional[TransponderScanEntry]:
    try:
        frequency_raw = row.get("frequency")
        symbol_rate_raw = row.get("symbolRate")
        polarity = (row.get("polarity") or "").strip().upper()
        transponder_number = row.get("transponderNumber")
    except AttributeError:  # pragma: no cover - defensive
        return None

    if not frequency_raw:
        return None
    try:
        frequency_hz = int(float(frequency_raw) * 1_000_000)
    except (TypeError, ValueError):
        log.debug("provider_astra: skipping row with invalid frequency %r", frequency_raw)
        return None

    symbol_rate = None
    if symbol_rate_raw:
        try:
            symbol_rate = int(float(symbol_rate_raw) * 1_000)
        except (TypeError, ValueError):
            log.debug("provider_astra: invalid symbol rate %r", symbol_rate_raw)

    quality = (row.get("qualityName") or "").lower()
    system = "DVB-S2" if quality in {"hd", "uhd"} else delivery_system
    packages = row.get("packages") or []
    encryption = row.get("encryption") or []

    extras: Dict[str, str] = {}
    if transponder_number:
        extras["transponder_number"] = str(transponder_number)
    if packages:
        extras["packages"] = ",".join(sorted(str(pkg) for pkg in packages))
    if encryption:
        extras["encryption"] = ",".join(sorted(str(enc) for enc in encryption))
    encoding = row.get("encoding")
    if encoding:
        extras["encoding"] = str(encoding)
    orbital = row.get("orbitalPosition") or orbital_position
    extras["orbital_position"] = str(orbital)
    service_type = row.get("serviceType")
    if service_type:
        extras["service_type"] = str(service_type)

    countries = row.get("countries") or []
    country_value = "; ".join(sorted({str(country) for country in countries if country})) or None

    return TransponderScanEntry(
        delivery_system=delivery_system,
        system=system,
        frequency_hz=frequency_hz,
        symbol_rate=symbol_rate,
        bandwidth_hz=None,
        modulation=None,
        fec=None,
        polarization=polarity or None,
        plp_id=None,
        country=country_value,
        provider=provider_name,
        region=None,
        last_seen=last_seen,
        source_provenance=source_url,
        extras=extras,
    )


register(ProviderAstraAdapter())
