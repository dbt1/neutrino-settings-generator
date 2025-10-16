# Security Policy / Sicherheitsrichtlinie

## English

We take security seriously and welcome responsible disclosures.

### Supported Versions

- **Released tags (`vX.Y.Z`)**: receive security fixes.
- **Unreleased branches**: best effort support; fix via rebase onto `main`.

### Reporting a Vulnerability

1. Email `security@example.com` with the subject `e2neutrino vulnerability`.
2. Provide detailed reproduction steps, impact assessment, and suggested remediation if available.
3. Allow at least 14 days for initial acknowledgement and triage.

Please avoid creating public issues or pull requests before the team responds. We coordinate embargo timelines as needed and credit reporters unless anonymity is requested.

### Security Hardening Checklist

- Keep dependencies pinned (`pyproject.toml`, `requirements.txt`).
- Validate upstream sources in ingest configs (license allowlist, HTTPS URLs).
- Run CI regularly; ensure `Sync and Build` uses cached sources to detect drifts.

## Deutsch

Wir nehmen Sicherheit ernst und freuen uns über verantwortungsvolle Meldungen.

### Unterstützte Versionen

- **Veröffentlichte Tags (`vX.Y.Z`)**: erhalten Sicherheitsfixes.
- **Unveröffentlichte Branches**: Best-Effort, Bugfix via Rebase auf `main`.

### Meldung einer Schwachstelle

1. E-Mail an `security@example.com` mit Betreff `e2neutrino vulnerability`.
2. Detailierte Reproduktionsschritte, Impact-Einschätzung und ggf. Fix-Vorschläge beilegen.
3. Bitte 14 Tage für erste Rückmeldung und Triage einplanen.

Vor einer Antwort keine öffentlichen Issues oder Pull Requests erstellen. Embargos stimmen wir bei Bedarf ab; Nennung der meldenden Person erfolgt nur mit Zustimmung.

### Hardening-Checkliste

- Abhängigkeiten bleiben festgeschrieben (`pyproject.toml`, `requirements.txt`).
- Upstream-Quellen in Ingest-Konfigurationen prüfen (Lizenz-Whitelist, HTTPS).
- CI regelmäßig ausführen; `Sync and Build` nutzt Cache, um Abweichungen zu erkennen.
