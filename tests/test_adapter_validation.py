from __future__ import annotations

import json
from pathlib import Path

import pytest

from e2neutrino.adapters.dvbsi import DvbSiAdapter
from e2neutrino.adapters.jsonapi import JSONAPIAdapter
from e2neutrino.adapters.m3u import M3UAdapter


def test_jsonapi_missing_required_field(tmp_path: Path) -> None:
    payload = {
        "channels": [
            {
                "name": "Official Channel",
                # deliberately omit sid to trigger schema validation
                "onid": 1,
                "tsid": 1,
                "namespace": 1,
                "service_type": 1,
            }
        ]
    }
    source_dir = tmp_path / "json"
    source_dir.mkdir()
    (source_dir / "channels.json").write_text(json.dumps(payload), encoding="utf-8")

    adapter = JSONAPIAdapter()
    with pytest.raises(ValueError):
        adapter.ingest(
            source_dir,
            {
                "id": "json",
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
        )


def test_m3u_rejects_unlisted_domain(tmp_path: Path) -> None:
    source_dir = tmp_path / "m3u"
    source_dir.mkdir()
    playlist = source_dir / "list.m3u"
    playlist.write_text(
        "#EXTM3U\n"
        "#EXTINF:-1 tvg-name=\"Test\" group-title=\"News\" provider=\"Official\" service-type=\"1\"\n"
        "http://illegal.example/stream\n",
        encoding="utf-8",
    )

    adapter = M3UAdapter()
    with pytest.raises(ValueError):
        adapter.ingest(
            source_dir,
            {
                "allowed_domains": ["official.example"],
                "provider": "Official Provider",
            },
        )


def test_dvbsi_requires_network_and_transport_ids(tmp_path: Path) -> None:
    source_dir = tmp_path / "dvb"
    source_dir.mkdir()
    dump_path = source_dir / "scan.dump"
    dump_path.write_text(
        "#SERVICE sid=0x1 onid=0x0 tsid=0x0 namespace=0x1 name=\"Broken\" type=1\n",
        encoding="utf-8",
    )

    adapter = DvbSiAdapter()
    with pytest.raises(ValueError):
        adapter.ingest(source_dir, {"path": dump_path})
