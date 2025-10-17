"""
Normalisation helpers for scanfile data.

Deutsch:
    Normalisierung von Scanfile-Daten (Kabel, Terrestrik).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ..models import TransponderScanEntry


@dataclass
class ScanfileDedupDecision:
    """
    Records a duplicate resolution for QA reporting.

    Deutsch:
        Dokumentiert eine Duplikat-Auflösung für QA Reports.
    """

    identity: str
    kept: TransponderScanEntry
    dropped: TransponderScanEntry
    reason: str


@dataclass
class ScanfileBundle:
    """
    Grouped scanfile entries separated by provider (cable) / region (terrestrial).
    """

    cable: Dict[str, List[TransponderScanEntry]] = field(default_factory=dict)
    terrestrial: Dict[str, List[TransponderScanEntry]] = field(default_factory=dict)
    provenance: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)

    def counts(self) -> Dict[str, Dict[str, int]]:
        return {
            "cable": {provider: len(entries) for provider, entries in self.cable.items()},
            "terrestrial": {region: len(entries) for region, entries in self.terrestrial.items()},
        }

    def total_entries(self) -> Tuple[int, int]:
        return (
            sum(len(entries) for entries in self.cable.values()),
            sum(len(entries) for entries in self.terrestrial.values()),
        )


@dataclass
class ScanfileNormalizationResult:
    bundle: ScanfileBundle
    deduplicated: List[ScanfileDedupDecision]
    warnings: List[str]
    missing_providers: Set[str] = field(default_factory=set)
    missing_regions: Set[str] = field(default_factory=set)


def normalize_scan_entries(
    entries: Iterable[TransponderScanEntry],
    *,
    providers: Optional[Set[str]] = None,
    regions: Optional[Set[str]] = None,
    expected_providers: Optional[Set[str]] = None,
    expected_regions: Optional[Set[str]] = None,
) -> ScanfileNormalizationResult:
    """
    Normalise and group scan entries for cable and terrestrial outputs.

    Deutsch:
        Normalisiert und gruppiert Scan-Einträge für Kabel/Terrestrik.
    """

    filtered = _filter_entries(entries, providers=providers, regions=regions)
    deduped, decisions = deduplicate_scan_entries(filtered)
    bundle = _group_entries(deduped)
    warnings: List[str] = []

    missing_providers = _compute_missing(bundle.cable.keys(), expected_providers)
    missing_regions = _compute_missing(bundle.terrestrial.keys(), expected_regions)

    if missing_providers:
        warnings.append(f"missing cable providers: {', '.join(sorted(missing_providers))}")
    if missing_regions:
        warnings.append(f"missing terrestrial regions: {', '.join(sorted(missing_regions))}")

    return ScanfileNormalizationResult(
        bundle=bundle,
        deduplicated=decisions,
        warnings=warnings,
        missing_providers=missing_providers,
        missing_regions=missing_regions,
    )


def deduplicate_scan_entries(
    entries: Iterable[TransponderScanEntry],
) -> Tuple[List[TransponderScanEntry], List[ScanfileDedupDecision]]:
    """
    Remove duplicates based on delivery + technical parameters while preferring fresher data.
    """

    seen: Dict[str, TransponderScanEntry] = {}
    decisions: List[ScanfileDedupDecision] = []
    for entry in entries:
        identity = _scan_identity(entry)
        existing = seen.get(identity)
        if existing is None:
            seen[identity] = entry
            continue
        keep, drop, reason = _prefer_entry(existing, entry)
        if keep is entry:
            seen[identity] = entry
        decisions.append(
            ScanfileDedupDecision(identity=identity, kept=keep, dropped=drop, reason=reason)
        )
    return list(seen.values()), decisions


def _group_entries(entries: Sequence[TransponderScanEntry]) -> ScanfileBundle:
    cable: Dict[str, List[TransponderScanEntry]] = {}
    terrestrial: Dict[str, List[TransponderScanEntry]] = {}
    provenance: Dict[str, Dict[str, List[str]]] = {}

    for entry in entries:
        delivery = (entry.delivery_system or "").upper()
        if delivery.startswith("DVB-C") or delivery == "CABLE":
            provider = entry.provider or "Unknown"
            bucket = cable.setdefault(provider, [])
            bucket.append(entry)
            provenance.setdefault("cable", {}).setdefault(provider, []).append(entry.source_provenance or "")
        elif delivery.startswith("DVB-T") or delivery == "TERRESTRIAL":
            region = entry.region or "Unknown"
            bucket = terrestrial.setdefault(region, [])
            bucket.append(entry)
            provenance.setdefault("terrestrial", {}).setdefault(region, []).append(entry.source_provenance or "")
        else:
            # Unsupported delivery is ignored but we emit a provenance hint.
            key = entry.provider or entry.region or "unknown"
            provenance.setdefault("ignored", {}).setdefault(key, []).append(entry.source_provenance or "")

    for entries_list in cable.values():
        entries_list.sort(key=_cable_sort_key)
    for entries_list in terrestrial.values():
        entries_list.sort(key=_terrestrial_sort_key)

    return ScanfileBundle(cable=cable, terrestrial=terrestrial, provenance=provenance)


def _filter_entries(
    entries: Iterable[TransponderScanEntry],
    *,
    providers: Optional[Set[str]],
    regions: Optional[Set[str]],
) -> List[TransponderScanEntry]:
    result: List[TransponderScanEntry] = []
    provider_filter = {item.lower() for item in providers} if providers else None
    region_filter = {item.lower() for item in regions} if regions else None
    for entry in entries:
        if provider_filter:
            provider = (entry.provider or "").lower()
            if provider and provider not in provider_filter:
                continue
        if region_filter:
            region = (entry.region or "").lower()
            if region and region not in region_filter:
                continue
        result.append(entry)
    return result


def _scan_identity(entry: TransponderScanEntry) -> str:
    delivery = (entry.delivery_system or "").upper()
    scope = ""
    if delivery.startswith("DVB-C") or delivery == "CABLE":
        scope = (entry.provider or "").lower()
    elif delivery.startswith("DVB-T") or delivery == "TERRESTRIAL":
        scope = (entry.region or "").lower()
    else:
        scope = (entry.provider or entry.region or "").lower()

    symbol_or_bandwidth = entry.symbol_rate or entry.bandwidth_hz or 0
    modulation = (entry.modulation or "").lower()
    fec = (entry.fec or "").lower()
    polarization = (entry.polarization or "").lower()

    return "|".join(
        [
            delivery,
            scope,
            str(entry.frequency_hz),
            str(symbol_or_bandwidth),
            modulation,
            fec,
            polarization,
        ]
    )


def _prefer_entry(
    first: TransponderScanEntry, second: TransponderScanEntry
) -> Tuple[TransponderScanEntry, TransponderScanEntry, str]:
    first_seen = _parse_last_seen(first.last_seen)
    second_seen = _parse_last_seen(second.last_seen)
    if first_seen and second_seen:
        if second_seen > first_seen:
            return second, first, "newer-last-seen"
        if first_seen > second_seen:
            return first, second, "older-last-seen"
    elif second_seen and not first_seen:
        return second, first, "newer-last-seen"
    elif first_seen and not second_seen:
        return first, second, "older-last-seen"

    # Prefer entries with richer metadata (i.e. extras length).
    first_extras = len(first.extras or {})
    second_extras = len(second.extras or {})
    if second_extras > first_extras:
        return second, first, "more-metadata"
    if first_extras > second_extras:
        return first, second, "more-metadata"

    # Stable fallback: keep the first occurrence.
    return first, second, "stable-order"


def _compute_missing(current: Iterable[str], expected: Optional[Set[str]]) -> Set[str]:
    if not expected:
        return set()
    present = {item.lower() for item in current}
    missing = {item for item in expected if item.lower() not in present}
    return missing


def _parse_last_seen(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _cable_sort_key(entry: TransponderScanEntry) -> Tuple[int, int, str]:
    return (entry.frequency_hz or 0, entry.symbol_rate or 0, entry.modulation or "")


def _terrestrial_sort_key(entry: TransponderScanEntry) -> Tuple[int, int, str]:
    return (entry.frequency_hz or 0, entry.bandwidth_hz or 0, entry.modulation or "")
