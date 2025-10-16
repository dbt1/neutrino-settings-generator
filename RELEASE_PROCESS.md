# Release Process / Release-Prozess

## English

The release workflow is fully automated via [release-please](https://github.com/google-github-actions/release-please-action). Follow this sequence to ship a new version:

1. **Merge pull requests with Conventional Commits.** The commit history on `main` drives SemVer bumps.
2. **Wait for the release-please PR.** For each change on `main`, the `Release` workflow opens/updates a PR named `chore(main): release vX.Y.Z` containing:
   - Version bump in `pyproject.toml`
   - Changelog entry in `CHANGELOG.md`
   - Git tag proposal (`vX.Y.Z`)
3. **Review and merge the release PR.** Ensure the generated notes match expectations and the SemVer increment is correct.
4. **Release automation triggers.** After the PR merges:
   - The action creates tag `vX.Y.Z`
   - A GitHub Release is published with the changelog body
   - Build artefacts from `CI` remain available; consider attaching wheels if needed (future enhancement).
5. **Monitor the `Release` workflow.** Confirm it completes successfully. Failures typically stem from insufficient permissions or missing secrets.

### Hotfix Procedure

- For urgent fixes, branch from the latest tag (e.g., `git checkout -b fix/critical v1.2.3`), apply the patch, commit with `fix:` (or `fix!:` if breaking), and merge back into `main`.
- release-please recalculates the bump (patch for `fix`, major for `fix!`, minor for `feat`).
- Avoid manually editing version numbers or the changelog.

### Publishing Artefacts

- Wheels and source distributions are produced by `make build` and `CI`.
- Container images can be published to GHCR in a follow-up (see `OPERATIONS.md` for optional steps).

## Deutsch

Der Release-Prozess wird vollständig durch [release-please](https://github.com/google-github-actions/release-please-action) automatisiert. Die Schritte:

1. **Pull Requests mit Conventional Commits mergen.** Die Historie auf `main` bestimmt den SemVer-Bump.
2. **Auf den release-please-PR warten.** Für jede Änderung auf `main` erstellt/aktualisiert der Workflow `Release` einen PR namens `chore(main): release vX.Y.Z` mit:
   - Versionsanhebung in `pyproject.toml`
   - Changelog-Eintrag in `CHANGELOG.md`
   - Vorgeschlagenem Git-Tag (`vX.Y.Z`)
3. **PR prüfen und mergen.** Notizen gegenprüfen und sicherstellen, dass der SemVer-Sprung korrekt ist.
4. **Automatisierte Freigabe.** Nach dem Merge:
   - Tag `vX.Y.Z` wird erstellt
   - GitHub Release mit Changelog-Text wird veröffentlicht
   - Build-Artefakte aus `CI` stehen bereit; Anhängen der Wheels ist optional (später).
5. **Workflow beobachten.** Der `Release`-Workflow muss erfolgreich enden. Fehler deuten meist auf Berechtigungs- oder Secret-Probleme hin.

### Hotfix-Prozess

- Für dringende Fixes von der letzten Version abzweigen (`git checkout -b fix/kritisch v1.2.3`), Patch anwenden, mit `fix:` (oder `fix!:` bei Breaking Changes) committen und zurück nach `main` mergen.
- release-please berechnet den Versionssprung neu (`fix` → Patch, `fix!` → Major, `feat` → Minor).
- Versionsnummern und Changelog niemals manuell anfassen.

### Artefakt-Veröffentlichung

- Wheels und Source-Distributions entstehen via `make build` und `CI`.
- Container-Images können perspektivisch in die GHCR gepusht werden (optional, siehe `OPERATIONS.md`).
