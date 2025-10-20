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

### Reference: Official Channel Lists

- DVB-T2 HD (Germany): https://www.dvb-t2hd.de/regionen
- ASTRA 19.2°E overview: https://astra.de/tv-radio-mehr/senderuebersicht
- ARD Digital parameters: https://www.ard-digital.de/empfang/fernsehen-per-satellit/contentblocks/empfangsparameter-hd
- HD+ satellite lineup: https://www.hd-plus.de/themen/sender
- Vodafone TV channel finder: https://www.vodafone.de/privat/fernsehen/sender.html
- PŸUR channel list: https://www.pyur.com/privat/fernsehen/senderliste
- MagentaTV channel downloads: https://www.telekom.de/hilfe/geraete/magenta-tv/senderlisten-downloads
- waipu.tv channels: https://www.waipu.tv/sender/
- Zattoo Germany lineup: https://zattoo.com/de/sender
- DAB+ digital radio: https://www.dabplus.de/sender/
- (Unofficial) KingOfSat ASTRA 19.2°E: https://de.kingofsat.net/pos-19.2E.php
- (Unofficial) LyngSat ASTRA 1KR/1L/1M/1N: https://www.lyngsat.com/Astra-1KR-1L-1M-1N.html

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

### Referenz: Offizielle Senderlisten

- DVB-T2 HD (Deutschland): https://www.dvb-t2hd.de/regionen
- ASTRA 19,2°E Übersicht: https://astra.de/tv-radio-mehr/senderuebersicht
- ARD Digital Empfangsparameter: https://www.ard-digital.de/empfang/fernsehen-per-satellit/contentblocks/empfangsparameter-hd
- HD+ Satellitenangebot: https://www.hd-plus.de/themen/sender
- Vodafone TV Sender: https://www.vodafone.de/privat/fernsehen/sender.html
- PŸUR Senderliste: https://www.pyur.com/privat/fernsehen/senderliste
- MagentaTV Senderlisten: https://www.telekom.de/hilfe/geraete/magenta-tv/senderlisten-downloads
- waipu.tv Sender: https://www.waipu.tv/sender/
- Zattoo Deutschland: https://zattoo.com/de/sender
- DAB+ Digitalradio: https://www.dabplus.de/sender/
- (Inoffiziell) KingOfSat ASTRA 19.2°E: https://de.kingofsat.net/pos-19.2E.php
- (Inoffiziell) LyngSat ASTRA 1KR/1L/1M/1N: https://www.lyngsat.com/Astra-1KR-1L-1M-1N.html
