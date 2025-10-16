# e2neutrino – Enigma2-zu-Neutrino Konvertierungs-Toolkit

`e2neutrino` wandelt deterministische Enigma2-Einstellungen in reproduzierbare Neutrino-(Zapit)-Bundles um. Das Projekt liefert ein installierbares Python-Paket mit produktionsreifer CLI, Docker-Image sowie CI/CD-Automatisierung – ausgerichtet auf nächtliche Synchronisationen und versionierte Releases.

- **Kernfunktionen:** reproduzierbare Konvertierungen, Golden-File-Tests, Multi-Source-Ingest (Datei, Git, HTTP), Kombination-Pakete, konfigurierbare Namensschemata und deterministische Ausgaben für Ziel-Repositories wie `neutrino-settings`.
- **Zielgruppe:** Release-Ingenieur:innen und Operator:innen, die offizielle Enigma2-Listen einlesen, kuratierte Zapit-Layouts bauen und als signierte Artefakte ausliefern möchten.

> ℹ️ Eine englische Einführung befindet sich in `README.en.md`. Betriebs-, Release- und Security-Guides enthalten jeweils englische und deutsche Abschnitte.

## Schnellstart

```bash
git clone https://github.com/example/neutrino-settings-generator.git
cd neutrino-settings-generator/converter
make init          # Erstellt .venv, installiert festgenagelte Toolchain, editable package
make lint test     # Fast-Fail: ruff → pytest
make build         # Wheel + sdist via python -m build erzeugen
```

### Beispielprofil konvertieren

```bash
make convert-sample
tree out/sample
```

Die Ausgabe umfasst `services.xml`, `bouquets.xml`, Transport-spezifische Ordner (`sat/`, `cable/`, `terrestrial/`), Kombinationen sowie `BUILDINFO.json`.

### Docker-Runtime

```bash
docker build -t e2neutrino:latest .
docker run --rm -v "$(pwd)/out:/out" e2neutrino:latest --help
```

## Installation

### Von PyPI (nach Veröffentlichung)

```bash
pip install e2neutrino
e2neutrino --help
```

### Aus dem Quellcode (editable)

```bash
make init
```

Das Target `init` installiert festgeschriebene Abhängigkeiten (`requirements.txt`) und linkt das Paket mit `--no-deps`, um die Lock-Datei zu respektieren.

### Hinweise zur virtuellen Umgebung

- Erfordert Python ≥ 3.10.
- Abhängigkeiten sind per SemVer festgelegt und sorgen für reproduzierbare Builds. Aktualisierungen erfolgen bewusst (Lock anpassen, Changelog ergänzen).

## CLI-Überblick

### `convert`

```bash
e2neutrino convert \
  --input samples/enigma2_profile_example \
  --output build/out \
  --api-version 4 \
  --include-types S,C,T \
  --name-scheme human \
  --combinations "Astra19.2E+Hotbird13.0E" \
  --fail-on-warn
```

- Erzeugt Neutrino-XML-Strukturen exakt gemäß Golden-Fixtures.
- Transport-Ausgaben lassen sich via `--no-sat/--no-cable/--no-terrestrial` deaktivieren.
- Namens-Mappings lädt `--name-map` (JSON/YAML).

### `ingest`

```bash
e2neutrino ingest \
  --config examples/sources.example.yml \
  --out work/ingest \
  --cache /tmp/e2n-cache
```

- Lädt Upstream-Quellen (git/http/file) über Adapter in `e2neutrino/adapters/`.
- Normalisiert Daten zu Enigma2-Profilen, die anschließend konvertiert werden.

Beide Befehle unterstützen `--verbose` (Root-Option) für detailliertes Logging.

## Deterministische Builds & Tests

- **Golden-Tests:** `tests/test_golden_output.py` prüft byte-genaue XML-Ausgabe. Fixtures bewusst über `make convert-sample` aktualisieren.
- **Fixture-Abdeckung:** Beinhaltet Beispiel-Lamedb, Bouquets, DVB-SI-Dumps sowie Name-Map-Beispiele.
- **Quality Gates:** `ruff` (Lint/Format), `pytest` (Unit/Integration). `mypy` ist optional und über die dev-Abhängigkeiten bereits verfügbar.
- **Reproduzierbarkeit:** Fest definierte Abhängigkeiten (`pyproject.toml`, `requirements.txt`) und ein Multi-Stage-Dockerfile erzeugen konsistente Wheels.

