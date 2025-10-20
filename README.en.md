# e2neutrino – Enigma2 to Neutrino Conversion Toolkit

The `e2neutrino` project converts deterministic Enigma2 settings exports into reproducible Neutrino (Zapit) channel bundles. It ships as an installable Python package with a production-ready CLI, Docker image, and CI/CD automation oriented towards nightly synchronisation and versioned releases.

- **Key capabilities:** reproducible conversions, golden-file verification, multi-source ingest (file, git, http), combination bundles, configurable naming schemes, and deterministic outputs consumable by target repositories such as `neutrino-settings`.
- **Audience:** release engineers and operators who need to ingest official Enigma2 channel lists, prepare curated Zapit layouts, and ship them as signed artefacts.

> ℹ️ A German-language introduction is provided in `README.de.md`. Operational, release, and security guides offer both English and German sections.

## Quick Start

```bash
git clone https://github.com/example/neutrino-settings-generator.git
cd neutrino-settings-generator/converter
make init          # creates .venv, installs pinned toolchain, editable package
make lint test     # fast-fail: ruff → pytest
make build         # produce wheel + sdist via python -m build
make smoke         # quick validation against bundled fixtures
make qa            # full ingest → convert → validate (requires official sources)
```

### Convert a Sample Profile

```bash
make convert-sample
tree out/sample
```

Outputs include `services.xml`, `bouquets.xml`, per-delivery splits (`sat/`, `cable/`, `terrestrial/`), combination bundles, and `BUILDINFO.json`.

### Docker Runtime

```bash
docker build -t e2neutrino:latest .
docker run --rm -v "$(pwd)/out:/out" e2neutrino:latest --help
```

## Installation

### From PyPI (after publication)

```bash
pip install e2neutrino
e2neutrino --help
```

### From Source (editable)

```bash
make init
```

The `init` target installs pinned dependencies (`requirements.txt`) and links the package in editable mode with `--no-deps` to preserve the lock.

### Virtual Environment Notes

- Python ≥ 3.10 is required.
- Dependencies are pinned (SemVer) to guarantee reproducible builds. Update via `make lock` (future task) or manual edits, then adjust the changelog.

## CLI Overview

### `convert`

```bash
e2neutrino convert \
  --input samples/enigma2_profile_example \
  --output build/out \
  --api-version 4 \
  --strict \
  --abort-on-empty \
  --min-services-sat 50 \
  --min-services-cable 20 \
  --min-services-terrestrial 20 \
  --include-types S,C,T \
  --name-scheme human \
  --combinations "Astra19.2E+Hotbird13.0E" \
  --fail-on-warn
```

- Generates Neutrino XML structures exactly matching golden fixtures.
- Toggle dedicated delivery outputs with `--no-sat/--no-cable/--no-terrestrial`.
- Provide YAML/JSON overrides through `--name-map`.
- `--strict` upgrades warnings to hard failures; `--abort-on-empty` enforces minimum service thresholds per delivery path.
- Tune thresholds using `--min-services-sat`, `--min-services-cable`, and `--min-services-terrestrial` (defaults: 50/20/20).

### `ingest`

```bash
e2neutrino ingest \
  --config examples/sources.example.yml \
  --out work/ingest \
  --cache /tmp/e2n-cache
```

- Fetches sample sources using adapters in `e2neutrino/adapters/`.
- The default configuration references local fixtures (`samples/`, `tests/fixtures/`) so CI can run offline; replace entries with production sources before enabling nightly syncs or committing secrets.
- Normalises data into Enigma2-like profiles for subsequent conversion.

Both commands honour `--verbose` on the root group for debug logging.

## Deterministic Builds & Testing

- **Golden tests:** `tests/test_golden_output.py` asserts byte-identical XML output. Update fixtures intentionally via `make convert-sample`.
- **Fixture coverage:** sample lamedb, bouquets, DVB-SI dumps, and name-map examples ensure wide coverage.
- **Quality gates:** `ruff` (lint/format), `pytest` (unit/integration). Optional `mypy` can be enabled via `pip install mypy` (already in dev extras).
- **Reproducibility:** pinned dependencies (`pyproject.toml`, `requirements.txt`) and multi-stage Docker image ensure consistent wheels.

## Quality Assurance Pipeline

- Run `make smoke` for a quick local validation against bundled fixtures.
- Run `make qa` to execute the full ingestion → conversion → validation chain. It generates
  per-profile `qa_report.md` files, refreshed `BUILDINFO.json` (with provenance, counts, thresholds), and enforces
  duplicate- and emptiness-checks via `--strict` and `--abort-on-empty`.
- CI and nightly workflows publish aggregated QA artefacts (`qa-report` archive) and fail early when thresholds are not met.
- Inspect `qa_report.md` for each profile to review service counts, stale-source detection, and deduplication summaries before promoting artefacts.

### Customising Bouquet Categories

Bouquet generation relies on several data-driven lookups. You can extend or override the defaults without touching code:

- `e2neutrino/data/bouquet_category_patterns.json`
  - Adds keyword → category mappings (e.g. grouping all “ServusTV” entries into an “Austria” bouquet).
  - Example:
    ```json
    {
      "My Network": ["my network", "mychannel"]
    }
    ```
- `e2neutrino/data/paytv_networks.json`
  - Declares pay-TV operators per country/resolution. Each entry creates a bouquet name like `PayTV – Sky – DE – HD`.
- `e2neutrino/data/provider_categories.json`
  - Maps provider strings to a bouquet category (useful when the service name itself does not contain the brand).
- `e2neutrino/data/radio_category_patterns.json`
  - Mirrors the TV patterns for radio bouquets (e.g. `Radio - News`, `Radio - Music`).

During conversion the engine

