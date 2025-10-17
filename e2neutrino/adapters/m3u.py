"""
Adapter for official M3U channel lists.

Deutsch:
    Adapter für offizielle M3U-Kanallisten.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..models import Bouquet, BouquetEntry, Profile, Service, Transponder
from . import BaseAdapter, register

log = logging.getLogger(__name__)


class M3UAdapter(BaseAdapter):
    name = "m3u"

    def ingest(self, source_path: Path, config: Dict[str, Any]) -> List[Profile]:
        files = _collect_files(source_path, config)
        allowed_domains = _collect_allowed_domains(config)
        default_provider = str(config.get("provider") or "M3U")
        profiles: List[Profile] = []
        for file_path in files:
            profile = _parse_m3u(file_path, allowed_domains, default_provider)
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


def _parse_m3u(path: Path, allowed_domains: set[str], default_provider: str) -> Profile:
    services: Dict[str, Service] = {}
    transponders: Dict[str, Transponder] = {}
    bouquets: Dict[str, Bouquet] = {}

    if not path.exists():
        raise FileNotFoundError(path)

    current_name = None
    current_meta: Dict[str, str] = {}
    service_counter = 1
    if not allowed_domains:
        raise ValueError("m3u adapter requires 'allowed_domains' list for official validation")
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTINF"):
                current_meta = _parse_extinf(line)
                current_name = _clean_text(current_meta.get("tvg-name") or current_meta.get("name"))
            elif line.startswith("#"):
                continue
            else:
                if not current_name:
                    current_name = _clean_text(line)
                parsed_url = _validate_stream_url(line, allowed_domains)
                group_title = _clean_text(current_meta.get("group-title") or "M3U")
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
                provider_name = _clean_text(current_meta.get("provider")) or default_provider
                service_type = int(current_meta.get("service-type", "1"))
                extra_meta = {
                    key: value
                    for key, value in current_meta.items()
                    if key not in {"name", "tvg-name", "group-title", "provider"}
                }
                extra_meta["stream_host"] = parsed_url.hostname or ""
                extra_meta["stream_scheme"] = parsed_url.scheme
                services[service_key] = Service(
                    key=service_key,
                    name=current_name,
                    service_type=service_type,
                    service_id=service_counter,
                    transponder_key=trans_key,
                    original_network_id=service_counter,
                    transport_stream_id=service_counter,
                    namespace=service_counter,
                    provider=provider_name,
                    caids=tuple(),
                    is_radio=current_meta.get("radio") == "1",
                    extra=extra_meta,
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
        meta["name"] = _clean_text(name)
        for attr_match in re.finditer(r'([a-zA-Z0-9\-]+)="([^"]+)"', attrs):
            meta[attr_match.group(1).lower()] = _clean_text(attr_match.group(2))
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


def _collect_allowed_domains(config: Dict[str, Any]) -> set[str]:
    domains = config.get("allowed_domains") or config.get("official_domains") or []
    result: set[str] = set()
    if isinstance(domains, (list, tuple, set)):
        for domain in domains:
            if isinstance(domain, str) and domain.strip():
                result.add(domain.strip().lower())
    return result


def _validate_stream_url(url: str, allowed_domains: set[str]):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"m3u entry {url!r} uses unsupported scheme {parsed.scheme}")
    host = (parsed.hostname or "").lower()
    if host.startswith("127.") or host.startswith("10.") or host.startswith("192.168.") or host.startswith("172."):
        raise ValueError(f"m3u entry {url!r} points to private or loopback address")
    if allowed_domains and host not in allowed_domains:
        raise ValueError(f"m3u entry host {host} not in allowed_domains {sorted(allowed_domains)}")
    if "get.php" in parsed.path.lower():
        raise ValueError(f"m3u entry {url!r} matches blocked pattern get.php")
    return parsed


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = value.replace("\x00", "").strip()
    text = unicodedata.normalize("NFC", text)
    return text


register(M3UAdapter())
