# VeriCivil Typicals — Milestone 1 preview

Local parametric rural section drafting, tracked by issue #76. This is a generic engineering drawing tool, not an approved MDOT standard or a native ORD corridor/template model. No criteria tables or existing superelevation formulas changed. No implementation push, release, or Site deployment is part of this work.

## Launch and use

From `web`, run `npm run dev`, then open `/calculators/typicals`. For the offline Electron app run `npm run desktop:dev`, then **Tools → VeriCivil Typicals**. Tools → Superelevation returns to the existing calculator. Select the matching tool before opening a project of that type. On this Mac the bundled Node executable cannot load Rolldown's native binding because of its signing identity; `PATH=/opt/homebrew/bin:$PATH npm run dev` (and the same prefix for build/desktop commands) uses the verified Homebrew Node installation.

1. Start with **New section**. Choose the coordinate foot definition explicitly. Enter lane/shoulder widths, signed cross slopes, roadside H:V and signed roadside rise independently left and right. Enter or leaving a numeric field applies its change. A positive cross slope rises **outward** from CL on either side; this convention is local to Typicals and does not change Superelevation's sign convention.
2. **Materials** controls vertical structure thickness in international inches. Layers extend continuously across the lanes and paved shoulders. Unpaved shoulders have no pavement structure in this MVP.
3. Select a line to identify its component. Shift drag or middle mouse pans; wheel/buttons zoom; Fit restores extents. Measure picks two coordinates, optionally snapping to the seven named geometry points. Dimensions and coordinate readouts use feet. Numerical property fields, rather than mouse dragging, provide precise geometry edits.
4. Lock named points to reject changes that would move them. Connections are fixed dependency chains: CL → lane edge → shoulder edge → roadside end. There is no general constraint solver. A conflicting edit fails without committing partial geometry or changing unrelated inputs. Undo/redo includes mappings, materials and annotation overrides (100 edits; session history is not saved).
5. **Sheet** edits metadata, station-range text (use semicolons for multiple ranges), notes, scale, annotation precision, standard font and sheet dimensions. CAD and print use the same geometry. Four dimension tiers show component, computed paved, travel-way and overall shoulder widths. Filled arrowheads, lane/shoulder labels, sloped H:V labels, layer-anchored material bubbles, structure-thickness and plan-grade leaders, hatched exterior ground and a centered title stack follow conventional drawing hierarchy. The revised layout uses the user's supplied plan-detail reference; dimensions still come from the project. Print line weights are independently editable in mm and never change CAD assignments, ByLevel weights or coordinates. Fixed dimension tiers and deterministic text-box avoidance reduce collisions; annotation offsets provide explicit corrections. Complex collision routing remains deferred. Standard fonts are condensed through an explicit .78 width factor, not a bundled proprietary MDOT typeface.
6. **Save project** saves versioned `section.typicals.json`. Open restores geometry, point locks, materials, mappings, catalog, metadata, drafting/print settings, and annotation offsets. Browser files stay local; Electron uses existing atomic file saves and recovery. A saved project under another filename is a reusable full-section preset. Dedicated reusable component libraries are deferred.
7. PDF/SVG are physical-size vector sheets. Print at **100%**, without “fit to page.” Oversized drawings fail with a recovery message; increase ft/in or paper size. DXF uses full-scale section coordinates, independently of sheet scale. Built-in PDF fonts support Western text only; unsupported scripts fail explicitly. SVG retains Unicode.

## Workspace discovery (2026-10-31)

Recursively discovered `tests/fixtures/Mdot Openroads Workspace/`; no assumed workspace location is used by the inventory command. The supplied tree contains **1,026 files, 219,985,704 bytes**, including 275 DGN, 70 DGNLIB, 6 CFG, 7 RSC, 55 XML, 7 TBL, 4 PLTCFG, 2 ITL and 14 TTF files. There are **no CSV level reports** in this tree. Complete per-file relative paths, byte sizes, SHA-256 hashes, extension counts and relevant configuration lines are in the local ignored `local/typicals/workspace-inventory.json`.

Reproduce this read-only inventory for any workspace root:

```sh
python3 scripts/inventory_typicals_workspace.py "/path/to/workspace" --output local/typicals/workspace-inventory.json
```

Important discovered authorities, relative to the supplied root:

