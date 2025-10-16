"""
Generate multilingual README files for the target repository.

The script inspects the publish staging directory and writes README.md (English)
and README.de.md (German) containing direct download links to the latest bundles
and a short overview for users.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path


def build_readme(
    release_date: dt.date,
    bundles: list[tuple[str, Path]],
    generated_root: Path,
    locale: str,
) -> str:
    header = {
        "en": "# Neutrino Settings\n\n",
        "de": "# Neutrino Settings\n\n",
    }[locale]

    intro = {
        "en": (
            "Latest automatically generated settings and bouquet lists for Neutrino.\n"
            f"* Build date: **{release_date.isoformat()}**\n"
        ),
        "de": (
            "Automatisch erzeugte Settings- und Bouquettlisten für Neutrino.\n"
            f"* Erzeugt am: **{release_date.isoformat()}**\n"
        ),
    }[locale]

    download_caption = {"en": "## Downloads\n", "de": "## Downloads\n"}[locale]

    link_lines = []
    for label, rel_path in bundles:
        link_text = {
            "en": f"- [{label}]({rel_path.as_posix()})",
            "de": f"- [{label}]({rel_path.as_posix()})",
        }[locale]
        link_lines.append(link_text)

    generated_caption = {
        "en": "## Generated Profiles\n",
        "de": "## Generierte Profile\n",
    }[locale]

    generated_lines = []
    if generated_root.exists():
        for source_dir in sorted(generated_root.iterdir()):
            if not source_dir.is_dir():
                continue
            for profile_dir in sorted(source_dir.iterdir()):
                if not profile_dir.is_dir():
                    continue
                rel = profile_dir.relative_to(generated_root)
                generated_lines.append(f"- `{rel.as_posix()}`")

    footer = {
        "en": (
            "\n---\n"
            "These files are refreshed automatically by the "
            "[neutrino-settings-generator](https://github.com/dbt1/neutrino-settings-generator) "
            "project."
        ),
        "de": (
            "\n---\n"
            "Die Aktualisierung erfolgt automatisch durch das "
            "[neutrino-settings-generator](https://github.com/dbt1/neutrino-settings-generator)-Projekt."
        ),
    }[locale]

    sections = [
        header,
        intro,
        download_caption,
        *(line + "\n" for line in link_lines),
        generated_caption,
        *(line + "\n" for line in generated_lines),
        footer,
    ]
    return "".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create README files for the publishing target."
    )
    parser.add_argument("publish_dir", type=Path)
    parser.add_argument("target_dir", type=Path)
    args = parser.parse_args()

    publish_dir: Path = args.publish_dir
    target_dir: Path = args.target_dir

    releases_root = publish_dir / "releases"
    if not releases_root.exists():
        raise SystemExit(f"Releases directory {releases_root} missing.")

    release_dirs = sorted(
        (path for path in releases_root.iterdir() if path.is_dir()),
        reverse=True,
    )
    if not release_dirs:
        raise SystemExit("No release directories found.")

    latest = release_dirs[0]
    release_date = dt.datetime.strptime(latest.name, "%Y-%m-%d").date()

    bundles: list[tuple[str, Path]] = []
    for file in sorted(latest.glob("*.zip")):
        label = file.stem.replace("-", " ").replace("_", " ").title()
        rel_path = Path("releases") / latest.name / file.name
        bundles.append((label, rel_path))

    generated_root = target_dir / "generated"

    readme_en = build_readme(release_date, bundles, generated_root, "en")
    readme_de = build_readme(release_date, bundles, generated_root, "de")

    (target_dir / "README.md").write_text(readme_en, encoding="utf-8")
    (target_dir / "README.de.md").write_text(readme_de, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
