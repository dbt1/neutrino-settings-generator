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
make smoke         # Schneller Fixture-Test
make qa            # Vollständige Pipeline (benötigt offizielle Quellen)
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

- Erzeugt Neutrino-XML-Strukturen exakt gemäß Golden-Fixtures.
- Transport-Ausgaben lassen sich via `--no-sat/--no-cable/--no-terrestrial` deaktivieren.
- Namens-Mappings lädt `--name-map` (JSON/YAML).
- `--strict` macht Warnungen kritisch; `--abort-on-empty` bricht bei unterschrittenen Mindest-Senderzahlen pro Empfangsweg ab.
- Mindestwerte über `--min-services-sat`, `--min-services-cable`, `--min-services-terrestrial` (Standard: 50/20/20) justieren.

### `ingest`

```bash
e2neutrino ingest \
  --config examples/sources.example.yml \
  --out work/ingest \
  --cache /tmp/e2n-cache
```

- Lädt Beispielquellen über Adapter in `e2neutrino/adapters/`.
- Die Standard-Konfiguration verweist auf lokale Fixtures (`samples/`, `tests/fixtures/`), damit CI ohne Netzwerkzugriff funktioniert. Für den Produktivbetrieb die Einträge entsprechend austauschen, bevor Nightly-Syncs aktiviert werden.
- Normalisiert Daten zu Enigma2-Profilen, die anschließend konvertiert werden.

Beide Befehle unterstützen `--verbose` (Root-Option) für detailliertes Logging.

## Deterministische Builds & Tests

- **Golden-Tests:** `tests/test_golden_output.py` prüft byte-genaue XML-Ausgabe. Fixtures bewusst über `make convert-sample` aktualisieren.
- **Fixture-Abdeckung:** Beinhaltet Beispiel-Lamedb, Bouquets, DVB-SI-Dumps sowie Name-Map-Beispiele.
- **Quality Gates:** `ruff` (Lint/Format), `pytest` (Unit/Integration). `mypy` ist optional und über die dev-Abhängigkeiten bereits verfügbar.
- **Reproduzierbarkeit:** Fest definierte Abhängigkeiten (`pyproject.toml`, `requirements.txt`) und ein Multi-Stage-Dockerfile erzeugen konsistente Wheels.

## Qualitätssicherungspipeline

- `make smoke` führt einen schnellen Funktionstest gegen die mitgelieferten Fixtures aus.
- `make qa` durchläuft Ingest → Konvertierung → Validierung. Pro Profil entstehen `qa_report.md`, aktualisierte `BUILDINFO.json`
  (mit Provenienz, Zählwerten, Schwellwerten) sowie harte Checks gegen Duplikate und leere Ergebnisse (`--strict`, `--abort-on-empty`).
- CI und Nightly-Workflows veröffentlichen aggregierte QA-Artefakte (`qa-report`) und schlagen fehl, sobald Mindestanforderungen
  verfehlt werden.
- Vor der Freigabe die jeweiligen `qa_report.md` prüfen: Sie enthalten Senderstatistiken, Hinweise auf veraltete Quellen sowie
  eine Übersicht der entfernten Duplikate.

### Bouquets gezielt steuern

Die Kategorisierung erfolgt datengetrieben und kann ohne Codeänderung erweitert werden. Relevante Dateien:

- `e2neutrino/data/bouquet_category_patterns.json`
  - Schlüsselwort → Kategorie-Zuordnung (z. B. alle ServusTV-Sender in „Austria“).
  - Beispiel:
    ```json
    {
      "Mein Paket": ["mein sender", "mein netzwerk"]
    }
    ```
- `e2neutrino/data/paytv_networks.json`
  - Deklariert PayTV-Operatoren inklusive Land/Auflösung. Daraus entstehen Bouquets à la `PayTV – Sky – DE – HD`.
- `e2neutrino/data/provider_categories.json`
  - Weist Provider-Bezeichnungen einer Kategorie zu, falls der Sendername allein nicht ausreicht.
- `e2neutrino/data/radio_category_patterns.json`
  - Entsprechende Regeln für Radiobouquets (`Radio - News`, `Radio - Music`, …).

Der Konverter

1. matched Sendernamen/Provider gegen `CATEGORY_PATTERNS` bzw. Overrides,
2. ergänzt PayTV- und Provider-Bouquets für TV-Dienste,
3. erkennt Auflösungen (`Resolution - UHD/HD/SD`) über Namens-Muster oder optionale `extra["resolution"]`-Metadaten,
4. baut Radiobouquets anhand der Radio-Pattern (Fallback: ein Gesamtbouquet `Radio`).

