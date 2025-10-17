"""
High-level conversion orchestration.

Deutsch:
    Orchestrierung der Konvertierung.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import yaml

from . import io_enigma, io_neutrino, validate
from .logging_conf import configure_logging
from .models import Bouquet, BouquetEntry, ConversionOptions, Profile, Service

log = logging.getLogger(__name__)

CATEGORY_ORDER: Sequence[str] = (
    "Movies",
    "Series",
    "News",
    "Sports",
    "Kids",
    "Music",
    "Documentary",
    "Regional",
    "UHD/4K",
    "Others",
)

CATEGORY_PATTERNS: Dict[str, Sequence[str]] = {
    "Movies": (r"film", r"cine", r"movie", r"cinema"),
    "Series": (r"serie", r"series", r"drama"),
    "News": (r"news", r"nachrichten", r"journal", r"tagesschau"),
    "Sports": (r"sport", r"bundesliga", r"uefa", r"espn", r"sky sport"),
    "Kids": (r"kinder", r"kids", r"cartoon", r"disney", r"junior"),
    "Music": (r"music", r"musik", r"mtv", r"viva"),
    "Documentary": (r"doku", r"documentary", r"history", r"geo", r"planet", r"nat.?geo"),
    "Regional": (r"regional", r"bayern", r"berlin", r"hamburg", r"ndr", r"mdr", r"rbb", r"swr", r"hr", r"wdr"),
    "UHD/4K": (r"uhd", r"4k", r"ultra"),
    "Others": (),
}

CATEGORY_REGEX: Dict[str, List[re.Pattern[str]]] = {
    category: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for category, patterns in CATEGORY_PATTERNS.items()
}


class ConversionError(Exception):
    """Raised when conversion fails. / Wird geworfen, wenn die Konvertierung scheitert."""


@dataclass
class ConversionResult:
    profile: Profile
    warnings: list[str]
    output_path: Path


@dataclass
class DeduplicationRecord:
    identity: str
    kept: Service
    dropped: Service


def convert(input_path: Path, output_path: Path, options: ConversionOptions) -> ConversionResult:
    configure_logging()
    input_path = Path(input_path)
    output_path = Path(output_path)

    log.info("loading Enigma2 profile: %s", input_path)
    profile = io_enigma.load_profile(input_path)

    provenance = _extract_provenance(profile)
    _ensure_fresh_profile(profile, options, provenance)

    dedup_records = _deduplicate_profile(profile)
    if dedup_records:
        profile.metadata["deduplicated_services"] = str(len(dedup_records))
        dedup_preview = [
            {
                "identity": record.identity,
                "kept": record.kept.name,
                "dropped": record.dropped.name,
            }
            for record in dedup_records[:20]
        ]
        profile.metadata["deduplicated_preview"] = json.dumps(dedup_preview, sort_keys=True)
    else:
        profile.metadata.setdefault("deduplicated_services", "0")

    name_map = _load_name_map(options.name_map_path) if options.name_map_path else None
    _apply_category_bouquets(profile, name_map)

    log.info("validating profile")
    report = validate.validate_profile(profile)
    warnings = list(report.warnings)

    if warnings:
        for warning in warnings:
            log.warning("validation: %s", warning)
        if options.strict or options.fail_on_warn:
            raise ConversionError("validation produced warnings; aborting due to strict mode")

    validate.assert_no_dupes(report.duplicates)

    thresholds = validate.Thresholds(
        sat=options.min_services_sat,
        cable=options.min_services_cable,
        terrestrial=options.min_services_terrestrial,
    )
    if options.abort_on_empty:
        active_deliveries = {trans.delivery for trans in profile.transponders.values()}
        validate.assert_minimums(report.stats, thresholds, active_deliveries)

    profile.metadata["stats"] = json.dumps(report.stats.to_dict(), sort_keys=True)
    profile.metadata["thresholds"] = json.dumps(thresholds.to_dict(), sort_keys=True)

    log.info("writing Neutrino settings to %s", output_path)
    io_neutrino.write_outputs(profile, output_path, options, name_map)

    validate.assert_output_schema(output_path, report.stats)
    _write_qa_report(output_path, profile, report, dedup_records, thresholds)

    return ConversionResult(profile=profile, warnings=warnings, output_path=output_path)


def _load_name_map(path: Path) -> Dict[str, Dict[str, str]]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"name map file {path} not found")
    with path.open("r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        if path.suffix in {".json"}:
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except Exception as exc:  # pragma: no cover - defensive
        raise ConversionError(f"failed to parse name map {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConversionError(f"name map {path} must contain a mapping")

    result: Dict[str, Dict[str, str]] = {}
    for category, mapping in data.items():
        if isinstance(mapping, dict):
            result[category] = {str(k): str(v) for k, v in mapping.items()}
    return result


def run_convert(
    *,
    inp: Union[str, Path],
    out: Union[str, Path],
    api_version: int = 4,
    filter_bouquets: Optional[str] = None,
    include_types: Optional[Union[Iterable[str], str]] = None,
    satellites: Optional[Union[Iterable[str], str]] = None,
    combinations: Optional[Union[Iterable[str], str]] = None,
    name_scheme: str = "human",
    name_map: Optional[Union[str, Path]] = None,
    no_sat: bool = False,
    no_cable: bool = False,
    no_terrestrial: bool = False,
    fail_on_warn: bool = False,
    strict: bool = False,
    abort_on_empty: bool = False,
    min_services_sat: int = 50,
    min_services_cable: int = 20,
    min_services_terrestrial: int = 20,
    include_stale: bool = False,
    stale_after_days: int = 120,
) -> ConversionResult:
    """
    Convenience wrapper used by the CLI to orchestrate conversions.
    """

    options = ConversionOptions(
        api_version=api_version,
        filter_bouquets=filter_bouquets,
        include_types=_normalise_iterable(include_types),
        satellites=_normalise_iterable(satellites),
        combinations=_normalise_iterable(combinations),
        name_scheme=name_scheme,
        name_map_path=Path(name_map) if name_map else None,
        include_sat=not no_sat,
        include_cable=not no_cable,
        include_terrestrial=not no_terrestrial,
        fail_on_warn=fail_on_warn or strict,
        strict=strict,
        abort_on_empty=abort_on_empty,
        min_services_sat=min_services_sat,
        min_services_cable=min_services_cable,
        min_services_terrestrial=min_services_terrestrial,
        include_stale=include_stale,
        stale_after_days=stale_after_days,
    )
    return convert(Path(inp), Path(out), options)


def _normalise_iterable(value: Optional[Union[Iterable[str], str]]) -> Optional[Set[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = list(value)
    result = {item.strip() for item in items if item and item.strip()}
    return result or None


def _extract_provenance(profile: Profile) -> Dict[str, Any]:
    provenance_raw = profile.metadata.get("source_provenance")
    if provenance_raw:
        try:
            return json.loads(provenance_raw)
        except json.JSONDecodeError:
            log.debug("failed to decode source_provenance metadata")
    return {}


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ensure_fresh_profile(profile: Profile, options: ConversionOptions, provenance: Dict[str, Any]) -> None:
    fetched_at = profile.metadata.get("fetched_at") or provenance.get("fetched_at")
    http_date = provenance.get("http_date") or provenance.get("commit_date")
    timestamp = _parse_iso_datetime(fetched_at) or _parse_iso_datetime(http_date)
    if timestamp is None and http_date:
        try:
            # Fallback for HTTP-date string (RFC 2822)
            timestamp = datetime.strptime(str(http_date), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        except ValueError:
            timestamp = None
    if timestamp is None:
        profile.metadata.setdefault("last_seen", fetched_at or "unknown")
        profile.metadata.setdefault("stale", "unknown")
        return

    profile.metadata["last_seen"] = timestamp.isoformat()
    age = datetime.now(timezone.utc) - timestamp
    if age > timedelta(days=options.stale_after_days):
        profile.metadata["stale"] = "true"
        log.warning(
            "profile %s marked stale (%s days old)",
            profile.metadata.get("profile_id", "unknown"),
            age.days,
        )
        if not options.include_stale:
            raise ConversionError(
                "source data is stale; re-run with --include-stale if this is intended"
            )
    else:
        profile.metadata["stale"] = "false"


def _deduplicate_profile(profile: Profile) -> List[DeduplicationRecord]:
    candidates: Dict[str, Tuple[str, Service, Tuple[int, int, int, int, str]]] = {}
    new_services: Dict[str, Service] = {}
    removed: List[DeduplicationRecord] = []
    priority = int(profile.metadata.get("source_priority", "100"))
    fetched = _parse_iso_datetime(profile.metadata.get("last_seen")) or datetime.now(timezone.utc)
    freshness_score = int(fetched.timestamp())

    for key, service in profile.services.items():
        identity = _service_identity(service)
        score = _score_service(service, priority, freshness_score)
        existing = candidates.get(identity)
        if existing is None:
            candidates[identity] = (key, service, score)
            new_services[key] = service
            continue
        kept_key, kept_service, kept_score = existing
        if score < kept_score:
            removed.append(DeduplicationRecord(identity=identity, kept=service, dropped=kept_service))
            candidates[identity] = (key, service, score)
            new_services.pop(kept_key, None)
            new_services[key] = service
        else:
            removed.append(DeduplicationRecord(identity=identity, kept=kept_service, dropped=service))

    profile.services = new_services
    valid_keys = set(new_services.keys())
    for bouquet in profile.bouquets:
        bouquet.entries = [entry for entry in bouquet.entries if _service_ref_to_key(entry.service_ref) in valid_keys]
    profile.bouquets = [bouquet for bouquet in profile.bouquets if bouquet.entries]
    profile.metadata["service_count"] = str(len(profile.services))
    return removed


def _score_service(service: Service, priority: int, freshness_score: int) -> Tuple[int, int, int, int, str]:
    provider_penalty = 0 if service.provider else 1
    name_length = -len(service.name.strip()) if service.name else 0
    return (
        priority,
        -freshness_score,
        provider_penalty,
        name_length,
        service.key,
    )


def _service_identity(service: Service) -> str:
    payload = (
        f"{service.original_network_id}:{service.transport_stream_id}:"
        f"{service.service_id}:{service.namespace}:{service.service_type}"
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _service_to_ref(service: Service) -> str:
    return (
        f"1:0:{service.service_type}:"
        f"{service.service_id:04x}:{service.transport_stream_id:04x}:"
        f"{service.original_network_id:04x}:{service.namespace:08x}:0:0:0:"
    )


def _service_ref_to_key(service_ref: str) -> str:
    parts = service_ref.split(":")
    if len(parts) < 7:
        return service_ref
    try:
        sid = int(parts[3], 16)
    except ValueError:
        sid = 0
    return f"{parts[6].lower()}:{parts[4].lower()}:{parts[5].lower()}:{sid:04x}"


def _apply_category_bouquets(profile: Profile, name_map: Optional[Mapping[str, Mapping[str, str]]]) -> None:
    services_sorted = sorted(
        profile.services.values(),
        key=lambda svc: (svc.is_radio, svc.name.lower(), svc.service_id),
    )
    category_buckets: Dict[str, List[Service]] = {category: [] for category in CATEGORY_ORDER}
    radio_services: List[Service] = []
    for service in services_sorted:
        if service.is_radio:
            radio_services.append(service)
            continue
        category = _infer_category(service)
        category_buckets.setdefault(category, []).append(service)

    new_bouquets: List[Bouquet] = []
    general_entries = [_make_entry(service) for service in services_sorted if not service.is_radio]
    if general_entries:
        new_bouquets.append(Bouquet(name="General", entries=general_entries, category="tv"))

    for category in CATEGORY_ORDER:
        entries = [_make_entry(service) for service in category_buckets.get(category, [])]
        if entries:
            new_bouquets.append(Bouquet(name=category, entries=entries, category="tv"))

    if radio_services:
        radio_entries = [_make_entry(service) for service in radio_services]
        new_bouquets.append(Bouquet(name="Radio", entries=radio_entries, category="radio"))

    # Append legacy bouquets at the end for reference, keeping original order.
    new_bouquets.extend(profile.bouquets)
    profile.bouquets = new_bouquets


def _infer_category(service: Service) -> str:
    haystack = f"{service.name} {service.provider or ''}"
    for category in CATEGORY_ORDER:
        for pattern in CATEGORY_REGEX.get(category, []):
            if pattern.search(haystack):
                return category
    return "Others"


def _make_entry(service: Service) -> BouquetEntry:
    return BouquetEntry(service_ref=_service_to_ref(service), name=service.name)


def _write_qa_report(
    output_path: Path,
    profile: Profile,
    report: validate.ValidationReport,
    dedup_records: List[DeduplicationRecord],
    thresholds: validate.Thresholds,
) -> None:
    lines: List[str] = []
    profile_id = profile.metadata.get("profile_id", "unknown")
    source_id = profile.metadata.get("source_id", "unknown")
    stale_flag = profile.metadata.get("stale", "unknown")
    last_seen = profile.metadata.get("last_seen", "n/a")
    lines.append(f"# QA Report – {profile_id}")
    lines.append("")
    lines.append(f"- Source ID: `{source_id}`")
    lines.append(f"- Services total: {report.stats.total_services}")
    lines.append(
        f"- Distribution: SAT={report.stats.sat_services}, CABLE={report.stats.cable_services}, "
        f"TERRESTRIAL={report.stats.terrestrial_services}, RADIO={report.stats.radio_services}"
    )
    lines.append(f"- Bouquets: {report.stats.bouquet_count}")
    lines.append(f"- Last seen: {last_seen}")
    lines.append(f"- Stale: {stale_flag}")
    lines.append(
        f"- Thresholds: SAT≥{thresholds.sat}, CABLE≥{thresholds.cable}, TERRESTRIAL≥{thresholds.terrestrial}"
    )
    lines.append("")

    if dedup_records:
        lines.append(f"## Duplicates Removed ({len(dedup_records)})")
        for record in dedup_records[:10]:
            lines.append(
                f"- `{record.identity}` → kept `{record.kept.name}`, dropped `{record.dropped.name}`"
            )
        if len(dedup_records) > 10:
            lines.append(f"- … and {len(dedup_records) - 10} more")
        lines.append("")
    else:
        lines.append("## Duplicates Removed")
        lines.append("- None")
        lines.append("")

    if report.warnings:
        lines.append("## Warnings")
        for warning in report.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    else:
        lines.append("## Warnings")
        lines.append("- None")
        lines.append("")

    qa_path = Path(output_path) / "qa_report.md"
    qa_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
