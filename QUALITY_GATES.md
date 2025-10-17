# Quality Gates / Qualitätsgrenzen

## English

This document explains the hard validation rules enforced by the `e2neutrino` pipeline.

### Thresholds

- **Minimum services:** defaults `SAT ≥ 50`, `Cable ≥ 20`, `Terrestrial ≥ 20`. Configurable via
  `--min-services-sat`, `--min-services-cable`, and `--min-services-terrestrial`.
- **Empty outputs:** `--abort-on-empty` (default in CI) aborts the conversion when thresholds are not met.
- **Strict mode:** `--strict` upgrades warnings to fatal errors and guarantees that `qa_report.md` is only emitted for
  successful profiles.

### Duplicate handling

- Services are identified by SHA-1 of `(onid, tsid, sid, namespace, service_type)` and deduplicated automatically.
- Deduplication previews (`qa_report.md`) show which variants were kept/dropped. Adjust source priorities in
  `examples/sources.official.yml` if necessary.
- Remaining duplicates cause `validate.assert_no_dupes` to raise a `ValidationError`.

### Staleness

- Sources older than `stale_after_days` (default 120) trigger a hard failure unless `--include-stale` is set.
- `SOURCE_PROVENANCE.json`, `source.lock`, and `BUILDINFO.json` store timestamps and commit/ETag metadata.

### Overrides & Local runs

- Developers may run `e2neutrino convert ... --allow-empty --strict/--no-strict` locally, but CI and nightly workflows
  always enforce `--strict --abort-on-empty` with default thresholds.
- To diagnose failures, inspect `qa_report.md`, enable `--verbose`, or reduce thresholds temporarily (never commit the
  relaxed values).

## Deutsch

Dieses Dokument beschreibt die harten Validierungsregeln der `e2neutrino`-Pipeline.

### Schwellwerte

- **Minimale Senderzahlen:** Standard `SAT ≥ 50`, `Kabel ≥ 20`, `Terrestrisch ≥ 20`. Anpassbar über
  `--min-services-sat`, `--min-services-cable`, `--min-services-terrestrial`.
- **Leere Ausgaben:** `--abort-on-empty` (Standard in CI) bricht die Konvertierung bei Unterschreitung der Grenzen ab.
- **Strikter Modus:** `--strict` behandelt Warnungen als Fehler und stellt sicher, dass `qa_report.md` nur bei erfolgreichen
  Profilen erzeugt wird.

### Duplikate

- Dienste werden über den SHA-1 von `(onid, tsid, sid, namespace, service_type)` identifiziert und automatisch dedupliziert.
- `qa_report.md` zeigt, welche Varianten behalten/verworfen wurden. Bei Bedarf Prioritäten in
  `examples/sources.official.yml` anpassen.
- Verbleibende Duplikate führen in `validate.assert_no_dupes` zu einem `ValidationError`.

### Veraltete Quellen

- Daten, die älter als `stale_after_days` (Standard 120) sind, verursachen ohne `--include-stale` einen Abbruch.
- `SOURCE_PROVENANCE.json`, `source.lock` und `BUILDINFO.json` enthalten Zeitstempel sowie Commit-/ETag-Metadaten.

### Überschreibungen & lokale Läufe

- Lokal dürfen die Schalter `--allow-empty` bzw. `--no-strict` genutzt werden, um zu debuggen. In CI/Nightlies gelten jedoch
  dauerhaft `--strict --abort-on-empty` mit den Standard-Schwellwerten.
- Bei Fehlern `qa_report.md` prüfen, `--verbose` aktivieren oder Schwellwerte testweise senken (Änderungen nicht einchecken).
