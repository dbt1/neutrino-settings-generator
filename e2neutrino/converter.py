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
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import yaml

from . import io_enigma, io_neutrino, validate
from .logging_conf import configure_logging
from .models import Bouquet, BouquetEntry, ConversionOptions, Profile, Service, TransponderScanEntry
from .scan import (
    ScanfileError,
    ScanfileNormalizationResult,
    ScanfileWriteReport,
    normalize_scan_entries,
    write_scanfiles,
)

log = logging.getLogger(__name__)

CATEGORY_ORDER_BASE: List[str] = [
    "Movies",
    "Series",
    "News",
    "Sports",
    "Kids",
    "Music",
    "Documentary",
    "Sky",
    "RTL",
    "ProSiebenSat.1",
    "ARD/ZDF",
    "ServusTV",
    "ORF",
    "BBC",
    "RAI",
    "TF1",
    "Nederland",
    "Austria",
    "Switzerland",
    "Spain",
    "Italy",
    "Poland",
    "PyTV",
    "Resolution - UHD",
    "Resolution - HD",
    "Resolution - SD",
    "Shopping",
    "Religion",
    "Adult",
    "International",
    "Regional",
    "UHD/4K",
    "Others",
]

CATEGORY_PATTERNS: Dict[str, List[str]] = {
    "Movies": [r"film", r"cine", r"movie", r"cinema"],
    "Series": [r"serie", r"series", r"drama"],
    "News": [r"news", r"nachrichten", r"journal", r"tagesschau"],
    "Sports": [r"sport", r"bundesliga", r"uefa", r"espn", r"sky sport"],
    "Kids": [r"kinder", r"kids", r"cartoon", r"disney", r"junior"],
    "Music": [r"music", r"musik", r"mtv", r"viva"],
    "Documentary": [r"doku", r"documentary", r"history", r"geo", r"planet", r"nat.?geo"],
    "Sky": [r"sky", r"sky sport", r"sky cinema", r"sky one", r"sky showcase"],
    "RTL": [r"rtl", r"nitro", r"vox", r"ntv", r"rtlup"],
    "ProSiebenSat.1": [r"prosieben", r"sat\\.1", r"kabel ?1", r"sixx", r"maxx", r"puls ?4"],
    "ARD/ZDF": [r"ard", r"zdf", r"wdr", r"ndr", r"mdr", r"hr", r"swr", r"br", r"phoenix", r"tagesschau"],
    "ServusTV": [r"servustv", r"servus tv"],
    "ORF": [r"orf", r"oe24", r"oe1", r"oe2", r"oe3"],
    "BBC": [r"bbc", r"cbbc", r"cbeebies", r"bbc world"],
    "RAI": [r"rai", r"italia", r"rai sport", r"rai movie"],
    "TF1": [r"tf1", r"france", r"canal+", r"m6"],
    "Nederland": [r"npo", r"rtl ?[45]", r"sbs ?6", r"veronica", r"net ?5", r"ziggo"],
    "Austria": [r"servus", r"orf", r"atv", r"oe24", r"krone tv", r"puls ?4"],
    "Switzerland": [r"srf", r"schweiz", r"swiss", r"tele ?z?uri", r"3sat ch"],
    "Spain": [r"espan", r"movistar", r"antena", r"rtve", r"tve", r"vamos"],
    "Italy": [r"italia", r"mediaset", r"tivusat", r"canale", r"la7", r"rai"],
    "Poland": [r"polonia", r"polsat", r"tvp", r"onet", r"canal\+ pol"],
    "PyTV": [r"pytv", r"py-tv"],
    "Shopping": [r"shop", r"shopping", r"kauf", r"qvc", r"teleshop", r"hse"],
    "Religion": [r"kirche", r"church", r"gottes", r"hope", r"bibel", r"faith", r"islam", r"evangel"],
    "Adult": [r"xxl", r"erotik", r"adult", r"playboy", r"hustler", r"dorcel", r"redlight"],
    "International": [r"france", r"turk", r"arab", r"ital", r"espan", r"globe", r"world", r"bbc", r"rai", r"bein"],
    "Regional": [r"regional", r"bayern", r"berlin", r"hamburg", r"ndr", r"mdr", r"rbb", r"swr", r"hr", r"wdr"],
    "UHD/4K": [r"uhd", r"4k", r"ultra"],
    "Resolution - UHD": [],
    "Resolution - HD": [],
    "Resolution - SD": [],
    "Others": [],
}

