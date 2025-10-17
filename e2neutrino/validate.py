"""
Validation helpers for profiles and generated Neutrino outputs.

Deutsch:
    Validierungshilfen für Profile und generierte Dateien.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List
from xml.etree import ElementTree as ET

from .models import Profile, Service

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
