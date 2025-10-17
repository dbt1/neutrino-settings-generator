"""
Validation helpers for profiles and generated Neutrino outputs.

Deutsch:
    Validierungshilfen für Profile und generierte Dateien.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List
from xml.etree import ElementTree as ET

from jsonschema import Draft7Validator

from .models import Profile, Service
from .schemas import load_schema

log = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails. / Wird geworfen, wenn die Validierung scheitert."""


@dataclass
class ProfileStats:
    total_services: int
    sat_services: int
    cable_services: int
    terrestrial_services: int
    radio_services: int
    bouquet_count: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_services": self.total_services,
            "sat_services": self.sat_services,
            "cable_services": self.cable_services,
            "terrestrial_services": self.terrestrial_services,
            "radio_services": self.radio_services,
            "bouquet_count": self.bouquet_count,
        }


@dataclass
class DuplicateRecord:
    identity: str
    services: List[Service]

    def summary(self) -> Dict[str, str]:
        first = self.services[0]
        other = self.services[1]
        return {
            "identity": self.identity,
            "first": first.name,
            "second": other.name,
        }


@dataclass
class ValidationReport:
    warnings: List[str]
    stats: ProfileStats
    duplicates: List[DuplicateRecord]


@dataclass
class Thresholds:
    sat: int
    cable: int
    terrestrial: int

    def to_dict(self) -> Dict[str, int]:
        return {"sat": self.sat, "cable": self.cable, "terrestrial": self.terrestrial}


def validate_profile(profile: Profile) -> ValidationReport:
    warnings: List[str] = []
    if not profile.services:
        warnings.append("profile contains no services")
    if not profile.transponders:
        warnings.append("profile contains no transponders")

    unresolved = _find_unresolved_transponders(profile)
    if unresolved:
        warnings.extend(unresolved)

    duplicates = _detect_duplicates(profile.services.values())
    if duplicates:
        warnings.append(f"detected {len(duplicates)} duplicate service identities")

    stats = _build_stats(profile)
    return ValidationReport(warnings=warnings, stats=stats, duplicates=duplicates)


def assert_minimums(stats: ProfileStats, thresholds: Thresholds, active: set[str] | None = None) -> None:
    errors: List[str] = []
    active = active or set()
    if thresholds.sat > 0 and "sat" in active and stats.sat_services < thresholds.sat:
        errors.append(f"sat services {stats.sat_services} below minimum {thresholds.sat}")
    if thresholds.cable > 0 and "cable" in active and stats.cable_services < thresholds.cable:
        errors.append(f"cable services {stats.cable_services} below minimum {thresholds.cable}")
    if thresholds.terrestrial > 0 and "terrestrial" in active and stats.terrestrial_services < thresholds.terrestrial:
        errors.append(
            f"terrestrial services {stats.terrestrial_services} below minimum {thresholds.terrestrial}"
        )
    if errors:
        raise ValidationError("; ".join(errors))


def assert_no_dupes(duplicates: List[DuplicateRecord]) -> None:
    if duplicates:
        details = ", ".join(record.summary()["identity"] for record in duplicates[:5])
        raise ValidationError(f"duplicate service identities remain: {details}")


def assert_output_schema(output_dir: Path, stats: ProfileStats) -> None:
    services_path = Path(output_dir) / "services.xml"
    bouquets_path = Path(output_dir) / "bouquets.xml"
    _validate_services_xml(services_path, stats.total_services)
    _validate_bouquets_xml(bouquets_path)
    _validate_scanfiles(Path(output_dir))


def validate_scanfiles(output_dir: Path) -> None:
    """Validate scanfile outputs (cable/terrestrial) against bundled schemas."""

    _validate_scanfiles(Path(output_dir))


def _build_stats(profile: Profile) -> ProfileStats:
    sat = cable = terrestrial = radio = 0
    for service in profile.services.values():
        trans = profile.transponders.get(service.transponder_key)
        if trans:
            if trans.delivery == "sat":
                sat += 1
            elif trans.delivery == "cable":
                cable += 1
            elif trans.delivery == "terrestrial":
                terrestrial += 1
        if service.is_radio:
            radio += 1
    return ProfileStats(
        total_services=len(profile.services),
        sat_services=sat,
        cable_services=cable,
        terrestrial_services=terrestrial,
        radio_services=radio,
        bouquet_count=len(profile.bouquets),
    )


def _find_unresolved_transponders(profile: Profile) -> List[str]:
    warnings: List[str] = []
    for service in profile.services.values():
        if service.transponder_key not in profile.transponders:
            warnings.append(
                f"service {service.name} references unknown transponder {service.transponder_key}"
            )
    return warnings


