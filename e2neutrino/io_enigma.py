"""
Enigma2 input handling (lamedb/lamedb5 + bouquets).

Deutsch:
    Enigma2 Eingabe-Handling (lamedb/lamedb5 + Bouquets).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple, Union, cast

from .models import Bouquet, BouquetEntry, Profile, Service, Transponder

log = logging.getLogger(__name__)

SERVICE_REF_PATTERN = re.compile(r'^[0-9a-fA-F]+(?::[0-9a-fA-F]+)+:?$')


def load_profile(base_path: Path) -> Profile:
    """
    Load an Enigma2 profile (lamedb + bouquets) into our normalised model.

    Deutsch:
        Lädt ein Enigma2-Profil in das normalisierte Modell.
    """

    base_path = Path(base_path)
    if not base_path.exists():
        raise FileNotFoundError(f"input path {base_path} not found")

    lamedb = _pick_lamedb(base_path)
    transponders, services = _parse_lamedb(lamedb)
    bouquets = _parse_bouquets(base_path)

    profile = Profile(services=services, transponders=transponders, bouquets=bouquets)
    _normalise_profile(profile)
    profile.metadata["source"] = str(base_path)
    if lamedb.name == "lamedb5":
        profile.metadata["lamedb_version"] = "5"
    else:
        profile.metadata["lamedb_version"] = "4"
    profile.metadata["service_count"] = str(len(profile.services))
    profile.metadata["transponder_count"] = str(len(profile.transponders))
    profile.metadata["bouquet_count"] = str(len(profile.bouquets))
    log.info(
        "parsed enigma2 profile %s -> %d services, %d transponders, %d bouquets",
        base_path,
        len(profile.services),
        len(profile.transponders),
        len(profile.bouquets),
    )
    return profile


def write_profile(profile: Profile, target_dir: Path) -> Path:
    """
    Serialise a profile back into an Enigma2-compatible folder structure.

    Deutsch:
        Serialisiert ein Profil in eine Enigma2-kompatible Ordnerstruktur.
    """

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    _write_lamedb(profile, target_dir / "lamedb")
    _write_bouquet_files(profile, target_dir)
    return target_dir


def _pick_lamedb(base_path: Path) -> Path:
    lamedb5 = base_path / "lamedb5"
    lamedb = base_path / "lamedb"
    if lamedb5.exists():
        return lamedb5
    if lamedb.exists():
        return lamedb
    raise FileNotFoundError(f"lamedb/lamedb5 missing in {base_path}")


def _parse_lamedb(path: Path) -> Tuple[Dict[str, Transponder], Dict[str, Service]]:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        lines = [line.rstrip("\r\n") for line in fh]

    if not lines or not lines[0].startswith("eDVB services"):
        raise ValueError(f"{path} does not look like a lamedb file")

    state: Optional[str] = None
    index = 1
    transponders: Dict[str, Transponder] = {}
    services: Dict[str, Service] = {}

    while index < len(lines):
        raw = lines[index].strip()
        if raw == "transponders":
            state = "trans"
            index += 1
            continue
        if raw == "services":
            state = "services"
            index += 1
            continue
        if raw == "end":
            state = None
            index += 1
            continue

        if state == "trans":
            key_line = lines[index].strip()
            index += 1
            if index >= len(lines):
                break
            data_line = lines[index].strip()
            index += 1
            transponder = _parse_transponder_entry(key_line, data_line, path)
            transponders[key_line.lower()] = transponder
            # Skip optional separator "/"
            if index < len(lines) and lines[index].strip() == "/":
                index += 1
            continue

        if state == "services":
            svc_id_line = lines[index].strip()
            index += 1
            if index >= len(lines):
                break
            name_line = lines[index].strip()
            index += 1

            extra_lines: List[str] = []
            while index < len(lines):
                nxt = lines[index].strip()
                if not nxt or SERVICE_REF_PATTERN.match(nxt):
                    break
                if nxt in {"/", "end"}:
                    break
                extra_lines.append(_clean_text(nxt))
                index += 1

            service = _parse_service_entry(svc_id_line, name_line, extra_lines, path)
            services[service.key] = service

            # Skip optional "/" separators
            if index < len(lines) and lines[index].strip() == "/":
                index += 1
            continue

        index += 1

    return transponders, services


def _parse_transponder_entry(key_line: str, data_line: str, path: Path) -> Transponder:
    key_line = key_line.strip()
    if key_line.lower() == "end":
        raise ValueError(f"unexpected end marker while parsing transponders in {path}")
    try:
        namespace_hex, tsid_hex, onid_hex = key_line.split(":")
    except ValueError as exc:
        raise ValueError(f"invalid transponder key '{key_line}' in {path}") from exc

    namespace = int(namespace_hex, 16)
    tsid = int(tsid_hex, 16)
    onid = int(onid_hex, 16)

    data_line = data_line.strip()
    if not data_line:
        raise ValueError(f"empty transponder payload for {key_line} in {path}")

    delivery_char = data_line[0]
    delivery_map = {"s": "sat", "c": "cable", "t": "terrestrial"}
    delivery = delivery_map.get(delivery_char.lower(), "sat")
    payload = data_line[1:].lstrip(" :")
    parts = [part for part in payload.replace(" ", ":").split(":") if part]

    freq = _safe_int(parts[0]) if parts else 0
    sym_rate = _safe_int(parts[1]) if len(parts) > 1 else None
    polarization = _decode_polarisation(parts[2]) if len(parts) > 2 else None
    fec = parts[3] if len(parts) > 3 else None
    orbital = None
    if delivery == "sat" and len(parts) > 4:
        orbital = _decode_orbital(parts[4])

    modulation = parts[7] if len(parts) > 7 else None
    system = parts[6] if len(parts) > 6 else None

    extra = {}
    if len(parts) > 4:
        extra["raw_fields"] = ",".join(parts)

    return Transponder(
        key=f"{namespace_hex.lower()}:{tsid_hex.lower()}:{onid_hex.lower()}",
        delivery=delivery,
        frequency=freq,
        symbol_rate=sym_rate,
        polarization=polarization,
        fec=fec,
        system=system,
        modulation=modulation,
        orbital_position=orbital,
        network_id=onid,
        transport_stream_id=tsid,
        namespace=namespace,
        extra=extra,
    )


def _parse_service_entry(svc_id_line: str, name_line: str, extra_lines: Iterable[str], path: Path) -> Service:
    parts = svc_id_line.split(":")
    if len(parts) < 6:
        raise ValueError(f"invalid service descriptor '{svc_id_line}' in {path}")

    sid = _safe_int(parts[0])
    namespace_hex = parts[1]
    tsid_hex = parts[2]
    onid_hex = parts[3]
    service_type = _safe_int(parts[4])
    trans_key = f"{namespace_hex.lower()}:{tsid_hex.lower()}:{onid_hex.lower()}"
    namespace = int(namespace_hex, 16)
    tsid = int(tsid_hex, 16)
    onid = int(onid_hex, 16)

    provider = None
    caids: List[int] = []
    extra: Dict[str, Union[str, List[str]]] = {}
    name_line = _clean_text(name_line)
    for line in extra_lines:
        if line.startswith("p:"):
            provider = _clean_text(line[2:].split(",", 1)[0])
        elif line.startswith("c:"):
            ca_val = line[2:]
            cas_list = cast(List[str], extra.setdefault("cas", []))
            cas_list.append(ca_val)
            try:
                caids.append(int(ca_val, 16))
            except ValueError:
                pass
        elif line.startswith("f:"):
            extra["flags"] = _clean_text(line[2:])
        elif ":" in line and line.split(":", 1)[0].isalpha():
            key, value = line.split(":", 1)
            extra[key] = _clean_text(value)

    extra_text = {k: ",".join(v) if isinstance(v, list) else v for k, v in extra.items()}

    service_key = f"{trans_key}:{sid:04x}"
    is_radio = service_type in {2, 10} or extra_text.get("f") == "radio"

    return Service(
        key=service_key,
        name=name_line,
        service_type=service_type,
        service_id=sid,
        transponder_key=trans_key,
        original_network_id=onid,
        transport_stream_id=tsid,
        namespace=namespace,
        provider=_clean_text(provider) if provider else None,
        caids=tuple(caids),
        is_radio=is_radio,
        extra=extra_text,
    )


def _parse_bouquets(base_path: Path) -> List[Bouquet]:
    bouquets: List[Bouquet] = []
    for bouquet_file in base_path.glob("bouquets.*"):
        referenced = _collect_referenced_bouquets(bouquet_file)
        for ref_name in referenced:
            path = base_path / ref_name
            if path.exists():
                bouquets.append(_parse_userbouquet(path))
            else:
                log.warning("referenced userbouquet %s not found in %s", ref_name, base_path)
    # Also include standalone bouquets if not referenced
    for ub_file in base_path.glob("userbouquet.*"):
        if not any(b.source_path == ub_file for b in bouquets):
            bouquets.append(_parse_userbouquet(ub_file))
    return bouquets


def _collect_referenced_bouquets(path: Path) -> List[str]:
    refs: List[str] = []
    seen: Set[str] = set()
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "FROM BOUQUET" in line:
                match = re.search(r'"([^"]+)"', line)
                if match:
                    value = match.group(1)
                    if value not in seen:
                        seen.add(value)
                        refs.append(value)
            elif line.startswith("userbouquet"):
                value = line.strip()
                if value not in seen:
                    seen.add(value)
                    refs.append(value)
    return refs


def _parse_userbouquet(path: Path) -> Bouquet:
    entries: List[BouquetEntry] = []
    name = path.stem
    category = "tv" if path.suffix == ".tv" else "radio"
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("#NAME"):
                name = _clean_text(line.split(" ", 1)[1])
                continue
            if line.startswith("#SERVICE"):
                ref = line.split(" ", 1)[1].strip()
                entries.append(BouquetEntry(service_ref=ref))
            elif line.startswith("#DESCRIPTION") and entries:
                entries[-1].name = _clean_text(line.split(" ", 1)[1])

    return Bouquet(name=name, entries=entries, category=category, source_path=path)


def _normalise_profile(profile: Profile) -> None:
    for bouquet in profile.bouquets:
        cleaned_name = _clean_text(bouquet.name)
        if cleaned_name:
            bouquet.name = cleaned_name
        for entry in bouquet.entries:
            if entry.name is not None:
                cleaned_entry = _clean_text(entry.name)
                entry.name = cleaned_entry or None


def _is_printable(ch: str) -> bool:
    return ord(ch) >= 32 or ch in {"\t"}


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = value.replace("\x00", "")
    text = "".join(ch for ch in text if _is_printable(ch))
    text = unicodedata.normalize("NFC", text)
    return text.strip()


def _write_lamedb(profile: Profile, path: Path) -> None:
    lines: List[str] = ["eDVB services /4/", "transponders"]
    for trans in sorted(profile.transponders.values(), key=lambda t: (t.delivery, t.namespace, t.transport_stream_id)):
        namespace_hex = f"{trans.namespace:08x}"
        tsid_hex = f"{trans.transport_stream_id:04x}"
        onid_hex = f"{trans.network_id:04x}"
        lines.append(f"{namespace_hex}:{tsid_hex}:{onid_hex}")
        payload = _format_transponder_payload(trans)
        lines.append(f"\t{payload}")
        lines.append("/")
    lines.append("services")
    sorted_services = sorted(
        profile.services.values(),
        key=lambda svc: (svc.namespace, svc.transport_stream_id, svc.service_id),
    )
    for service in sorted_services:
        sid_hex = f"{service.service_id:04x}"
        namespace_hex = f"{service.namespace:08x}"
        tsid_hex = f"{service.transport_stream_id:04x}"
        onid_hex = f"{service.original_network_id:04x}"
        lines.append(f"{sid_hex}:{namespace_hex}:{tsid_hex}:{onid_hex}:{service.service_type}:0")
        lines.append(service.name)
        if service.provider:
            lines.append(f"p:{service.provider}")
        for caid in service.caids:
            lines.append(f"c:{caid:06x}")
        lines.append("/")
    lines.append("end")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_transponder_payload(trans: Transponder) -> str:
    delivery_char = {"sat": "s", "cable": "c", "terrestrial": "t"}.get(trans.delivery, "s")
    pol_map = {"H": "0", "V": "1", "L": "2", "R": "3"}
    pol_code = pol_map.get((trans.polarization or "").upper(), "0")
    orbital_code = str(int(round((trans.orbital_position or 0.0) * 10)))
    freq = str(trans.frequency)
    sym = str(trans.symbol_rate or 0)
    fec = trans.fec or "0"
    system = trans.system or "0"
    modulation = trans.modulation or "0"
    return f"{delivery_char} {freq}:{sym}:{pol_code}:{fec}:{orbital_code}:2:0:{system}:{modulation}:0:0"


def _write_bouquet_files(profile: Profile, target_dir: Path) -> None:
    tv_files: List[str] = []
    radio_files: List[str] = []
    used_names: Set[str] = set()

    for bouquet in profile.bouquets:
        suffix = ".tv" if bouquet.category != "radio" else ".radio"
        if bouquet.source_path:
            filename = bouquet.source_path.name
        else:
            slug = _slugify(bouquet.name)
            base = f"userbouquet.{slug}{suffix}"
            filename = base
            idx = 1
            while filename in used_names:
                filename = f"userbouquet.{slug}_{idx}{suffix}"
                idx += 1
        used_names.add(filename)
        path = target_dir / filename
        lines = [f"#NAME {bouquet.name}"]
        for entry in bouquet.entries:
            lines.append(f"#SERVICE {entry.service_ref}")
            if entry.name:
                lines.append(f"#DESCRIPTION {entry.name}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if suffix == ".tv":
            tv_files.append(filename)
        else:
            radio_files.append(filename)

    _write_master_bouquet(target_dir / "bouquets.tv", "User - Bouquets (TV)", sorted(tv_files))
    _write_master_bouquet(target_dir / "bouquets.radio", "User - Bouquets (Radio)", sorted(radio_files))


def _write_master_bouquet(path: Path, title: str, filenames: List[str]) -> None:
    lines = [f"#NAME {title}"]
    for filename in filenames:
        lines.append(f'#SERVICE: 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{filename}" ORDER BY bouquet')
        lines.append(filename)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_") or "bouquet"


def _safe_int(value: str) -> int:
    value = value.strip()
    base = 16 if any(c in value.lower() for c in "abcdef") else 10
    try:
        return int(value, base)
    except ValueError:
        return 0


def _decode_orbital(value: str) -> float:
    try:
        pos_int = int(value, 10)
    except ValueError:
        return 0.0
    return pos_int / 10.0


def _decode_polarisation(value: str) -> str:
    mapping = {
        "0": "H",
        "1": "V",
        "2": "L",
        "3": "R",
    }
    return mapping.get(value, value)
