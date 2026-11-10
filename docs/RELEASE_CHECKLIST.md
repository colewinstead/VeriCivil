# Release Checklist

This checklist applies to every paid-pilot build. Record the operator, date, commit SHA, application version, calculation-engine version, Windows image, and evidence location. A checked box without retained evidence is not validation.

Start each candidate with a private workspace created outside the repository using `python scripts/create_pilot_evidence_bundle.py --output <private-directory>`. Complete `docs/templates/PRIVATE_PE_VALIDATION_RECORD.md` and `docs/templates/PILOT_ACCEPTANCE_RECORD.md` in that private workspace. Follow `docs/PILOT_OPERATIONS.md`. Keep legal review records and attorney communications outside the public repository. Generated records begin unapproved.

## Release authorization

- [ ] Commercial license/EULA and pilot support terms are approved for the intended recipients.
- [ ] Third-party build and runtime licensing, including the current Inno Setup commercial-license guidance, has been reviewed and recorded.
- [ ] A qualified roadway engineer has approved the criteria/source traceability matrix and golden calculations for every enabled calculation path.
- [ ] Known limitations, supported inputs, and required independent checks are accepted by the pilot owner.
- [ ] `app_info.py` contains the intended semantic application version and calculation-engine version.
- [ ] Release notes identify calculation-impacting changes separately from application-only changes.

## Source and automated verification

- [ ] Worktree and commit SHA are recorded; release source is immutable and reviewable.
- [ ] `python -m unittest -v` passes without skipped, removed, or weakened tests.
- [ ] Dependency versions and security advisories are reviewed.
- [ ] No customer data, credentials, signing keys, Bentley files, or confidential fixtures are present in the repository or build context.

## Windows build and distribution

Current public desktop releases are free, unsigned Windows x64 builds. Code signing work and all Mac desktop builds are paused. Paid-pilot authorization above remains separate from public release packaging.

- [ ] Retain the Windows x64 Full Release artifacts for the intended commit and both editions.
- [ ] Confirm EXE ProductVersion/FileVersion matches `app_info.py`.
- [ ] Verify the downloaded SHA-256 checksums and label the app and installer unsigned. Do not claim publisher verification.
- [ ] Scan release artifacts using the organization's approved malware controls.
- [ ] Install, upgrade, and uninstall using a standard Windows account; verify project/recovery preservation and edition coexistence.
- [ ] Confirm Windows Defender/SmartScreen behavior and unknown-publisher prompts are documented accurately.
- [ ] Verify user-approved update downloads/restarts and the correct unsigned feed for each edition. Portable previews require manual replacement.

No Apple or signing workflow runs in the active release process. Existing Mac packages remain historical downloads; resuming Mac distribution requires separate platform acceptance.

## Built-application acceptance

- [ ] Launch the installed executable and confirm the displayed version.
- [ ] Run approved golden manual calculations and compare every numeric result and warning.
- [ ] Load sanitized LandXML covering lines/arcs, units, and station equations; verify names, stationing, radii, and direction.
- [ ] Confirm spiral LandXML produces the documented DXF block/warning and is not treated as supported geometry.
- [ ] Export PDF and verify version, engine, criteria warning, pagination, values, and legibility.
- [ ] Export ORD CSV and complete a real OpenRoads round trip; verify lanes, point types, station regions, slopes, and pivots.
- [ ] Export DXF and verify coordinates, units, levels/layers, text style, rotation, and placement in the target DGN.
- [ ] Save/reload a new project and approved v1/v2 compatibility fixtures; compare calculations and metadata.
- [ ] Force one failure for each file workflow and confirm the message, rotating log, and Open Log Folder action.

## Browser build acceptance

- [ ] Run `npm ci`, `npm exec tsc -- --noEmit`, and `npm test` from `web`; retain the Pyodide parity output.
- [ ] Open the production build on desktop and mobile-width browsers; verify calculation, project open/save, LandXML replacement warning, lookup, and all exports.
- [ ] Confirm the browser network log shows no project/LandXML upload or calculation API calls.
- [ ] Open one schema-v5 project in the browser and verify calculations, explicit reverse-curve pairs, embedded LandXML integrity, metadata, and export results.
- [ ] Publish the exact validated commit and verify the public URL before announcing it.

## Delivery and support

- [ ] Publish immutable, versioned browser and checksum assets with release notes. Publish Windows installers, portable previews, and update feeds only after their platform acceptance checks pass. Do not add new Mac artifacts while builds are paused.
- [ ] Verify downloaded hashes on a clean Windows machine and record that the current artifacts are unsigned.
- [ ] Launch the current desktop release with GitHub available and unavailable; confirm the update check stays silent, then test a mocked older build and confirm its download points to the correct Windows asset and edition.
- [ ] Provide installation, onboarding, limitations, privacy/log-sharing, backup, update, and rollback instructions.
- [ ] Record the 3–5 authorized pilot users, their application versions, and the support contact.
- [ ] Retain the prior validated Windows installer for rollback; do not silently auto-update pilot machines.
- [ ] Archive test output, golden comparisons, screenshots, signatures, hashes, release notes, and approval records.
- [ ] Generate a no-project-file diagnostic bundle and verify any explicitly selected application log is redacted before support transmission.
- [ ] Confirm release, engineering acceptance, pilot operations, and legal approval owners signed the private acceptance record.
