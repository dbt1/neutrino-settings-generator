# e2neutrino – Enigma2 ➜ Neutrino Converter / Konverter

English 🇬🇧 / Deutsch 🇩🇪 – key passages appear in both languages.

## Overview / Überblick
- **Goal / Ziel:** Automate ingestion of official Enigma2 settings and convert them into deterministic Neutrino (Zapit) profiles (services.xml & bouquets.xml).
- **Pipeline:** `ingest` gathers upstream sources (git/http/file) → adapters normalise data → `convert` exports Zapit layouts incl. satellite/provider/region splits.
- **Use cases / Einsatz:** CI/CD generation of Neutrino settings, reproducible builds, provider overlays, nightly syncs for target repo `neutrino-settings`.

## Quick Start / Schnellstart
```bash
# Create and activate virtualenv / Virtuelle Umgebung
python -m venv .venv
source .venv/bin/activate

# Install package with dev extras / Installation inkl. Dev-Abhängigkeiten
pip install -e ".[dev]"

# Run tests & lint / Tests und Linting
make lint test
```

### Convert a profile / Profil konvertieren
```bash
e2neutrino convert \
  --input samples/enigma2_profile_example \
  --output build/out \
  --api-version 4 \
  --name-scheme human \
  --combinations "Astra-19.2E+Hotbird-13.0E"
```
- Generates `services.xml`, `bouquets.xml`, plus `sat/`, `cable/`, `terrestrial/` subfolders and combination bundles.
- Deterministic ordering; warnings optionally fail builds via `--fail-on-warn`.

### Ingest upstream sources / Quellen einlesen
```bash
e2neutrino ingest \
  --config examples/sources.example.yml \
  --out work/ingest \
  --cache .cache/e2n
```
- Fetches *official* channel lists via Git/HTTP/File adapters, caches ETag/Last-Modified, verifies allowlists (see config), then writes normalised Enigma2-like folders under `work/ingest/<source>/<profile>/enigma2/`.

## Repository Layout / Struktur
- `e2neutrino/`: core package with adapters for Enigma2, Neutrino legacy XML, DVB-SI dumps, M3U, JSON APIs.
- `tests/`: pytest suite with golden files ensuring byte-identical XML output.
- `examples/`: sample configuration including name maps (Sat/Provider/Region).
- `.github/workflows/`: CI (`ci.yml`) and nightly sync (`sync-and-build.yml`).
- `neutrino-settings/`: target repo staging area to be published by CI (see below).

## Key Features / Zentrale Funktionen
- **Multi-source ingestion / Multi-Quellen-Ingest:** Adapters for git/http/file, optional caching, license allowlists.
- **Deterministic output / Deterministische Ausgabe:** Sorted XML, golden-file tests, reproducible builds.
- **Transport splits / Aufteilung nach Übertragungsweg:** Always emits `sat/`, `cable/`, `terrestrial/` (toggle via CLI).
- **Combination bundles / Kombinationen:** Create Astra/Hotbird etc. combos via `--combinations`.
- **Name mapping / Namens-Mapping:** `--name-map` allows JSON/YAML overrides for satellite, cable providers, terrestrial regions (examples provided).
- **Validation / Validierung:** Sanity checks for duplicate services, missing transponders; warnings can abort builds.

## CI/CD Integration
- `make docker-build`: Builds multi-stage image (`base` for testing, `runtime` minimal).
- GitHub Actions:
  - `ci.yml`: Lint (ruff), type-check (mypy), pytest, build wheel/sdist artefacts.
  - `sync-and-build.yml`: Nightly/Manual workflow to ingest sources, convert per profile, zip and push artefacts to sibling repo `neutrino-settings`.
- Deployment uses PAT or deploy key; configure `NEUTRINO_SETTINGS_DEPLOY_KEY` or `NEUTRINO_SETTINGS_TOKEN` secrets in GitHub.

## Target Repo Layout / Ziel-Repo-Struktur (`neutrino-settings/`)
```
neutrino-settings/
├─ README.md
├─ releases/YYYY-MM-DD/
│  ├─ <source_id>.zip
│  └─ checksums.txt
└─ <source_id>/
   ├─ services.xml
   ├─ bouquets.xml
   ├─ BUILDINFO.json
   ├─ sat/<Name>/...
   ├─ cable/<Provider>/...
   └─ terrestrial/<Region>/...
```
- `BUILDINFO.json` includes source metadata (commit/ETag), display names, API version.
- Copy desired folder to Neutrino boxes (`/var/tuxbox/zapit/` etc.), restart zapit.

## Development Notes / Hinweise
- `ruff` handles linting/formatting; `mypy` ensures type hygiene.
- Golden tests will fail on accidental XML reordering – update fixtures intentionally via `make update-golden`.
- Keep code comments bilingual where clarification is needed; docstrings follow EN/DE pattern.

## License
MIT – see [LICENSE](LICENSE). / MIT-Lizenz, siehe [LICENSE](LICENSE).
