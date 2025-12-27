"""
Writers for Neutrino-compatible scanfiles.

Deutsch:
    Writer für Neutrino-kompatible Scanfiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List
from xml.etree import ElementTree as ET

from ..models import ConversionOptions, TransponderScanEntry
from .dvb_codes import (
    bandwidth_to_code,
    fec_to_code,
    guard_interval_to_code,
    hierarchy_to_code,
    modulation_to_code,
    polarization_to_code,
    system_to_code,
    transmission_mode_to_code,
)
from .normalizer import ScanfileBundle


class ScanfileError(RuntimeError):
    """Raised when scanfile generation fails."""


@dataclass
class ScanfileWriteReport:
    cable_counts: Dict[str, int] = field(default_factory=dict)
    terrestrial_counts: Dict[str, int] = field(default_factory=dict)
    satellite_counts: Dict[str, int] = field(default_factory=dict)
    output_paths: Dict[str, Path] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def write_scanfiles(
    bundle: ScanfileBundle,
    target_dir: Path,
    options: ConversionOptions,
) -> ScanfileWriteReport:
    """
    Write satellites.xml, cables.xml and terrestrial.xml into the target directory.

    Generates Neutrino-compatible scanfiles with integer codes for all DVB parameters.
    """

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    report = ScanfileWriteReport(
        cable_counts=bundle.counts().get("cable", {}),
        terrestrial_counts=bundle.counts().get("terrestrial", {}),
        satellite_counts=bundle.counts().get("satellite", {}),
    )

    if not options.emit_scanfiles:
        report.warnings.append("scanfile emission disabled by CLI option")
        return report

    # Write satellites.xml
    satellite_path = target_dir / "satellites.xml"
    if bundle.satellite:
        _write_satellites_file(satellite_path, bundle.satellite)
        report.output_paths["satellites"] = satellite_path
    else:
        report.warnings.append("no satellites available for satellites.xml")
        if options.strict_scanfiles:
            raise ScanfileError("strict scanfile mode: satellites.xml would be empty")

    # Write cables.xml
    cable_path = target_dir / "cables.xml"
    if bundle.cable:
        _write_cables_file(cable_path, bundle.cable)
        report.output_paths["cables"] = cable_path
    else:
        report.warnings.append("no cable providers available for cables.xml")
        if options.strict_scanfiles:
            raise ScanfileError("strict scanfile mode: cables.xml would be empty")

    # Write terrestrial.xml
    terrestrial_path = target_dir / "terrestrial.xml"
    if bundle.terrestrial:
        _write_terrestrial_file(terrestrial_path, bundle.terrestrial)
        report.output_paths["terrestrial"] = terrestrial_path
    else:
        report.warnings.append("no terrestrial regions available for terrestrial.xml")
        if options.strict_scanfiles:
            raise ScanfileError("strict scanfile mode: terrestrial.xml would be empty")

    _enforce_thresholds(bundle, options)

    return report


def _write_satellites_file(path: Path, satellites: Dict[str, List[TransponderScanEntry]]) -> None:
    """
    Write satellites.xml in Neutrino format.

    Structure:
        <satellites>
          <sat name="..." flags="0" position="192">
            <transponder frequency="..." symbol_rate="..." polarization="1" fec_inner="2" system="1" modulation="2"/>
          </sat>
        </satellites>
    """
    root = ET.Element("satellites")

    for sat_name in sorted(satellites.keys()):
        entries = satellites[sat_name]
        if not entries:
            continue

        # Extract orbital position from first entry
        # Position should be in extras as "orbital_position" (e.g., "19.2")
        position_decimal = entries[0].extras.get("orbital_position", "0")
        try:
            position_int = int(float(position_decimal) * 10)  # 19.2 -> 192
        except (ValueError, TypeError):
            position_int = 0

        sat_el = ET.SubElement(root, "sat")
        sat_el.set("name", sat_name)
        sat_el.set("flags", "0")  # Default flags
        sat_el.set("position", str(position_int))

        for entry in entries:
            trans_el = ET.SubElement(sat_el, "transponder")
            trans_el.set("frequency", str(entry.frequency_hz))
            trans_el.set("symbol_rate", str(entry.symbol_rate or 0))
            trans_el.set("polarization", str(polarization_to_code(entry.polarization)))
            trans_el.set("fec_inner", str(fec_to_code(entry.fec)))
            trans_el.set("system", str(system_to_code(entry.system)))
            trans_el.set("modulation", str(modulation_to_code(entry.modulation, "sat")))

    _indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="iso-8859-1", xml_declaration=True)


def _write_cables_file(path: Path, providers: Dict[str, List[TransponderScanEntry]]) -> None:
    """
    Write cables.xml in Neutrino format.

    Structure:
        <cables>
          <cable name="..." flags="9">
            <transponder frequency="..." symbol_rate="..." fec_inner="0" modulation="3"/>
          </cable>
        </cables>
    """
    root = ET.Element("cables")

    for provider in sorted(providers.keys()):
        entries = providers[provider]
        if not entries:
            continue

        cable_el = ET.SubElement(root, "cable")
        cable_el.set("name", provider)
        cable_el.set("flags", "9")  # Default flags for cable

        for entry in entries:
            trans_el = ET.SubElement(cable_el, "transponder")
            trans_el.set("frequency", str(entry.frequency_hz // 1000))  # Convert to kHz
            if entry.symbol_rate:
                trans_el.set("symbol_rate", str(entry.symbol_rate))
            trans_el.set("fec_inner", str(fec_to_code(entry.fec)))
            trans_el.set("modulation", str(modulation_to_code(entry.modulation, "cable")))

    _indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="iso-8859-1", xml_declaration=True)


def _write_terrestrial_file(path: Path, regions: Dict[str, List[TransponderScanEntry]]) -> None:
    """
    Write terrestrial.xml in Neutrino format.

    Structure:
        <locations>
          <terrestrial name="..." flags="5">
            <transponder frequency="..." bandwidth="1" constellation="6"
                         transmission_mode="2" code_rate_HP="9" code_rate_LP="9"
                         guard_interval="4" hierarchy="0" />
          </terrestrial>
        </locations>
    """
    root = ET.Element("locations")

    for region in sorted(regions.keys()):
        entries = regions[region]
        if not entries:
            continue

        terrestrial_el = ET.SubElement(root, "terrestrial")
        terrestrial_el.set("name", region)
        terrestrial_el.set("flags", "5")  # Default flags for terrestrial

        for entry in entries:
            trans_el = ET.SubElement(terrestrial_el, "transponder")
            trans_el.set("frequency", str(entry.frequency_hz // 1000))  # Convert to kHz
            trans_el.set("bandwidth", str(bandwidth_to_code(entry.bandwidth_hz)))
            trans_el.set("constellation", str(modulation_to_code(entry.modulation, "terrestrial")))

            # DVB-T specific parameters from extras or defaults
            transmission_mode = entry.extras.get("transmission_mode", "AUTO")
            code_rate_hp = entry.extras.get("code_rate_hp", entry.fec or "AUTO")
            code_rate_lp = entry.extras.get("code_rate_lp", "AUTO")
            guard_interval = entry.extras.get("guard_interval", "AUTO")
            hierarchy = entry.extras.get("hierarchy", "NONE")

            trans_el.set("transmission_mode", str(transmission_mode_to_code(transmission_mode)))
            trans_el.set("code_rate_HP", str(fec_to_code(code_rate_hp)))
            trans_el.set("code_rate_LP", str(fec_to_code(code_rate_lp)))
            trans_el.set("guard_interval", str(guard_interval_to_code(guard_interval)))
            trans_el.set("hierarchy", str(hierarchy_to_code(hierarchy)))

    _indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="iso-8859-1", xml_declaration=True)


def _indent(element: ET.Element, level: int = 0) -> None:
    """Add indentation to XML elements for pretty printing."""
    indent_str = "\t"  # Use tabs like in original Neutrino files
    indent = "\n" + indent_str * level
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + indent_str
        for child in list(element):
            _indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent + indent_str
        if not element[-1].tail or not element[-1].tail.strip():
            element[-1].tail = indent
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = indent


def _enforce_thresholds(bundle: ScanfileBundle, options: ConversionOptions) -> None:
    """Enforce minimum transponder count thresholds if strict mode is enabled."""
    if not options.strict_scanfiles:
        return

    for satellite, entries in bundle.satellite.items():
        if len(entries) < options.min_scanfile_entries_cable:  # Reuse cable threshold
            raise ScanfileError(
                f"satellite {satellite} has {len(entries)} entries, "
                f"below strict minimum {options.min_scanfile_entries_cable}"
            )

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