1. Matches service names/providers against `CATEGORY_PATTERNS` + overrides.
2. Applies pay-TV and provider mappings for TV services.
3. Detects `Resolution - UHD/HD/SD` via name keywords (`UHD`, `4K`, `HD`, `SD`) or optional `service.extra["resolution"]` metadata.
4. Builds radio bouquets using the radio patterns (fallback: a single `Radio` bouquet).

> Tip: keep custom JSON files under version control or ship them via packages so that automated pipelines pick them up consistently.

## CI/CD Pipelines

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `CI` | `push`, `pull_request` | Fast-fail lint → test → build |
| `Release` | `push` to `main`, manual dispatch | `release-please` drives SemVer bumps, tags, GitHub Releases, and `CHANGELOG.md` |
| `Sync and Build` | Nightly cron (`0 2 * * *`), manual dispatch | Ingest upstream sources, convert all profiles, zip outputs with checksums, publish artefacts |

See `.github/workflows/*.yml` for full definitions. Nightly artefacts can be published to the `neutrino-settings` repository via deploy key or PAT (documented in `OPERATIONS.md`).

## Enable GitHub Workflows (Beginner Friendly)

1. **Allow Actions:** `Settings → Actions → General → Allow all actions and reusable workflows`.
2. **Provide Secrets (if publishing):** `Settings → Secrets and variables → Actions → New repository secret`.
   - `ENV_GLOBAL`: fine-grained PAT (`contents:write`) that can push to `dbt1/neutrino-settings`.
3. **Verify Workflows:** Open the **Actions** tab and ensure `CI`, `Release`, and `Sync and Build` are listed.
4. **Test CI:** Push any branch or open a PR; the `CI` workflow should run automatically and report fast-fail status.
5. **Manual Release (optional):** From **Actions → Release → Run workflow**. When the release-please PR is merged, it will tag `vX.Y.Z`, update `CHANGELOG.md`, and create a GitHub Release.
6. **Nightly Sync:** Wait for the 02:00 UTC cron or trigger **Run workflow** on `Sync and Build`. Download artefacts and verify checksums.

Troubleshooting tips:
- Workflows missing → confirm files reside in `.github/workflows/` on the `master` branch.
- Releases not created → ensure the PAT/deploy key has `contents: write` scope and that the `Release` workflow completed.
- Build failures → inspect logs (`Actions → run → job → step`). Fix lint/test failures locally using `make lint test`.

German guidance is mirrored in `README.de.md`.

## Troubleshooting

- **Why are my lists empty?** Verify that (1) the upstream source is reachable (`git`/`http` adapters honour ETag caching and host allowlists),
  (2) `lamedb` or `lamedb5` files exist and parse without errors, (3) bouquets reference actual services after deduplication, and (4) the
  minimum thresholds are met. Re-run with `--verbose` to inspect per-stage counts and consult the generated `qa_report.md`.
- **Stale source warning (`stale: true` in metadata)** → the fetched timestamp exceeded the default 120-day window. Either refresh the upstream
  data or re-run with `--include-stale` (not recommended for releases).
- **Duplicate service identities reported** → review the deduplication preview inside `qa_report.md` and adjust source priorities if the incorrect
  variant was selected.

## Repository Layout

```
.github/workflows/  # CI/CD, release, nightly sync
e2neutrino/         # Package code & adapters
tests/              # Pytest suite with golden fixtures
samples/            # Example Enigma2 profile
examples/           # Sources and name-map examples
scripts/            # Helper scripts (packaging, tooling)
Dockerfile          # Multi-stage builder/runtime image
Makefile            # Local developer ergonomics
pyproject.toml      # PEP 621 metadata + dependencies
requirements.txt    # Locked tooling/runtime deps
```

### Target Repository Structure

```
neutrino-settings/
  generated/
    <source_id>/
      <profile_id>/
        services.xml
        bouquets.xml
        BUILDINFO.json
        sat/...
        cable/...
        terrestrial/...
  releases/
    YYYY-MM-DD/
      <source_id>-<profile_id>.zip
      all-sources.zip
      checksums.txt
      RELEASEINFO.json
```

The nightly workflow keeps the `generated/` tree in sync with the latest conversion outputs and writes dated ZIP bundles plus checksums into `releases/`. The separate `neutrino-settings` repository receives these updates.

## Links & Further Reading

- Contribution guidelines: `CONTRIBUTING.md`
- Release SOP: `RELEASE_PROCESS.md`
- Operations handbook: `OPERATIONS.md`
- Publishing guide: `docs/PUBLISHING.md`
- Official channel references:
  - DVB-T2 HD regions: https://www.dvb-t2hd.de/regionen
  - ASTRA 19.2°E overview: https://astra.de/tv-radio-mehr/senderuebersicht
  - ARD Digital parameters: https://www.ard-digital.de/empfang/fernsehen-per-satellit/contentblocks/empfangsparameter-hd
  - HD+ satellite lineup: https://www.hd-plus.de/themen/sender
  - Vodafone cable lineup: https://www.vodafone.de/privat/fernsehen/sender.html
  - PŸUR channel list: https://www.pyur.com/privat/fernsehen/senderliste
  - MagentaTV channel downloads: https://www.telekom.de/hilfe/geraete/magenta-tv/senderlisten-downloads
  - waipu.tv channels: https://www.waipu.tv/sender/
  - Zattoo lineup: https://zattoo.com/de/sender
  - DAB+ radio: https://www.dabplus.de/sender/
- Security policy: `SECURITY.md`
- Issue templates: `.github/ISSUE_TEMPLATE/`
- Change history: `CHANGELOG.md` (managed by `release-please`)

## License

Licensed under the MIT License. Refer to `LICENSE` for details.
