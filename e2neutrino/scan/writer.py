"""
Writers for Neutrino-compatible scanfiles.

Deutsch:
    Writer für Neutrino-kompatible Scanfiles.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple
from pathlib import Path
from xml.etree import ElementTree as ET

from ..models import ConversionOptions, TransponderScanEntry
from .normalizer import ScanfileBundle


class ScanfileError(RuntimeError):
    """Raised when scanfile generation fails."""


@dataclass
class ScanfileWriteReport:
    cable_counts: Dict[str, int] = field(default_factory=dict)
    terrestrial_counts: Dict[str, int] = field(default_factory=dict)
    output_paths: Dict[str, Path] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def write_scanfiles(
    bundle: ScanfileBundle,
    target_dir: Path,
    options: ConversionOptions,
) -> ScanfileWriteReport:
    """
    Write cable.xml and terrestrial.xml into the target directory using the provided bundle.
    """

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    report = ScanfileWriteReport(
        cable_counts=bundle.counts().get("cable", {}),
        terrestrial_counts=bundle.counts().get("terrestrial", {}),
    )

    if not options.emit_scanfiles:
        report.warnings.append("scanfile emission disabled by CLI option")
        return report

    cable_path = target_dir / "cable.xml"
    terrestrial_path = target_dir / "terrestrial.xml"

    if bundle.cable:
        _write_cable_file(cable_path, bundle.cable)
        report.output_paths["cable"] = cable_path
    else:
        report.warnings.append("no cable providers available for cable.xml")
        if options.strict_scanfiles:
            raise ScanfileError("strict scanfile mode: cable.xml would be empty")

    if bundle.terrestrial:
        _write_terrestrial_file(terrestrial_path, bundle.terrestrial)
        report.output_paths["terrestrial"] = terrestrial_path
    else:
        report.warnings.append("no terrestrial regions available for terrestrial.xml")
        if options.strict_scanfiles:
            raise ScanfileError("strict scanfile mode: terrestrial.xml would be empty")

    _enforce_thresholds(bundle, options)

    return report


def _write_cable_file(path: Path, providers: Dict[str, List[TransponderScanEntry]]) -> None:
    root = ET.Element("cable")
    for provider in sorted(providers.keys()):
        entries = providers[provider]
        provider_el = ET.SubElement(root, "provider")
        provider_attrs = OrderedDict()
        provider_attrs["name"] = provider
        if entries and entries[0].country:
            provider_attrs["country"] = entries[0].country or ""
        if entries and entries[0].delivery_system:
            provider_attrs["delivery_system"] = entries[0].delivery_system
        _assign_attrs(provider_el, provider_attrs.items())

        for entry in entries:
            transponder_el = ET.SubElement(provider_el, "transponder")
            attrs = OrderedDict()
            attrs["frequency"] = _format_frequency(entry.frequency_hz)
            if entry.symbol_rate:
                attrs["symbol_rate"] = str(entry.symbol_rate)
            if entry.modulation:
                attrs["modulation"] = entry.modulation
            if entry.fec:
                attrs["fec_inner"] = entry.fec
            if entry.polarization:
                attrs["polarization"] = entry.polarization
            if entry.system:
                attrs["system"] = entry.system
            for key in sorted((entry.extras or {}).keys()):
                value = entry.extras[key]
                if value is None:
                    continue
                attrs[key] = str(value)
            _assign_attrs(transponder_el, attrs.items())

    _indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _write_terrestrial_file(path: Path, regions: Dict[str, List[TransponderScanEntry]]) -> None:
    root = ET.Element("terrestrial")
    for region in sorted(regions.keys()):
        entries = regions[region]
        region_el = ET.SubElement(root, "region")
        region_attrs = OrderedDict()
        region_attrs["name"] = region
        if entries and entries[0].country:
            region_attrs["country"] = entries[0].country or ""
        if entries and entries[0].delivery_system:
            region_attrs["delivery_system"] = entries[0].delivery_system
        _assign_attrs(region_el, region_attrs.items())

        for entry in entries:
            transponder_el = ET.SubElement(region_el, "transponder")
            attrs = OrderedDict()
            attrs["frequency"] = _format_frequency(entry.frequency_hz)
            if entry.bandwidth_hz:
                attrs["bandwidth"] = _format_bandwidth(entry.bandwidth_hz)
            if entry.modulation:
                attrs["modulation"] = entry.modulation
            if entry.fec:
                attrs["fec"] = entry.fec
            if entry.plp_id is not None:
                attrs["plp_id"] = str(entry.plp_id)
            if entry.system:
                attrs["system"] = entry.system
            for key in sorted((entry.extras or {}).keys()):
                value = entry.extras[key]
                if value is None:
                    continue
                attrs[key] = str(value)
            _assign_attrs(transponder_el, attrs.items())

    _indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _format_frequency(value_hz: int) -> str:
    if value_hz <= 0:
        return "0"
    if value_hz % 1_000 == 0:
        return str(value_hz // 1_000)
    return f"{value_hz / 1_000:.3f}".rstrip("0").rstrip(".")


def _format_bandwidth(value_hz: int) -> str:
    if value_hz >= 1_000_000:
        return f"{value_hz // 1_000_000}MHz"
    if value_hz >= 1_000:
        return f"{value_hz // 1_000}kHz"
    return f"{value_hz}Hz"


def _assign_attrs(element: ET.Element, items: Iterable[Tuple[str, Optional[str]]]) -> None:
    element.attrib.clear()
    for key, value in items:
        if value is None:
            continue
        element.attrib[key] = str(value)


def _indent(element: ET.Element, level: int = 0) -> None:
    indent = "\n" + "  " * level
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + "  "
        for child in list(element):
            _indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent + "  "
        if not element[-1].tail or not element[-1].tail.strip():
            element[-1].tail = indent
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = indent


def _enforce_thresholds(bundle: ScanfileBundle, options: ConversionOptions) -> None:
    if not options.strict_scanfiles:
        return
    for provider, entries in bundle.cable.items():
        if len(entries) < options.min_scanfile_entries_cable:
            raise ScanfileError(
                f"provider {provider} has {len(entries)} cable entries, "
                f"below strict minimum {options.min_scanfile_entries_cable}"
            )
    for region, entries in bundle.terrestrial.items():
        if len(entries) < options.min_scanfile_entries_terrestrial:
            raise ScanfileError(
                f"region {region} has {len(entries)} terrestrial entries, "
                f"below strict minimum {options.min_scanfile_entries_terrestrial}"
            )
