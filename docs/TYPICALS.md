# VeriCivil Typicals — component designer preview

Local parametric section drafting with ordered, editable components, tracked by issue #76. This is a generic engineering drawing tool, not an approved MDOT standard or a native ORD corridor/template model. No criteria tables or existing superelevation formulas changed. No implementation push, release, or Site deployment is part of this work.

## Launch and use

From `web`, run `npm run dev`, then open `/calculators/typicals`. For the offline Electron app run `npm run desktop:dev`, then **Tools → VeriCivil Typicals**. Tools → Superelevation returns to the existing calculator. Select the matching tool before opening a project of that type. On this Mac the bundled Node executable cannot load Rolldown's native binding because of its signing identity; `PATH=/opt/homebrew/opt/node@22/bin:$PATH npm run dev` (and the same prefix for build/desktop commands) uses the verified Node 22 installation. The separate Node 26 binary currently fails to load its simdjson shared library; no global Node or Homebrew settings were changed.

1. Start with **New section**. In **Section**, choose Left or Right, then select a component in the list or drawing. The chain runs outward from CL. Add inserts after the selection; **Inward / Outward**, **Duplicate**, and **Remove** edit its order. Without a selection, lanes default beside existing lanes, medians default at the inside, and other components default before the roadside chain.
2. Edit component dimensions and names in the inspector. Positive planar cross slopes rise **outward** on either side. Numeric fields apply on Enter or leaving the field. Units remain explicit international or US survey feet; curb and pavement thicknesses use international inches. The unit selector reinterprets coordinate values and does not convert them.
3. Available component types: travel lane, auxiliary lane, shoulder, median, sidewalk, curb/gutter, ditch, side slope, barrier, guardrail outline, retaining wall, and custom point profile. The shared Python library defines parameter fields and defaults; React does not calculate section geometry. Defaults are generic examples, never approved MDOT designs.
4. A ditch exposes foreslope drop/H:V, bottom width, backslope H:V and rise. A retaining wall exposes thickness and signed grade step; the following component connects to its changed grade. Barriers/guardrail occupy their footprint without raising the following grade to their top. Their profiles are schematic dimensional geometry, not structural, reinforcement, hydraulic, accessibility or crashworthiness designs.
5. A custom profile uses local `[outward offset, rise]` points starting at `[0,0]`; its last point connects the next component. Non-paved profiles can close, step vertically, or overhang. Paved custom profiles require strictly increasing offsets to keep pavement boundaries unambiguous.
6. **Apply pavement structure** opts graded components into the project-wide layer stack. **Materials** changes that stack. Connected paved components have continuous boundaries; unpaved medians, barriers, walls and other non-paved components split it into separate runs. The engine never draws a fictitious pavement bridge over those gaps. Independently specified per-component material stacks remain future work.
7. **Save component preset…** stores the selected component in `.vccomponent` JSON. **Import component preset…** inserts a validated copy on the chosen side with a fresh ID/end-point name. Dimensions, profile points, names and paved flag persist; CAD levels remain project-specific. Save a whole project under another name for a reusable complete section.
8. Shift/middle-mouse drag pans; wheel/buttons zoom; Fit restores extents. Measure picks two coordinates, optionally snapping to calculated vertices and named end points. Select any component's linework to edit it. Named end points and vertex locks reject conflicting edits atomically. Unlock a point before deleting/renaming its component. Undo/redo stores 100 session edits, including component additions/removals/order and level assignments.
9. **Levels** maps used categories to actual imported TS_ levels. A component's **Component CAD level** overrides its category using another imported level. Each actual level has one visibility toggle for all assigned geometry. Missing used mappings block DXF. The existing read-only workspace/report procedure below still applies.
10. **Sheet** edits metadata, semicolon-separated station ranges, notes, scale, annotation precision, standard font, independent print weights and sheet size. Computed dimension tiers, slope arrows, material bubbles, thickness/plan-grade leaders, ground hatching and centered title use the same coordinates as CAD. Text offsets provide manual corrections where dense annotations need detailing. Fonts use an explicit .78 width factor; no proprietary MDOT font is bundled.
11. PDF/SVG are vector sheets at explicit physical size. Print at 100%, without fit-to-page. Oversized drawings fail with a recovery message: increase ft/in or paper size. The on-screen sheet fits its viewport without altering export scale. DXF remains full scale. Standard PDF fonts support Western text; SVG retains Unicode.

## Project compatibility