| Purpose | Configured / supplied source |
| --- | --- |
| Organization configuration | `Organization-Civil/MDOT_Standards_CE.cfg` |
| WorkSpace / WorkSet overrides | `Workspaces/MDOT_Standards_CE.cfg`, `Workspaces/MDOT_Standards_CE/Template/WorkSet.cfg` |
| Roadway levels and element templates | `Organization-Civil/MDOT_Standards_CE/Dgnlib/Feature Definitions/_MDOT_2_Features_Annotations_Levels_ElementTemplates.dgnlib` (organization CFG lines 96, 105) |
| Additional configured levels | same directory, `Bridge_Features_Levels_Elem Temp Imperial.dgnlib` (line 97) |
| Text favorites, text and dimension styles | same directory, `_MDOT_01_Text Favorites_Text Styles_Dimension Styles.dgnlib` (lines 99–101) |
| Other feature library | same directory, `_MDOT_03_DU_Features_Annotations_Levels_ElementTemplates_ItemTypes.dgnlib` |
| Color table | `Organization-Civil/MDOT_Standards_CE/ColorTables/rwdco.tbl` via `MS_DEFCTBL` (line 135) |
| RSC styles | `Organization-Civil/MDOT_Standards_CE/Dgnlib/Line Styles/{mdotsty,2dlstyle,3dlstyle,MDOT 3D Pavement Marking}.rsc` via `MS_SYMBRSRC` (line 120) |
| Fonts | `.../Fonts/MDOT_MstnFontConfig.XML`, `mdotfont.rsc`, Engineering TrueType variants and SHX files (lines 150–152) |
| Printing styles | `.../Dgnlib/Printing/PrintStyles.dgnlib` (line 116) |
| Printer configuration | `.../Pltcfg/{pdf,pdf_color,printer,RwdPdfXS}.pltcfg` (line 164) |
| Pen tables | `.../Pen Tables/{RwdPdf_Details,RwdPdf_Details_Final,RwdPdf_Color,RwdPdf_Color_Final,stamp,SMD}.tbl` plus DesignScripts (line 165) |
| Sheet seeds | `.../Dgnlib/Sheet Seeds/` and `.../Seed/Sheets/` |
| Units / scales | `.../Scales/{units,scales,sheetsizes}.def` |
| Supplied template libraries | `.../Template Library/rwd.itl`, `.../Dgnlib/Sheet Seeds/null.itl` |

Active WorkSet overrides can supersede organization settings. A report must identify the actual active configuration and source libraries. Binary DGN/DGNLIB/RSC properties were **not decoded**. The fact that an ITL is supplied does not prove a supported ITL authoring interface. No supplied binaries, fonts, template contents or full pen-table contents are staged into the browser/Electron bundles. The workspace is ignored by Git. Its licensing has not been established; do not redistribute it or local reports without the owner's permission.

## TS_ names actually observed

The following **30 name references** were extracted from textual `IN_LEVEL` entries in `RwdPdf_Details.tbl`, `RwdPdf_Details_Final.tbl` and `stamp.tbl`; the color tables reference 27 of them. These are observed names, **not a verified exhaustive list of levels in the binary DGNLIB**, and establish no descriptions, colors, weights or styles:

```text
TS_ANGLE_REPOSE          TS_AREA_PATTERNS        TS_BACKBONE
TS_BARRIERS              TS_CURB_GUTTER          TS_DESCRIPTIONS_TX
TS_DETAILS               TS_DIMENSIONS          TS_DIMENSIONS_TX
TS_DIRECTION             TS_DRAINAGE            TS_EXISTING_LABELS
TS_FILL_SLOPE_SCHEDULE   TS_GRASS               TS_GUARDRAIL
TS_MATCH_LINES           TS_PAVMT_DETERMINATION  TS_PROPOSED_LABELS
TS_PROPOSED_NOTES        TS_RETAINING_WALL       TS_SIDEWALK
TS_SIDE_SLOPE_LT         TS_SIDE_SLOPE_RT        TS_SLOPES_TX
TS_SPECIAL_NOTES         TS_SUBGRADE            TS_TITLE_BLOCK_TX
TS_UNDERDRAINS           TS_X_GROUND            TS_X_NOTES
```

The inventory's embedded catalog is `name-references-only` and cannot authorize export. No guessed official assignments or symbology are supplied. The drawing uses visibly disclosed illustrative preview colors until an actual report is imported.

## Bentley level report procedure

