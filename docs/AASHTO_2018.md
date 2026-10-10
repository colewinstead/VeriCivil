# AASHTO 2018 implementation and acceptance record

Profile: `aashto-green-book-2018-2019-10`. Application 1.6.0; calculation engine 1.3.0. Work is on `codex/aashto-table-corrections`; no merge, release, deployment, or publication of restricted sources is authorized.

This is a **limited profile requiring independent engineering review**, not a claim of complete Green Book implementation or PE approval. Continuous Method 5 rate calculation, Table 3-13, and Tables 3-17 through 3-20 are excluded. The limits below are enforced rather than filled with MDOT/TDOT assumptions.

## Sources and rights

- AASHTO, *A Policy on Geometric Design of Highways and Streets*, seventh edition, 2018: Tables 3-8 through 3-12; §§3.3.5.1, 3.3.8.2.1–3.3.8.2.3, 3.3.8.4.6, and 3.3.8.6; Table 3-15; Table 3-16a; Equations 3-23, 3-24, and 3-25; Figure 3-8. Publication information: [AASHTO bookstore](https://store.transportation.org/).
- [October 2019 seventh-edition errata](https://downloads.transportation.org/GDHS-7-Errata.pdf): corrected Table 3-12 radius, Table 3-16 runoff values, and Figure 3-8 positioning. Equation 3-11 also has an erratum; this profile does not implement the continuous Method 5 equations that use it.
- [FHWA 2018 Green Book workbook](https://highways.dot.gov/federal-lands/design/tools/superelevation-tables), revision 15-Apr-2022: identified as the independent numerical validation reference. **Numerical comparison remains outstanding:** the linked XLSX download returned HTTP 403 in this environment. Do not treat listing its source URL as completed numerical validation.

The supplied PDF contains AASHTO/IHS reproduction restrictions. Possession of a PDF, XLSX, or CSV does not establish redistribution permission. Permission to publish the table grids has **not** been established. The supplied PDF, corrected XLSX, and CSV remain local and uncommitted. Browser bundles include equations, validation code, and reviewed-content hashes, not the copyrighted grids. The workbook import reads values locally and rejects changes to the reviewed radius/runoff cells; revised data need a new review/version. It does not establish the user's license rights.

Projects embed the locally imported criteria values so they can reopen reproducibly. Keep those project files private unless sharing rights have been established. Reports contain project values and references, not entire source tables. A one-sheet CSV is not a replacement for the complete seven-sheet corrected workbook.

## Criteria and automatic rates

Maximum rates are 4%, 6%, 8%, 10%, and 12%, mapped to Tables 3-8, 3-9, 3-10, 3-11, and 3-12 respectively. Published table speeds are used without speed interpolation. Table 3-8's 4% maximum is limited to an applicable urban freeway/high-speed context and speeds through 60 mph. Low-speed urban streets/Method 2/Table 3-13 are unsupported; Table 3-13 is not a relative-gradient table.

Automatic rate selection requires the reviewed local workbook. It supports the verified NC/RC threshold regions and **unambiguous exact published radius rows**. Between-row interpolation, continuous Method 5 evaluation, and ties caused by published radius rounding are not verified. These cases require an independently checked manual rate; no conservative row-selection rule is invented. With a workbook present, even manual rates must meet its supported speed/minimum-radius limits. Without one, radius/rate applicability remains an explicit manual-review responsibility.

Relative gradients use §3.3.8.2.1, with inverse-gradient interpolation at intermediate published speeds and explicit classification in results. Undivided sections use the unrounded Table 3-15 footnote. One-way sections use the unadjusted gradient, with no assumed multilane ramp discount. Equation 3-23 is evaluated using the controlling fixed-pivot edge rise across the actual section sequence, including the reverse-crown breakpoint. Equation 3-24 is used for the conventional crown case; other supported sections derive runout from their actual adverse edge movement. Favorable single slopes have no fabricated runout or crown-removal events.

Corrected Table 3-16a values are retained as published whole-foot values when applicable to 12-ft lanes, centerline rotation, and one/two lanes on each side. Other supported dimensions use calculated values without display rounding in the engine. Published rounding is disclosed and allowed in gradient checks; undersized manual lengths are rejected. Circular placement checks Equation 3-25 using actual bank attained at PC/PT. Profile results identify each lookup, calculation, interpolation, project placement, and manual override.

## Supported sections

- One roadway section: two-way undivided or one-way carriageway/ramp. A one-way section does not create opposing lanes or infer a second divided carriageway.
- Equal positive lane widths; one to seven actual lanes, subject to crown and Table 3-15 applicability limits. Explicit widths are ordered left to right relative to increasing station.
- Symmetric crowned sections with the crown at carriageway center and on a lane boundary, equal 1.5–2.0% normal slopes, or one-way uniform sections with a signed 1.5–2.0% initial slope. A positive initial uniform slope rises toward physical left.
- A fixed centerline, left pavement edge, or right pavement edge pivot. Results identify an edge pivot as inside/outside the curve and record actual edge offsets/distances and elevations relative to that pivot.

Figure 3-8's crowned sequence is represented explicitly: outside lanes reach level, inside lanes retain normal slope until the reverse-crown section, then the section rotates as a plane. Applying an edge pivot translates section heights relative to that fixed edge and checks its controlling gradient; it does not just change a runoff multiplier. Lane-table slope signs retain VeriCivil's outward-from-alignment convention and recorded lane side. Relative edge heights are physical left/right heights; they are not absolute elevations or a vertical alignment.

Unequal widths, off-center/asymmetric crowns, crowns through a lane, shoulder rotation, moving pivots, independently rotating divided carriageways, and out-of-scope rotated lane counts are rejected. Longitudinal grades, edge-profile vertical-curve smoothing (§3.3.8.7), drainage design, and interchange-specific criteria outside the recorded scope still require project design review.

## Placement

For circular curves, AASHTO requires an explicit runoff-on-tangent percentage. Entry runoff runs from PC − pLr to PC + (1 − p)Lr; exit placement is mirrored about PT. Runout is adjacent to the outer runoff ends. Percentages do not change runoff length or geometry. Entirely-on-tangent/curve selections trigger review; Equation 3-25 or overlapping runoffs may block them. Imported tangent availability and alignment limits are checked.

Existing MDOT 70/30 **runoff** placement and TDOT 50/50 **total runout + runoff** placement remain their defaults. Their optional project override uses a runoff percentage and records the departure. A TDOT default is never relabeled as 50/50 runoff. MDOT reverse-pair coordination cannot silently overwrite a custom placement or an AASHTO transition.

For established spirals, PC/PT inputs become SC/CS. Full super is fixed at SC and CS and maintained on the entire circular arc. Unequal spiral lengths are checked independently:

| Runout option | Entry | Exit | Minimum spiral |
|---|---|---|---|
| On tangent (AASHTO default) | Runout ends at TS; runoff finishes at SC | Runoff starts at CS; runout follows ST | Lr |
| In spiral | Initial section holds until SC − (Lt + Lr), then transitions finish at SC | Runoff starts at CS, then runout; initial section holds to ST | Lt + Lr |

Short spirals block calculation. No geometry is lengthened, no runoff is stretched, and no transition is moved onto the circular arc to fit. Equal runoff/spiral lengths with on-tangent runout are distinguished from project placement departures. Longer on-tangent spirals can hold the applicable outside-lane-level/zero-crown section, requiring explicit acknowledgement and drainage review. In-spiral runout is recorded as a project placement choice, not automatically asserted to be standard AASHTO practice.

Zero-crown findings record the actual hold interval and length. They recommend in-spiral runout only when the section needs conventional runout and the affected spiral accommodates Lt + Lr; otherwise they state its deficiency. A favorable uniform initial slope is an initial-section hold, not a zero-crown hold. The method never changes automatically.

## Geometry, QA, and outputs

LandXML imports retain an ordered line/arc/clothoid model. Supported clothoids have one zero-curvature end and one circular-curvature end, finite positive length, endpoints, rotation, and sufficient preceding geometry to establish heading. Both directions, unequal entry/exit lengths, and mixed simple circular/spiral curve groups are supported. Endpoints, headings, curvature joins, and arc constraints are checked without warping geometry. Unsupported spiral types, compound/partial definitions, missing orientation, inconsistent rotations, or unsupported geometry elements are rejected.

Adaptive integration targets 1e-7 native units per coordinate axis; source endpoint consistency tolerance is 0.001 native units. DXF sampling uses a 0.01-native-unit chord-error bound and records it in warnings. Tests compare synthetic geometry against independent power-series/analytic arc calculations, not the same solver used as its own oracle.

Continuous station distance is internal. Repeated civil labels require an explicit region suffix, e.g. `10+00R2`, or a range that leaves one possible location. Imported group labels include a region when needed. Station equations are validated for consistent back/ahead/internal stations. A prior defect allowed a broad range to silently select the first of repeated stations; ambiguous ranges now reject rather than choose a location.

Foot-based calculations only. Metric geometry cannot feed this US-unit profile. Imported units/CRS declarations are retained, including explicit US survey foot declarations; no coordinate reprojection or station-unit conversion is performed, and an opaque `foot` declaration is not promoted to an exact foot type. Manual station-only inputs remain available but need independent tangent/geometry checks; coordinate overlays require matching imported geometry.

Results/projects record resolved sections, pivots, unit/source identity, criteria edition/errata, calculation-source classifications, actual/required spiral lengths, anchors, holds, warnings, and overrides. Browser calculations, lane tables, lookup, reports, and exports all consume the Python results. AASHTO reports omit MDOT artwork.

Corridor QA retains blocking findings for short spirals, overlaps, unavailable tangent/runout space, invalid inputs/order, geometry mismatch, and gradient violations; excess spiral length is a review finding, not an AASHTO maximum-spiral violation. Browser failure diagnostics can save with a project and produce a diagnostics-only PDF. Exporters recheck AASHTO results against their saved inputs and block stale results and unsafe transition overlaps.

ORD CSV's verified LS/RS mapping supports two lanes about their common edge, or one uniform lane about a pavement edge. Other fixed-pivot configurations cannot be faithfully represented by that mapping and are explicitly blocked for CSV, while supported reports/geometry DXF remain available. AASHTO CSV uses optional PointType U; classifications remain in the project/report. Lane names and actual imported pivot behavior require ORD verification. Geometry DXF is a graphics handoff, not a constructed civil corridor.

## Validation and outstanding acceptance

Automated tests cover all five maximum-rate options, every locally available radius cell against the source PDF plus errata, all published rate boundaries, corrected runoff/equation agreement, gradient/lane factors, crown and pivot sequences, percentage placement, both spiral methods, unequal/short/long spirals, continuity, station equations/regions, invalid definitions, actual-lane exports, stale/overlap blocking, project/report diagnostics, entitlements, and existing MDOT/TDOT regressions. Native Python/Pyodide parity covers the new section and placement cases and independent synthetic clothoid coordinates. Restricted-source tests explicitly skip when their private inputs are absent.

A local CROSSGATES ORD LandXML check evaluates eight spirals/four curve groups, compares evaluated endpoints to ORD-serialized endpoints, and checks the declared USSurveyFoot unit and station equation. This is **serialized-file geometry evidence**, not a native ORD/CAD overlay or corridor round trip. Private real-file content is not added to the repository.

Required final commands: profile integration validator, `python3 -m unittest -v`, `git diff --check`, TypeScript check, lint, and `npm test` (production build, browser policy/rendering tests, Pyodide parity). The Mac needs a temporary `python` alias pointing to its `python3` for the repository's existing npm prebuild command; no project dependency change is needed.

Completed locally on 10-Oct-2026: all **208 Python tests passed**, including the private table/PDF transcription checks and serialized CROSSGATES geometry check. The profile integration validator, TypeScript check, lint, and `git diff --check` passed. `npm test` passed the production build, **31 browser policy/rendering tests**, and Python/Pyodide parity (all five maximum rates, placements, pivots, ramps, CSV, and clothoid import/coordinates). The generated AASHTO PDF was rendered and visually inspected. These results do not constitute PE approval or a native application acceptance test.

Batch failures identify the affected source curve and preserve its findings; projects retain diagnostic findings. Browser and desktop can produce a diagnostics-only PDF when the current AASHTO calculation is blocked. Actual-lane diagrams and lookup use the section events and physical edge heights, with runoff/runout references selected from the recorded transition intervals.

Outstanding acceptance: redistribution permission; independent FHWA workbook comparison; continuous Method 5/between-row rule verification; native Excel inspection/recalculation; native ORD round trip and actual CAD overlay review; project PE approval. Automatic alignment construction, omitted spiral-design/limiting-rate tables, expanded MDOT/TDOT edge/ramp models, and unsupported section/export configurations remain deferred.
