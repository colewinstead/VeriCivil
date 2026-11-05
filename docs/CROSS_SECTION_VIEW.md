# Superelevation cross-section view

The browser and Electron workspaces share **Cross Section** in the engineering analysis tabs. Choose a curve, drag the station slider, enter a station and choose **Go**, or step to the previous/next calculated event. Arrow keys move one internal foot. Wheel/trackpad movement advances by station only while the slider has focus. Station entry uses the existing equation-aware parser; ambiguous stations require an explicit station region such as `R2`, following the parser's diagnostic.

The view looks ahead along increasing alignment station. It defaults to **5× vertical exaggeration**. Physically defined sections also offer **True scale**. Framing stays fixed for the selected curve, so rescaling does not disguise pavement rotation. Lane slope signs retain the recorded outward-from-alignment convention; physical edge heights are relative to the fixed pivot, not survey elevations or a vertical alignment.

## Implemented roadway support

This is an audit of this application's implementation, not the full scope of the agency publications.

| Criteria profile | Calculation support | Cross-section display | Export boundary |
| --- | --- | --- | --- |
| MDOT | Centerline/outside-edge calculation cases; rural, urban, and local criteria. The rotated-lane lookup can round or substitute lane counts. | Labeled left/right slope schematic. Inputs do not establish individual lane distribution or complete physical pivot geometry. | Existing CSV/PDF/DXF behavior is unchanged; a schematic adds no physical section/export capability. |
| AASHTO Case II | Paired carriageways, 1–7 equal-width travel lanes per side; separate uniform initial slopes and median-side travel-lane pivots. | One baseline station, actual signed offsets, two level pivots, dimensioned median interval and recorded lane edges. | Common relative profile only; shoulders, median grading, absolute elevations and Case II ORD CSV are excluded. |
| TDOT | Undivided roadway lane events; whole-roadway lane counts 2–6; urban/rural criteria. Divided output is explicitly blocked. | Labeled left/right slope schematic; no invented individual lanes, dimensions, or pivot. | Recorded divided-roadway source drawings do not enable divided-roadway exports. |
| AASHTO | One equal-width two-way undivided or one-way/ramp section; 1–7 actual lanes subject to centered-crown and Table 3-15 applicability limits. Fixed centerline, left-edge, or right-edge pivot. | Actual recorded lane widths, edge heights, and pivot. Crowned sections are centered and symmetric; single-slope sections are one-way. New ramps offer edge pivots; saved centerline pivots remain explicit. | ORD CSV mapping remains limited to two lanes about their common edge or one uniform lane about a pavement edge. Other supported section geometry is not automatically CSV-compatible. |

Two-way undivided includes opposing travel lanes separated by centerline striping. It does **not** model two carriageways separated by inside shoulders and a median/barrier. The one-way model represents a supported travel-lane section, not an entire divided highway.

Sources in this repository: `Super.py` (`lanes_to_n1_bw`, TDOT validation and profile calculation paths); `tdot_criteria.py` (`lane_factors`); `aashto_superelevation.py` (section validation, fixed-pivot edge heights and export validation); `super_service.py` (`application_manifest`); and [AASHTO scope](AASHTO_2018.md). Regression evidence lives in `test_tdot_criteria.py`, `test_aashto_criteria.py`, `test_super_cross_section.py`, and `web/tests/pyodide-parity.mjs`.

## Missing roadway models

- Independently rotating divided carriageways, medians/barriers, and shoulders with their own slope/rotation rules.
- Unequal lane widths, asymmetric/off-center crowns, and crowns through a lane.
- Moving pivots, station-dependent widening, lane additions/drops, and ramp-to-mainline warping.
- Longitudinal grade, absolute elevation, pavement-layer thickness, and drainage design.

Rural/urban/local criteria choices do not supply these physical features. The view does not construct missing geometry or relax existing unsupported-section/export gates. Existing AASHTO legal and independent engineering-review limitations still apply.

## Extension boundary

`super_cross_section.py` presents existing results as ordered segments with endpoint coordinates, optional widths/pivot, labels, and an explicit physical/schematic/unavailable mode. `curve_diagram` includes stable section bounds; `diagram_lookup` adds the station's section packet. String stations use the shared parser, while numeric stations retain internal continuous feet. These are additive presentation fields, not new saved-project or export formats.

Corridor packets also include `cross_section_frames`: Python-generated geometry and numeric slope percentages at profile breakpoints. While scrubbing, the shared browser/Electron view interpolates these presentation values together and marks slope labels with **≈**. After 100 ms of inactivity, or immediately on release, it requests the exact Python station result. The drawing stays mounted; the edge-height table retains its last exact values and identifies their station until the new result arrives. Preview values do not change saved projects, calculation criteria, or exports.

Preview station labels retain station notation. Python supplies each frame's civil-station origin and equation region, with a frame at every station equation so the preview never interpolates across a station-number jump. Between frames, equation-bearing previews include an explicit region suffix (for example, `10+12.852R2`); exact labels retain the shared Python formatter's existing convention.

Arrow stops show the recorded event below the station. Divided-section events identify the participating left/right lane or lanes; coincident events retain their separate lane associations. Arrow tooltips name the destination event and station. During a drag the caption stays on “Scrubbing…” even across event stations, then updates once on release; keyboard and wheel navigation settle on release or inactivity. Its reserved space prevents layout shifts, and the subtle text-color transition respects reduced motion.

New roadway models must supply verified Python geometry and rotation behavior, then adapt their results to those segments. The React SVG maps supplied coordinates to pixels; it contains no agency-specific section calculations. Do not create a roadway plug-in framework before a second verified model needs it.

Validation includes analytical crown/full-bank and fixed-pivot checks in both directions, event/midpoint agreement with existing edge lookup, multi-lane/retained ramps, equation-aware station entry, legacy schematic limits, unavailable geometry, native/Pyodide parity, and latest-request queue tests. `npm run desktop:test:cross-section` exercises the actual Electron renderer and worker, including native keyboard/station input and scale switching; set `VERICIVIL_CAPTURE_DIR` to retain light/dark screenshots.
