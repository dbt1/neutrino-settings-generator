# Publishing Settings to `neutrino-settings`

This guide explains how to update the downstream repository with fresh zapit files.
Deutsch folgt unterhalb.

## English – Local Workflow

1. **Prepare repositories**
   - `neutrino-settings-generator`: working tree clean.
   - `neutrino-settings`: fresh clone tracking `origin/master`.
2. **Populate artefacts**
   ```bash
   PATH=.venv/bin:$PATH make qa
   .venv/bin/python scripts/package_outputs.py out ../neutrino-settings
   .venv/bin/python scripts/generate_target_readme.py ../neutrino-settings ../neutrino-settings
   ```
3. **Review & commit** in `../neutrino-settings`:
   ```bash
   cd ../neutrino-settings
   git status
   git add generated releases README.md README.de.md
   git commit -m "chore: publish <YYYY-MM-DD> neutrino settings"
   git push origin master
   ```
4. **Clean up**: keep this clone only for publishing – do not edit files manually.

### Automating via GitHub Actions

The workflow `ci/nightly-settings` performs the same steps with the latest `make qa` output. Inspect the run log for warnings; demo fixtures are automatically ignored.

## Deutsch – Lokaler Ablauf

1. **Repos vorbereiten**
   - `neutrino-settings-generator`: Arbeitsbaum sauber.
   - `neutrino-settings`: frischer Clone auf `origin/master`.
2. **Artefakte erzeugen**
   ```bash
   PATH=.venv/bin:$PATH make qa
   .venv/bin/python scripts/package_outputs.py out ../neutrino-settings
   .venv/bin/python scripts/generate_target_readme.py ../neutrino-settings ../neutrino-settings
   ```
3. **Prüfen & committen** in `../neutrino-settings`:
   ```bash
   cd ../neutrino-settings
   git status
   git add generated releases README.md README.de.md
   git commit -m "chore: publish <YYYY-MM-DD> neutrino settings"
   git push origin master
   ```
4. **Hinweis**: Dieses Repo nur zum Beliefern nutzen, keine manuellen Änderungen vornehmen.

### Automatisierung per GitHub Actions

Der Workflow `ci/nightly-settings` führt denselben Ablauf täglich durch. Warnungen im Log prüfen; Demo-Datensätze werden automatisch übersprungen.
