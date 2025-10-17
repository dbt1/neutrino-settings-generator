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
        system="DVB-S2" if provider else "DVB-T2",
        frequency_hz=frequency,
        symbol_rate=symbol_rate,
        bandwidth_hz=bandwidth,
        modulation="QAM256" if provider else "COFDM",
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

    assert "cable" in report.output_paths
    assert "terrestrial" in report.output_paths

    cable_tree = ET.parse(report.output_paths["cable"])
    cable_root = cable_tree.getroot()
    provider = cable_root.find("provider")
    assert provider is not None
    assert provider.attrib["name"] == "vodafone-de"
    transponder = provider.find("transponder")
    assert transponder is not None
    assert transponder.attrib["frequency"] == "450000"

    terrestrial_tree = ET.parse(report.output_paths["terrestrial"])
    terrestrial_root = terrestrial_tree.getroot()
    region = terrestrial_root.find("region")
    assert region is not None
    assert region.attrib["name"] == "de-berlin"


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
    entries = [
        _entry(provider="fixture-provider", frequency=330_000_000, symbol_rate=6_900_000),
        _entry(region="fixture-region", frequency=546_000_000, bandwidth=8_000_000),
    ]
    bundle = normalize_scan_entries(entries).bundle
    write_scanfiles(bundle, tmp_path, ConversionOptions())

    validate.validate_scanfiles(tmp_path)
