from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from e2neutrino.ingest import ingest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def sources_config(tmp_path: Path) -> Path:
    enigma_source = tmp_path / "enigma_source"
    enigma_source.mkdir()
    (enigma_source / "lamedb").write_text((FIXTURE_DIR / "sample_lamedb").read_text(encoding="utf-8"), encoding="utf-8")
    shutil.copy(FIXTURE_DIR / "bouquets.tv", enigma_source / "bouquets.tv")
    shutil.copy(FIXTURE_DIR / "userbouquet.favourites.tv", enigma_source / "userbouquet.favourites.tv")

    json_source = tmp_path / "json_source"
    json_source.mkdir()
    shutil.copy(FIXTURE_DIR / "json_payload.json", json_source / "channels.json")

    config = {
        "require_primary": False,
        "sources": [
            {
                "id": "local-enigma",
                "type": "file",
                "path": str(enigma_source),
                "adapter": "enigma2",
            },
            {
                "id": "jsonapi",
                "type": "file",
                "path": str(json_source),
                "adapter": "jsonapi",
                "json_pointer": "/channels",
                "mapping": {
                    "name": "name",
                    "sid": "sid",
                    "onid": "onid",
                    "tsid": "tsid",
                    "namespace": "namespace",
                    "service_type": "service_type",
                },
            },
        ]
    }
    config_path = tmp_path / "sources.yml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path


def test_ingest_sources(tmp_path: Path, sources_config: Path) -> None:
    out_dir = tmp_path / "work"
    results = ingest(sources_config, out_dir)

    assert len(results) >= 2
    for result in results:
        profile_dir = result.output_path / "enigma2"
        assert profile_dir.exists()
        assert (profile_dir / "lamedb").exists() or (profile_dir / "lamedb5").exists()
        assert (profile_dir.parent / "BUILDINFO.json").exists()
        provenance_path = result.output_path / "SOURCE_PROVENANCE.json"
        assert provenance_path.exists()
        data = json.loads(provenance_path.read_text(encoding="utf-8"))
        assert data.get("source_id") == result.source_id

    # json adapter should produce Enigma-like folder
    json_profile = out_dir / "jsonapi"
    assert json_profile.exists()
