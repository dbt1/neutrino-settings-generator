"""
Adapter for official M3U channel lists.

Deutsch:
    Adapter für offizielle M3U-Kanallisten.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from ..models import Bouquet, BouquetEntry, Profile, Service, Transponder
from . import BaseAdapter, register

log = logging.getLogger(__name__)


class M3UAdapter(BaseAdapter):
    name = "m3u"

    def ingest(self, source_path: Path, config: Dict[str, Any]) -> List[Profile]:
        files = _collect_files(source_path, config)
        profiles: List[Profile] = []
        for file_path in files:
            profile = _parse_m3u(file_path)
            profile.metadata.setdefault("profile_id", file_path.stem)
            profiles.append(profile)
        return profiles


def _collect_files(source_path: Path, config: Dict[str, Any]) -> List[Path]:
    include = config.get("include")
    files: List[Path] = []
    if isinstance(include, list):
        for pattern in include:
            files.extend(Path(source_path).glob(str(pattern)))
    else:
        files.extend(Path(source_path).glob("*.m3u"))
        files.extend(Path(source_path).glob("*.m3u8"))
    return [path for path in files if path.is_file()]


def _parse_m3u(path: Path) -> Profile:
    services: Dict[str, Service] = {}
    transponders: Dict[str, Transponder] = {}
    bouquets: Dict[str, Bouquet] = {}

    if not path.exists():
        raise FileNotFoundError(path)

    current_name = None
    current_meta: Dict[str, str] = {}
    service_counter = 1
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTINF"):
                current_meta = _parse_extinf(line)
                current_name = current_meta.get("tvg-name") or current_meta.get("name")
            elif line.startswith("#"):
                continue
            else:
                if not current_name:
                    current_name = line
                group_title = current_meta.get("group-title") or "M3U"
                trans_key = f"m3u:{_slugify(group_title)}"
                if trans_key not in transponders:
                    transponders[trans_key] = Transponder(
                        key=trans_key,
                        delivery="cable",
                        frequency=service_counter,
                        symbol_rate=None,
                        polarization=None,
                        fec=None,
                        system=None,
                        modulation=None,
                        orbital_position=None,
                        network_id=service_counter,
                        transport_stream_id=service_counter,
                        namespace=service_counter,
                    )
                service_key = f"{trans_key}:{service_counter:04x}"
                services[service_key] = Service(
                    key=service_key,
                    name=current_name,
                    service_type=int(current_meta.get("service-type", "1")),
                    service_id=service_counter,
                    transponder_key=trans_key,
                    original_network_id=service_counter,
                    transport_stream_id=service_counter,
                    namespace=service_counter,
                    provider=current_meta.get("provider") or "M3U",
                    caids=tuple(),
                    is_radio=current_meta.get("radio") == "1",
                )
                bouquet = bouquets.setdefault(
                    group_title,
                    Bouquet(name=group_title, entries=[], category="tv"),
                )
                bouquet.entries.append(
                    BouquetEntry(
                        service_ref=_build_service_ref(services[service_key]),
                        name=current_name,
                    )
                )
                service_counter += 1
                current_name = None
                current_meta = {}

    profile = Profile(services=services, transponders=transponders, bouquets=list(bouquets.values()))
    profile.metadata["source_path"] = str(path)
    profile.metadata["format"] = "m3u"
    return profile


def _parse_extinf(line: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    match = re.match(r"#EXTINF:-?1 ?(.*?),(.*)", line)
    if match:
        attrs = match.group(1)
        name = match.group(2)
        meta["name"] = name.strip()
        for attr_match in re.finditer(r'([a-zA-Z0-9\-]+)="([^"]+)"', attrs):
            meta[attr_match.group(1).lower()] = attr_match.group(2)
    return meta


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


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "group"


register(M3UAdapter())