New projects save as **version 2**, with ordered `left` / `right` component arrays. Each component carries a stable ID, named end point, kind, editable parameters and paved flag. Metadata, layers, catalog, mappings, locks, annotations, print and presentation settings remain in the native JSON.

Version-1 projects remain readable. On open the engine converts each side's lane, shoulder and roadside slope into equivalent components while retaining the original end-point names and all seven original coordinate values. It preserves units, materials, metadata, settings, maps and locks. Reading never changes the source file. The editor identifies the conversion and requests Save As for the first native save; browser downloads use `section.typicals.v2.json`. Keep the original file for rollback: the older fixed editor cannot read version 2. Unknown/incomplete legacy geometry is rejected instead of silently discarded.

Version 2 supports up to 60 components per side and 40 points per custom profile. These are implementation bounds, not agency criteria. Connections are explicit sequential endpoint dependencies, not a general nonlinear constraint solver or automatic ground daylighting system.

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

- `typicals/model.py`: version-1 migration, version-2 component model, analytical connected geometry, separated paved runs, locks and persistence. `typicals/components.py`: shared parameter library and geometry for all 12 component types. No UI or export dependencies.
- `typicals/workspace.py`: versioned CSV/JSON report ingestion and mapping/export gate.
- `typicals/drawing.py`: shared drawing primitives, dimensions, annotations and style lookup.
- `typicals/exports.py`: ezdxf and ReportLab exporters plus SVG serialization; existing dependencies, no additional packages.
- `typicals/service.py`, `typicals/__init__.py`: native/Pyodide service boundary and engine version.
- `web/app/TypicalsApp.tsx`, `TypicalsComponents.tsx`, `typicals.css`, `calculators/typicals/page.tsx`: editor/route. `web/lib/typicals-types.ts`: renderer types. `web/lib/typicals-history.ts`: immutable bounded history.
- `calculators/catalog.py`, `vericivil_service.py`, `web/app/CalculatorCards.tsx`: discovery/runtime integration.
- `web/desktop/renderer.tsx`, `prepare-runtime.mjs`, `desktop/{main,projects,security}.cjs`: offline workspace, menu switch, existing native saves/recovery and export extensions.
- `scripts/inventory_typicals_workspace.py`, `.gitignore`: private workspace inventory and packaging boundary.
- `test_typicals.py`, `tests/fixtures/typicals_synthetic_levels.csv`, `web/tests/{typicals-history.test,pyodide-parity,rendered-html.test}.mjs`, `desktop/tests/typicals-smoke.cjs`: synthetic checks; no ORD dependency or proprietary binary CI fixtures.
- `web/package.json`, generated calculator/release metadata, `app_info.py`: test wiring and application version 1.8.1, greater than verified release v1.7.1.

The existing `super_dxf.DxfWriter` was inspected. It is tailored to Superelevation records and ACI-based styling; Typicals uses the already installed ezdxf directly for true color, explicit linetypes, circles and native dimensions, preserving those existing exports untouched.

## Validation and roadmap

Reproduce with `python3 -m unittest -v`; from `web`: `npx tsc --noEmit`, `npm run lint`, `npm test`, `npm run desktop:build`, `npm run desktop:test`, `npm run desktop:test:offline`, and `node ../desktop/tests/run-typicals.cjs`. Use Node 22 on this Mac as described above. PDF/scene inspection artifacts and logs are local under `local/typicals/`. Full final results are recorded in `local/typicals-components/validation.md` after the checks run.

The original rural workflow now uses the version-2 component editor. Additions and source-file migration have analytical, native/Pyodide and actual UI checks. An actual Bentley report and measured ORD round trip remain external acceptance tasks; pen-table name references cannot fill that evidence gap.

- **Remaining component work:** independently specified material stacks per component, full engineered structural details, curved profiles, ground daylighting, general constraints and sophisticated annotation routing. The current geometry is fully editable through supported parameters and custom point profiles; no claim of every civil-design analysis is made.
- **Presentation milestone:** a second renderer using the same `model.solve()` results, material/terrain fills, licensed decorative assets, existing/proposed comparisons and high-resolution PNG. No decorative asset may change engineering coordinates.
- **ORD milestone:** actual compatibility matrix and template-import trials, followed by supported DGN/ITL interfaces or an ORD companion only after proof.

The calculator directory now uses equal, bounded previews and an authentic compressed editor screenshot at `web/public/showcase/typicals-editor.webp`; its capture provenance is stored alongside it. The former oversized illustrative SVG is removed. This changes the catalog presentation without changing other calculator engines.
