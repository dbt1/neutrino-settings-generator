"""
Ingestion pipeline for multi-source settings.

Deutsch:
    Ingest-Pipeline für mehrere offizielle Quellen.
"""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union
from urllib.parse import urljoin, urlparse

import requests
import yaml

from . import __version__, io_enigma
from .adapters import get_adapter
from .logging_conf import configure_logging
from .models import Profile

log = logging.getLogger(__name__)

MANDATORY_PRIMARY_SOURCE_ID = "oe-alliance"
MANDATORY_PRIMARY_URL = "https://github.com/oe-alliance/oe-alliance-settings"
DEFAULT_ALLOWED_HOSTS = {"github.com", "raw.githubusercontent.com"}
NEGATIVE_CACHE_TTL = timedelta(hours=6)
HTTP_RETRY_ATTEMPTS = 5
HTTP_TIMEOUT = 30
HTTP_BACKOFF_BASE = 1.5
HTTP_REDIRECT_LIMIT = 5
GLOBAL_REQUEST_SEMAPHORE = threading.BoundedSemaphore(4)
USER_AGENT = f"e2neutrino/{__version__} (+https://github.com/dbt1/neutrino-settings-generator)"


@dataclass
class IngestResult:
    source_id: str
    profile_id: str
    output_path: Path  # points to directory containing enigma2/...
    metadata: Dict[str, Any]


@dataclass
class IngestConfig:
    sources: List[Dict[str, Any]]
    allow_hosts: set[str] = field(default_factory=set)
    require_primary: bool = True


@dataclass
class SourceWorkspace:
    source_id: str
    root: Path
    raw_dir: Path
    lock_path: Path
    provenance_path: Path
    cache_path: Optional[Path]
    lock_payload: Dict[str, Any]


@dataclass
class FetchOutcome:
    workspace: SourceWorkspace
    raw_path: Path
    provenance: Dict[str, Any]


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

    bundle = _load_config(config_path)
    if bundle.require_primary:
        _ensure_mandatory_source(bundle.sources)

    requested = set(item.strip() for item in only) if only else None
    results: List[IngestResult] = []
    for source in bundle.sources:
        source_id = str(source.get("id"))
        if not source_id or source_id == "None":
            raise IngestError("source entry missing 'id'")
        if requested and source_id not in requested:
            log.info("skipping source %s (filtered)", source_id)
            continue
        _ensure_source_allowed(source, bundle.allow_hosts)
        workspace = _prepare_workspace(out_dir, source_id, cache_dir)
        try:
            outcome = _fetch_source(source, workspace, bundle.allow_hosts)
            adapter_name = str(source.get("adapter", "enigma2"))
            adapter = get_adapter(adapter_name)
            profiles = adapter.ingest(outcome.raw_path, source)
            if not profiles:
                log.warning("adapter %s returned no profiles for %s", adapter.name, source_id)
            provenance_record = dict(outcome.provenance)
            profile_ids: List[str] = []
            for profile in profiles:
                profile_id = profile.metadata.get("profile_id") or adapter.default_profile_id(outcome.raw_path)
                profile.metadata["source_id"] = source_id
                profile.metadata.setdefault("profile_id", profile_id)
                priority_value = _coerce_int(source.get("priority"), default=100)
                profile.metadata["source_priority"] = str(priority_value)
                profile.metadata["source_provenance"] = json.dumps(provenance_record, sort_keys=True)
                profile.metadata.setdefault("fetched_at", provenance_record.get("fetched_at", _iso_now()))
                profile_path = out_dir / source_id / profile_id / "enigma2"
                profile_path.parent.mkdir(parents=True, exist_ok=True)
                io_enigma.write_profile(profile, profile_path)
                buildinfo = _build_buildinfo(
                    source_id=source_id,
                    profile_id=profile_id,
                    adapter=adapter.name,
                    raw_path=outcome.raw_path,
                    profile=profile,
                    provenance=provenance_record,
                )
                buildinfo_path = profile_path.parent / "BUILDINFO.json"
                buildinfo_path.write_text(json.dumps(buildinfo, indent=2, sort_keys=True), encoding="utf-8")
                profile_provenance_path = profile_path.parent / "SOURCE_PROVENANCE.json"
                _write_json_atomic(profile_provenance_path, provenance_record)
                profile_ids.append(profile_id)
                results.append(
                    IngestResult(
                        source_id=source_id,
                        profile_id=profile_id,
                        output_path=profile_path.parent,
                        metadata=buildinfo,
                    )
                )
            provenance_record["profiles"] = profile_ids
            _write_json_atomic(workspace.provenance_path, provenance_record)
            _finalise_workspace(workspace, "completed", {"profiles": len(profiles)})
        except Exception as exc:  # pragma: no cover - defensive
            log.error("failed to ingest source %s: %s", source_id, exc, exc_info=log.isEnabledFor(logging.DEBUG))
            _finalise_workspace(workspace, "failed", {"error": str(exc)})
            raise
    return results


