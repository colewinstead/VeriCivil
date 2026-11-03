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

## Cross-section extension

Mode remains Operate. This is an ordinary extension of the incumbent alignment review desk, with the existing tokens, system typography, teal/amber lane roles, system light/dark appearance, inspector composition, and export boundaries preserved.

The shared browser/Electron `SuperelevationAnalysis` adds **Cross Section**. `web/app/SuperelevationCrossSection.tsx` maps the ordered geometry packet from `super_cross_section.py` to SVG; `web/app/globals.css` and `web/desktop/desktop.css` retain the shared and desktop styling roles. Station slider, equation-aware entry, exact event steps, and focused wheel movement share the existing inspector. The drawing looks ahead along increasing station, defaults to 5× vertical exaggeration, offers true scale for physical sections, and holds curve framing stable. Physical AASHTO output shows recorded lane widths, fixed pivot, and relative edge heights. MDOT/TDOT remains a labeled slope schematic without physical dimensions or pivot. Mobile browser labels reflow into HTML; accessible SVG descriptions include schematic slopes. `docs/CROSS_SECTION_VIEW.md` audits support and extension boundaries: new road models require verified Python geometry, not new React engineering logic or a speculative framework.

### Scoped finish record: cross section

Reviewer verdict: **SHIP**, scoped only to the three findings below and their resolved fixes. This is not blanket acceptance of the desktop, browser, engineering scope, or release.

- Light-appearance expanded-analysis **Close** contrast: resolved using the existing appearance roles.
- Mobile lane/slope labels: resolved through readable HTML reflow below the diagram.
- Schematic accessible slopes: resolved by including the slope values in the SVG's accessible description.

Local actual Electron/browser smoke checks passed native keyboard/station entry, focused wheel handling, physical true-scale ratio, invalid-input recovery, curve-gap clamping when switching to a ramp and back, and shared-inspector continuity. Schematic checks confirmed no physical pivot or physical scale control and accessible slope values. These checks do not constitute Windows hardware acceptance or real screen-reader speech acceptance.

Local visual evidence uses a valid synthetic four-lane example:

- `.impeccable/review/cross-section-electron-light.png` and `cross-section-electron-light-lower.png`.
- `.impeccable/review/cross-section-electron-dark.png` and `cross-section-electron-dark-lower.png`.
- `.impeccable/review/cross-section-browser-desktop.png` and `cross-section-browser-desktop-lower.png`.
- `.impeccable/review/cross-section-browser-mobile.png` and `cross-section-browser-mobile-lower.png`.

These screenshots are ignored local review evidence; no shipping raster was created. The earlier finish record remains historical. The preexisting DESIGN.md/sidecar stale finding was not repaired by this scoped documentation update. No publishing, signing, or release acceptance is implied.
