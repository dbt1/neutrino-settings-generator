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
from typing import Dict

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