def _load_config(path: Path) -> IngestConfig:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or "sources" not in data:
        raise IngestError("config must define a 'sources' list")
    sources_raw = data["sources"]
    if not isinstance(sources_raw, list):
        raise IngestError("'sources' must be a list")
    sources = [source for source in sources_raw if isinstance(source, dict)]
    allow_hosts = {host.lower() for host in DEFAULT_ALLOWED_HOSTS}
    extra_hosts = data.get("allow_hosts")
    if isinstance(extra_hosts, list):
        for host in extra_hosts:
            if isinstance(host, str) and host.strip():
                allow_hosts.add(host.strip().lower())
    require_primary = bool(data.get("require_primary", True))
    return IngestConfig(sources=sources, allow_hosts=allow_hosts, require_primary=require_primary)


def _ensure_mandatory_source(sources: Iterable[Dict[str, Any]]) -> None:
    for source in sources:
        source_id = str(source.get("id"))
        if source_id != MANDATORY_PRIMARY_SOURCE_ID:
            continue
        if str(source.get("type")) != "git":
            raise IngestError(f"mandatory source {MANDATORY_PRIMARY_SOURCE_ID} must be of type 'git'")
        url = str(source.get("url") or "")
        if url.rstrip("/") != MANDATORY_PRIMARY_URL:
            raise IngestError(
                f"mandatory source {MANDATORY_PRIMARY_SOURCE_ID} must use url {MANDATORY_PRIMARY_URL}, got {url}"
            )
        return
    raise IngestError(f"mandatory source {MANDATORY_PRIMARY_SOURCE_ID} missing from configuration")


def _ensure_source_allowed(source: Dict[str, Any], allow_hosts: set[str]) -> None:
    if source.get("is_mock") or source.get("mock"):
        raise IngestError(f"source {source.get('id')} flagged as mock; refusing to ingest")
    source_type = str(source.get("type", "file"))
    if source_type in {"git", "http"}:
        url = str(source.get("url") or "")
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname not in allow_hosts:
            raise IngestError(f"source {source.get('id')} host {hostname} not in allowlist")


def _prepare_workspace(out_dir: Path, source_id: str, cache_dir: Optional[Path]) -> SourceWorkspace:
    root = out_dir / source_id
    raw_dir = root / "_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    lock_path = root / "source.lock"
    provenance_path = root / "SOURCE_PROVENANCE.json"
    cache_path = Path(cache_dir) / f"{source_id}.json" if cache_dir else None
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
    lock_payload = {
        "source_id": source_id,
        "pid": os.getpid(),
        "locked_at": _iso_now(),
        "status": "processing",
    }
    _write_json_atomic(lock_path, lock_payload)
    return SourceWorkspace(
        source_id=source_id,
        root=root,
        raw_dir=raw_dir,
        lock_path=lock_path,
        provenance_path=provenance_path,
        cache_path=cache_path,
        lock_payload=lock_payload,
    )


