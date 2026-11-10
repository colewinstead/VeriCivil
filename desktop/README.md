# VeriCivil Electron desktop preview

This desktop entry point reuses `web/app/CalculatorApp.tsx` and the same Python modules as the browser and Tkinter editions. It bundles Pyodide, its nine required packages, and the pinned ReportLab/ezdxf wheels. Engineering processing runs locally without an internet connection. Formulas, criteria, project schemas, and export implementations are unchanged.

Current desktop tools are free without account sign-in or device licensing. The desktop app does not bill, collect analytics, or retain LandXML remotely. It stores recovery snapshots, recent-project paths, and bounded support logs locally. Unsigned Windows installers support updates with explicit download/restart approval. Portable Windows builds require manual replacement. Code signing work and all Mac desktop builds are paused; older Mac assets remain in release history.

For normal downloads, edition/platform choices, and an explanation of the GitHub release assets, see the [release download guide](../docs/RELEASE_ASSETS.md).

See the [production desktop readiness plan](../docs/desktop-production-readiness.md) for implementation status and remaining release acceptance.

## Build and run

Use the repository's supported Node/Python versions. Install the native Python requirements if running the parity checks. Dependency installation and the first desktop build require internet access; the resulting app does not.

```sh
npm --prefix web ci --ignore-scripts
node web/node_modules/electron/install.js
npm --prefix web run desktop:dev
```

`desktop:dev` builds and launches the packaged application source. The explicit Electron install step downloads the pinned runtime after npm installs dependencies without running package scripts. On this Mac, use a standard Node installation (for example the existing Homebrew Node), rather than the Node executable embedded in a signed application; the latter can reject native build bindings with a different-Team-ID error.

```sh
npm --prefix web run desktop:package:windows
# On Windows:
npm --prefix web run desktop:installer
```

The package command targets Windows x64, including from a Mac development host. Build and accept installers on Windows CI. Outputs are under `desktop/releases/`. Runtime downloads and generated application assets are ignored by Git. The runtime cache records dependency URLs and verified SHA-256 values in `desktop/runtime/checksums.json`. Repeated builds verify cached bytes before use.

`desktop:installer` builds an unsigned NSIS installer on Windows under `desktop/installers/`. The installer uses the stable identity `com.vericivil.superelevation`. Windows creates Start menu/desktop shortcuts and an uninstaller; upgrades and uninstall preserve user projects and the local profile. Local Windows Application Control can prevent NSIS from executing its unsigned build stub; use the clean Windows CI runner for acceptance rather than bypassing that policy.

## Neutral desktop edition

`desktop/editions.json` supplies build-time branding for the shared UI, Electron shell, and packaging. `DESKTOP_EDITION` accepts `vericivil` (the default) or `neutral`; unknown values fail the build. This is not an installer choice or an in-app preference. UI and calculation changes apply to both editions.

To build **Superelevation Calculator** without VeriCivil branding:

```sh
DESKTOP_EDITION=neutral npm --prefix web run desktop:dev
DESKTOP_EDITION=neutral npm --prefix web run desktop:package
DESKTOP_EDITION=neutral npm --prefix web run desktop:installer
DESKTOP_EDITION=neutral npm --prefix web run desktop:test:offline
python3 scripts/package_electron_release.py --platform win32 --arch x64 --edition neutral
python3 scripts/stage_desktop_installers.py --platform win32 --arch x64 --edition neutral
```

On Windows PowerShell, set `$env:DESKTOP_EDITION = 'neutral'` before the npm commands and use `python` for the Python commands. Clear that environment variable to return to the default edition. Each staging/archive command requires the corresponding package to have been built first. The neutral app stages under `desktop/app-neutral/`, preview packages under `desktop/releases/neutral/`, and installers under `desktop/installers/neutral/`.

The neutral installer has its own app identity, shortcuts, uninstaller, updater cache, and `Superelevation Calculator` profile directory under the OS application-data folder. It can coexist with VeriCivil without migrating or sharing recovery data. It opens existing `.json` and `.vericivil` projects, saves new projects as `.json`, and registers neither extension, leaving existing file associations alone. The neutral workspace omits the desktop promotional label and footer. Required ownership information stays in About and the bundled license; engineering verification guidance remains in About.

Both editions are built by the Windows x64 release job. Neutral installers/previews and separate checksums are public GitHub Release assets, but the website's download buttons ignore them. Windows neutral installers use `latest-neutral-unsigned-win32-x64.yml`, accept only matching neutral installer filenames, and still require approval before downloading or restarting. Portable apps check for matching neutral assets and require manual replacement. Missing neutral assets never fall back to a branded download. A public GitHub asset is unadvertised, not access-restricted.

Signing workflows are paused. Existing signed-build validation remains in the packaging code; requesting a signed neutral build fails explicitly. Regenerate the neutral geometric SE artwork with `python3 scripts/create_neutral_desktop_icons.py` (Pillow required).

## Projects, recovery, and support

New desktop projects use `.vericivil` (the existing JSON project format). Older `.json` projects still open. File → Open recent remembers ten paths; double-clicking a `.vericivil` file opens it in the existing application instance. Save updates the opened project; Save As chooses another destination. File validation and shared-engine schema checks run before accepting the opened project.

Dirty work is snapshotted locally every two seconds; a startup banner offers Restore work or Discard snapshot. A failed/unreadable recovery file is preserved until an explicit discard. Recovery does not replace a separate backup of saved projects. Updates refuse restart while work is unsaved, an operation is running, or recovery needs a decision.

On Windows, **Restart and install** applies the approved update silently in the existing installation and reopens the app. The first-install wizard still offers an installation location. Older installed versions retain their previous update behavior until this fix has been installed; that update may still require completing the wizard and reopening the app manually.

