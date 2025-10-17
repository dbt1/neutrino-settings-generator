from __future__ import annotations

import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from e2neutrino.converter import ConversionOptions, convert, run_convert

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def enigma_profile(tmp_path: Path) -> Path:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_lamedb", profile_dir / "lamedb")
    shutil.copy(FIXTURE_DIR / "bouquets.tv", profile_dir / "bouquets.tv")
    shutil.copy(FIXTURE_DIR / "userbouquet.favourites.tv", profile_dir / "userbouquet.favourites.tv")
    return profile_dir


def test_basic_conversion(enigma_profile: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    options = ConversionOptions()
    result = convert(enigma_profile, out_dir, options)

    services_all = out_dir / "services.xml"
    bouquets_all = out_dir / "bouquets.xml"
    assert services_all.exists()
    assert bouquets_all.exists()
    qa_report = out_dir / "qa_report.md"
    assert qa_report.exists()
    report_text = qa_report.read_text(encoding="utf-8")
    assert "QA Report" in report_text

    tree = ET.parse(services_all)
    root = tree.getroot()
    satellites = root.find("satellites")
    assert satellites is not None
    sat_services = satellites.findall(".//service")
    assert len(sat_services) == 2

    cable_dir = out_dir / "cable"
    assert cable_dir.exists()
    sat_dir = out_dir / "sat"
    assert sat_dir.exists()

    buildinfo = (out_dir / "BUILDINFO.json").read_text(encoding="utf-8")
    assert '"api_version": 4' in buildinfo
    assert result.profile.metadata["lamedb_version"] == "4"


def test_lamedb5(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile5"
    profile_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_lamedb5", profile_dir / "lamedb5")
    shutil.copy(FIXTURE_DIR / "bouquets.tv", profile_dir / "bouquets.tv")
    shutil.copy(FIXTURE_DIR / "userbouquet.favourites.tv", profile_dir / "userbouquet.favourites.tv")

    out_dir = tmp_path / "out5"
    options = ConversionOptions()
    result = convert(profile_dir, out_dir, options)

    assert result.profile.metadata["lamedb_version"] == "5"
    assert (out_dir / "services.xml").exists()


def test_run_convert_wrapper(enigma_profile: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "wrapper"
    result = run_convert(
        inp=enigma_profile,
        out=out_dir,
        include_types="S,C",
        no_terrestrial=True,
        api_version=4,
    )
    assert (out_dir / "services.xml").exists()
    assert result.output_path == out_dir