def _finalise_workspace(workspace: SourceWorkspace, status: str, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = dict(workspace.lock_payload)
    payload["status"] = status
    payload["updated_at"] = _iso_now()
    if extra:
        payload.update(extra)
    _write_json_atomic(workspace.lock_path, payload)


def _fetch_source(
    source: Dict[str, Any],
    workspace: SourceWorkspace,
    allow_hosts: set[str],
) -> FetchOutcome:
    source_type = str(source.get("type", "file")).lower()
    if source_type == "file":
        return _fetch_file_source(source, workspace)
    if source_type == "git":
        return _fetch_git_source(source, workspace)
    if source_type == "http":
        return _fetch_http_source(source, workspace, allow_hosts)
    raise IngestError(f"unsupported source type {source_type}")


def _fetch_file_source(source: Dict[str, Any], workspace: SourceWorkspace) -> FetchOutcome:
    path_value = source.get("path", "")
    path = Path(str(path_value))
    if not path.exists():
        raise IngestError(f"file source {workspace.source_id} path {path} missing")
    _clear_directory(workspace.raw_dir)
    for entry in path.iterdir():
        target = workspace.raw_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)
    fetched_at = _iso_now()
    provenance = {
        "source_id": workspace.source_id,
        "type": "file",
        "path": str(path.resolve()),
        "fetched_at": fetched_at,
        "source_mtime": _iso_timestamp(path.stat().st_mtime),
    }
    return FetchOutcome(workspace=workspace, raw_path=workspace.raw_dir, provenance=provenance)


def _fetch_git_source(source: Dict[str, Any], workspace: SourceWorkspace) -> FetchOutcome:
    url = str(source.get("url") or "")
    ref = str(source.get("ref") or "HEAD")
    target_root = workspace.raw_dir
    if any(target_root.iterdir()):
        if not (target_root / ".git").exists():
            _clear_directory(target_root)
    if not (target_root / ".git").exists():
        args = ["clone", "--depth=1", "--filter=blob:none"]
        if ref and ref not in {"HEAD"} and not _looks_like_commit(ref):
            args.extend(["--branch", ref])
        args.extend([url, str(target_root)])
        _run_git(args)
    else:
        fetch_cmd = ["fetch", "--depth", "1", "origin"]
        if ref and ref not in {"", "HEAD"}:
            fetch_cmd.append(ref)
        _run_git(fetch_cmd, cwd=target_root)
        if not ref or ref == "HEAD":
            checkout_target = "origin/HEAD"
        elif _looks_like_commit(ref) or ref.startswith("origin/"):
            checkout_target = ref
        else:
            checkout_target = f"origin/{ref}"
        _run_git(["checkout", "--detach", checkout_target], cwd=target_root)
        _run_git(["reset", "--hard", checkout_target], cwd=target_root)

    commit = _run_git(["rev-parse", "HEAD"], cwd=target_root, capture_output=True).strip()
    commit_date = _run_git(["show", "-s", "--format=%cI", "HEAD"], cwd=target_root, capture_output=True).strip()
    fetched_at = _iso_now()
    provenance = {
        "source_id": workspace.source_id,
        "type": "git",
        "url": url,
        "ref": ref,
        "commit": commit,
        "commit_date": commit_date,
        "fetched_at": fetched_at,
    }
    return FetchOutcome(workspace=workspace, raw_path=target_root, provenance=provenance)


