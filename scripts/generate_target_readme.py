"""
Generate multilingual README files for the target repository.

The script inspects the publish staging directory and writes README.md (English)
and README.de.md (German) containing direct download links to the latest bundles
and a short overview for users.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zipfile import ZipFile


def build_readme(
    release_date: dt.date,
    bundles: list[dict[str, str]],
    generated_root: Path,
    locale: str,
    sources: list[dict[str, str]],
    providers: list[dict[str, str]],
) -> str:
    translations = {
        "en": {
            "title": "# Neutrino Settings\n\n",
            "intro": (
                "Latest automatically generated zapit files for Neutrino.\n"
                f"* Build date: **{release_date.isoformat()}**\n"
            ),
            "tldr": "## TL;DR – Quick Start\n",
            "tldr_points": [
                "Select your **Source** and **Provider** below.",
                "Download only the files your reception path needs – nothing more.",
                "Copy all XMLs into `neutrino/data/config` and reboot or reload services."
            ],
            "download_caption": "## Downloads (Cards)\n",
            "download_empty": "_No bundles available._\n",
            "table_caption": "## What do I actually need?\n",
            "table_headers": (
                "| Source | Provider | Required file(s) | Last updated | Note |\n"
                "| --- | --- | --- | --- | --- |\n"
            ),
            "release_caption": "## Release Packages\n",
            "release_headers": "| Archive | Contains |\n| --- | --- |\n",
            "howto_caption": "## Install\n",
            "howto_body": (
                "1. ⬇️ Download the XMLs listed for your provider.\n"
                "2. 📂 Copy them to `.../neutrino/data/config/`.\n"
                "3. 🔁 Restart Neutrino or reload settings via the menu.\n"
                "4. ✅ Verify the SHA256 checksum if you want to be extra safe.\n"
            ),
            "profiles_caption": "## Generated Profiles\n",
            "profiles_table_headers": "| Source | Provider | Profile path |\n| --- | --- | --- |\n",
            "footnotes_caption": "## Sources & Footnotes\n",
            "satellite_hint": "⚠️ Satellite (DVB-S/S2) packages are documented separately – no direct downloads here.",
            "quick_hint": "Tip: Use the table above if you are unsure which files you need.",
            "card_descriptions": {
                "cable.xml": "Cable frequencies, QAM and symbol rates.",
                "terrestrial.xml": "Terrestrial multiplex list (DVB-T/T2).",
                "bouquets.xml": "Favourite and bouquet structure.",
                "satellites.xml": "Satellite orbital positions (not part of this dataset)."
            }
        },
        "de": {
            "title": "# Neutrino Settings\n\n",
            "intro": (
                "Automatisch erzeugte zapit-Dateien für Neutrino.\n"
                f"* Erzeugt am: **{release_date.isoformat()}**\n"
            ),
            "tldr": "## TL;DR – Schnellstart\n",
            "tldr_points": [
                "Wähle zuerst **Source** (Empfangsart) und danach den **Provider**.",
                "Lade nur die Dateien herunter, die zu deinem Empfangsweg passen.",
                "Kopiere alle XMLs nach `neutrino/data/config` und starte Neutrino neu."
            ],
            "download_caption": "## Downloads (Karten)\n",
            "download_empty": "_Keine Downloads verfügbar._\n",
            "table_caption": "## Was brauche ich wirklich?\n",
            "table_headers": (
                "| Source | Provider | Benötigte Datei(en) | Zuletzt aktualisiert | Hinweis |\n"
                "| --- | --- | --- | --- | --- |\n"
            ),
            "release_caption": "## Release-Pakete\n",
            "release_headers": "| Archiv | Enthält |\n| --- | --- |\n",
            "howto_caption": "## Installation\n",
            "howto_body": (
                "1. ⬇️ Lade die für deinen Provider aufgeführten XML-Dateien.\n"
                "2. 📂 Kopiere sie nach `.../neutrino/data/config/`.\n"
                "3. 🔁 Starte Neutrino neu oder lade die Einstellungen neu.\n"
                "4. ✅ Prüfe optional die SHA256-Prüfsumme.\n"
            ),
            "profiles_caption": "## Generierte Profile\n",
            "profiles_table_headers": "| Source | Anbieter | Profilpfad |\n| --- | --- | --- |\n",
            "footnotes_caption": "## Quellen & Fußnoten\n",
            "satellite_hint": "⚠️ Satellit (DVB-S/S2) wird hier nicht ausgeliefert und ist separat dokumentiert.",
            "quick_hint": "Tipp: Die Tabelle oben zeigt dir sofort, welche Dateien du brauchst.",
            "card_descriptions": {
                "cable.xml": "Kabel-Frequenzen mit QAM und Symbolrate.",
                "terrestrial.xml": "DVB-T/T2-Multiplexliste.",
                "bouquets.xml": "Favoriten- und Bouquet-Struktur.",
                "satellites.xml": "Satellitenpositionen (nicht Bestandteil dieses Pakets)."
            }
        },
    }

    t = translations[locale]

    # Build source lookup
    source_lookup = {item["id"]: item for item in sources}

    # Prepare footnotes from provider origins
    footnote_map: dict[str, int] = {}
    footnotes: list[str] = []
    for provider in providers:
        origin = provider.get("origin", "")
        if origin and origin not in footnote_map:
            footnote_map[origin] = len(footnotes) + 1
            footnotes.append(origin)

    # TL;DR bullet list
    tldr_lines = [t["tldr"]]
    for point in t["tldr_points"]:
        tldr_lines.append(f"- {point}\n")
    tldr_lines.append("\n")

    # Downloads table focusing on explicit files (cable/terrestrial/bouquets)
    key_files = ["cable.xml", "terrestrial.xml", "bouquets.xml"]
    download_lines = [t["download_caption"]]
    download_lines.append("| File | Purpose |\n| --- | --- |\n")
    for filename in key_files:
        description = t["card_descriptions"].get(filename, "")
        download_lines.append(f"| ⬇️ `{filename}` | {description} |\n")
    download_lines.append("\n")

    release_lines: list[str] = [t["release_caption"], t["release_headers"]]
    if bundles:
        for bundle in bundles:
            release_lines.append(
                f"| ⬇️ [{bundle['label']}]({bundle['path']}) | {bundle['contents']} |\n"
            )
        release_lines.append("\n")
    else:
        release_lines.append(t["download_empty"])


    # Quick pick table rows
    table_lines = [t["table_caption"], t["table_headers"]]
    for provider in providers:
        source = source_lookup.get(provider["source_id"], {})
        source_label = source.get(f"label_{locale}", provider["source_id"]).replace("DVB", "DVB")
        provider_label = provider.get(f"name_{locale}", provider["name_en"])
        files = ", ".join(f"`{name}`" for name in provider.get("files", [])) or "—"
        updated = provider.get("last_updated", "—")
        note = provider.get(f"note_{locale}", "")
        origin = provider.get("origin", "")
        if origin:
            marker = footnote_map.get(origin)
            if marker:
                note = f"{note} [^{marker}]" if note else f"[^{marker}]"
        table_lines.append(f"| {source_label} | {provider_label} | {files} | {updated} | {note} |\n")
    table_lines.append("\n")
    table_lines.append(f"{t['satellite_hint']}\n\n")
    table_lines.append(f"{t['quick_hint']}\n\n")

    # Generated profiles table (as before)
    generated_caption = t["profiles_caption"]

    def category_heading(key: str) -> str:
        labels = {
            "sat": {"en": "Satellite profiles", "de": "Satellit-Profile"},
            "cable": {"en": "Cable profiles", "de": "Kabel-Profile"},
            "terrestrial": {"en": "Terrestrial profiles", "de": "Terrestrik-Profile"},
            "sat-cable": {"en": "Satellite + cable mixes", "de": "Satellit/Kabel-Mixe"},
            "sat-terrestrial": {"en": "Satellite + terrestrial mixes", "de": "Satellit/Terrestrik-Mixe"},
            "cable-terrestrial": {"en": "Cable + terrestrial mixes", "de": "Kabel/Terrestrik-Mixe"},
        }
        base = key.replace("-", "/").title()
        return labels.get(key, {}).get(locale, base)

    entries_by_category: dict[str, list[tuple[str, str, str, str]]] = {}
    if generated_root.exists():
        for category_dir in sorted(generated_root.iterdir()):
            if not category_dir.is_dir():
                continue
            category = category_dir.name
            for source_dir in sorted(category_dir.iterdir()):
                if not source_dir.is_dir():
                    continue
                for provider_dir in sorted(source_dir.iterdir()):
                    if not provider_dir.is_dir():
                        continue
                    for profile_dir in sorted(provider_dir.iterdir()):
                        if not profile_dir.is_dir():
                            continue
                        rel = profile_dir.relative_to(generated_root).as_posix()
                        entries_by_category.setdefault(category, []).append(
                            (source_dir.name, provider_dir.name, profile_dir, rel)
                        )

    generated_lines: list[str] = []
    if entries_by_category:
        for category in sorted(entries_by_category):
            generated_lines.append(f"### {category_heading(category)}\n")
            generated_lines.append(t["profiles_table_headers"])
            for source, provider, profile_path, rel in sorted(
                entries_by_category[category], key=lambda item: (item[0], item[1], item[3])
            ):
                satellites = profile_path / "satellites.xml"
                if satellites.exists():
                    link = satellites.relative_to(generated_root).as_posix()
                    rel_display = f"[satellites.xml]({link})"
                else:
                    rel_display = f"`{rel}`"
                generated_lines.append(f"| `{source}` | `{provider}` | {rel_display} |\n")
            generated_lines.append("\n")
    else:
        fallback = {
            "en": "No generated profiles available.\n",
            "de": "Keine generierten Profile verfügbar.\n",
        }[locale]
        generated_lines.append(fallback)

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

    # Footnotes section
    footnote_lines: list[str] = []
    if footnotes:
        footnote_lines.append(f"{t['footnotes_caption']}")
        for index, origin in enumerate(footnotes, start=1):
            footnote_lines.append(f"[^{index}]: {origin}\n")
        footnote_lines.append("\n")

    sections = [
        t["title"],
        t["intro"],
        *tldr_lines,
        *download_lines,
        *release_lines,
        *table_lines,
        generated_caption,
        *generated_lines,
        t["howto_caption"],
        t["howto_body"],
        *footnote_lines,
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

    metadata_root = Path(__file__).resolve().parent.parent / "app" / "data"
    sources = json.loads((metadata_root / "sources.json").read_text(encoding="utf-8"))
    providers = json.loads((metadata_root / "providers.json").read_text(encoding="utf-8"))

    readme_en = build_readme(release_date, bundles, generated_root, "en", sources, providers)
    readme_de = build_readme(release_date, bundles, generated_root, "de", sources, providers)

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
