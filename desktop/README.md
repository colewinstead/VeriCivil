# VeriCivil Electron desktop preview

This desktop entry point reuses `web/app/CalculatorApp.tsx` and the same Python modules as the browser and Tkinter editions. It bundles Pyodide, its nine required packages, and the pinned ReportLab/ezdxf wheels. Engineering processing runs locally without an internet connection. Formulas, criteria, project schemas, and export implementations are unchanged.

The preview enables the existing local Pro workflows for evaluation. It does not sign in, bill, grant a production subscription, collect analytics, retain LandXML remotely, or install updates. GitHub distributes it explicitly as an unsigned evaluation preview. Signed distribution and production desktop licensing remain separate work.

See the [production desktop readiness plan](../docs/desktop-production-readiness.md) for the remaining distribution, update, licensing, recovery, and support work.

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
```

The first command packages the host platform: the current Mac architecture, or Windows x64 when run on Windows. The second packages Windows x64, including from a Mac. Outputs are under `desktop/releases/`. Runtime downloads and generated application assets are ignored by Git. The runtime cache records dependency URLs and verified SHA-256 values in `desktop/runtime/checksums.json`. Repeated builds verify cached bytes before use.

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

After merge to `main`, desktop and browser builds run against the merged source. The public versioned GitHub Release is published only after all release build jobs succeed, and includes both Mac DMGs, the Windows ZIP, per-target checksums, and the browser archive. The **Legacy Tkinter macOS Build** and **Legacy Tkinter Windows Build** jobs remain manual rollback builds; they do not produce the Electron release files. Website publishing remains a separate `Ship main` operation.

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

The browser build remains its own entry point. `python3 super_app.py`, the PyInstaller specifications, and the manual legacy build workflows remain available. The earlier Tkinter redesign is an unmerged checkpoint on `codex/58-desktop-workspace`; the Electron implementation is on its linked issue branch. Automatic Electron preview packaging and release assets are enabled in the release workflow; no website deployment, production licensing, signing, or updater is configured by that workflow.