> Tipp: Eigene JSON-Erweiterungen versionieren oder paketieren, damit automatisierte Pipelines stets denselben Stand verwenden.

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
   - `ENV_GLOBAL`: Fine-Grained PAT (`contents:write`) mit Push-Rechten auf `dbt1/neutrino-settings`.
3. **Workflows prüfen:** Im Tab **Actions** sollten `CI`, `Release`, `Sync and Build` sichtbar sein.
4. **CI testen:** Commit pushen oder PR öffnen → `CI` läuft automatisch und liefert Fast-Fail-Feedback.
5. **Release manuell (optional):** **Actions → Release → Run workflow**. Nach Merge des release-please-PRs entsteht Tag `vX.Y.Z`, ein GitHub-Release sowie ein aktualisiertes `CHANGELOG.md`.
6. **Nightly Sync:** Auf den Cron um 02:00 UTC warten oder **Run workflow** auf `Sync and Build` auslösen. Artefakte herunterladen und Checksums prüfen.

Troubleshooting:
- Workflows fehlen → Liegen die Dateien in `.github/workflows/` auf `master`?
- Release erzeugt nichts → Besitzt das Secret `contents: write` und ist der Workflow erfolgreich durchgelaufen?
- Build schlägt fehl → Logs öffnen (`Actions → Run → Job → Step`) und Lint/Test-Fehler lokal via `make lint test` beheben.

Die englische Anleitung befindet sich in `README.en.md`.

## Fehlersuche

- **Warum sind meine Listen leer?** Prüfen, ob (1) die Quelle erreichbar ist (`git`/`http`-Adapter nutzen ETag-Caching und Host-Allowlists),
  (2) `lamedb` oder `lamedb5` vorhanden und fehlerfrei lesbar sind, (3) Bouquets nach der Deduplizierung noch Einträge besitzen und (4)
  die Mindestschwellen erfüllt werden. Erneut mit `--verbose` ausführen und die erzeugte `qa_report.md` heranziehen.
- **Stale-Warnung (`stale: true` in den Metadaten)** → Der Abrufzeitpunkt überschreitet standardmäßig 120 Tage. Quelle aktualisieren oder – nur für
  Tests – mit `--include-stale` ausführen.
- **Duplikate gemeldet** → Die Vorschau in `qa_report.md` zeigt, welche Variante behalten wurde. Prioritäten der Quellen ggf. anpassen.

## Repository-Aufbau

```
.github/workflows/  # CI/CD, Release, Nightly Sync
e2neutrino/         # Paket-Code & Adapter
tests/              # Pytest-Suite inkl. Golden-Fixtures
samples/            # Beispiel-Enigma2-Profil
examples/           # Quellen- und Name-Map-Beispiele
scripts/            # Helfer-Skripte (Packaging, Tooling)
Dockerfile          # Multi-Stage-Builder/Runtime-Image
Makefile            # Entwickler-Tasks
pyproject.toml      # PEP-621-Metadaten & Abhängigkeiten
requirements.txt    # Fixierte Laufzeit- und Tool-Abhängigkeiten
```

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
- Veröffentlichungsleitfaden: `docs/PUBLISHING.md`
- Offizielle Sender-Referenzen:
  - DVB-T2 HD Regionen: https://www.dvb-t2hd.de/regionen
  - ASTRA 19,2°E Übersicht: https://astra.de/tv-radio-mehr/senderuebersicht
  - ARD-Digital Empfangsparameter: https://www.ard-digital.de/empfang/fernsehen-per-satellit/contentblocks/empfangsparameter-hd
  - HD+ Senderangebot: https://www.hd-plus.de/themen/sender
  - Vodafone Kabel-Angebot: https://www.vodafone.de/privat/fernsehen/sender.html
  - PŸUR Senderliste: https://www.pyur.com/privat/fernsehen/senderliste
  - MagentaTV Senderlisten: https://www.telekom.de/hilfe/geraete/magenta-tv/senderlisten-downloads
  - waipu.tv Sender: https://www.waipu.tv/sender/
  - Zattoo Programm: https://zattoo.com/de/sender
  - DAB+ Radio: https://www.dabplus.de/sender/
- Security-Policy: `SECURITY.md`
- Issue-Templates: `.github/ISSUE_TEMPLATE/`
- Änderungsverlauf: `CHANGELOG.md` (verwaltet durch `release-please`)

## Lizenz

Veröffentlicht unter der MIT-Lizenz. Details siehe `LICENSE`.
