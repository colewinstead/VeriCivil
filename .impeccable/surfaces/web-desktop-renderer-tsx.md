---
version: 1
slug: "web-desktop-renderer-tsx"
primary_target: "web/desktop/renderer.tsx"
related_targets: ["web/app/CalculatorApp.tsx","desktop/main.cjs"]
---

# Electron desktop workspace

Mode: Operate. Inherit the existing VeriCivil React calculator and the user's selected alignment-review direction. User explicitly approved Electron after choosing inputs beside a large results/diagram area and following Mac appearance. This is a new desktop surface using the existing web UI, not a new website or a new aesthetic workshop.

## Direction contract
THESIS: One shared calculator interface, shaped as a desktop review desk. A compact Project/Curve inspector leaves most width for engineering results and the station-aware diagram.
OWN-WORLD: System sans and tabular measurements, neutral green-tinted work surfaces, teal/amber lane traces, restrained borders. Follow system light/dark appearance; preserve the web product's recognisable engineering vocabulary without its three-column constraint.
STORY: Open or import local files, enter curve/roadway inputs, inspect lane profiles and source criteria, save compatible projects and exports through native dialogs. All runtime and engineering processing are bundled locally; this evaluation preview has no analytics, uploads, account login, or billing.
FIRST VIEWPORT: Native title/menu bar, compact workspace toolbar, Project/Curve selector, a 360px scrolling inspector and a large independently scrolling review area, exports at the foot. The diagram's station cursor remains the signature interaction. Warnings and provenance remain in the review area.
FORM: Preserve the selected alignment review desk (#7, seed 85bb43a6); code-led. Electron shares React and Python/Pyodide rather than translating the UI into Tkinter. Preview access is explicit and separate from production paid entitlements.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Stop condition: runnable offline Electron preview; shared-engine parity, project and export proof; type/lint/Python/browser checks; bounded native visual review. No publishing, signing, production licensing, new calculation logic, or automatic updates. Keep Tkinter as rollback.

## Finish record

The bounded review returned `fix`. SVG control icons and persistent synthetic labels were resolved in the packaged Mac capture. The station cursor now uses theme-aware ink, with the browser's white fallback preserved. Light/dark palette checks and laptop/wide layout checks passed in the actual Electron test. A light-appearance capture with a selected station remains outstanding: native coordinate actions returned `noWindowsAvailable`, so the reviewer could not close that visual evidence gap. Windows visual acceptance also remains unverified. DESIGN.md and .impeccable/design.json record the implemented desktop system. This is a draft evaluation preview, not a signed or published release.