PAYTV_LOOKUP: List[Dict[str, Any]] = []
PROVIDER_CATEGORY_LOOKUP: List[Dict[str, str]] = []
RADIO_CATEGORY_PATTERNS: Dict[str, List[re.Pattern[str]]] = {}

RESOLUTION_REGEX: List[Tuple[str, List[re.Pattern[str]]]] = [
    (
        "Resolution - UHD",
        [
            re.compile(r"\buhd\b", re.IGNORECASE),
            re.compile(r"\b4k\b", re.IGNORECASE),
            re.compile(r"ultra\s*hd", re.IGNORECASE),
            re.compile(r"hdr\b", re.IGNORECASE),
        ],
    ),
    (
        "Resolution - HD",
        [
            re.compile(r"(?<!u)hd\+?\b", re.IGNORECASE),
            re.compile(r"full\s*hd", re.IGNORECASE),
            re.compile(r"high\s*definition", re.IGNORECASE),
        ],
    ),
    (
        "Resolution - SD",
        [
            re.compile(r"\bsd\b", re.IGNORECASE),
            re.compile(r"standard\s*definition", re.IGNORECASE),
        ],
    ),
]


def _apply_category_overrides() -> None:
    try:
        with resources.as_file(
            resources.files("e2neutrino.data").joinpath("bouquet_category_patterns.json")
        ) as path:
            if not path.exists():
                return
            overrides = json.loads(path.read_text("utf-8"))
    except (ImportError, FileNotFoundError, json.JSONDecodeError):
        return

    order_mutable = list(CATEGORY_ORDER_BASE)
    for category, keywords in overrides.items():
        normalized = category.strip()
        if not normalized:
            continue
        if normalized not in CATEGORY_PATTERNS:
            CATEGORY_PATTERNS[normalized] = []
            order_mutable.append(normalized)
        existing = CATEGORY_PATTERNS[normalized]
        existing.extend(keyword for keyword in keywords if keyword)
        CATEGORY_PATTERNS[normalized] = existing
    CATEGORY_ORDER_BASE[:] = order_mutable


_apply_category_overrides()


def _load_paytv_catalog() -> None:
    try:
        with resources.as_file(
            resources.files("e2neutrino.data").joinpath("paytv_networks.json")
        ) as path:
            if not path.exists():
                return
            catalog = json.loads(path.read_text("utf-8"))
    except (ImportError, FileNotFoundError, json.JSONDecodeError):
        return

    order_mutable = list(CATEGORY_ORDER_BASE)
    for entry in catalog:
        brand = str(entry.get("brand", "")).strip()
        if not brand:
            continue
        country = str(entry.get("country", "")).strip()
        resolution = str(entry.get("resolution", "")).strip()
        keywords_raw = entry.get("keywords", [])
        keywords = [str(item).lower() for item in keywords_raw if str(item).strip()]
        if not keywords:
            continue
        parts = ["PayTV", brand]
        if country:
            parts.append(country)
        if resolution:
            parts.append(resolution)
        category_name = " - ".join(parts)
        if category_name not in CATEGORY_PATTERNS:
            CATEGORY_PATTERNS[category_name] = []
            order_mutable.append(category_name)
        PAYTV_LOOKUP.append({"category": category_name, "keywords": keywords})
    CATEGORY_ORDER_BASE[:] = order_mutable


_load_paytv_catalog()


