# VeriCivil Electron desktop preview

This desktop entry point reuses `web/app/CalculatorApp.tsx` and the same Python modules as the browser and Tkinter editions. It bundles Pyodide, its nine required packages, and the pinned ReportLab/ezdxf wheels. Engineering processing runs locally without an internet connection. Formulas, criteria, project schemas, and export implementations are unchanged.

Current desktop tools are free without account sign-in or device licensing. The desktop app does not bill, collect analytics, or retain LandXML remotely. It stores recovery snapshots, recent-project paths, and bounded support logs locally. Unsigned builds can check for newer releases and open the download page, but cannot install updates automatically. Signed builds support verified updates with an explicit download/restart flow.

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
npm --prefix web run desktop:package
npm --prefix web run desktop:package:windows
npm --prefix web run desktop:installer
```

The first command packages the host platform: the current Mac architecture, or Windows x64 when run on Windows. The second packages Windows x64, including from a Mac. Outputs are under `desktop/releases/`. Runtime downloads and generated application assets are ignored by Git. The runtime cache records dependency URLs and verified SHA-256 values in `desktop/runtime/checksums.json`. Repeated builds verify cached bytes before use.

`desktop:installer` builds an unsigned NSIS installer on Windows, or DMG and update ZIP on Mac, under `desktop/installers/`. The installer uses the stable identity `com.vericivil.superelevation`. Windows creates Start menu/desktop shortcuts and an uninstaller; upgrades and uninstall preserve user projects and the local profile. Local Windows Application Control can prevent NSIS from executing its unsigned build stub; use the clean Windows CI runner for acceptance rather than bypassing that policy.

## Projects, recovery, and support

New desktop projects use `.vericivil` (the existing JSON project format). Older `.json` projects still open. File → Open recent remembers ten paths; double-clicking a `.vericivil` file opens it in the existing application instance. Save updates the opened project; Save As chooses another destination. File validation and shared-engine schema checks run before accepting the opened project.

Dirty work is snapshotted locally every two seconds; a startup banner offers Restore work or Discard snapshot. A failed/unreadable recovery file is preserved until an explicit discard. Recovery does not replace a separate backup of saved projects. Updates refuse restart while work is unsaved, an operation is running, or recovery needs a decision.

The profile is `%APPDATA%/VeriCivil Superelevation` on Windows and `~/Library/Application Support/VeriCivil Superelevation` on Mac. It contains recovery/project data and recent paths; do not include the profile in public reports. Help → Export diagnostics writes only versions, platform/architecture, and bounded event/error-code logs, excluding project contents, file paths, and credentials. No diagnostic upload is performed.

## Signed production releases

The public [Code signing policy](https://vericivil.com/code-signing) records pending SignPath approval and current unsigned status. See [SignPath onboarding](../docs/signpath-onboarding.md) for the protected **Windows SignPath Review** workflow, required configuration after approval, and remaining Electron/NSIS production gates. Its outputs are review artifacts only, not installable signed production releases or update feeds.

Signing identities are not currently configured. PR/main builds remain unsigned, and never publish automatic-update feeds. Production packaging fails when required signing credentials are absent. Keep secrets in the protected GitHub environment `desktop-production`, restricted to `main`, with release approval:

The environment is configured to allow only the `main` branch and requires approval by the repository owner. Signing secrets still need to be supplied.

- Windows: `WINDOWS_CSC_LINK` (certificate path/secure URL/base64 supported by electron-builder), `WINDOWS_CSC_KEY_PASSWORD`, and `WINDOWS_PUBLISHER` matching the certificate identity.
- Mac: `MAC_CSC_LINK`, `MAC_CSC_KEY_PASSWORD`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, and `APPLE_TEAM_ID` for signing and notarization.

After a successful main release, run **Signed Desktop Release** with that latest stable tag. It checks out the released main commit, tests/builds each target, requires signing, verifies Windows signatures and Mac notarization, and uploads binaries before the architecture-specific update metadata. The workflow does not create a public release from a PR. The updater uses GitHub Releases; `https://vericivil.com/downloads` discovers those artifacts and labels unsigned builds. Do not put signing keys in this repository or paste them into chat.

The updater implementation uses pinned electron-builder/electron-updater versions. Signing, tampered-package rejection by real OS signatures, and signed N-to-N+1 installation on each Mac architecture require credential-backed acceptance before production distribution. Mocked updater tests are not evidence of those OS checks.

The Mac app bundle and Windows executable use the VeriCivil icon, and the running window uses the same artwork. The portable ZIP itself keeps the operating system's archive icon; extract it to see the branded executable. Native icons in `desktop/icons/` come from `web/public/brand/vericivil-icon.png`. To regenerate them with Pillow installed, run from the repository root:

```sh
python -c "from PIL import Image; im = Image.open('web/public/brand/vericivil-icon.png'); im.save('desktop/icons/vericivil.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]); im.save('desktop/icons/vericivil.icns')"
```

To create a downloadable archive after packaging, run the matching command from the repository root:

```sh
python3 scripts/package_electron_release.py --platform darwin --arch arm64
# Intel Mac: use --arch x64 instead.
python scripts/package_electron_release.py --platform win32 --arch x64
```

Mac DMG creation requires macOS. Windows ZIP creation can also run on a Mac using `python3`. Archives and matching SHA-256 files are written to `desktop/release-assets/`; filenames include the app version and target platform. The helper refuses missing packages and stale staged versions. A Windows ZIP contains the full portable application folder; extract it before launching the EXE.

## Automated builds and GitHub Releases

The **Full Release** workflow validates `APP_VERSION` before building Electron previews for macOS arm64 (`macos-15`), macOS x64 (`macos-15-intel`), and Windows x64 (`windows-latest`). Opening, updating, reopening, or marking a version-bumped PR ready for review runs the builds, including on draft PRs. Documentation-only changes skip packaging, and invalid/reused versions stop before desktop jobs run.

Each native runner installs the pinned Electron runtime, checks the save/security boundaries, packages the app, exercises the offline runtime against native Python, and creates its DMG or portable ZIP plus checksum. PR runs have read-only repository permissions and upload `desktop-release-<version>-<target>` Actions artifacts retained for 30 days. They do not publish a GitHub Release or use signing secrets.

After merge to `main`, desktop and browser builds run against the merged source. The public versioned GitHub Release is published only after all release build jobs succeed, and includes unsigned installers, both preview Mac DMGs, the portable Windows ZIP, checksums, and the browser archive. Windows CI installs version N, upgrades to a synthetic N+1, and uninstalls, checking that project and recovery data survive. The **Legacy Tkinter macOS Build** and **Legacy Tkinter Windows Build** jobs remain manual rollback builds. Website publishing remains a separate `Ship main` operation.

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

The browser build remains its own entry point. `python3 super_app.py`, the PyInstaller specifications, and manual legacy build workflows remain available. Unsigned preview archives and installers use the normal release workflow; signing and update-feed publication use the separate protected manual workflow. Website publication still requires Ship main. Production licensing is intentionally deferred while desktop tools remain free.