def _fetch_http_source(
    source: Dict[str, Any],
    workspace: SourceWorkspace,
    allow_hosts: set[str],
) -> FetchOutcome:
    url = str(source.get("url") or "")
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if hostname not in allow_hosts:
        raise IngestError(f"source {workspace.source_id} host {hostname} not in allowlist")
    filename = str(source.get("filename") or Path(parsed.path).name or "payload")
    target_path = workspace.raw_dir / filename
    cache_entry = _read_cache_entry(workspace.cache_path)
    headers: Dict[str, str] = {}
    if cache_entry and not cache_entry.get("negative"):
        etag = cache_entry.get("etag")
        last_modified = cache_entry.get("last_modified")
        if etag:
            headers["If-None-Match"] = str(etag)
        if last_modified:
            headers["If-Modified-Since"] = str(last_modified)
    elif cache_entry and cache_entry.get("negative"):
        cached_at = _parse_iso(cache_entry.get("fetched_at"))
        if cached_at and datetime.now(timezone.utc) - cached_at < NEGATIVE_CACHE_TTL:
            raise IngestError(
                f"upstream {workspace.source_id} cached negative response {cache_entry.get('status')} "
                f"at {cache_entry.get('fetched_at')}; wait for TTL to expire"
            )

    response = _http_get_with_retry(url, headers, allow_hosts)
    if response.status_code == 304:
        if cache_entry and cache_entry.get("path"):
            cached_path = Path(cache_entry["path"])
            if cached_path.exists():
                if not target_path.exists():
                    # Re-link cached file into workspace to keep layout deterministic.
                    shutil.copy2(cached_path, target_path)
                provenance = _build_http_provenance(
                    workspace=workspace,
                    url=url,
                    response=response,
                    target_path=target_path,
                    cached=True,
                )
                return FetchOutcome(workspace=workspace, raw_path=workspace.raw_dir, provenance=provenance)
        response.close()
        raise IngestError(f"http cache for {workspace.source_id} invalidated; cached payload missing")

    if response.status_code == 404 or response.status_code >= 500:
        _write_cache_entry(
            workspace.cache_path,
            {
                "negative": True,
                "status": response.status_code,
                "fetched_at": _iso_now(),
            },
        )
        response.close()
        raise IngestError(f"http fetch failed for {workspace.source_id}: {response.status_code}")

    if response.status_code >= 400:
        response.close()
        raise IngestError(f"http fetch failed for {workspace.source_id}: {response.status_code}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    with tmp_path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=65536):
            fh.write(chunk)
    response.close()
    tmp_path.replace(target_path)

    headers_lower = {k.lower(): v for k, v in response.headers.items()}
    cache_payload = {
        "path": str(target_path),
        "etag": headers_lower.get("etag"),
        "last_modified": headers_lower.get("last-modified"),
        "fetched_at": _iso_now(),
        "status": response.status_code,
    }
    _write_cache_entry(workspace.cache_path, cache_payload)

    provenance = _build_http_provenance(
        workspace=workspace,
        url=url,
        response_headers=headers_lower,
        target_path=target_path,
        cached=False,
    )
    return FetchOutcome(workspace=workspace, raw_path=workspace.raw_dir, provenance=provenance)


def _build_http_provenance(
    workspace: SourceWorkspace,
    url: str,
    response: Optional[requests.Response] = None,
    response_headers: Optional[Dict[str, str]] = None,
    target_path: Optional[Path] = None,
    cached: bool = False,
) -> Dict[str, Any]:
    headers_lower = response_headers or {k.lower(): v for k, v in (response.headers if response else {}).items()}
    fetched_at = _iso_now()
    content_length = None
    if target_path and target_path.exists():
        content_length = target_path.stat().st_size
    elif response is not None and response.headers.get("Content-Length"):
        try:
            content_length = int(response.headers["Content-Length"])
        except ValueError:
            content_length = None
    provenance = {
        "source_id": workspace.source_id,
        "type": "http",
        "url": url,
        "fetched_at": fetched_at,
        "etag": headers_lower.get("etag"),
        "last_modified": headers_lower.get("last-modified"),
        "content_length": content_length,
        "cached": cached,
    }
    if headers_lower.get("date"):
        provenance["http_date"] = headers_lower["date"]
    if target_path:
        provenance["payload_path"] = str(target_path)
        provenance["payload_sha1"] = _sha1_of_path(target_path)
    return provenance


def _http_get_with_retry(url: str, headers: Dict[str, str], allow_hosts: set[str]) -> requests.Response:
    session = _get_http_session()
    current_url = url
    last_exc: Optional[Exception] = None
    for attempt in range(HTTP_RETRY_ATTEMPTS):
        try:
            response = _perform_http_request(session, current_url, headers, allow_hosts)
        except requests.RequestException as exc:
            last_exc = exc
            _sleep_with_jitter(attempt)
            continue
        if response.status_code in {429} or 500 <= response.status_code < 600:
            if attempt == HTTP_RETRY_ATTEMPTS - 1:
                return response
            response.close()
            _sleep_with_jitter(attempt)
            continue
        return response
    if last_exc:
        raise IngestError(f"http fetch failed for {url}: {last_exc}") from last_exc
    raise IngestError(f"http fetch failed for {url}: exceeded retries")


def _perform_http_request(
    session: requests.Session,
    url: str,
    headers: Dict[str, str],
    allow_hosts: set[str],
) -> requests.Response:
    current_url = url
    for _ in range(HTTP_REDIRECT_LIMIT + 1):
        _ensure_allowed_host(current_url, allow_hosts)
        with GLOBAL_REQUEST_SEMAPHORE:
            response = session.get(
                current_url,
                headers=headers,
                stream=True,
                timeout=HTTP_TIMEOUT,
                allow_redirects=False,
            )
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise IngestError(f"redirect without location for {current_url}")
            current_url = urljoin(current_url, location)
            continue
        return response
    raise IngestError(f"too many redirects for {url}")


def _ensure_allowed_host(url: str, allow_hosts: set[str]) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if hostname not in allow_hosts:
        raise IngestError(f"redirected url host {hostname} not in allowlist")


def _build_buildinfo(
    *,
    source_id: str,
    profile_id: str,
    adapter: str,
    raw_path: Path,
    profile: Profile,
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    buildinfo: Dict[str, Any] = {
        "source_id": source_id,
        "profile_id": profile_id,
        "adapter": adapter,
        "origin": str(raw_path),
        "fetched_at": provenance.get("fetched_at"),
        "service_count": len(profile.services),
        "transponder_count": len(profile.transponders),
        "bouquet_count": len(profile.bouquets),
        "provenance": provenance,
    }
    buildinfo.update({k: v for k, v in profile.metadata.items() if isinstance(k, str)})
    return buildinfo


def _clear_directory(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for entry in path.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _read_cache_entry(cache_path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not cache_path or not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return None


def _write_cache_entry(cache_path: Optional[Path], payload: Dict[str, Any]) -> None:
    if not cache_path:
        return
    _write_json_atomic(cache_path, payload)


def _coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _looks_like_commit(ref: str) -> bool:
    if len(ref) != 40:
        return False
    allowed = set("0123456789abcdef")
    return all(char in allowed for char in ref.lower())



def _run_git(args: List[str], cwd: Optional[Path] = None, capture_output: bool = False) -> str:
    import subprocess

    cmd = ["git", *args]
    log.debug("running %s (cwd=%s)", " ".join(cmd), cwd or ".")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        capture_output=capture_output,
        text=True,
    )
    return result.stdout if capture_output else ""


def _get_http_session() -> requests.Session:
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, application/xml, text/plain, */*",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
        )
        _HTTP_SESSION = session
    return _HTTP_SESSION


_HTTP_SESSION: Optional[requests.Session] = None


def _sleep_with_jitter(attempt: int) -> None:
    base = HTTP_BACKOFF_BASE ** attempt
    time.sleep(random.uniform(0.5, 1.5) * base)


def _sha1_of_path(path: Path) -> str:
    import hashlib

    sha1 = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha1.update(chunk)
    return sha1.hexdigest()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _parse_iso(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


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
        items = list(value)
    result = [item.strip() for item in items if item and item.strip()]
    return result or None
