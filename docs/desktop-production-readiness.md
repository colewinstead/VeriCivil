# Production desktop readiness

Assessment: October 27, 2026. This is a plan, not a claim that production distribution is implemented.

## Implementation status for v1.7.0

The implementation branch adds Windows NSIS/Mac installer packaging, manual/automatic release discovery, signed-build download/restart controls, free desktop access, native `.vericivil` files and recent projects, single-instance file opening, local recovery, bounded diagnostic logs, `/downloads`, and a credential-gated production signing workflow. The shared engine and browser subscription behavior are unchanged.

Signing credentials are not configured. Unsigned builds do not install updates automatically and do not publish update feeds. Production signing/notarization, real signed-update authenticity checks, and signed installed-app upgrade acceptance on all targets remain release gates. Windows CI also exercises unsigned install/upgrade/uninstall data preservation. The priorities below remain the acceptance checklist; code presence alone does not complete those external gates.

SignPath preparation: the pending-status [Code signing policy](https://vericivil.com/code-signing) is linked from the website/downloads and release notes; the protected manual **Windows SignPath Review** workflow is prepared but requires approved SignPath configuration before use. It signs only review copies of the outer installer and standalone app executable, without publication or update feeds. See [onboarding and production gates](signpath-onboarding.md). [AASHTO clearance steps and an unsent permissions request](aashto-permission-request.md) remain separate from signing approval.

## Existing foundation

The Electron edition already has the shared React interface and Python calculation engine, a bundled offline Pyodide runtime, VeriCivil icons, native save dialogs, atomic file writes, an unsaved-close confirmation, and isolated renderer/IPC boundaries. CI builds Windows x64, Apple Silicon, and Intel Mac previews and exercises offline calculations and exports. Keep these foundations and the engineering results unchanged.

At the baseline, distribution was a portable Windows ZIP and Mac DMGs without an updater, persistent native support log, or production desktop licensing. The implementation status above records the changes; desktop access remains free by the owner's decision. Existing browser account/billing services do not license a desktop installation.

## Work in priority order

| Priority | Gap | Required behavior and acceptance |
| --- | --- | --- |
| 1 | Installed application and stable identity | Produce a Windows installer with shortcuts and uninstall support; keep a Mac installation flow and add the archive required by the chosen updater. Set stable app IDs, publisher, architecture, and installation paths before the first production release. Verify clean install, upgrade, and uninstall with project files preserved. |
| 1 | Signing and release trust | Sign the Windows app/installer. Sign, notarize, and staple Mac distribution artifacts. Protect signing credentials outside the repo and PR jobs. Verify signatures and notarization in the production release pipeline. Existing private Windows signing work is a starting point; confirm it covers Electron artifacts. |
| 1 | Update delivery and application UI | Add automatic checks, a manual Check for Updates action, release notes, download/progress/error states, and a restart-to-install prompt. Publish platform/architecture-specific metadata and artifacts only after release validation. Verify update authenticity, keep offline startup working, retain the working installation after download failures, and defer restart until unsaved work is handled. |
| 2 | Production access and licensing | Decide whether desktop is free, paid, or shares the web subscription. For paid/shared access, replace the preview Pro bypass with verified desktop entitlements; define offline access, expiry/grace periods, sign-out, and device policy. Reuse existing account/billing services where applicable. Keep credentials out of project files and the renderer. |
| 2 | Recovery and native project workflow | Add crash recovery/autosave and test restoring work after a forced exit. Add recent projects, file association/open-from-Explorer-or-Finder handling, and a deliberate single/multiple-instance policy. Reuse project schemas and save validation; recover the saved inputs/results without silently recalculating them under newer criteria. |
| 2 | Support and runtime resilience | Add persistent native logs, actionable startup/worker errors, and an exportable diagnostic bundle with app/engine versions. Exclude project/LandXML contents and credentials by default. Offer consent before uploading any diagnostics. Test renderer/worker failure and restart behavior. |
| 1, throughout | Installed-app acceptance | Keep calculation/export parity and IPC/security tests. Also test the installed app upgrading from version N to N+1 on each supported target, failed/interrupted updates, offline launch, unsaved projects during update/restart, invalid signatures, and wrong-architecture artifacts. Manually verify native dialogs, first launch, Gatekeeper/Windows behavior, and common display sizes. |

## Recommended first milestone

Deliver one complete Windows installation and update cycle before adding more desktop features. Keep the current renderer and runtime build; add the supported installer/update packaging around it. Forge was the first candidate because it builds on `@electron/packager`. The implementation selects pinned electron-builder/electron-updater instead for NSIS installation, download progress, Windows update signature verification, and direct GitHub Release delivery. Existing packager-based previews remain available during migration.

The milestone is complete when a user can install a signed Windows build, save a project, receive a newer version, choose when to restart, and reopen that project after the upgrade. Test cancellation, interrupted downloads, offline operation, and preservation of user data. A notification linking to a download is a useful intermediate step, but does not complete automatic updating.

Then bring signed/notarized Mac builds through the same upgrade tests. If production access is paid, licensing is also a launch requirement; if it is free, remove the evaluation bypass and clearly define the supported free features instead. Avoid adding account/device machinery until that commercial decision is made.

## Important implementation constraints

- Electron's macOS updater requires a signed app. A DMG/portable ZIP and download checksums alone are not an installed-app update system; the selected updater also needs its own supported packages and release metadata.
- Keep release/auth/update network access in the native main process behind a narrow bridge and trusted endpoints. Do not remove the renderer's existing outbound-request restrictions to implement an updater.
- Keep app identity and supported OS/architecture requirements explicit. Preserve user projects and preferences across upgrades, and keep a documented manual reinstall/recovery path if installation fails.
- Gate publication on all applicable checks. PR builds stay unpublished previews without production signing credentials. Stable releases need complete, validated update artifacts before clients can discover the new version.
- The remaining private engineering-source comparisons and real ORD acceptance checks retain their existing limitations; desktop packaging does not resolve them.

## Evidence and official references

Repository evidence: `desktop/main.cjs`, `desktop/preload.cjs`, `desktop/launch.cjs`, `desktop/files.cjs`, `web/desktop/package.mjs`, `web/desktop/build.mjs`, `web/app/CalculatorApp.tsx`, `desktop/tests/offline-smoke.cjs`, and `.github/workflows/release.yml`.

- [Electron application updates](https://www.electronjs.org/docs/latest/tutorial/updates): update packages, feeds, and release metadata.
- [Electron autoUpdater](https://www.electronjs.org/docs/latest/api/auto-updater): platform requirements and macOS signing requirement.
- [Electron signing and notarization](https://www.electronjs.org/docs/latest/tutorial/code-signing): distribution trust and signing workflows.
- [GitHub squash merge configuration](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/configuring-commit-squashing-for-pull-requests): repository merge-method controls.
