# Neutrino Settings Releases / Veröffentlichungen

English 🇬🇧 / Deutsch 🇩🇪

## Purpose / Zweck
- Host generated Neutrino (Zapit) channel lists produced by the `e2neutrino` converter.
- Provide per-source bundles (`<source_id>-<profile_id>/`) plus daily aggregated zips under `releases/<YYYY-MM-DD>/`.
- Offer deterministic settings for DVB-S/S2, DVB-C, DVB-T/T2 receivers running Neutrino.

## Structure / Struktur
```
neutrino-settings/
├─ README.md
├─ releases/
│  └─ YYYY-MM-DD/
│     ├─ <source_id>-<profile_id>.zip
│     ├─ all-sources.zip
│     └─ checksums.txt
└─ <source_id>-<profile_id>/
   ├─ services.xml
   ├─ bouquets.xml
   ├─ BUILDINFO.json
   ├─ sat/<Name>/...
   ├─ cable/<Provider>/...
   └─ terrestrial/<Region>/...
```

## Usage / Anwendung
1. Download the desired zip bundle (per source or `all-sources.zip`).
2. Extract and copy to your Neutrino box (e.g. `/var/tuxbox/zapit/`).
3. Restart zapit or reboot the receiver.

`BUILDINFO.json` contains provenance information (source commit/ETag, display names, API version) for auditability.

## Updates / Aktualisierung
- Nightly GitHub Action (`sync-and-build.yml`) ingests upstream Enigma2 settings, converts them, and pushes updates here.
- Manual trigger via workflow dispatch is possible when new official lists are published.

## License / Lizenz
- Generated settings inherit licensing from upstream sources (see `BUILDINFO.json`).
- Repository metadata and tooling are released under MIT (see converter project).
