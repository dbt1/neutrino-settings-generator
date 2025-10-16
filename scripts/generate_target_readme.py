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
from zipfile import ZipFile


def build_readme(
    release_date: dt.date,
    bundles: list[dict[str, str]],
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
    for bundle in bundles:
        label = bundle["label"]
        rel_path = bundle["path"]
        contents = bundle["contents"]
        link_text = {
            "en": f"- [{label}]({rel_path}) – contains {contents}",
            "de": f"- [{label}]({rel_path}) – enthält {contents}",
        }[locale]
        link_lines.append(link_text)

    instructions_caption = {
        "en": "## How To Use\n",
        "de": "## Anleitung\n",
    }[locale]

    instructions_body = {
        "en": (
            "1. Pick the ZIP that matches your receiver or preferred profile.\n"
            "2. Download and unzip the archive on your computer.\n"
            "3. Copy the unpacked `ALL/` contents onto your Neutrino box via FTP "
            "(usually `/var/tuxbox/config/zapit/`).\n"
            "4. Reboot or reload services so the new settings appear.\n"
        ),
        "de": (
            "1. Wähle das passende ZIP für deinen Receiver bzw. das gewünschte Profil.\n"
            "2. Lade das Archiv herunter und entpacke es am PC.\n"
            "3. Kopiere den entpackten Inhalt aus `ALL/` per FTP auf deine Neutrino-Box "
            "(meist `/var/tuxbox/config/zapit/`).\n"
            "4. Box neu starten oder Kanallisten neu laden, damit die Settings aktiv werden.\n"
        ),
    }[locale]

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
        instructions_caption,
        instructions_body,
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

    bundles: list[dict[str, str]] = []
    for file in sorted(latest.glob("*.zip")):
        label = file.stem.replace("-", " ").replace("_", " ").title()
        rel_path = Path("releases") / latest.name / file.name
        zip_contents = describe_zip(file)
        bundles.append(
            {
                "label": label,
                "path": rel_path.as_posix(),
                "contents": zip_contents,
            }
        )

    generated_root = target_dir / "generated"

    readme_en = build_readme(release_date, bundles, generated_root, "en")
    readme_de = build_readme(release_date, bundles, generated_root, "de")

    (target_dir / "README.md").write_text(readme_en, encoding="utf-8")
    (target_dir / "README.de.md").write_text(readme_de, encoding="utf-8")

    return 0


def describe_zip(path: Path) -> str:
    with ZipFile(path) as zf:
        top_entries: set[str] = set()
        for name in zf.namelist():
            name = name.rstrip("/")
            if not name:
                continue
            top_entries.add(name.split("/", 1)[0])
    entries = sorted(top_entries)
    if not entries:
        return "no files"
    if len(entries) == 1:
        return f"`{entries[0]}`"
    return ", ".join(f"`{entry}`" for entry in entries)


if __name__ == "__main__":
    raise SystemExit(main())
