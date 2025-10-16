"""
Ingestion pipeline for multi-source settings.

Deutsch:
    Ingest-Pipeline für mehrere offizielle Quellen.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import yaml

from . import io_enigma
from .adapters import get_adapter
from .logging_conf import configure_logging

log = logging.getLogger(__name__)


@dataclass
class IngestResult:
    source_id: str
    profile_id: str
    output_path: Path  # points to directory containing enigma2/...
    metadata: Dict[str, str]


class IngestError(Exception):
    """Raised when ingestion fails. / Wird geworfen, wenn der Ingest fehlschlägt."""


def ingest(
    config_path: Path,
    out_dir: Path,
    only: Optional[Iterable[str]] = None,
    cache_dir: Optional[Path] = None,
) -> List[IngestResult]:
    configure_logging()
    config_path = Path(config_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = _load_config(config_path)

    requested = set(item.strip() for item in only) if only else None
    results: List[IngestResult] = []
    for source in config:
        source_id = str(source.get("id"))
        if source_id == "None":
            raise IngestError("source entry missing 'id'")
        if requested and source_id not in requested:
            log.info("skipping source %s (filtered)", source_id)
            continue
        log.info("processing source %s", source_id)
        raw_path = _fetch_source(source, out_dir, cache_dir)
        adapter_name = str(source.get("adapter", "enigma2"))
        adapter = get_adapter(adapter_name)
        profiles = adapter.ingest(raw_path, source)
        if not profiles:
            log.warning("adapter %s returned no profiles for %s", adapter.name, source_id)
            continue
        for profile in profiles:
            profile_id = profile.metadata.get("profile_id") or adapter.default_profile_id(raw_path)
            profile.metadata["source_id"] = source_id
            profile.metadata.setdefault("profile_id", profile_id)
            profile_path = out_dir / source_id / profile_id / "enigma2"
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            io_enigma.write_profile(profile, profile_path)
            buildinfo = {
                "source_id": source_id,
                "profile_id": profile_id,
                "adapter": adapter.name,
                "origin": str(raw_path),
            }
            buildinfo.update(profile.metadata)
            buildinfo_path = profile_path.parent / "BUILDINFO.json"
            buildinfo_path.write_text(
                json.dumps(buildinfo, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            buildinfo_str = {k: str(v) for k, v in buildinfo.items()}
            results.append(
                IngestResult(
                    source_id=source_id,
                    profile_id=profile_id,
                    output_path=profile_path.parent,
                    metadata=buildinfo_str,
                )
            )
    return results


def _load_config(path: Path) -> List[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or "sources" not in data:
        raise IngestError("config must define a 'sources' list")
    sources = data["sources"]
    if not isinstance(sources, list):
        raise IngestError("'sources' must be a list")
    return [source for source in sources if isinstance(source, dict)]


def _fetch_source(source: Dict[str, Any], workdir: Path, cache_dir: Optional[Path]) -> Path:
    source_type = str(source.get("type", "file"))
    source_id = str(source.get("id"))
    target_root = workdir / source_id / "_raw"
    target_root.parent.mkdir(parents=True, exist_ok=True)

    if source_type == "file":
        path_value = source.get("path", "")
        path = Path(str(path_value))
        if not path.exists():
            raise IngestError(f"file source {source_id} path {path} missing")
        if target_root.exists():
            shutil.rmtree(target_root)
        shutil.copytree(path, target_root)
        return target_root

    if source_type == "git":
        url = source.get("url")
        if not isinstance(url, str):
            raise IngestError(f"git source {source_id} requires an url")
        if target_root.exists():
            log.info("updating existing clone for %s", source_id)
            _run_git(["fetch", "--depth", "1", "origin"], cwd=target_root)
            _run_git(["reset", "--hard", "origin/HEAD"], cwd=target_root)
        else:
            _run_git(["clone", "--depth", "1", url, str(target_root)])
        return target_root

    if source_type == "http":
        url = source.get("url")
        if not isinstance(url, str):
            raise IngestError(f"http source {source_id} requires url")
        import requests

        headers = {}
        cache_base = None
        if cache_dir:
            cache_dir = Path(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_base = cache_dir / f"{source_id}.json"
            if cache_base.exists():
                cached = json.loads(cache_base.read_text(encoding="utf-8"))
                if "etag" in cached:
                    headers["If-None-Match"] = cached["etag"]
                if "last_modified" in cached:
                    headers["If-Modified-Since"] = cached["last_modified"]
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 304 and cache_base:
            cached = json.loads(cache_base.read_text(encoding="utf-8"))
            path = Path(cached["path"])
            if path.exists():
                log.info("using cached HTTP payload for %s", source_id)
                return path
        if resp.status_code >= 400:
            raise IngestError(f"http fetch failed for {source_id}: {resp.status_code}")
        target_root.mkdir(parents=True, exist_ok=True)
        filename_value = source.get("filename") or "payload"
        payload_path = target_root / str(filename_value)
        payload_path.write_bytes(resp.content)
        if cache_base:
            cache = {
                "path": str(payload_path),
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
            }
            cache_base.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
        return target_root

    raise IngestError(f"unsupported source type {source_type}")


def _run_git(args: List[str], cwd: Path | None = None) -> None:
    import subprocess

    cmd = ["git"]
    cmd.extend(args)
    log.debug("running %s (cwd=%s)", " ".join(cmd), cwd or ".")
    subprocess.run(cmd, cwd=cwd, check=True)


def run_ingest(
    *,
    config_path: Union[str, Path],
    out_dir: Union[str, Path],
    only: Optional[Union[Iterable[str], str]] = None,
    cache: Optional[Union[str, Path]] = None,
) -> List[IngestResult]:
    """
    Convenience wrapper used by the CLI to execute the ingest pipeline.
    """

    only_values = _normalise_iterable(only)
    cache_dir = Path(cache) if cache else None
    return ingest(
        Path(config_path),
        Path(out_dir),
        only=only_values,
        cache_dir=cache_dir,
    )


def _normalise_iterable(value: Optional[Union[Iterable[str], str]]) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = value
    result = [item.strip() for item in items if item and item.strip()]
    return result or None
