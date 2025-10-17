"""
Adapter for wilhelm.tel's official DVB-C channel list (pre-parsed JSON dataset).

Deutsch:
    Adapter für die wilhelm.tel-Kanalliste (DVB-C), basierend auf einer
    vorverarbeiteten JSON-Datei.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..models import Profile, TransponderScanEntry
from . import AdapterResult, BaseAdapter, register

log = logging.getLogger(__name__)


class ProviderWilhelmTelDEAdapter(BaseAdapter):
    name = "provider_wilhelm_tel_de"

    def ingest(self, source_path: Path, config: Dict[str, object]) -> List[Profile]:  # pragma: no cover - legacy
        log.info("provider_wilhelm_tel_de emits scan entries only; no Enigma2 profile is produced")
        return []

    def ingest_bundle(self, source_path: Path, config: Dict[str, object]) -> AdapterResult:
        data_dir = Path(source_path)
        if not data_dir.exists():
            raise FileNotFoundError(f"wilhelm.tel payload directory {data_dir} missing")

        json_files = sorted(data_dir.glob("*.json"))
        if not json_files:
            raise FileNotFoundError(f"no JSON datasets found in {data_dir}")

        country = str(config.get("country", "DE"))
        region = str(config.get("region", "de-hamburg"))
        provider_name = str(config.get("provider_name", "wilhelm-tel"))

        entries: List[TransponderScanEntry] = []
        sources: List[str] = []

        for json_path in json_files:
            payload = _load_dataset(json_path)
            transponders = payload.get("transponders") or []
            if not isinstance(transponders, list):
                log.warning("dataset %s has no transponder list", json_path)
                continue
            stand_raw = payload.get("stand")
            stand_value: Optional[str] = str(stand_raw) if isinstance(stand_raw, str) else None
            retrieved_raw = payload.get("retrieved_at")
            retrieved_value: Optional[str] = str(retrieved_raw) if isinstance(retrieved_raw, str) else None
            last_seen = _parse_stand(stand_value) or retrieved_value
            last_seen_iso = _normalise_timestamp(last_seen)
            for transponder in transponders:
                entry = _build_entry(
                    transponder,
                    provider=provider_name,
                    country=country,
                    region=region,
                    provenance=json_path.name,
                    last_seen=last_seen_iso,
                )
                if entry:
                    entries.append(entry)
            sources.append(json_path.name)

        metadata = {
            "entry_count": str(len(entries)),
            "sources": sources,
            "provider": provider_name,
        }
        return AdapterResult(profiles=[], scan_entries=entries, extra_metadata=metadata)


def _load_dataset(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"failed to parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"dataset {path} must contain a JSON object")
    return data


def _build_entry(
    transponder: Dict[str, object],
    *,
    provider: str,
    country: str,
    region: str,
    provenance: str,
    last_seen: Optional[str],
) -> Optional[TransponderScanEntry]:
    frequency_hz = _maybe_int(transponder.get("frequency_hz"))
    if frequency_hz is None:
        log.warning("skipping transponder without valid frequency: %s", transponder)
        return None
    symbol_rate = _maybe_int(transponder.get("symbol_rate"))
    modulation = _maybe_str(transponder.get("modulation"))
    bouquets = _maybe_list_str(transponder.get("bouquets"))
    channels_raw = transponder.get("channels")
    channels: List[Dict[str, object]] = []
    if isinstance(channels_raw, list):
        for candidate in channels_raw:
            if isinstance(candidate, dict):
                normalised = {str(key): value for key, value in candidate.items()}
                channels.append(normalised)
    extras: Dict[str, str] = {
        "channel_count": str(len(channels)),
    }
    if bouquets:
        extras["bouquets"] = ",".join(sorted(set(bouquets)))
    # Preserve a compact channel preview for validation/debugging.
    preview = []
    for item in channels[:10]:
        raw_name = item.get("name")
        name = raw_name if isinstance(raw_name, str) else None
        if not name:
            continue
        lcn_value = item.get("lcn")
        lcn_text = str(lcn_value) if lcn_value is not None else "?"
        preview.append(f"{lcn_text}:{name}")
    if preview:
        extras["channel_preview"] = ";".join(preview)

    return TransponderScanEntry(
        delivery_system="DVB-C",
        system="DVB-C",
        frequency_hz=frequency_hz,
        symbol_rate=symbol_rate,
        bandwidth_hz=None,
        modulation=modulation,
        fec=None,
        polarization=None,
        plp_id=None,
        country=country,
        provider=provider,
        region=region,
        last_seen=last_seen,
        source_provenance=provenance,
        extras=extras,
    )


def _parse_stand(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return None


def _normalise_timestamp(value: Optional[str]) -> Optional[str]:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    value = str(value).strip()
    if value.endswith("Z"):
        value = value[:-1]
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc).isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _maybe_int(value: object) -> Optional[int]:
    if isinstance(value, bool):  # pragma: no cover - defensive
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value:
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _maybe_str(value: object) -> Optional[str]:
    return str(value) if isinstance(value, str) and value else None


def _maybe_list_str(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str) and item]
    return []


register(ProviderWilhelmTelDEAdapter())
