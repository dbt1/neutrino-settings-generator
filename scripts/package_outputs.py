"""
Package conversion results into release artefacts.

Deutsch:
    Verpackt die Konvertierungsergebnisse in Release-Artefakte.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "metadata" / "packages.yml"


@dataclass
class PackageSpec:
    package_id: str
    source_id: str
    profile_id: str
    display_name: str
    description: str
    include: list[str]
    receivers: list[str] = field(default_factory=list)
    satellites: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    content_summary: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def archive_name(self) -> str:
        return f"{self.package_id}.zip"


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: package_outputs.py <out_dir> <dest_dir>", file=sys.stderr)
        return 1

    out_dir = Path(sys.argv[1])
    dest_dir = Path(sys.argv[2])
    if not out_dir.exists():
        print(f"output directory {out_dir} not found", file=sys.stderr)
        return 2

    try:
        specs = load_package_specs(MANIFEST_PATH)
    except (OSError, ValueError) as exc:
        print(f"failed to load package manifest: {exc}", file=sys.stderr)
        return 3

    specs_by_profile: dict[tuple[str, str], list[PackageSpec]] = {}
    for spec in specs:
        specs_by_profile.setdefault((spec.source_id, spec.profile_id), []).append(spec)

    dest_dir.mkdir(parents=True, exist_ok=True)
    generated_root = dest_dir / "generated"
    if generated_root.exists():
        shutil.rmtree(generated_root)
    generated_root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    release_date = now.strftime("%Y-%m-%d")
    release_root = dest_dir / "releases" / release_date
    release_root.mkdir(parents=True, exist_ok=True)

    checksums: list[tuple[str, str]] = []
    package_archives: list[Path] = []
    package_metadata: list[dict[str, Any]] = []
    seen_spec_ids: set[str] = set()

    for source_dir in sorted(out_dir.iterdir()):
        if not source_dir.is_dir():
            continue
        for profile_dir in sorted(source_dir.iterdir()):
            if not profile_dir.is_dir():
                continue
            label = f"{source_dir.name}-{profile_dir.name}"
            all_dir = profile_dir / "ALL"
            if not all_dir.exists():
                print(f"skip {label}: no ALL output", file=sys.stderr)
                continue

            category = classify_profile(all_dir)
            publish_path, provider_slug = build_publish_path(category, source_dir.name, profile_dir.name)
            target_dir = dest_dir / "generated" / publish_path
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(all_dir, target_dir)

            buildinfo = profile_dir / "BUILDINFO.json"
            if buildinfo.exists():
                shutil.copy2(buildinfo, target_dir / "BUILDINFO.json")

            profile_specs = specs_by_profile.get((source_dir.name, profile_dir.name), [])
            if profile_specs:
                for spec in profile_specs:
                    archive_path, included_files = create_spec_archive(spec, target_dir, release_root)
                    digest = sha256_file(archive_path)
                    package_archives.append(archive_path)
                    checksums.append((archive_path.name, digest))
                    metadata_entry = build_spec_metadata(
                        spec,
                        archive_path,
                        digest,
                        included_files,
                    )
                    metadata_entry.update(
                        {
                            "category": category,
                            "provider": provider_slug,
                            "publish_path": publish_path.as_posix(),
                        }
                    )
                    package_metadata.append(metadata_entry)
                    seen_spec_ids.add(spec.package_id)
            else:
                archive_path, included_files = create_default_archive(
                    source_dir.name,
                    profile_dir.name,
                    target_dir,
                    release_root,
                )
                digest = sha256_file(archive_path)
                package_archives.append(archive_path)
                checksums.append((archive_path.name, digest))
                metadata_entry = build_default_metadata(
                    source_dir.name,
                    profile_dir.name,
                    archive_path,
                    digest,
                    included_files,
                )
                metadata_entry.update(
                    {
                        "category": category,
                        "provider": provider_slug,
                        "publish_path": publish_path.as_posix(),
                    }
                )
                package_metadata.append(metadata_entry)

    unused_specs = [spec for spec in specs if spec.package_id not in seen_spec_ids]
    for spec in unused_specs:
        print(
            f"warning: package '{spec.package_id}' did not match any output "
            f"(source={spec.source_id}, profile={spec.profile_id})",
            file=sys.stderr,
        )

    bundle_metadata: list[dict[str, Any]] = []
    if package_archives:
        all_bundle = release_root / "all-sources.zip"
        if all_bundle.exists():
            all_bundle.unlink()
        with ZipFile(all_bundle, "w", ZIP_DEFLATED) as zf:
            for bundle in package_archives:
                zf.write(bundle, arcname=bundle.name)
        all_digest = sha256_file(all_bundle)
        checksums.append((all_bundle.name, all_digest))
        bundle_metadata.append(
            {
                "archive": all_bundle.name,
                "label": "All packages combined",
                "contains": [path.name for path in package_archives],
                "size_bytes": all_bundle.stat().st_size,
                "checksum": all_digest,
            }
        )

    checksum_path = release_root / "checksums.txt"
    with checksum_path.open("w", encoding="utf-8") as fh:
        for name, digest in checksums:
            fh.write(f"{digest}  {name}\n")

    manifest_path = release_root / "packages_manifest.json"
    manifest_data = {
        "generated_at": now.isoformat(),
        "packages": package_metadata,
        "bundles": bundle_metadata,
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2, sort_keys=True), encoding="utf-8")

    metadata_path = release_root / "RELEASEINFO.json"
    metadata = {
        "generated_at": now.isoformat(),
        "packages_manifest": manifest_path.name,
        "packages": [entry["archive"] for entry in package_metadata],
        "bundles": [entry["archive"] for entry in bundle_metadata],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    return 0


def load_package_specs(path: Path) -> list[PackageSpec]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    packages = data.get("packages", [])
    if not isinstance(packages, list):
        raise ValueError("packages manifest must contain a list under 'packages'")

    specs: list[PackageSpec] = []
    seen_ids: set[str] = set()
    for item in packages:
        if not isinstance(item, dict):
            raise ValueError("each package entry must be a mapping")
        package_id = str(item.get("package_id", "")).strip()
        source_id = str(item.get("source_id", "")).strip()
        profile_id = str(item.get("profile_id", "")).strip()
        display_name = str(item.get("display_name", "")).strip()
        description = str(item.get("description", "")).strip()
        include = _ensure_str_list(item.get("include"))
        receivers = _ensure_str_list(item.get("receivers"))
        satellites = _ensure_str_list(item.get("satellites"))
        tags = _ensure_str_list(item.get("tags"))
        content_summary = item.get("content_summary")

        if not package_id:
            raise ValueError("package entry missing 'package_id'")
        if package_id in seen_ids:
            raise ValueError(f"duplicate package_id '{package_id}' in manifest")
        seen_ids.add(package_id)

        if not source_id or not profile_id:
            raise ValueError(f"package '{package_id}' missing source_id/profile_id")
        if not display_name:
            raise ValueError(f"package '{package_id}' missing display_name")
        if not include:
            raise ValueError(f"package '{package_id}' must define at least one include entry")

        known_keys = {
            "package_id",
            "source_id",
            "profile_id",
            "display_name",
            "description",
            "include",
            "receivers",
            "satellites",
            "tags",
            "content_summary",
        }
        extra = {key: value for key, value in item.items() if key not in known_keys}

        specs.append(
            PackageSpec(
                package_id=package_id,
                source_id=source_id,
                profile_id=profile_id,
                display_name=display_name,
                description=description,
                include=include,
                receivers=receivers,
                satellites=satellites,
                tags=tags,
                content_summary=str(content_summary) if content_summary is not None else None,
                extra=extra,
            )
        )
    return specs


def classify_profile(all_dir: Path) -> str:
    buildinfo_path = all_dir / "BUILDINFO.json"
    if not buildinfo_path.exists():
        return "unknown"
    try:
        metadata = json.loads(buildinfo_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return "unknown"

    stats_raw = metadata.get("stats")
    if isinstance(stats_raw, str):
        try:
            stats = json.loads(stats_raw)
        except json.JSONDecodeError:
            stats = {}
    elif isinstance(stats_raw, dict):
        stats = stats_raw
    else:
        stats = {}

    sat = int(stats.get("sat_services", 0))
    cable = int(stats.get("cable_services", 0))
    terrestrial = int(stats.get("terrestrial_services", 0))

    categories = {
        "sat": sat,
        "cable": cable,
        "terrestrial": terrestrial,
    }
    active = [name for name, count in categories.items() if count > 0]
    if not active:
        return "unknown"
    if len(active) == 1:
        return active[0]
    return "-".join(sorted(active))


def build_publish_path(category: str, source_id: str, profile_id: str) -> tuple[Path, str]:
    provider_slug = profile_id.split(".", 1)[0] if profile_id else "unknown"
    safe_category = category or "unknown"
    return Path(safe_category) / source_id / provider_slug / profile_id, provider_slug


def create_spec_archive(spec: PackageSpec, source_dir: Path, release_root: Path) -> tuple[Path, list[str]]:
    archive_path = release_root / spec.archive_name()
    if archive_path.exists():
        archive_path.unlink()

    prefix = source_dir.name
    added: set[str] = set()
    included: list[str] = []
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as zf:
        for pattern in spec.include:
            files = _collect_files_for_pattern(source_dir, pattern)
            if not files:
                raise FileNotFoundError(
                    f"package '{spec.package_id}' include pattern '{pattern}' matched no files"
                )
            for file_path in files:
                rel = file_path.relative_to(source_dir).as_posix()
                if rel in added:
                    continue
                arcname = f"{prefix}/{rel}" if rel else prefix
                zf.write(file_path, arcname=arcname)
                added.add(rel)
                included.append(rel)

    if not included:
        raise RuntimeError(f"package '{spec.package_id}' produced an empty archive")
    return archive_path, included


def create_default_archive(
    source_id: str,
    profile_id: str,
    source_dir: Path,
    release_root: Path,
) -> tuple[Path, list[str]]:
    zip_base = release_root / f"{source_id}-{profile_id}"
    archive_path = Path(
        shutil.make_archive(
            str(zip_base),
            "zip",
            root_dir=source_dir.parent,
            base_dir=source_dir.name,
        )
    )
    files = sorted(
        path.relative_to(source_dir).as_posix()
        for path in source_dir.rglob("*")
        if path.is_file()
    )
    return archive_path, files


def build_spec_metadata(
    spec: PackageSpec,
    archive_path: Path,
    checksum: str,
    included_files: list[str],
) -> dict[str, Any]:
    metadata = {
        "package_id": spec.package_id,
        "archive": archive_path.name,
        "display_name": spec.display_name,
        "description": spec.description,
        "source_id": spec.source_id,
        "profile_id": spec.profile_id,
        "files": included_files,
        "receivers": spec.receivers,
        "satellites": spec.satellites,
        "tags": spec.tags,
        "content_summary": spec.content_summary or ", ".join(included_files),
        "size_bytes": archive_path.stat().st_size,
        "checksum": checksum,
    }
    if spec.extra:
        metadata.update(spec.extra)
    return metadata


def build_default_metadata(
    source_id: str,
    profile_id: str,
    archive_path: Path,
    checksum: str,
    included_files: list[str],
) -> dict[str, Any]:
    return {
        "package_id": f"{source_id}-{profile_id}",
        "archive": archive_path.name,
        "display_name": f"{source_id}/{profile_id}",
        "description": "Complete output bundle for this source/profile.",
        "source_id": source_id,
        "profile_id": profile_id,
        "files": included_files,
        "receivers": [],
        "satellites": [],
        "tags": ["auto"],
        "content_summary": "complete output",
        "size_bytes": archive_path.stat().st_size,
        "checksum": checksum,
    }


def _collect_files_for_pattern(base_dir: Path, pattern: str) -> list[Path]:
    pattern = pattern.strip()
    if not pattern:
        return []
    matches = list(base_dir.glob(pattern))
    files: list[Path] = []
    for match in matches:
        if match.is_dir():
            files.extend(path for path in match.rglob("*") if path.is_file())
        elif match.is_file():
            files.append(match)
    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: list[Path] = []
    for file_path in files:
        rel = file_path.relative_to(base_dir).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        ordered.append(file_path)
    return ordered


def _ensure_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, Iterable):
        items = list(value)
    else:
        items = [value]
    result = [str(item).strip() for item in items if str(item).strip()]
    return result


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


if __name__ == "__main__":
    sys.exit(main())
