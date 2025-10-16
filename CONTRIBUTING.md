# Contributing / Beiträge leisten

## English

Thank you for supporting the `e2neutrino` toolchain. We aim for production-grade changes with deterministic results. Please follow the checklist below when opening pull requests.

### Ground Rules

- **Conventional Commits:** use `type(scope): message`. Supported types: `feat`, `fix`, `perf`, `docs`, `chore`, `ci`, `refactor`, `test`, `build`. Use `feat!`/`fix!` to signal breaking changes (major bump).
- **Tests first:** add or update pytest coverage and golden fixtures before modifying core functionality. Ensure outputs remain deterministic.
- **Type hints & style:** all new code must include type hints. Run `ruff check .` and `pytest -q` locally before pushing.
- **Documentation:** update both English and German guides when user-facing behaviour changes.

### Development Environment

```bash
make init          # create .venv, install pinned deps, editable package
source .venv/bin/activate
make lint test     # must pass before PR submission
```

Optional checks:

- `ruff format .` to auto-format.
- `mypy e2neutrino` to run optional static typing.
- `make build` to confirm package build success.

### Pull Request Workflow

1. Branch off `main`: `git checkout -b feat/my-feature`.
2. Keep commits scoped and conventional; squash merge in GitHub to maintain a clean history.
3. Ensure CI is green (lint → test → build). The `CI` workflow must succeed before merging.
4. Provide release notes in the PR description if behaviour changes (this feeds release-please).
5. Do not update `CHANGELOG.md` manually; release-please manages it.

### Updating Golden Fixtures

If legitimate output changes break golden tests:

```bash
make convert-sample
cp out/sample/services.xml tests/fixtures/golden/services.xml
cp out/sample/bouquets.xml tests/fixtures/golden/bouquets.xml
```

Explain why the update is required in the PR.

## Deutsch

Vielen Dank für deine Unterstützung der `e2neutrino`-Toolchain. Wir akzeptieren nur produktionsnahe Änderungen mit deterministischen Ergebnissen. Bitte beachte die folgende Checkliste für Pull Requests.

### Grundsätze

- **Conventional Commits:** Verwende `type(scope): message`. Zulässige Typen: `feat`, `fix`, `perf`, `docs`, `chore`, `ci`, `refactor`, `test`, `build`. Nutze `feat!`/`fix!` für Breaking Changes (Major-Version).
- **Tests zuerst:** Ergänze oder aktualisiere Pytest- und Golden-Fixture-Abdeckung vor Kernänderungen. Ergebnisse müssen deterministisch bleiben.
- **Type Hints & Stil:** Neue Funktionen benötigen Type Hints. Lokal `ruff check .` und `pytest -q` ausführen, bevor du pusht.
- **Dokumentation:** Benutzersichtbare Änderungen erfordern Updates in englischen und deutschen Guides.

### Entwicklungsumgebung

```bash
make init          # .venv erzeugen, festgelegte Abhängigkeiten installieren
source .venv/bin/activate
make lint test     # Muss vor dem PR bestehen
```

Optionale Prüfungen:

- `ruff format .` für Autoformatierung.
- `mypy e2neutrino` für den optionalen Typscheck.
- `make build` um den Paket-Build zu validieren.

### Pull-Request-Ablauf

1. Von `main` abzweigen: `git checkout -b feat/mein-feature`.
2. Commits thematisch fokussiert halten, im PR per Squash-Merge zusammenführen.
3. CI muss grün sein (Lint → Tests → Build). Der Workflow `CI` darf nicht fehlschlagen.
4. Beschreibe Verhaltensänderungen im PR-Text – `release-please` nutzt diese Informationen.
5. `CHANGELOG.md` niemals manuell anpassen; die Action verwaltet die Datei.

### Golden Fixtures aktualisieren

Sollten legitime Änderungen Golden-Tests betreffen:

```bash
make convert-sample
cp out/sample/services.xml tests/fixtures/golden/services.xml
cp out/sample/bouquets.xml tests/fixtures/golden/bouquets.xml
```

Im PR unbedingt begründen, weshalb die Anpassung notwendig ist.
