# Desktop release readiness

Status: November 9, 2026. Current desktop work focuses on unsigned Windows x64 installers and portable previews. Code signing work and all Mac desktop builds are paused. Existing Apple packaging code and any local signing identities are retained for possible future work; they are not evidence of a signed or notarized release.

## Active release scope

The Full Release workflow builds both existing Windows editions and the browser archive. PRs produce review artifacts; publication runs from validated main source. Windows CI exercises offline calculations and exports plus install, synthetic N-to-N+1 upgrade, uninstall, edition coexistence, and project/recovery preservation. The legacy Tkinter Windows build remains manual-only. Apple, signed-desktop, and provider-review workflows have been removed.

The shared React interface, Python engineering engine, formulas, criteria, project schemas, and exports stay shared. Desktop access remains free without accounts or device licensing. Calculations run locally with the bundled offline runtime. Native saves, recovery snapshots, recent projects, and bounded diagnostic exports remain available.

## Windows acceptance priorities

- Verify clean installation, Start menu launch, upgrade, and uninstall on the supported Windows x64 test PC; retain evidence that project and recovery files survive.
- Verify user-approved update download and restart, unsaved-work protection, offline operation, interrupted downloads, and a working manual reinstall/rollback path. Synthetic CI upgrades and a real published-version upgrade are separate evidence.
- Keep the two editions' identities, profiles, filenames, and unsigned update feeds separate. Portable previews require manual replacement.
- Preserve calculation/export parity and renderer/IPC security checks. Engineering acceptance, real OpenRoads validation, and [AASHTO redistribution clearance](aashto-permission-request.md) remain separate requirements.
- Label unsigned downloads clearly. Windows updates use HTTPS and SHA-512 checksums without publisher-signature verification. Windows may show unknown-publisher or SmartScreen warnings; checksums do not establish publisher identity.

Signing is not an acceptance gate for the active unsigned release channel. Dormant signing helpers and signature checks must not be weakened or silently used to describe an unsigned artifact as signed. Reintroducing signing or Mac releases requires an explicit scope change and platform acceptance.

## Distribution and evidence

See the [desktop guide](../desktop/README.md), [download guide](RELEASE_ASSETS.md), and public [code signing policy](https://vericivil.com/code-signing). Website deployment remains a separate Ship main operation after the matching GitHub Release succeeds. Older releases retain historical Mac downloads; current website buttons offer Windows only.

Repository evidence: `.github/workflows/release.yml`, `desktop/main.cjs`, `desktop/updates.cjs`, `desktop/tests/`, and `scripts/test_windows_installer.ps1`. Code presence does not prove that an installed release passed manual acceptance.
