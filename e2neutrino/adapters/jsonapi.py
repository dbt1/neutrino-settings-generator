"""
Adapter for JSON-based HTTP APIs.

Deutsch:
    Adapter für JSON-basierte HTTP-APIs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, cast

from ..models import Bouquet, BouquetEntry, Profile, Service, Transponder
from . import BaseAdapter, register

log = logging.getLogger(__name__)


class JSONAPIAdapter(BaseAdapter):
    name = "jsonapi"

    def ingest(self, source_path: Path, config: Dict[str, Any]) -> List[Profile]:
        payload = _load_payload(source_path)
        pointer = cast(Optional[str], config.get("json_pointer"))
        items = _apply_pointer(payload, pointer)
        if not isinstance(items, list):
            raise ValueError("jsonapi adapter expects list after pointer resolution")
        raw_mapping = config.get("mapping") or {}
        mapping: Dict[str, str]
        if isinstance(raw_mapping, Mapping):
            mapping = {str(k): str(v) for k, v in raw_mapping.items()}
        else:
            mapping = {}
        delivery = str(config.get("delivery") or "cable")
        name_field = str(mapping.get("name", "name"))
        sid_field = str(mapping.get("sid", "sid"))
        onid_field = str(mapping.get("onid", "onid"))
        tsid_field = str(mapping.get("tsid", "tsid"))
        namespace_field = str(mapping.get("namespace", "namespace"))
        service_type_field = str(mapping.get("service_type", "service_type"))

        services: Dict[str, Service] = {}
        transponders: Dict[str, Transponder] = {}
        bouquets = Bouquet(name="All Channels", entries=[], category="tv")

        typed_items = cast(List[Mapping[str, Any]], items)
        for idx, item in enumerate(typed_items, start=1):
            if not isinstance(item, Mapping):
                continue
            sid = _safe_int(item.get(sid_field, idx))
            onid = _safe_int(item.get(onid_field, 0))
            tsid = _safe_int(item.get(tsid_field, idx))
            namespace = _safe_int(item.get(namespace_field, idx))
            name = str(item.get(name_field, f"Channel {idx}"))
            service_type = _safe_int(item.get(service_type_field, 1))
            trans_key = f"{namespace:08x}:{tsid:04x}:{onid:04x}"
            if trans_key not in transponders:
                transponders[trans_key] = Transponder(
                    key=trans_key,
                    delivery=delivery,
                    frequency=idx,
                    symbol_rate=None,
                    polarization=None,
                    fec=None,
                    system=None,
                    modulation=None,
                    orbital_position=None,
                    network_id=onid,
                    transport_stream_id=tsid,
                    namespace=namespace,
                    extra={"source": "jsonapi"},
                )
            service_key = f"{trans_key}:{sid:04x}"
            services[service_key] = Service(
                key=service_key,
                name=name,
                service_type=service_type,
                service_id=sid,
                transponder_key=trans_key,
                original_network_id=onid,
                transport_stream_id=tsid,
                namespace=namespace,
                provider=str(item.get("provider") or config.get("provider") or "JSON API"),
                caids=tuple(),
                is_radio=service_type == 2,
            )
            bouquets.entries.append(BouquetEntry(service_ref=_build_service_ref(services[service_key]), name=name))

        profile = Profile(services=services, transponders=transponders, bouquets=[bouquets])
        profile.metadata["format"] = "jsonapi"
        profile.metadata["profile_id"] = str(config.get("id", "jsonapi"))
        return [profile]


def _load_payload(source_path: Path) -> Any:
    for candidate in Path(source_path).glob("*.json"):
        return json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"no JSON payload found in {source_path}")


def _apply_pointer(data: Any, pointer: Optional[str]) -> Any:
    if not pointer:
        return data
    if not pointer.startswith("/"):
        raise ValueError("json_pointer must start with '/'")
    parts = [part for part in pointer.split("/") if part]
    current = data
    for part in parts:
        if isinstance(current, Mapping):
            current = current.get(part)
        elif isinstance(current, list):
            index = int(part)
            current = current[index]
        else:
            raise ValueError(f"json pointer segment {part} not resolvable")
    return current


def _safe_int(value, default: int = 0) -> int:
    if value is None:
        return default
    try:
        if isinstance(value, str) and value.startswith("0x"):
            return int(value, 16)
        return int(value)
    except (ValueError, TypeError):
        return default


def _build_service_ref(service: Service) -> str:
    parts = [
        "1",
        "0",
        str(service.service_type),
        f"{service.service_id:04x}",
        f"{service.transport_stream_id:04x}",
        f"{service.original_network_id:04x}",
        f"{service.namespace:08x}",
        "0",
        "0",
        "0",
        "",
    ]
    return ":".join(parts)


register(JSONAPIAdapter())
