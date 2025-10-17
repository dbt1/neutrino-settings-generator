from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from e2neutrino.converter import ConversionOptions, convert

FIXTURE_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = FIXTURE_DIR / "golden"


@pytest.fixture()
def enigma_profile(tmp_path: Path) -> Path:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_lamedb", profile_dir / "lamedb")
    shutil.copy(FIXTURE_DIR / "bouquets.tv", profile_dir / "bouquets.tv")
    shutil.copy(FIXTURE_DIR / "userbouquet.favourites.tv", profile_dir / "userbouquet.favourites.tv")
    return profile_dir


def test_golden_output(enigma_profile: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    convert(enigma_profile, out_dir, ConversionOptions())

    generated_services = (out_dir / "services.xml").read_text(encoding="utf-8")
    generated_bouquets = (out_dir / "bouquets.xml").read_text(encoding="utf-8")
    qa_report = (out_dir / "qa_report.md").read_text(encoding="utf-8")

    expected_services = (GOLDEN_DIR / "services.xml").read_text(encoding="utf-8")
    expected_bouquets = (GOLDEN_DIR / "bouquets.xml").read_text(encoding="utf-8")

    assert generated_services == expected_services
    assert generated_bouquets == expected_bouquets
    assert "QA Report" in qa_report
