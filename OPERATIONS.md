# Operations Handbook / Operations-Handbuch

## English

This guide summarises the operational duties required to run `e2neutrino` in production.

### Environments

- **GitHub Actions:** primary execution environment. All workflows run on `ubuntu-latest` runners with Python 3.11.
- **Docker:** multi-stage image builds wheels for reproducible deployments.
- **Target repository:** `neutrino-settings/` receives nightly artefacts (ZIP bundles + checksums).

### Secrets & Configuration

| Secret | Purpose | Notes |
|--------|---------|-------|
| `ENV_GLOBAL` | Write access to `dbt1/neutrino-settings` for publishing artefacts | Use a fine-grained PAT with `contents:write`; stored as repository secret |
| `GH_TOKEN` (optional) | Alternative token for release-please if repository-wide writes are restricted | Defaults to `GITHUB_TOKEN` when omitted |

Store secrets under `Settings → Secrets and variables → Actions`. Rotate tokens at least every 90 days.

### Nightly Sync (`Sync and Build` workflow)

1. Cron schedule `0 2 * * *` (02:00 UTC) executes the end-to-end QA pipeline via `make qa` (ingest → convert → validate).
2. Each conversion emits `qa_report.md`, refreshed `BUILDINFO.json`, and provenance metadata (`SOURCE_PROVENANCE.json`, `source.lock`).
3. The workflow aggregates all reports into a root-level `qa_report.md`. On failure a GitHub issue is opened automatically (`peter-evans/create-issue-from-file`).
4. When QA succeeds, artefacts are packaged (`scripts/package_outputs.py`) and uploaded through `actions/upload-artifact`.
5. Optional publish: add a deployment step that pushes bundles into `neutrino-settings` (target layout `releases/YYYY-MM-DD/`). Use the configured secret.
6. A `sha256sum` file is produced per release folder; descriptive package names remain configurable in `metadata/packages.yml`.

### Monitoring & Alerts

- Enable GitHub Actions notifications (email or Slack integration) for failures.
- Inspect logs under `Actions → workflow → job` for details.
- Consider adding status badges in the README (future task).

### Quotas & Limits

- **Runner minutes:** standard GitHub quota applies; conversions are CPU/light IO bound.
- **Storage:** artefact retention defaults to 90 days. Clean up manually if required.
- **Network:** ingestion honours ETag/Last-Modified caching and a host allowlist (`examples/sources.official.yml`). Per-source workdirs maintain negative-cache TTLs to avoid hammering upstreams.

### Disaster Recovery

- Regenerate PAT/deploy keys if compromised.
- Re-run `Sync and Build` manually to repopulate artefacts.
- For reproducibility, keep tagged releases; rebuild via `git checkout vX.Y.Z && make build`.

## Deutsch

Dieser Leitfaden fasst die operativen Aufgaben für den produktiven Betrieb von `e2neutrino` zusammen.

### Umgebungen

- **GitHub Actions:** Haupt-Ausführungsumgebung. Alle Workflows laufen auf `ubuntu-latest` mit Python 3.11.
- **Docker:** Multi-Stage-Image erzeugt reproduzierbare Wheels.
- **Ziel-Repository:** `neutrino-settings/` erhält nächtliche Artefakte (ZIP-Bundles + Checksums).

### Secrets & Konfiguration

| Secret | Zweck | Hinweise |
|--------|-------|----------|
| `ENV_GLOBAL` | Schreibrechte auf `dbt1/neutrino-settings` für die Artefakt-Publikation | Fine-Grained PAT mit `contents:write` als Repository-Secret hinterlegen |
| `GH_TOKEN` (optional) | Alternatives Token für release-please bei restriktiven Repos | Standardmäßig genügt `GITHUB_TOKEN` |

Secrets unter `Settings → Secrets and variables → Actions` speichern und mindestens alle 90 Tage rotieren.

### Nightly Sync (Workflow `Sync and Build`)

1. Cron-Trigger `0 2 * * *` (02:00 UTC) startet die QA-Pipeline via `make qa` (Ingest → Konvertierung → Validierung).
2. Jede Konvertierung erzeugt `qa_report.md`, aktualisierte `BUILDINFO.json` sowie Provenienzdateien (`SOURCE_PROVENANCE.json`, `source.lock`).
3. Alle Reports werden zu einer zentralen `qa_report.md` zusammengeführt; bei Fehlern eröffnet der Workflow automatisch ein GitHub-Issue (`peter-evans/create-issue-from-file`).
4. Bei erfolgreicher QA werden die Artefakte mit `scripts/package_outputs.py` gebündelt und per `actions/upload-artifact` bereitgestellt.
5. Optionale Veröffentlichung: Deployment-Schritt ergänzen, der Bundles nach `neutrino-settings` pusht (Zielstruktur `releases/YYYY-MM-DD/`).
6. Pro Release-Ordner entsteht eine `sha256sum`-Datei; sprechende Paketnamen bleiben über `metadata/packages.yml` konfigurierbar.

### Monitoring & Alerts

- GitHub-Actions-Benachrichtigungen (E-Mail oder Slack) bei Fehlern aktivieren.
- Logs unter `Actions → Workflow → Job` prüfen.
- README-Status-Badges können optional nachgerüstet werden.

### Quoten & Limits

- **Runner-Minuten:** Standard-GitHub-Kontingent; Konvertierungen sind CPU-/I/O-light.
- **Storage:** Artefakte werden 90 Tage vorgehalten. Bei Bedarf manuell bereinigen.
- **Netzwerk:** Ingest nutzt ETag/Last-Modified-Caching und eine Host-Allowlist (`examples/sources.official.yml`). Negative-Cache-TTLs verhindern unnötige Wiederholungen bei Fehlern.

### Disaster Recovery

- PAT/Deploy Keys bei Kompromittierung neu generieren.
- `Sync and Build` manuell starten, um Artefakte erneut zu erzeugen.
- Dank Versions-Tags genügt `git checkout vX.Y.Z && make build`, um Builds reproduzierbar wiederherzustellen.


## Vodafone DVB-C

Vodafone Germany does not publish an official DVB-C frequency table including MHz/Symbolrate/Modulation. The adapter `provider_vodafone_de` therefore remains blocked until an authorised source is available. QA/CI will raise a descriptive failure when the adapter is requested. For parser tests use official fixtures from other operators (e.g. wilhelm.tel) without rebranding them as Vodafone outputs.
