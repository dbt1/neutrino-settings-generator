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
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: package_outputs.py <out_dir> <dest_dir>", file=sys.stderr)
        return 1

    out_dir = Path(sys.argv[1])
    dest_dir = Path(sys.argv[2])
    if not out_dir.exists():
        print(f"output directory {out_dir} not found", file=sys.stderr)
        return 2

    dest_dir.mkdir(parents=True, exist_ok=True)
    release_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    release_root = dest_dir / "releases" / release_date
    release_root.mkdir(parents=True, exist_ok=True)

    checksums: list[tuple[str, str]] = []
    bundle_paths: list[Path] = []

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

            target_dir = dest_dir / "generated" / source_dir.name / profile_dir.name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(all_dir, target_dir)

            buildinfo = profile_dir / "BUILDINFO.json"
            if buildinfo.exists():
                shutil.copy2(buildinfo, target_dir / "BUILDINFO.json")

            zip_base = release_root / f"{source_dir.name}-{profile_dir.name}"
            archive_path = Path(
                shutil.make_archive(
                    str(zip_base),
                    "zip",
                    root_dir=target_dir.parent,
                    base_dir=target_dir.name,
                )
            )
            bundle_paths.append(archive_path)
            checksums.append((archive_path.name, sha256_file(archive_path)))

    if bundle_paths:
        all_bundle = release_root / "all-sources.zip"
        if all_bundle.exists():
            all_bundle.unlink()
        with ZipFile(all_bundle, "w", ZIP_DEFLATED) as zf:
            for bundle in bundle_paths:
                zf.write(bundle, arcname=bundle.name)
        checksums.append((all_bundle.name, sha256_file(all_bundle)))
        bundle_paths.append(all_bundle)

    checksum_path = release_root / "checksums.txt"
    with checksum_path.open("w", encoding="utf-8") as fh:
        for name, digest in checksums:
            fh.write(f"{digest}  {name}\n")

    metadata_path = release_root / "RELEASEINFO.json"
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bundles": [path.name for path in bundle_paths],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    return 0


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


if __name__ == "__main__":
    sys.exit(main())
