from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from e2neutrino.adapters import get_adapter


@pytest.mark.parametrize("adapter_name", ["provider_wilhelm_tel_de"])
def test_wilhelm_tel_adapter_produces_scan_entries(tmp_path: Path, adapter_name: str) -> None:
    source_dir = tmp_path / "source"
    shutil.copytree(Path("metadata/scan_sources/wilhelm-tel.de"), source_dir)

    adapter = get_adapter(adapter_name)
    result = adapter.ingest_bundle(source_dir, {"region": "de-hamburg"})

    assert result.profiles == []
    assert result.scan_entries, "expected DVB-C transponder entries"

    frequencies = {entry.frequency_hz for entry in result.scan_entries}
    assert 618_000_000 in frequencies

    sample = next(entry for entry in result.scan_entries if entry.frequency_hz == 618_000_000)
    assert sample.symbol_rate == 6_900_000
    assert sample.modulation == "QAM256"
    assert sample.provider == "wilhelm-tel"
    assert sample.region == "de-hamburg"

    assert sample.extras.get("channel_count")
    preview = sample.extras.get("channel_preview")
    assert preview and "ProSieben" in preview

    # Ensure metadata enumerates the JSON file
    assert result.extra_metadata.get("sources")
