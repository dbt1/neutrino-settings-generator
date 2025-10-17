"""
Adapter for raw DVB-SI dumps (simplified parsing).

Deutsch:
    Adapter für rohe DVB-SI-Dumps (vereinfachtes Parsen).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List

from ..models import Bouquet, BouquetEntry, Profile, Service, Transponder
from . import BaseAdapter, register

log = logging.getLogger(__name__)


class DvbSiAdapter(BaseAdapter):
    name = "dvbsi"

    def ingest(self, source_path: Path, config: Dict[str, Any]) -> List[Profile]:
        dump_path = _find_dump(source_path, config)
        services, transponders = _parse_dump(dump_path)
        bouquet = Bouquet(name="DVB Scan", entries=[], category="tv")
        for service in services.values():
            bouquet.entries.append(BouquetEntry(service_ref=_build_service_ref(service), name=service.name))
        profile = Profile(services=services, transponders=transponders, bouquets=[bouquet])
        profile.metadata["format"] = "dvbsi"
        profile.metadata["profile_id"] = Path(dump_path).stem
        profile.metadata["source_path"] = str(dump_path)
        return [profile]


def _find_dump(source_path: Path, config: Dict[str, Any]) -> Path:
    explicit = config.get("path")
    if isinstance(explicit, str):
        candidate = Path(explicit)
        if not candidate.is_absolute():
            candidate = Path(source_path) / candidate
        if candidate.exists():
            return candidate
    for candidate in Path(source_path).glob("*.dump"):
        return candidate
    raise FileNotFoundError(f"no DVB dump found in {source_path}")


def _parse_dump(path: Path) -> tuple[Dict[str, Service], Dict[str, Transponder]]:
    services: Dict[str, Service] = {}
    transponders: Dict[str, Transponder] = {}
    pattern = re.compile(
        r"#SERVICE\s+sid=(?P<sid>[0-9a-fA-Fx]+)\s+onid=(?P<onid>[0-9a-fA-Fx]+)\s+tsid=(?P<tsid>[0-9a-fA-Fx]+)"
        r"\s+namespace=(?P<namespace>[0-9a-fA-Fx]+)\s+name=\"(?P<name>[^\"]+)\"\s+type=(?P<type>\d+)"
        r"(?:\s+delivery=(?P<delivery>\w+))?"
        r"(?:\s+frequency=(?P<frequency>\d+))?"
        r"(?:\s+symbol_rate=(?P<symbol_rate>\d+))?"
        r"(?:\s+orbital=(?P<orbital>[0-9.\-]+))?"
        r"(?:\s+provider=\"(?P<provider>[^\"]+)\")?"
    )
    with Path(path).open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            match = pattern.match(line)
            if not match:
                continue
            data = match.groupdict()
            delivery = (data.get("delivery") or "sat").lower()
            namespace = int(data["namespace"], 16 if "x" in data["namespace"] else 10)
            tsid = int(data["tsid"], 16 if "x" in data["tsid"] else 10)
            onid = int(data["onid"], 16 if "x" in data["onid"] else 10)
            sid = int(data["sid"], 16 if "x" in data["sid"] else 10)
            if onid == 0 or tsid == 0:
                raise ValueError(f"service {data['name']} missing network or transport id in {path}")
            trans_key = f"{namespace:08x}:{tsid:04x}:{onid:04x}"
            if trans_key not in transponders:
                transponders[trans_key] = Transponder(
                    key=trans_key,
                    delivery=delivery,
                    frequency=int(data.get("frequency") or 0),
                    symbol_rate=int(data.get("symbol_rate") or 0) or None,
                    polarization=None,
                    fec=None,
                    system=None,
                    modulation=None,
                    orbital_position=float(data.get("orbital") or 0.0) or None,
                    network_id=onid,
                    transport_stream_id=tsid,
                    namespace=namespace,
                    extra={"source": "dvbsi"},
                )
            service_key = f"{trans_key}:{sid:04x}"
            services[service_key] = Service(
                key=service_key,
                name=unicodedata.normalize("NFC", data["name"]),
                service_type=int(data["type"]),
                service_id=sid,
                transponder_key=trans_key,
                original_network_id=onid,
                transport_stream_id=tsid,
                namespace=namespace,
                provider=data.get("provider") or "DVB",
                caids=tuple(),
                is_radio=False,
            )
    return services, transponders


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


register(DvbSiAdapter())
