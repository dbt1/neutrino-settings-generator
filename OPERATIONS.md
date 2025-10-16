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

1. Cron schedule `0 2 * * *` (02:00 UTC) performs ingest → convert → zip.
2. Artefacts are uploaded via `actions/upload-artifact`.
3. Optional publish: extend workflow with a deployment step pushing artefacts into `neutrino-settings`. Use the stored secret and document the destination path (`releases/YYYY-MM-DD/`).
4. Checksum file (`sha256sum`) is generated per release folder.

### Monitoring & Alerts

- Enable GitHub Actions notifications (email or Slack integration) for failures.
- Inspect logs under `Actions → workflow → job` for details.
- Consider adding status badges in the README (future task).

### Quotas & Limits

- **Runner minutes:** standard GitHub quota applies; conversions are CPU/light IO bound.
- **Storage:** artefact retention defaults to 90 days. Clean up manually if required.
- **Network:** ingestion may hit upstream rate limits; caching via `--cache` reduces impact.

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

1. Cron-Zeitplan `0 2 * * *` (02:00 UTC) führt ingest → convert → zip aus.
2. Artefakte werden per `actions/upload-artifact` hochgeladen.
3. Optionale Veröffentlichung: Workflow um einen Deploy-Schritt erweitern, der Artefakte nach `neutrino-settings` pusht. Secret nutzen und Zielpfad (`releases/YYYY-MM-DD/`) dokumentieren.
4. Für jeden Releasetag wird eine `sha256sum`-Datei erstellt.

### Monitoring & Alerts

- GitHub-Actions-Benachrichtigungen (E-Mail oder Slack) bei Fehlern aktivieren.
- Logs unter `Actions → Workflow → Job` prüfen.
- README-Status-Badges können optional nachgerüstet werden.

### Quoten & Limits

- **Runner-Minuten:** Standard-GitHub-Kontingent; Konvertierungen sind CPU-/I/O-light.
- **Storage:** Artefakte werden 90 Tage vorgehalten. Bei Bedarf manuell bereinigen.
- **Netzwerk:** Ingest kann Upstream-Limits erreichen; Caching via `--cache` mindert Last.

### Disaster Recovery

- PAT/Deploy Keys bei Kompromittierung neu generieren.
- `Sync and Build` manuell starten, um Artefakte erneut zu erzeugen.
- Dank Versions-Tags genügt `git checkout vX.Y.Z && make build`, um Builds reproduzierbar wiederherzustellen.
