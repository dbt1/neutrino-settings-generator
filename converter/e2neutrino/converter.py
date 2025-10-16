"""
High-level conversion orchestration.

Deutsch:
    Orchestrierung der Konvertierung.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Union

import yaml

from . import io_enigma, io_neutrino, validate
from .logging_conf import configure_logging
from .models import ConversionOptions, Profile

log = logging.getLogger(__name__)


class ConversionError(Exception):
    """Raised when conversion fails. / Wird geworfen, wenn die Konvertierung scheitert."""


@dataclass
class ConversionResult:
    profile: Profile
    warnings: list[str]
    output_path: Path


def convert(input_path: Path, output_path: Path, options: ConversionOptions) -> ConversionResult:
    configure_logging()
    input_path = Path(input_path)
    output_path = Path(output_path)

    log.info("loading Enigma2 profile: %s", input_path)
    profile = io_enigma.load_profile(input_path)

    log.info("validating profile")
    warnings = validate.validate_profile(profile)

    if warnings:
        for warning in warnings:
            log.warning("validation: %s", warning)
        if options.fail_on_warn:
            raise ConversionError("validation produced warnings; aborting due to --fail-on-warn")

    name_map = _load_name_map(options.name_map_path) if options.name_map_path else None

    log.info("writing Neutrino settings to %s", output_path)
    io_neutrino.write_outputs(profile, output_path, options, name_map)

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
        fail_on_warn=fail_on_warn,
    )
    return convert(Path(inp), Path(out), options)


def _normalise_iterable(value: Optional[Union[Iterable[str], str]]) -> Optional[Set[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = value
    result = {item.strip() for item in items if item and item.strip()}
    return result or None
