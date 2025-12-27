from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from e2neutrino import validate
from e2neutrino.models import ConversionOptions, TransponderScanEntry
from e2neutrino.scan import normalize_scan_entries, write_scanfiles
from e2neutrino.scan.writer import ScanfileError


def _entry(
    *,
    provider: str | None = None,
    region: str | None = None,
    frequency: int,
    symbol_rate: int | None = None,
    bandwidth: int | None = None,
    last_seen: str = "2025-01-01T00:00:00+00:00",
) -> TransponderScanEntry:
    return TransponderScanEntry(
        delivery_system="DVB-C" if provider else "DVB-T2",
        system="DVB-C" if provider else "DVB-T2",
        frequency_hz=frequency,
        symbol_rate=symbol_rate,
        bandwidth_hz=bandwidth,
        modulation="QAM256" if provider else "QAM256",
        fec="3/4",
        polarization=None,
        plp_id=None,
        country="DE",
        provider=provider,
        region=region,
        last_seen=last_seen,
        source_provenance="https://example.test/source",
        extras={"note": "fixture"},
    )


def test_normalize_scan_entries_deduplicates_and_groups() -> None:
    entries = [
        _entry(
            provider="vodafone-de",
            frequency=450_000_000,
            symbol_rate=6_900_000,
            last_seen="2024-12-01T00:00:00+00:00",
        ),
        _entry(
            provider="vodafone-de",
            frequency=450_000_000,
            symbol_rate=6_900_000,
            last_seen="2025-01-01T00:00:00+00:00",
        ),
        _entry(region="de-berlin", frequency=482_000_000, bandwidth=8_000_000),
    ]

    result = normalize_scan_entries(entries, providers={"vodafone-de"}, regions={"de-berlin"})

    assert not result.missing_providers
    assert not result.missing_regions
    assert result.bundle.counts()["cable"]["vodafone-de"] == 1
    assert result.bundle.counts()["terrestrial"]["de-berlin"] == 1
    assert len(result.deduplicated) == 1
    kept = result.deduplicated[0].kept
    assert kept.last_seen == "2025-01-01T00:00:00+00:00"


def test_write_scanfiles_creates_neutrino_xml(tmp_path: Path) -> None:
    """Test that scanfiles are created with correct Neutrino format."""
    entries = [
        _entry(
            provider="vodafone-de",
            frequency=450_000_000,
            symbol_rate=6_900_000,
            last_seen="2025-01-01T00:00:00+00:00",
        ),
        _entry(region="de-berlin", frequency=482_000_000, bandwidth=8_000_000),
    ]
    result = normalize_scan_entries(entries)

    options = ConversionOptions()
    report = write_scanfiles(result.bundle, tmp_path, options)

    # Check that cables.xml and terrestrial.xml are created
    assert "cables" in report.output_paths
    assert "terrestrial" in report.output_paths

    # Verify cables.xml structure: <cables><cable>
    cable_tree = ET.parse(report.output_paths["cables"])
    cable_root = cable_tree.getroot()
    assert cable_root.tag == "cables"
    cable = cable_root.find("cable")
    assert cable is not None
    assert cable.attrib["name"] == "vodafone-de"
    assert cable.attrib["flags"] == "9"

    transponder = cable.find("transponder")
    assert transponder is not None
    assert transponder.attrib["frequency"] == "450000"  # kHz
    assert transponder.attrib["modulation"] == "5"  # QAM256 = 5
    assert transponder.attrib["fec_inner"] == "3"  # 3/4 = 3

    # Verify terrestrial.xml structure: <locations><terrestrial>
    terrestrial_tree = ET.parse(report.output_paths["terrestrial"])
    terrestrial_root = terrestrial_tree.getroot()
    assert terrestrial_root.tag == "locations"
    terrestrial = terrestrial_root.find("terrestrial")
    assert terrestrial is not None
    assert terrestrial.attrib["name"] == "de-berlin"
    assert terrestrial.attrib["flags"] == "5"

    terr_transponder = terrestrial.find("transponder")
    assert terr_transponder is not None
    assert terr_transponder.attrib["frequency"] == "482000"  # kHz
    assert terr_transponder.attrib["bandwidth"] == "0"  # 8MHz = 0
    assert terr_transponder.attrib["constellation"] == "5"  # QAM256 = 5
    # Check DVB-T specific parameters
    assert "transmission_mode" in terr_transponder.attrib
    assert "code_rate_HP" in terr_transponder.attrib
    assert "code_rate_LP" in terr_transponder.attrib
    assert "guard_interval" in terr_transponder.attrib
    assert "hierarchy" in terr_transponder.attrib


def test_write_scanfiles_satellites(tmp_path: Path) -> None:
    """Test that satellites.xml is created correctly."""
    sat_entry = TransponderScanEntry(
        delivery_system="DVB-S2",
        system="DVB-S2",
        frequency_hz=11229000,
        symbol_rate=22000000,
        bandwidth_hz=None,
        modulation="8PSK",
        fec="2/3",
        polarization="V",
        plp_id=None,
        country="DE",
        provider="Astra 19.2E",
        region=None,
        last_seen="2025-01-01",
        source_provenance="test",
        extras={"orbital_position": "19.2"},
    )

    result = normalize_scan_entries([sat_entry])
    options = ConversionOptions()
    report = write_scanfiles(result.bundle, tmp_path, options)

    # Check that satellites.xml is created
    assert "satellites" in report.output_paths

    # Verify satellites.xml structure: <satellites><sat>
    sat_tree = ET.parse(report.output_paths["satellites"])
    sat_root = sat_tree.getroot()
    assert sat_root.tag == "satellites"
    sat = sat_root.find("sat")
    assert sat is not None
    assert sat.attrib["name"] == "Astra 19.2E"
    assert sat.attrib["position"] == "192"  # 19.2 * 10 = 192
    assert sat.attrib["flags"] == "0"

    transponder = sat.find("transponder")
    assert transponder is not None
    assert transponder.attrib["frequency"] == "11229000"  # Hz (not kHz for satellites)
    assert transponder.attrib["symbol_rate"] == "22000000"
    assert transponder.attrib["polarization"] == "1"  # V = 1
    assert transponder.attrib["fec_inner"] == "2"  # 2/3 = 2
    assert transponder.attrib["system"] == "1"  # DVB-S2 = 1
    assert transponder.attrib["modulation"] == "2"  # 8PSK = 2


def test_write_scanfiles_strict_failure(tmp_path: Path) -> None:
    options = ConversionOptions(strict_scanfiles=True)
    with pytest.raises(ScanfileError):
        write_scanfiles(normalize_scan_entries([]).bundle, tmp_path, options)


def test_blocked_adapter_registered() -> None:
    from e2neutrino.adapters.provider_vodafone_de import (
        BLOCKED_MESSAGE,
        ProviderVodafoneDEAdapter,
        VodafoneBlockedError,
    )

    adapter = ProviderVodafoneDEAdapter()
    with pytest.raises(VodafoneBlockedError) as exc:
        adapter.ingest_bundle(Path("."), {})
    assert BLOCKED_MESSAGE in str(exc.value)


def test_validate_scanfiles_schema(tmp_path: Path) -> None:
    """Test that generated scanfiles pass validation."""
    entries = [
        _entry(provider="fixture-provider", frequency=330_000_000, symbol_rate=6_900_000),
        _entry(region="fixture-region", frequency=546_000_000, bandwidth=8_000_000),
    ]
    bundle = normalize_scan_entries(entries).bundle
    write_scanfiles(bundle, tmp_path, ConversionOptions())

    # This will validate the new format
    validate.validate_scanfiles(tmp_path)