def _detect_duplicates(services: Iterable[Service]) -> List[DuplicateRecord]:
    seen: Dict[str, Service] = {}
    duplicates: List[DuplicateRecord] = []
    for service in services:
        identity = _service_identity(service)
        other = seen.get(identity)
        if other is None:
            seen[identity] = service
        else:
            duplicates.append(DuplicateRecord(identity=identity, services=[other, service]))
    return duplicates


def _service_identity(service: Service) -> str:
    payload = (
        f"{service.original_network_id}:{service.transport_stream_id}:"
        f"{service.service_id}:{service.namespace}:{service.service_type}"
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _validate_services_xml(path: Path, expected_services: int) -> None:
    if not path.exists():
        raise ValidationError(f"missing services.xml at {path}")
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "zapit":
        raise ValidationError("services.xml root element must be <zapit>")
    service_nodes = root.findall(".//service")
    if len(service_nodes) != expected_services:
        raise ValidationError(
            f"services.xml contains {len(service_nodes)} services, expected {expected_services}"
        )


def _validate_bouquets_xml(path: Path) -> None:
    if not path.exists():
        raise ValidationError(f"missing bouquets.xml at {path}")
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "zapit":
        raise ValidationError("bouquets.xml root element must be <zapit>")
    bouquets = root.findall("bouquet")
    if not bouquets:
        raise ValidationError("bouquets.xml contains no <bouquet> entries")
    for bouquet in bouquets:
        for channel in bouquet.findall("channel"):
            if not channel.get("service_ref"):
                raise ValidationError("bouquets.xml contains channel without service_ref")


def _validate_scanfiles(output_dir: Path) -> None:
    tasks = [
        (
            "cable",
            output_dir / "cable.xml",
            "scanfile.cable.schema.json",
            _parse_cable_scanfile,
        ),
        (
            "terrestrial",
            output_dir / "terrestrial.xml",
            "scanfile.terrestrial.schema.json",
            _parse_terrestrial_scanfile,
        ),
    ]
    for kind, path, schema_name, parser in tasks:
        if not path.exists():
            continue
        data = parser(path)
        schema = load_schema(schema_name)
        validator = Draft7Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
        if errors:
            messages = "; ".join(
                f"{'.'.join(str(part) for part in error.path)} -> {error.message}" for error in errors
            )
            raise ValidationError(f"{kind}.xml failed schema validation: {messages}")


def _parse_cable_scanfile(path: Path) -> Dict[str, object]:
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "cable":
        raise ValidationError("cable.xml root element must be <cable>")
    providers: List[Dict[str, object]] = []
    for provider_el in root.findall("provider"):
        name = (provider_el.get("name") or "").strip()
        if not name:
            raise ValidationError("cable.xml provider missing name attribute")
        provider: Dict[str, object] = {"name": name}
        country = provider_el.get("country")
        if country:
            provider["country"] = country
        delivery = provider_el.get("delivery_system")
        if delivery:
            provider["delivery_system"] = delivery
        extras = _extract_extras(provider_el, {"name", "country", "delivery_system"})
        if extras:
            provider["extras"] = extras
        transponders = []
        for trans_el in provider_el.findall("transponder"):
            transponders.append(_parse_cable_transponder(trans_el))
        if transponders:
            provider["transponders"] = transponders
            providers.append(provider)
    if not providers:
        raise ValidationError("cable.xml contains no providers with transponders")
    return {"providers": providers}


def _parse_terrestrial_scanfile(path: Path) -> Dict[str, object]:
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "terrestrial":
        raise ValidationError("terrestrial.xml root element must be <terrestrial>")
    regions: List[Dict[str, object]] = []
    for region_el in root.findall("region"):
        name = (region_el.get("name") or "").strip()
        if not name:
            raise ValidationError("terrestrial.xml region missing name attribute")
        region: Dict[str, object] = {"name": name}
        country = region_el.get("country")
        if country:
            region["country"] = country
        delivery = region_el.get("delivery_system")
        if delivery:
            region["delivery_system"] = delivery
        extras = _extract_extras(region_el, {"name", "country", "delivery_system"})
        if extras:
            region["extras"] = extras
        transponders = []
        for trans_el in region_el.findall("transponder"):
            transponders.append(_parse_terrestrial_transponder(trans_el))
        if transponders:
            region["transponders"] = transponders
            regions.append(region)
    if not regions:
        raise ValidationError("terrestrial.xml contains no regions with transponders")
    return {"regions": regions}


def _parse_cable_transponder(element: ET.Element) -> Dict[str, object]:
    known = {
        "frequency",
        "symbol_rate",
        "bandwidth",
        "bandwidth_hz",
        "modulation",
        "fec_inner",
        "polarization",
        "system",
    }
    freq_attr = element.get("frequency")
    if not freq_attr:
        raise ValidationError("cable.xml transponder missing frequency attribute")
    transponder: Dict[str, object] = {"frequency_hz": _frequency_to_hz(freq_attr)}
    symbol_rate = element.get("symbol_rate")
    if symbol_rate:
        transponder["symbol_rate"] = _to_int(symbol_rate)
    bandwidth_hz_attr = element.get("bandwidth_hz")
    bandwidth_attr = element.get("bandwidth")
    bandwidth_hz = None
    if bandwidth_hz_attr:
        bandwidth_hz = _to_int(bandwidth_hz_attr)
    elif bandwidth_attr:
        bandwidth_hz = _parse_bandwidth(bandwidth_attr)
    if bandwidth_hz:
        transponder["bandwidth_hz"] = bandwidth_hz
    modulation = element.get("modulation")
    if modulation:
        transponder["modulation"] = modulation
    fec = element.get("fec_inner") or element.get("fec")
    if fec:
        transponder["fec"] = fec
    polarization = element.get("polarization")
    if polarization:
        transponder["polarization"] = polarization.upper()
    system = element.get("system")
    if system:
        transponder["system"] = system
    extras = _extract_extras(element, known)
    if extras:
        transponder["extras"] = extras
    return transponder


def _parse_terrestrial_transponder(element: ET.Element) -> Dict[str, object]:
    known = {
        "frequency",
        "bandwidth",
        "bandwidth_hz",
        "symbol_rate",
        "modulation",
        "fec",
        "plp_id",
        "system",
    }
    freq_attr = element.get("frequency")
    if not freq_attr:
        raise ValidationError("terrestrial.xml transponder missing frequency attribute")
    transponder: Dict[str, object] = {"frequency_hz": _frequency_to_hz(freq_attr)}
    bandwidth = element.get("bandwidth")
    if bandwidth:
        bandwidth_hz = _parse_bandwidth(bandwidth)
        if bandwidth_hz:
            transponder["bandwidth_hz"] = bandwidth_hz
    symbol_rate = element.get("symbol_rate")
    if symbol_rate:
        transponder["symbol_rate"] = _to_int(symbol_rate)
    modulation = element.get("modulation")
    if modulation:
        transponder["modulation"] = modulation
    fec = element.get("fec")
    if fec:
        transponder["fec"] = fec
    plp = element.get("plp_id")
    if plp:
        transponder["plp_id"] = _to_non_negative_int(plp)
    system = element.get("system")
    if system:
        transponder["system"] = system
    extras = _extract_extras(element, known)
    if extras:
        transponder["extras"] = extras
    return transponder


def _extract_extras(element: ET.Element, known: set[str]) -> Dict[str, str]:
    extras: Dict[str, str] = {}
    for key, value in element.attrib.items():
        if key not in known:
            extras[key] = value
    return extras


def _parse_bandwidth(value: str) -> int | None:
    text = value.strip().lower()
    multiplier = 1
    if text.endswith("mhz"):
        multiplier = 1_000_000
        text = text[:-3]
    elif text.endswith("khz"):
        multiplier = 1_000
        text = text[:-3]
    elif text.endswith("hz"):
        multiplier = 1
        text = text[:-2]
    if not text:
        return None
    try:
        magnitude = Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValidationError(f"invalid bandwidth value {value!r}") from exc
    result = int(magnitude * multiplier)
    return result if result > 0 else None


def _frequency_to_hz(value: str) -> int:
    try:
        magnitude = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValidationError(f"invalid frequency value {value!r}") from exc
    hz = int(magnitude * 1_000)
    if hz <= 0:
        raise ValidationError(f"frequency must be positive, got {value!r}")
    return hz


def _to_int(value: str) -> int:
    try:
        magnitude = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValidationError(f"invalid integer value {value!r}") from exc
    result = int(magnitude)
    if result <= 0:
        raise ValidationError(f"value must be positive integer, got {value!r}")
    return result


def _to_non_negative_int(value: str) -> int:
    try:
        magnitude = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValidationError(f"invalid integer value {value!r}") from exc
    result = int(magnitude)
    if result < 0:
        raise ValidationError(f"value must be non-negative integer, got {value!r}")
    return result