def _load_provider_categories() -> None:
    try:
        with resources.as_file(
            resources.files("e2neutrino.data").joinpath("provider_categories.json")
        ) as path:
            if not path.exists():
                return
            catalog = json.loads(path.read_text("utf-8"))
    except (ImportError, FileNotFoundError, json.JSONDecodeError):
        return

    order_mutable = list(CATEGORY_ORDER_BASE)
    for entry in catalog:
        provider_name = str(entry.get("provider", "")).strip()
        target_category = str(entry.get("category", "")).strip()
        if not provider_name or not target_category:
            continue
        if target_category not in CATEGORY_PATTERNS:
            CATEGORY_PATTERNS[target_category] = []
            order_mutable.append(target_category)
        PROVIDER_CATEGORY_LOOKUP.append(
            {
                "provider": provider_name.lower(),
                "category": target_category,
            }
        )
    CATEGORY_ORDER_BASE[:] = order_mutable


_load_provider_categories()


def _load_radio_category_patterns() -> None:
    try:
        with resources.as_file(
            resources.files("e2neutrino.data").joinpath("radio_category_patterns.json")
        ) as path:
            if not path.exists():
                return
            raw = json.loads(path.read_text("utf-8"))
    except (ImportError, FileNotFoundError, json.JSONDecodeError):
        return

    for category, keywords in raw.items():
        patterns = [re.compile(keyword, re.IGNORECASE) for keyword in keywords]
        RADIO_CATEGORY_PATTERNS[category] = patterns


_load_radio_category_patterns()

CATEGORY_ORDER: Sequence[str] = tuple(CATEGORY_ORDER_BASE)

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

    scan_report = None
    if options.emit_scanfiles:
        scan_entries = _load_scan_entries(input_path)
        scan_result = normalize_scan_entries(
            scan_entries,
            providers=options.scanfile_providers,
            regions=options.scanfile_regions,
        )
        if scan_result.warnings:
            warnings.extend(f"scanfiles: {message}" for message in scan_result.warnings)
            for message in scan_result.warnings:
                log.warning("scanfiles: %s", message)
        try:
            scan_report = write_scanfiles(scan_result.bundle, output_path, options)
        except ScanfileError as exc:
            log.error("failed to generate scanfiles: %s", exc)
            if options.strict_scanfiles:
                raise ConversionError(str(exc)) from exc
            warnings.append(f"scanfiles: {exc}")
            scan_report = None
        else:
            log.info(
                "wrote scanfiles -> satellite:%d / cable:%d / terrestrial:%d",
                sum(scan_result.bundle.counts().get("satellite", {}).values()),
                sum(scan_result.bundle.counts().get("cable", {}).values()),
                sum(scan_result.bundle.counts().get("terrestrial", {}).values()),
            )
        _record_scan_metadata(profile, scan_result, scan_report)
    else:
        profile.metadata["scanfiles"] = json.dumps({"enabled": False})

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


def _load_scan_entries(input_path: Path) -> List[TransponderScanEntry]:
    base_path = Path(input_path)
    candidates: set[Path] = set()
    for ancestor in (base_path,) + tuple(base_path.parents):
        candidates.add(Path(ancestor) / "scan")
        candidates.add(Path(ancestor) / "scanfiles")
    entries: List[TransponderScanEntry] = []
    seen_paths: Set[Path] = set()
    for directory in candidates:
        if not directory.exists() or not directory.is_dir():
            continue
        for json_path in sorted(directory.glob("*.json")):
            if json_path in seen_paths:
                continue
            seen_paths.add(json_path)
            entries.extend(_parse_scan_json(json_path))
    return entries


def _parse_scan_json(path: Path) -> List[TransponderScanEntry]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        log.error("failed to parse scan JSON %s: %s", path, exc)
        return []

    if isinstance(payload, dict):
        entries_raw = payload.get("entries") or payload.get("transponders") or payload.get("data")
        if isinstance(entries_raw, list):
            payload_list = entries_raw
        else:
            payload_list = []
    elif isinstance(payload, list):
        payload_list = payload
    else:
        log.warning("scanfile json %s has unsupported structure", path)
        return []

    entries: List[TransponderScanEntry] = []
    for index, item in enumerate(payload_list):
        entry = _coerce_scan_entry(path, index, item)
        if entry:
            entries.append(entry)
    return entries