## CI/CD-Pipelines

| Workflow | Auslöser | Zweck |
|----------|----------|-------|
| `CI` | `push`, `pull_request` | Fast-Fail: Lint → Tests → Build |
| `Release` | Push auf `main`, manueller Dispatch | `release-please` führt SemVer-Bumps, Tags, GitHub-Release und `CHANGELOG.md` Updates durch |
| `Sync and Build` | Nächtlicher Cron (`0 2 * * *`), manueller Dispatch | Quellen einlesen, Profile konvertieren, Artefakte zippen, Checksums erzeugen |

Details stehen in `.github/workflows/*.yml`. Nächtliche Artefakte lassen sich per Deploy Key oder PAT in das Repository `neutrino-settings` ausliefern (siehe `OPERATIONS.md`).

## GitHub-Workflows aktivieren (Einsteiger:innen)

1. **Actions freischalten:** `Settings → Actions → General → Allow all actions and reusable workflows`.
2. **Secrets anlegen (bei Publish):** `Settings → Secrets and variables → Actions → New repository secret`.
   - `PAT_PUSH_NEUTRINO_SETTINGS`: Fine-Grained PAT (`contents:write`) mit Push-Rechten auf `dbt1/neutrino-settings`.
3. **Workflows prüfen:** Im Tab **Actions** sollten `CI`, `Release`, `Sync and Build` sichtbar sein.
4. **CI testen:** Commit pushen oder PR öffnen → `CI` läuft automatisch und liefert Fast-Fail-Feedback.
5. **Release manuell (optional):** **Actions → Release → Run workflow**. Nach Merge des release-please-PRs entsteht Tag `vX.Y.Z`, ein GitHub-Release sowie ein aktualisiertes `CHANGELOG.md`.
6. **Nightly Sync:** Auf den Cron um 02:00 UTC warten oder **Run workflow** auf `Sync and Build` auslösen. Artefakte herunterladen und Checksums prüfen.

Troubleshooting:
- Workflows fehlen → Liegen die Dateien in `.github/workflows/` auf `main`?
- Release erzeugt nichts → Besitzt das Secret `contents: write` und ist der Workflow erfolgreich durchgelaufen?
- Build schlägt fehl → Logs öffnen (`Actions → Run → Job → Step`) und Lint/Test-Fehler lokal via `make lint test` beheben.

Die englische Anleitung befindet sich in `README.en.md`.

## Repository-Aufbau

```
converter/
  e2neutrino/         # Paket-Code & Adapter
  tests/              # Pytest-Suite inkl. Golden-Fixtures
  samples/            # Beispiel-Enigma2-Profil
  examples/           # Quellen- und Name-Map-Beispiele
  .github/workflows/  # CI/CD, Release, Nightly Sync
  Dockerfile          # Multi-Stage-Builder/Runtime-Image
  Makefile            # Entwickler-Tasks
  pyproject.toml      # PEP-621-Metadaten & Abhängigkeiten
```

Das Schwesterverzeichnis `neutrino-settings/` dient als Ziel für nächtliche Artefakt-Publikationen (ZIPs, Checksums).

### Ziel-Repository-Struktur

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

Der Nightly-Workflow hält den Baum `generated/` synchron zu den aktuellsten Ergebnissen und legt datierte ZIP-Bundles samt Checksums in `releases/` ab.

## Weitere Dokumentation

- Beitragende: `CONTRIBUTING.md`
- Release-Ablauf: `RELEASE_PROCESS.md`
- Operations-Handbuch: `OPERATIONS.md`
- Security-Policy: `SECURITY.md`
- Issue-Templates: `.github/ISSUE_TEMPLATE/`
- Änderungsverlauf: `CHANGELOG.md` (verwaltet durch `release-please`)

## Lizenz

Veröffentlicht unter der MIT-Lizenz. Details siehe `LICENSE`.
