# VeriCivil Electron desktop preview

This desktop entry point reuses `web/app/CalculatorApp.tsx` and the same Python modules as the browser and Tkinter editions. It bundles Pyodide, its nine required packages, and the pinned ReportLab/ezdxf wheels. Engineering processing runs locally without an internet connection. Formulas, criteria, project schemas, and export implementations are unchanged.

The preview enables the existing local Pro workflows for evaluation. It does not sign in, bill, grant a production subscription, collect analytics, retain LandXML remotely, or install updates. Signed distribution and production desktop licensing remain separate work. Do not publish this preview as a commercial release.

## Build and run

Use the repository's supported Node/Python versions. Install the native Python requirements if running the parity checks. Dependency installation and the first desktop build require internet access; the resulting app does not.

```sh
npm --prefix web ci
npm --prefix web run desktop:dev
```

`desktop:dev` builds and launches the packaged application source. If npm's script policy skipped the Electron binary download, run `node web/node_modules/electron/install.js` once. On this Mac, use a standard Node installation (for example the existing Homebrew Node), rather than the Node executable embedded in a signed application; the latter can reject native build bindings with a different-Team-ID error.

```sh
npm --prefix web run desktop:package
npm --prefix web run desktop:package:windows
```

The first command packages the host Mac architecture; the second creates the Windows x64 preview. Outputs are under `desktop/releases/`. Runtime downloads and generated application assets are ignored by Git. The runtime cache records dependency URLs and verified SHA-256 values in `desktop/runtime/checksums.json`. Repeated builds verify cached bytes before use.

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

On Windows use `python` instead of `python3`. The offline Electron test launches the real application and worker with outbound requests blocked in a disposable app profile, compares a calculation against native Python, exercises LandXML, PDF/ORD CSV/overlay DXF, and round-trips a project. It also verifies isolated renderer globals, the native save bridge (including cancellation), laptop/wide layout bounds, and both system appearance palettes. Dialog destinations are stubbed inside the test. The Mac native Save dialog and its cancellation, plus the unsaved-close confirmation, were also checked interactively.

The Windows x64 package was built and copied to the LAN test PC in an isolated temporary directory. Its Electron executable and local Python runtime loaded; the remote test did not confirm a visible window. Windows visual and interactive acceptance remain unverified.

## Rollback and scope

The browser build remains its own entry point. `python3 super_app.py`, the PyInstaller specifications, and the manual native build workflows remain available. The earlier Tkinter redesign is an unmerged checkpoint on `codex/58-desktop-workspace`; this Electron work starts from `origin/main` on the linked issue branch. No automatic desktop release job, website deployment, production licensing, signing, or updater was added.