def _coerce_scan_entry(path: Path, index: int, item: object) -> Optional[TransponderScanEntry]:
    if not isinstance(item, dict):
        log.warning("scan entry #%d in %s is not a mapping", index, path)
        return None

    frequency_hz = _coerce_frequency(item)
    if frequency_hz is None or frequency_hz <= 0:
        log.warning("scan entry #%d in %s missing frequency", index, path)
        return None

    delivery = str(item.get("delivery_system") or item.get("delivery") or "UNKNOWN")
    system = item.get("system")

    symbol_rate = _coerce_int(item.get("symbol_rate"))
    bandwidth_hz = _coerce_bandwidth(item)
    modulation = _coerce_text(item.get("modulation"))
    fec = _coerce_text(item.get("fec") or item.get("fec_inner"))
    polarization = _coerce_text(item.get("polarization"))
    plp_id = _coerce_int(item.get("plp_id"))
    country = _coerce_text(item.get("country"))
    provider = _coerce_text(item.get("provider"))
    region = _coerce_text(item.get("region"))
    last_seen = _coerce_text(item.get("last_seen"))
    provenance = _coerce_text(item.get("source_provenance") or item.get("provenance"))

    known_keys = {
        "delivery_system",
        "delivery",
        "system",
        "frequency_hz",
        "frequency",
        "frequency_khz",
        "frequency_mhz",
        "symbol_rate",
        "bandwidth",
        "bandwidth_hz",
        "modulation",
        "fec",
        "fec_inner",
        "polarization",
        "plp_id",
        "country",
        "provider",
        "region",
        "last_seen",
        "source_provenance",
        "provenance",
        "extras",
    }

    extras = {}
    raw_extras = item.get("extras")
    if isinstance(raw_extras, dict):
        extras.update({str(k): str(v) for k, v in raw_extras.items() if v is not None})
    for key, value in item.items():
        if key in known_keys:
            continue
        if value is None:
            continue
        extras[str(key)] = str(value)

    return TransponderScanEntry(
        delivery_system=delivery,
        system=_coerce_text(system),
        frequency_hz=frequency_hz,
        symbol_rate=symbol_rate,
        bandwidth_hz=bandwidth_hz,
        modulation=modulation,
        fec=fec,
        polarization=polarization,
        plp_id=plp_id,
        country=country,
        provider=provider,
        region=region,
        last_seen=last_seen,
        source_provenance=provenance,
        extras=extras,
    )


def _coerce_frequency(item: Dict[str, object]) -> Optional[int]:
    for key in ("frequency_hz", "frequencyHz"):
        value = item.get(key)
        if value is not None:
            return _coerce_int(value)
    value = item.get("frequency_khz") or item.get("frequencyKHz")
    if value is not None:
        khz = _coerce_float(value)
        if khz is not None:
            return int(khz * 1_000)
    value = item.get("frequency_mhz") or item.get("frequencyMHz")
    if value is not None:
        mhz = _coerce_float(value)
        if mhz is not None:
            return int(mhz * 1_000_000)
    value = item.get("frequency")
    if value is not None:
        freq = _coerce_float(value)
        if freq is not None:
            if freq >= 1_000_000:
                return int(freq)
            if freq >= 1_000:
                return int(freq * 1_000)
            return int(freq * 1_000_000)
    return None


def _coerce_bandwidth(item: Dict[str, object]) -> Optional[int]:
    value = item.get("bandwidth_hz") or item.get("bandwidthHz")
    if value is not None:
        return _coerce_int(value)
    value = item.get("bandwidth")
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith("MHz"):
        base = _coerce_float(text[:-3])
        if base is not None:
            return int(base * 1_000_000)
    if text.endswith("kHz"):
        base = _coerce_float(text[:-3])
        if base is not None:
            return int(base * 1_000)
    numeric = _coerce_float(text)
    if numeric is None:
        return None
    if numeric > 10_000:
        return int(numeric)
    if numeric > 100:
        return int(numeric * 1_000)
    return int(numeric * 1_000_000)


