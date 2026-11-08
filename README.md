# VeriCivil

**Roadway software you can verify.**

Calculate superelevation transitions, review lane slopes and stationing, and prepare engineering deliverables for OpenRoads Designer and MicroStation. This repository contains VeriCivil’s website, browser calculators, shared Python engines, and Electron desktop workspace.

[Open Superelevation](https://vericivil.com/calculators/superelevation) · [Estimate crushed stone base](https://vericivil.com/calculators/crushed-stone-base) · [Run from source](#quick-start) · [Engineering notes](#engineering-notes)

[![Tests](https://img.shields.io/github/actions/workflow/status/colewinstead/VeriCivil/tests.yml?branch=main&label=tests)](https://github.com/colewinstead/VeriCivil/actions/workflows/tests.yml)

## Tools

| Tool | What you can do | Where to start |
| --- | --- | --- |
| **Superelevation Calculator** | Calculate roadway transitions, inspect lane slopes and cross sections, save projects, and export PDF, ORD CSV, and overlay DXF. | [Browser workspace](https://vericivil.com/calculators/superelevation) |
| **Guardrail** | Calculate near/opposing lengths, save projects and generate PDFs with optional MDOT references. | [Free browser calculator](https://vericivil.com/calculators/guardrail) |
| **Crushed Stone Base** | Estimate compacted base volume and order tonnage across multiple construction segments. | [Free calculator](https://vericivil.com/calculators/crushed-stone-base) |
| **Electron desktop preview** | Use the Superelevation workspace with a bundled offline calculation and export runtime. Current desktop tools are free without account sign-in. | [Downloads](https://vericivil.com/downloads) · [Build guide](desktop/README.md) |

[RoadStation by VeriCivil](https://vericivil.com/roadstation) is a separate iPhone product for LandXML alignment, station, and LT/RT offset workflows. Its native implementation lives in the [Road-Stationing-App repository](https://github.com/colewinstead/Road-Stationing-App).

## Superelevation workflow

1. Enter curve data or import a supported LandXML alignment.
2. Select the governing criteria profile and confirm roadway, lane, stationing, and coordinate inputs.
3. Review transition stations, signed lane slopes, cross sections, and corridor QA findings. Resolve blocking findings before engineering export.
4. Save the project and export the supported PDF report, ORD CSV, or overlay DXF.
5. Verify the deliverables against the governing standards and in the project’s design file before production use.

To explore without project data, open the workspace and choose **Load synthetic sample** after the engine is ready. Hosted features follow the current account entitlement; local development defaults to Pro for testing.

<details>
<summary>View an example calculation report</summary>

![Example Superelevation PDF report showing project metadata, the MDOT governing standard, and a two-curve index.](web/public/showcase/pdf-report.png)

Existing illustrative report capture; it is not a current workspace screenshot or evidence of project approval. [Open the sample PDF](web/public/showcase/superelevation-report-sample.pdf).

</details>

> [!IMPORTANT]
> VeriCivil is an engineering aid. The professional responsible for the project must independently verify criteria, applicability, inputs, stationing, coordinate systems, results, and exported geometry.

## Quick start

The [hosted calculators](https://vericivil.com/calculators) require no local Python installation. To run from source, install **Python 3.11+** and a standalone **Node.js 22.13+**, with both available on PATH.

Run these commands from the repository root:

```sh
git clone https://github.com/colewinstead/VeriCivil.git
cd VeriCivil
npm --prefix web ci --ignore-scripts
npm --prefix web run dev
```

Open [localhost:3000/calculators/superelevation](http://localhost:3000/calculators/superelevation), or use the port printed by the server. Keep the terminal running; **Ctrl+C** stops it. To choose a port, use `npm --prefix web run dev -- --port 3001`.

Python stages the shared engine modules; the browser runs them through Pyodide. Native Python dependencies are needed for native calculations and Python tests, rather than browser startup. On Windows, use `python` in place of `python3` in the Python commands below.

### Production browser build

```sh
npm --prefix web run build
```

The build writes `web/dist`, including browser assets and a Cloudflare Workers-compatible server runtime. Use the development command above for local testing; the configured production server requires Cloudflare bindings and cannot run through plain Node with `npm --prefix web start`.

The first browser visit downloads the Python runtime and required packages. Calculations and exports then run on the user’s device. Account services and analytics still use the network; see [Data and privacy](#data-and-privacy).

### Desktop development

After installing the web dependencies, download Electron and launch the desktop workspace:

```sh
node web/node_modules/electron/install.js
npm --prefix web run desktop:dev
```

This builds and opens the native window. It does not watch for edits; close the app and rerun after changes. The first build needs internet access to bundle the offline runtime.

See the [desktop guide](desktop/README.md) for packaging, installers, the neutral **Superelevation Calculator** edition, local recovery, updates, and signing. Automated previews are unsigned. Windows installers support user-approved updates; unsigned Mac and portable builds require manual replacement. Check the [download page](https://vericivil.com/downloads) and [code signing policy](https://vericivil.com/code-signing) for distribution status.

## Engineering notes

### Criteria and roadway scope

| Profile | Implemented scope and review boundary |
| --- | --- |
| **MDOT** — `mdot-rdsd-2026-04-22` | Versioned Mississippi criteria, shared piecewise-linear lane transitions, and explicit eligible reverse-curve coordination. See the [MDOT transition model](docs/MDOT_TRANSITION_MODEL.md). |
| **TDOT** — `tdot-rd11-2026-04-30` | RD11-LR-1 desirable 4% urban and RD11-LR-2 desirable 8% rural tables, with RD11-SE-1 transition equations for undivided-roadway lane events. Supporting typical-section references do not automatically model divided-roadway geometry. |
| **AASHTO 2018** — `aashto-green-book-2018-2019-10` | Limited table-based profile with recorded sources, fixed-pivot sections, ramps, established clothoids, and divided-roadway Case II. Continuous Method 5 equations and new alignment construction are excluded. Embedded-data redistribution clearance remains unresolved. Read the [scope, source, and acceptance record](docs/AASHTO_2018.md) before use. |

The **Cross Section** view shows recorded lane geometry and fixed pivots for supported AASHTO sections. MDOT/TDOT use labeled slope schematics where physical layouts are unspecified. See the [cross-section guide and roadway support audit](docs/CROSS_SECTION_VIEW.md).

Case II calculates both carriageways on a common baseline with separate inputs and explicit inside travel-lane pivots. Supported browser/Electron inspection, projects, PDF, and DXF identify both sides. **Case II ORD CSV and legacy Tkinter editing/export are blocked.** See the [Case II validation record](docs/AASHTO_2018.md#case-ii-divided-roadway-engine-160).

Reverse-curve overlap notices and corridor QA identify conditions requiring review; they do not modify horizontal geometry or shorten transitions. Eligible MDOT pairs can be linked explicitly. AASHTO/TDOT overlaps require engineering review. The calculated spacing demand is not a universal agency minimum.

### Files and exports

| Format | Behavior and limits |
| --- | --- |
| **Project JSON** | Save and reopen recorded inputs, results, and provenance. Older supported schemas migrate in memory to the current schema defined in `super_project.py`; newer unsupported schemas are refused. Resaving does not silently recalculate recorded results. |
| **LandXML** | Imports supported alignment metadata, units, lines, circular arcs, and station equations. Unsupported or incomplete geometry, ambiguous stations, and missing coordinate context require review. Profile-specific spiral limits are described in the AASHTO guide. |
| **PDF** | Reports recorded calculation data, source criteria, and diagnostics. A report does not establish design approval. |
| **ORD CSV** | Uses Bentley superelevation import columns and accounts for station equations and ORD regions. Confirm lane names, slope signs, pivots, and import behavior in the target design file. |
| **Overlay DXF** | Produces a real-coordinate graphics handoff with lane leaders, slope labels, and curve callouts. It is not a native Bentley civil model. Verify units, origin, placement, styling, and coordinate context in CAD. |

ORD CSV columns:

```text
SuperelevationLane,Station,CrossSlope,PivotAbout,PointType,TransitionType,NonLinearCurveLength
```

LandXML points are interpreted as Northing/Easting and written to CAD as X=Easting, Y=Northing. Optional MDOT MS83/2011 East/West transformation requires the correct source and target zones and exact units. Do not infer CRS, datum, or foot type from coordinate magnitude or filenames.

For the MDOT two-lane convention, normal crown is negative on both lanes. At full super, a right-hand curve has positive left-lane and negative right-lane slope; a left-hand curve reverses those signs. Positive display values include `+`. Review other section types using their recorded geometry and pivot conventions.

Application and engine versions come from [`app_info.py`](app_info.py) and are recorded in new projects and PDF reports. See the [commercial readiness record](docs/COMMERCIAL_READINESS.md), [pilot readiness record](docs/PAID_PILOT_READINESS.md), and [pilot operations guide](docs/PILOT_OPERATIONS.md) for additional acceptance limits.

## Data and privacy

Calculation and export processing runs locally through Pyodide. **Local processing does not mean the hosted calculator transmits no engineering data.**

- The hosted service provides sign-in, entitlements, billing, and usage analytics.
- Successful superelevation calculations send the selected standard/revision, exact speed and radius, and entered PC/PT stationing to engineering analytics, without account or session linkage.
- **LandXML retention is enabled by default.** Uncheck the retention control **before selecting a file** to prevent sending its contents for product improvement. Successfully parsed files up to 1 MiB may be retained for 30 days in administrator-only storage. Turning retention off affects future selections. Local import and calculation work with retention disabled.
- The standalone desktop app does not use the browser service’s analytics, billing, or remote LandXML retention. It stores recovery data and bounded support logs locally and checks GitHub for updates.

LandXML may contain confidential coordinates, project names, or author details. Only share files you have permission to provide. See the [privacy policy](https://vericivil.com/privacy) and [desktop privacy notice](https://vericivil.com/code-signing#desktop-privacy) for the complete data-handling details.

## Development and validation

The browser and Electron interfaces use the shared Python engines. Keep calculation logic there rather than duplicating it in React. Treat formulas, lookup tables, stationing, coordinate transforms, ORD mappings, and engineering results as frozen unless a clear defect is identified and explained.

| Location | Responsibility |
| --- | --- |
| [`calculators/catalog.py`](calculators/catalog.py) | Available calculators and explicit browser runtime bundles |
| [`super_service.py`](super_service.py) | Superelevation calculations, projects, and exports |
| [`Super.py`](Super.py), [`super_transition.py`](super_transition.py) | Core calculations and lane transition profiles |
| [`criteria_info.py`](criteria_info.py) | Versioned criteria and source metadata |
| [`super_landxml.py`](super_landxml.py), [`super_project.py`](super_project.py) | Alignment parsing, station geometry, and project persistence |
| [`super_exports.py`](super_exports.py), [`super_pdf.py`](super_pdf.py), [`super_dxf.py`](super_dxf.py) | Engineering deliverables |
| [`calculators/crushed_stone_base/`](calculators/crushed_stone_base) | Base quantity engine and service |
| [`web/`](web), [`desktop/`](desktop) | React/Pyodide browser app and Electron shell |

Run the Python suite from the repository root:

```sh
python3 -m pip install -r requirements-lock.txt
python3 -m unittest -v
```

Run browser checks after installing web dependencies:

```sh
npm --prefix web exec -- tsc --noEmit -p web/tsconfig.json
npm --prefix web run lint
npm --prefix web test
```

`npm test` includes a production build, browser/server checks, and Pyodide parity with CSV, PDF, and DXF generation. The suites cover shared calculations, stationing, lane signs, LandXML, coordinate transforms, project compatibility, criteria provenance, and export behavior. Passing tests are evidence for the tested cases, not blanket engineering certification.

### Troubleshooting

- **Missing `package.json` or lockfile:** run commands from the repository root with `--prefix web`.
- **Native module “different Team IDs” error on macOS:** check `node -p "process.execPath"`. Use a standalone Node installation rather than a runtime embedded in another signed application, then open a new terminal. Reinstalling dependencies alone does not fix the executable mismatch.
- **Electron failed to install:** rerun `node web/node_modules/electron/install.js` after `npm ci --ignore-scripts`.
- **Electron opens as a Node process:** check that `ELECTRON_RUN_AS_NODE` is unset before launching.

For a bug report, include OS/browser, application and engine versions, selected criteria, expected behavior, and a minimal reproduction with non-sensitive data. Review logs before sharing them.

## Contributing and releases

1. Open or reuse an [issue](https://github.com/colewinstead/VeriCivil/issues) with the problem, expected behavior, and acceptance criteria.
2. Create a short-lived branch from the latest `main` through the issue’s **Development** section or `gh issue develop`.
3. Make the scoped change, run applicable checks, and open a PR into `main`. Use `Closes #123` for a fully resolved issue or `Related to #123` for partial work.
4. Merge only after required checks pass, using **Squash and merge**. If a branch update is required, merge the latest `origin/main` into the issue branch and rerun checks. Start the next issue from updated `main`.

Changes confined to documentation (`.md`, `.rst`, and license files), `.codex/`, or `.agents/skills/` need no version bump or release. Other changes, including images outside those exempt paths, tests, dependencies, builds, and workflows, require an `APP_VERSION` increase beyond the latest release. Mixed changes also require a bump.

Version-bumped PRs build unsigned desktop previews for Apple Silicon, Intel Mac, and Windows x64 as Actions artifacts. They do not publish public releases. Successful release jobs on `main` publish versioned browser and desktop assets with checksums. Publishing to the existing live website is a separate **Ship main** step; preserve the Site identified by `web/.openai/hosting.json`.

See [`AGENTS.md`](AGENTS.md) for repository policy and the [release checklist](docs/RELEASE_CHECKLIST.md) for release validation.

## License

Project code is licensed under the [MIT License](LICENSE), copyright © 2026 Cole Winstead. Third-party dependencies and source materials retain their own terms; the project license does not resolve the AASHTO data redistribution limits described above.
## Guardrail browser integration

The free Guardrail browser workspace uses a pinned, unchanged engine from the
separately maintained Guardrail Calculator repository. See
[integration and update instructions](docs/GUARDRAIL_BROWSER.md) for ownership,
project files, supported PDFs and validation limits.