Bentley documents **Level Manager → Levels → Export** for CSV level reports and identifies `ByLevelColor`, `ByLevelStyle`, and `ByLevelWeight` as separate attributes. See [Levels and Level Libraries](https://bentleysystems.service-now.com/community?id=kb_article&sysparm_article=KB0108776). Menu wording may differ by installed ORD/MicroStation version; check the version's Help if necessary.

1. Open a scratch DGN using the intended MDOT WorkSpace and WorkSet. Keep original libraries read-only. Inspect `MS_DGNLIBLIST_LEVELS`, the library source column, and active overrides in Level Manager. Include **all TS_ levels**, including unused library levels. If library levels are not exported, copy/import them into the scratch DGN, never into the authoritative library.
2. Set symbology inspection to **ByLevel**, not Overrides. Export CSV including Name, Description, ByLevelColor, ByLevelWeight, ByLevelStyle and Plot. Preserve the original report and identify source DGNLIB filenames, hashes, workspace revision, ORD/MicroStation version and export date in a sidecar or catalog source/revision fields.
3. Resolve each indexed Bentley color using the active source DGN color table to **RGB `#RRGGBB`**. Bentley color index 3 is not automatically AutoCAD ACI 3. Keep original `ByLevelColor` beside RGB.
4. Resolve each Bentley weight to the **intended DXF/PDF lineweight in mm**, based on the project's plotting setup. Do not equate a weight index with mm. Supported DXF weights: 0, .05, .09, .13, .15, .18, .20, .25, .30, .35, .40, .50, .53, .60, .70, .80, .90, 1.00, 1.06, 1.20, 1.40, 1.58, 2.00, 2.11. An unsupported value is rejected rather than rounded silently.
5. Add an explicit `DashFT` column: `[]` for confirmed continuous, or a JSON array alternating positive draw/negative gap lengths **in the project's selected coordinate feet**, e.g. `"[1,-0.5]"`. RSC symbol-based custom styles cannot be faithfully represented by a simple pattern; have the CAD administrator approve a simplified mapping or leave it unresolved (DXF remains blocked). The report preserves the original ByLevelStyle for review.
6. Import CSV/JSON in **Levels**, identify the source and revision, inspect every imported property, and select an actual imported TS_ level for each drawing role. One actual level may serve multiple roles. Missing levels, duplicates, invalid names, unresolved fields, and unsupported weights block DXF. A new report replaces the catalog; existing mappings are rechecked, not silently reassigned.

CSV schema (example values below are synthetic and **not MDOT values**):

```csv
Name,Description,ByLevelColor,ByLevelWeight,ByLevelStyle,RGB,LineWeightMM,DashFT,Plot
TS_TEST_ONLY,Synthetic example,3,2,0,#00aa66,0.35,[],1
```

Standard Bentley reports without RGB/mm/dash enrichments import with unresolved fields and stay blocked. Only explicit `ByLevel*` columns are read; ambiguous `Color`, `Weight`, or `Style` columns are not assumed to mean ByLevel. Locale-specific headers/delimiters need normalization to this UTF-8 comma-separated schema. JSON uses this native catalog structure:

```json
{
  "format": "vericivil.typicals.levels", "version": 1,
  "source": "Source library; ORD version; active workspace; original report hash",
  "revision": "Workspace revision / export date", "extraction_status": "report-imported",
  "levels": [{
    "name": "TS_TEST_ONLY", "description": "Synthetic example, not MDOT",
    "bylevel_color": "3", "bylevel_weight": "2", "bylevel_style": "0",
    "rgb": "#00aa66", "lineweight_mm": 0.35, "dash_ft": [], "plot": true
  }]
}
```

`report-imported` means the file passed structural validation; it is not an independent claim of MDOT authenticity. CSV imports record SHA-256 of the received UTF-8 report. Projects embed the versioned catalog and source metadata. JSON catalogs can retain additional source hashes/metadata. The importer cannot authenticate a user-supplied report; verify it in Bentley before project use.

## DXF → ORD / MicroStation acceptance procedure

1. Choose the coordinate foot definition before design/export. International foot uses DXF `$INSUNITS=2`; US survey foot uses `21`. DXF is R2018, full scale, with X=local offset and Y=elevation, Z=0. It has no map CRS. The project unit selector **reinterprets**, rather than converts, coordinate values; inches always mean 0.0254 m.
2. Resolve all Levels issues and export DXF. Save its readable export report. Entities include native LINE, CIRCLE, TEXT, SOLID arrowheads and DIMENSION; dimensions include editable anonymous display blocks. Every engineering entity is assigned an imported TS_ layer; entity color/style/weight use ByLayer. Layer true color avoids DGN-index/ACI confusion. DXF has a neutral `txt` text style; proprietary workspace fonts are not bundled or claimed to be preserved. In the view, each actual level has one visibility toggle for all its assigned drawing roles.
3. In the installed ORD/MicroStation version, File → Open the DXF (or attach/import into a scratch DGN). Check source units and any unit conversion prompts; disable unintended rescaling. Measure a 12 ft reference lane and its .24 ft elevation drop, the 6 ft shoulder with .24 ft drop, and 3 ft roadside rise with 9/12 ft runs in the starter. Check the exact foot type, origin, layer names, RGB and ByLevel mappings against the report. US survey feet may be interpreted differently by older importers; resolve that explicitly before saving.
4. Inspect dimension/leader/text editability, layer visibility/Plot flags, font substitution and simplified styles. Apply licensed workspace text/dimension styles as needed. Save As **DGN** using the project's approved seed, then reopen and repeat dimensional/level checks. Print through the actual MDOT plotting configuration and compare with the exported vector sheet. VeriCivil's monochrome sheet is a generic DOT-style sheet, not a reproduction of MDOT pen-table rules or an official title border.
5. Record exact ORD/MicroStation version, workspace revision and measured residuals in a project QA record. Passing serialization tests does not establish receiving-application compatibility. ORD was not installed/run for this implementation.

Bentley documents the separate [Import Template command](https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0018137) for ORD 10.07.03.18+. Follow that version's Help/video to select supported design linework in the DGN, import into Create Template, identify origin/components, then assign point names, component features, materials and constraints. Select section geometry only; exclude sheet annotations/ground where inappropriate. Inspect the result in Template Editor and test a controlled corridor drop. A CAD drawing is not a constrained ORD template: imported graphics need explicit civil semantics and validation. Direct ITL/DGN generation and a companion plugin are **not implemented**.

## Architecture and changed files

- `typicals/model.py`: versioned native model, validation, analytical dependency chains, locked-point conflict checks and persistence. No UI or export dependencies.
- `typicals/workspace.py`: versioned CSV/JSON report ingestion and mapping/export gate.
- `typicals/drawing.py`: shared drawing primitives, dimensions, annotations and style lookup.
- `typicals/exports.py`: ezdxf and ReportLab exporters plus SVG serialization; existing dependencies, no additional packages.
- `typicals/service.py`, `typicals/__init__.py`: native/Pyodide service boundary and engine version.
- `web/app/TypicalsApp.tsx`, `typicals.css`, `calculators/typicals/page.tsx`: editor/route. `web/lib/typicals-history.ts`: immutable bounded history.
- `calculators/catalog.py`, `vericivil_service.py`, `web/app/CalculatorCards.tsx`: discovery/runtime integration.
- `web/desktop/renderer.tsx`, `prepare-runtime.mjs`, `desktop/{main,projects,security}.cjs`: offline workspace, menu switch, existing native saves/recovery and export extensions.
- `scripts/inventory_typicals_workspace.py`, `.gitignore`: private workspace inventory and packaging boundary.
- `test_typicals.py`, `tests/fixtures/typicals_synthetic_levels.csv`, `web/tests/{typicals-history.test,pyodide-parity,rendered-html.test}.mjs`, `desktop/tests/typicals-smoke.cjs`: synthetic checks; no ORD dependency or proprietary binary CI fixtures.
- `web/package.json`, generated calculator/release metadata, `app_info.py`: test wiring and application version 1.8.0, greater than verified release v1.7.1.

The existing `super_dxf.DxfWriter` was inspected. It is tailored to Superelevation records and ACI-based styling; Typicals uses the already installed ezdxf directly for true color, explicit linetypes, circles and native dimensions, preserving those existing exports untouched.

## Validation and roadmap

Reproduce with `python3 -m unittest -v`; from `web`: `npx tsc --noEmit`, `npm run lint`, `npm test`, `npm run desktop:build`, `npm run desktop:test`, `npm run desktop:test:offline`, and `node ../desktop/tests/run-typicals.cjs`. Use Homebrew Node on this Mac as described above. PDF/scene inspection artifacts and logs are local under `local/typicals/`. Full final results are recorded in `local/typicals/validation.md` after the checks run.

Milestone 1 implements the basic rural section workflow, report import, mapped editable CAD export and vector sheets. Its remaining external acceptance is an actual Bentley level report and a measured ORD round trip. The pen-table references do not fill that evidence gap.

- **Milestone 2:** auxiliary lanes, medians, curbs/gutters, sidewalks, ditches, foreslope/backslope chains and ground daylighting, barriers; general connections/constraints, component preset files, full text/dimension/RSC/plot mappings and better annotation routing.
- **Milestone 3:** a second presentation renderer using `model.solve()` geometry, colored material/terrain fills, licensed decorative assets, vehicles/people/landscaping, existing/proposed comparisons and high-resolution PNG. No decorative asset may change engineering coordinates. No presentation-mode placeholder is exposed now.
- **Milestone 4:** actual ORD compatibility matrix, supported template-import workflow trials, then investigate documented DGN/ITL interfaces or an ORD companion. Require proof before claiming native civil-model output.