def _coerce_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _coerce_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _record_scan_metadata(
    profile: Profile,
    normalization: Optional[ScanfileNormalizationResult],
    report: Optional[ScanfileWriteReport],
) -> None:
    metadata: Dict[str, Any] = {}
    if normalization:
        metadata["counts"] = normalization.bundle.counts()
        metadata["warnings"] = normalization.warnings
        metadata["deduplicated"] = [
            {
                "identity": item.identity,
                "reason": item.reason,
            }
            for item in normalization.deduplicated
        ]
    if report:
        metadata["outputs"] = {name: str(path) for name, path in report.output_paths.items()}
        metadata["cable_counts"] = report.cable_counts
        metadata["terrestrial_counts"] = report.terrestrial_counts
        metadata["writer_warnings"] = report.warnings
    profile.metadata["scanfiles"] = json.dumps(metadata, sort_keys=True)


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
    emit_scanfiles: bool = True,
    providers: Optional[Union[Iterable[str], str]] = None,
    regions: Optional[Union[Iterable[str], str]] = None,
    strict_scanfiles: bool = False,
    min_scanfile_entries_cable: int = 10,
    min_scanfile_entries_terrestrial: int = 3,
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
        emit_scanfiles=emit_scanfiles,
        scanfile_providers=_normalise_iterable(providers),
        scanfile_regions=_normalise_iterable(regions),
        strict_scanfiles=strict_scanfiles,
        min_scanfile_entries_cable=min_scanfile_entries_cable,
        min_scanfile_entries_terrestrial=min_scanfile_entries_terrestrial,
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
    radio_category_buckets: Dict[str, List[Service]] = {}
    for service in services_sorted:
        if service.is_radio:
            radio_services.append(service)
            for category in _match_radio_categories(service):
                radio_category_buckets.setdefault(category, []).append(service)
            continue
        category = _infer_category(service)
        category_buckets.setdefault(category, []).append(service)
        for paytv_category in _match_paytv_categories(service):
            category_buckets.setdefault(paytv_category, []).append(service)
        provider_category = _match_provider_category(service)
        if provider_category:
            category_buckets.setdefault(provider_category, []).append(service)
        for resolution_category in _match_resolution_categories(service):
            category_buckets.setdefault(resolution_category, []).append(service)

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
        for category, services_list in sorted(radio_category_buckets.items()):
            entries = [_make_entry(service) for service in services_list]
            if entries:
                new_bouquets.append(Bouquet(name=category, entries=entries, category="radio"))

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


def _match_paytv_categories(service: Service) -> List[str]:
    name = service.name.lower()
    provider = (service.provider or "").lower()
    matches: List[str] = []
    for entry in PAYTV_LOOKUP:
        category = entry["category"]
        for keyword in entry["keywords"]:
            if keyword in name or keyword in provider:
                matches.append(category)
                break
    return matches


def _match_provider_category(service: Service) -> Optional[str]:
    provider = (service.provider or "").lower().strip()
    if not provider:
        return None
    for entry in PROVIDER_CATEGORY_LOOKUP:
        pattern = entry["provider"]
        if pattern and pattern in provider:
            return entry["category"]
    return None


def _match_resolution_categories(service: Service) -> List[str]:
    haystack = f"{service.name} {(service.provider or '')}".lower()
    matches: List[str] = []
    for category, regexes in RESOLUTION_REGEX:
        if any(regex.search(haystack) for regex in regexes):
            if category == "Resolution - SD" and matches:
                continue
            matches.append(category)
            if category != "Resolution - SD":
                break
    if not matches and service.extra.get("resolution"):
        value = service.extra["resolution"].upper()
        if value in {"UHD", "4K"}:
            matches.append("Resolution - UHD")
        elif value in {"HD", "FHD"}:
            matches.append("Resolution - HD")
        elif value in {"SD"}:
            matches.append("Resolution - SD")
    return matches


def _match_radio_categories(service: Service) -> List[str]:
    if not RADIO_CATEGORY_PATTERNS:
        return []
    haystack = f"{service.name} {(service.provider or '')}".lower()
    matches: List[str] = []
    for category, patterns in RADIO_CATEGORY_PATTERNS.items():
        if any(pattern.search(haystack) for pattern in patterns):
            matches.append(category)
    return matches


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