The profile is `%APPDATA%/VeriCivil Superelevation` on Windows and `~/Library/Application Support/VeriCivil Superelevation` on Mac. It contains recovery/project data and recent paths; do not include the profile in public reports. Help → Export diagnostics writes only versions, platform/architecture, and bounded event/error-code logs, excluding project contents, file paths, and credentials. No diagnostic upload is performed.

## Windows release status

Desktop releases target unsigned Windows x64 builds. Code signing work and Mac desktop builds are paused. The public [Code signing policy](https://vericivil.com/code-signing) describes the current status and desktop privacy. Provider onboarding and the protected signing workflows have been retired. Existing credential-backed packaging helpers and signature-verification code remain dormant; no signing credentials are needed for the active release pipeline.

Main releases publish separate `latest-unsigned-win32-x64.yml` and `latest-neutral-unsigned-win32-x64.yml` feeds. PR builds never publish releases. Windows installer updates use HTTPS and SHA-512 checksums without publisher-signature verification, so trust depends on the GitHub release account and delivery service. Users approve downloads and restarts. Windows may display unknown-publisher or SmartScreen warnings. Portable builds require manual replacement. Existing manual-only Windows builds need one manual upgrade to gain in-app installation.

Keep any existing signing identities outside the repository. Retaining dormant Apple packaging or local credentials does not mean current Mac releases are signed, notarized, or supported. Resuming either platform or signing requires a separate, validated change.

The Windows executable uses the VeriCivil icon, and the running window uses the same artwork. The portable ZIP itself keeps the operating system's archive icon; extract it to see the branded executable. Native icons in `desktop/icons/` come from `web/public/brand/vericivil-icon.png`. To regenerate them with Pillow installed, run from the repository root:

```sh
python -c "from PIL import Image; im = Image.open('web/public/brand/vericivil-icon.png'); im.save('desktop/icons/vericivil.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]); im.save('desktop/icons/vericivil.icns')"
```

To create a downloadable archive after packaging, run the matching command from the repository root:

```sh
python scripts/package_electron_release.py --platform win32 --arch x64
```

Windows ZIP creation can also run on a Mac using `python3`. Archives and matching SHA-256 files are written to `desktop/release-assets/`; filenames include the app version and target platform. The helper refuses missing packages and stale staged versions. A Windows ZIP contains the full portable application folder; extract it before launching the EXE.

## Automated builds and GitHub Releases

The **Full Release** workflow validates `APP_VERSION` before building Windows x64 Electron installers and portable previews (`windows-latest`). Opening, updating, reopening, or marking a version-bumped PR ready for review runs the builds, including on draft PRs. Documentation-only changes skip packaging, and invalid/reused versions stop before desktop jobs run.

The Windows runner installs the pinned Electron runtime, checks the save/security boundaries, packages the app, exercises the offline runtime against native Python, and creates its portable ZIP plus checksum. PR runs have read-only repository permissions and upload `desktop-release-<version>-<target>` Actions artifacts retained for 30 days. They do not publish a GitHub Release or use signing secrets.

After merge to `main`, desktop and browser builds run against the merged source. The public versioned GitHub Release is published only after all release build jobs succeed, and includes unsigned Windows installers and portable ZIPs for both editions, checksums, update feeds, and the browser archive. Windows CI installs version N, upgrades to a synthetic N+1, and uninstalls, checking that project and recovery data survive. The **Legacy Tkinter Windows Build** job remains a manual rollback build. Mac and signed-desktop workflows have been removed while that work is paused. Website publishing remains a separate `Ship main` operation.

## Interface and file handling

Curve inputs and Project & LandXML share a scrolling inspector beside the larger engineering review area. The application follows the system light/dark appearance. File → New/Open/Save uses the same React handlers as the toolbar. Native Save dialogs choose the destination for projects and PDF/CSV/DXF exports. Cancellation preserves the unsaved state; writes use a temporary file and rename so a failed write does not truncate an existing project. Each export is limited to 64 MiB.

The renderer is sandboxed, has context isolation enabled, and has no Node integration. The preload exposes only saving and menu events. Assets are served from a confined custom protocol; outbound HTTP/WebSocket requests, window navigation, and permissions are restricted. The native save handler validates the requesting frame, filename, type, and size. Standard input file pickers handle local imports.

## Checks

```sh
python3 -m unittest -v
npm --prefix web exec -- tsc --noEmit -p web/tsconfig.json
npm --prefix web run lint
npm --prefix web test
npm --prefix web run desktop:test
npm --prefix web run desktop:build
npm --prefix web run desktop:test:offline
```

On Windows use `python` instead of `python3`. The offline Electron test launches the real application and worker with outbound requests blocked in a disposable app profile, compares a calculation against native Python, exercises LandXML, PDF/ORD CSV/overlay DXF, and round-trips a project. The parent test runner enforces an exit timeout and cleans up the profile after Electron releases it. It also verifies isolated renderer globals, the native save bridge (including cancellation), laptop/wide layout bounds, and both system appearance palettes. Dialog destinations are stubbed inside the test. The Mac native Save dialog and its cancellation, plus the unsaved-close confirmation, were also checked interactively.

The Windows x64 package was built and copied to the LAN test PC in an isolated temporary directory. Its Electron executable and local Python runtime loaded; the remote test did not confirm a visible window. Windows visual and interactive acceptance remain unverified.

## Rollback and scope

The browser build remains its own entry point. `python3 super_app.py`, the PyInstaller specifications, and the manual legacy Windows workflow remain available. Unsigned Windows preview archives, installers, and update feeds use the normal release workflow. Mac packaging scripts remain in source for a future resumption; no workflow currently publishes Mac or signed desktop builds. Website publication still requires Ship main. Production licensing is intentionally deferred while desktop tools remain free.
