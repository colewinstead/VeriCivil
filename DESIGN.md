---
name: VeriCivil Electron Superelevation Preview
description: A local engineering review desk with a compact inspector and station-aware results.
colors:
  teal-light: "#126e5e"
  teal-dark: "#67d8b6"
  lane-teal-light: "#137869"
  lane-amber-light: "#90600d"
  amber-light: "#8c590e"
  amber-dark: "#e6b76a"
  error-light: "#ad302c"
  error-dark: "#ff9690"
  ink-light: "#1f302c"
  ink-dark: "#e8f0ed"
  muted-light: "#536960"
  muted-dark: "#a0b4ab"
  paper-light: "#eef3f1"
  paper-dark: "#0e1714"
  panel-light: "#ffffff"
  panel-dark: "#14211b"
  raised-light: "#f3f7f5"
  raised-dark: "#1d2d25"
  line-light: "#cedbd4"
  line-dark: "#35483e"
  navy-light: "#21463d"
  navy-dark: "#234438"
typography:
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "19px"
    fontWeight: 650
    letterSpacing: "-.025em"
  section:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "16px"
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "13px"
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "12px"
    fontWeight: 600
    letterSpacing: "normal"
  measurement:
    fontFamily: '"SFMono-Regular", Consolas, monospace'
    fontSize: "20px"
    fontWeight: 600
  table:
    fontFamily: '"SFMono-Regular", Consolas, monospace'
    fontSize: "12px"
    fontWeight: 500
rounded:
  field: "5px"
  control: "6px"
  panel: "9px"
spacing:
  compact: "6px"
  control-gap: "7px"
  field-gap: "14px"
  gutter: "16px"
  panel: "18px"
  toolbar-inline: "20px"
components:
  button-secondary-light:
    backgroundColor: "{colors.raised-light}"
    textColor: "{colors.ink-light}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
    typography: "{typography.body}"
  button-primary-light:
    backgroundColor: "{colors.teal-light}"
    textColor: "{colors.panel-light}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  button-primary-dark:
    backgroundColor: "{colors.teal-dark}"
    textColor: "{colors.panel-dark}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  field-light:
    backgroundColor: "{colors.raised-light}"
    textColor: "{colors.ink-light}"
    rounded: "{rounded.field}"
    padding: "7px 9px"
  panel-light:
    backgroundColor: "{colors.panel-light}"
    textColor: "{colors.ink-light}"
    rounded: "{rounded.panel}"
    padding: "18px"
---

# Design System: VeriCivil Electron Superelevation Preview

## Overview

**Creative North Star: "Alignment review desk"**

This system applies to the Electron Superelevation preview, whose entry point is `web/desktop/renderer.tsx` and whose overrides are in `web/desktop/desktop.css`. It does not replace the public website, browser calculator, or RoadStation visual systems. The renderer shares calculator components while applying its own desktop composition and appearance tokens.

The desk is compact and calm: inputs sit beside a larger engineering review area, with station-aware profiles as the working graphic. Borders and green-tinted neutral surfaces organize the workspace. Platform control typography keeps attention on measurements, source criteria, and local file actions. The appearance follows the operating system, including the contrast of the station cursor.

**Key Characteristics:**
- Compact inspector beside independently scrolling results.
- System control typography with monospaced, tabular engineering measurements.
- Green-tinted neutral surfaces and restrained borders in light and dark appearances.
- Teal and amber lane profiles, with dashed right-side traces.
- Persistent export actions and explicit preview and synthetic-data labels.

## Colors

The palette uses quiet green neutrals for work surfaces, reserving stronger teal and amber for actions, engineering traces, and status.

### Primary
- **Review teal:** `teal-light` and `teal-dark` supply primary actions, selection, and focus. The dark appearance uses a lighter teal against its dark panel.

### Secondary
- **Lane teal:** `lane-teal-light` supplies the light appearance's first profile; dark profiles share review teal.
- **Lane amber:** `lane-amber-light` and `amber-dark` distinguish the opposing lane profile. Amber status text and warning borders use `amber-light` and `amber-dark`.
- **Action-needed red:** `error-light` and `error-dark` identify required attention.

### Neutral
- **Desk paper:** `paper-light` and `paper-dark` sit behind the workspace and footer.
- **Panel surface:** `panel-light` and `panel-dark` contain the inspector, results, and toolbar.
- **Raised surface:** `raised-light` and `raised-dark` identify fields and nested review areas without shadows.
- **Reading ink:** `ink-light` and `ink-dark` carry primary text and the selected-station cursor.
- **Secondary ink:** `muted-light` and `muted-dark` carry labels, helpers, and chart axes.
- **Divider green:** `line-light` and `line-dark` separate sections and outline controls.
- **Table navy:** `navy-light` and `navy-dark` back lane-table headings.

**The Appearance Pair Rule.** Change light and dark roles together; station cursors use reading ink rather than a fixed white stroke.

## Typography

**Control Font:** Platform sans (`-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, then sans-serif).
**Measurement Font:** Platform mono (`SFMono-Regular`, `Consolas`, then monospace).

The build has no separate display typography role. Its application title is a compact utility heading. Labels use ordinary case and normal tracking; measured results use monospaced numerals and tabular figures.

### Hierarchy
- **Title:** Compact application identity (`19px`, weight `650`, tracking `-.025em`).
- **Section:** Inspector and result section headings (`16px`).
- **Body:** Controls and ordinary interface text (`13px`); buttons use weight `600`.
- **Label:** Field labels and helpers (`12px`); labels use weight `600`, while longer helpers use line-height `1.55`.
- **Measurement:** Primary result values (`20px`, weight `600`) in the mono stack.
- **Table:** Station and slope records (`12px`, weight `500`) in the mono stack; table headers and secondary result notes use `11px`.

**The Measured Value Rule.** Preserve mono and tabular alignment for engineering values; do not promote status copy to the result hierarchy.

## Layout

The renderer fills the window and contains a toolbar, input-context navigation, two-pane workspace, export region, and footer. The workspace is a grid with a fixed inspector (`360px`) and a flexible review area, separated by a compact gap (`14px`). Both panes scroll independently; exports sit below them as a non-growing region.

At widths at or below the desktop breakpoint (`1200px`), the inspector narrows (`330px`), the diagram's station inspector moves underneath the plot, and overlay coordinate context moves onto a second export row. The desktop window has a minimum size (`1040 × 700px`); this is a desktop system rather than a phone layout.

Panel padding is comfortable within a dense app (`18px`). Fields separate vertically (`14px`), with compact label gaps (`6px`). The review order is metrics, warnings, diagram, criteria, lane events, then lookup. Plot height follows available window height using `clamp(160px, calc(100dvh - 560px), 300px)`; expanded analysis uses the available window.

**The Review Continuity Rule.** Keep the input inspector and review area independently scrollable while export actions remain outside their scrolling content.

## Elevation & Depth

The desktop is flat at rest. Solid panel surfaces, raised neutral fills, and fine borders establish grouping; primary panes have no shadows. A transient message alone receives the small floating shadow (`0 8px 24px #0002`). Focus is shown with a teal outline (`2px`, offset `3px`), with the inherited field focus treatment retained. Button state transitions inherit the shared duration (`.16s ease`) without movement. Reduced-motion preferences remove transitions.

## Shapes

Controls use gently rounded corners (`6px`), fields are slightly tighter (`5px`), and primary panels are broader (`9px`). Borders are fine (`1px`) and tonal. Nested criteria panels use the control radius. Rounded status tags are inherited from shared components; they are not the defining shape of the desk.

## Components

### Buttons

Compact and explicit. Secondary buttons use raised surfaces, reading ink, a divider border, and compact padding (`7px 12px`), with minimum height (`34px`). Primary actions use review teal with panel-colored text. Hover adjusts fill, border, or text without translation. Focus uses the shared teal outline; disabled buttons reduce opacity (`.55`). Native file actions retain descriptive labels such as “Save project…”.

### Inputs / Fields

Raised neutral fields with reading ink, divider borders, teal carets, and a minimum height (`36px`). Padding is compact (`7px 9px`). Labels remain above their fields, required markers remain visible, and source or unit helper text stays adjacent. Related fields form a two-column inspector grid.

### Navigation

Curve inputs and Project & LandXML are compact toggle buttons. The selected control uses panel fill, a divider border, and review teal text, with `aria-pressed` conveying state. Diagram tabs use a teal inset underline (`2px`) and panel fill when active. Native application menus provide file and editing actions.

### Cards / Containers

Primary panels use the panel surface, divider border, panel radius, and no shadow. Nested source, criteria, lookup, and station-inspector regions use raised fill. Result metrics are unboxed; they are grouped through spacing instead of individual cards.

### Status Tags

Preview status is plain secondary text alongside the product name. Criteria identification may wrap and occupies at most `65%` of its heading row. Unsaved status accompanies the Project & LandXML selector and project panel. Preserve the meaning and readable text when using shared status components.

### Station-Aware Diagram

The profile is a data graphic, not decorative artwork. Teal and amber differentiate the single curve's lane profiles, and the right side is also dashed (`7 4`). The station cursor follows the appearance's reading ink. Inline SVG controls use inherited text color and accessible button labels; icon paths are authored in `ControlIcon.tsx`. Keep axis labels, legend, engineering warnings, source criteria, and station inspection available alongside the plot.

### Cross Section

An ordinary extension of the existing review desk, shared with the browser through the **Cross Section** tab in `SuperelevationAnalysis.tsx`. `SuperelevationCrossSection.tsx` renders ordered Python geometry packets from `super_cross_section.py`; retain the incumbent controls, teal/amber lane roles, system appearance, and shared station inspector. Choose a curve, scrub or enter a station, or step to exact calculated events. Arrow keys move one internal foot; wheel/trackpad station movement applies only while the slider has focus. Invalid entry remains recoverable through the field or slider.

Look ahead along increasing station. Physical AASHTO sections show recorded lanes, widths, a fixed pivot, and relative edge heights; they default to 5× vertical exaggeration and offer 1× true scale. Preserve framing across stations within the selected curve so pavement rotation remains legible. MDOT/TDOT output remains an explicitly labeled left/right slope schematic without invented physical lane distribution, dimensions, or pivot. Its accessible SVG description includes the slope values. This presentation does not add roadway models or expand export support; keep the support audit in `docs/CROSS_SECTION_VIEW.md` authoritative.

On browser widths up to `600px`, reflow lane names, slopes, widths, and pivot labels into readable HTML below the SVG rather than shrinking SVG labels. Preserve left-to-right order, units, warnings, and the physical edge-height table. Shared styles live in `web/app/globals.css`; `web/desktop/desktop.css` supplies the existing desktop appearance overrides. Do not extend desktop-only layout rules to the phone browser.

## Do's and Don'ts

### Do:
- **Do** pair light and dark tokens and use reading ink for the station cursor.
- **Do** preserve monospaced engineering measurements, units, source criteria, and warnings.
- **Do** keep export actions outside the scrolling input and review panes.
- **Do** use authored inline SVG controls with accessible labels.
- **Do** identify synthetic examples and desktop evaluation access explicitly.

### Don't:
- **Don't** apply these desktop overrides to the public website or RoadStation.
- **Don't** substitute decorative imagery for the engineering diagram or obscure its axes and legend.
- **Don't** use character glyphs as substitutes for the authored control icons.
- **Don't** turn preview access, unsigned packaging, or local processing into claims of production release readiness.


# Scoped Extension: Guardrail Browser Calculator

## Overview

This guidance applies only to `/calculators/guardrail`, implemented by `web/app/GuardrailCalculator.tsx`, `web/app/guardrail.css`, and its page wrapper. It extends the existing public browser calculator family. The desktop tokens and rules above retain their original scope; this extension neither replaces them nor changes `.impeccable/design.json`.

Keep the compact site header and footer, practical input groups, and side-by-side near/opposing review. The working graphic is the calculation table. Product truth and engineering boundaries remain in `PRODUCT.md` and `docs/GUARDRAIL_BROWSER.md`.

## Colors

Use the public website roles from `web/app/globals.css`: dark paper, panel and raised fields; reading ink and muted helpers; divider borders; teal actions and current results; amber file status; red errors. Do not import Electron appearance overrides. The PDF action has a scoped deep teal fill with white text (`#126e5e`, hover `#105e50`); retain its readable text contrast rather than inheriting the brighter global primary-button fill.

## Typography

Use the website's Manrope sans stack for headings, controls and table labels, and IBM Plex Mono for numeric table cells. The compact page title is `2rem`, weight `650`, line-height `1.2`, with `-.025em` tracking; it reduces to `1.6rem` on phones. Section headings are `1.1rem`; field text is `.9rem`; labels are `.85rem`; helpers and table text are `.8rem`. The phone table is `.75rem`. Keep sentence-case table labels, right-aligned tabular numerals, explicit feet in the caption, and four decimal places in both exposure columns.

## Layout

The centered shell caps at `1360px`, with `40px 24px 72px` padding. Two equal, flexible columns have a `40px` gap: grouped roadway/traffic and hazard/barrier inputs on the left; length review, PDF options, and source/applicability on the right. Optional project metadata stays in a disclosure below the input groups. Related fields use two columns with `18px` row and `16px` column gaps.

At `1000px` and below, stack the header runtime status and then the workspace, inputs before review, with a `32px` gap. At `600px` and below, use one field column, shell padding `28px 16px 48px`, `16px` review padding, a wrapped file-toolbar metadata row, and the smaller table type. Preserve both near/opposing columns and their row labels without shrinking the entire workspace.

## Elevation & Depth

The Guardrail workspace uses flat surfaces, fine borders, and spacing rather than new shadows or decoration. Button hover changes color without translation. Loading, error and current-input review messages occupy the result region; avoid decorative placeholders that could be mistaken for engineering output.

## Shapes

Fields use `6px` corners, `1px` divider borders, raised fill, and a minimum height of `44px`. The review panel uses `12px` corners and `24px` padding before the phone reduction. Retain inherited website button shapes; PDF download is full width with a minimum height of `44px`.

## Components

The file toolbar exposes Open project and Save project, textual unsaved status, engine version, and feet/mph context. Preserve native labeled inputs and selects, adjacent units/helpers, a real table with a caption and scoped headers, and native project-details disclosure. Within this shell, buttons, fields, selects, disclosure summaries and links receive a visible teal outline (`2px`, offset `3px`); text selection uses teal with paper-colored text. Disabled actions retain their disabled behavior and muted treatment. Runtime and file notices use status semantics; errors use alert semantics.

**The Accepted Inputs Rule.** An input edit immediately hides the previous results and blocks project/PDF export until current inputs calculate successfully. Keep the waiting, invalid-input, engine-loading and engine-error messages distinct. Python supplies accepted results after the typing pause; the interface must not reproduce engineering arithmetic. File operations use one captured input set and block duplicate actions while busy.

All current calculation selections remain available without a paywall. The PDF group retains its three upstream styles and optional facility-selected MDOT references. Keep source V8.5.2 / `c5df84a`, the simplified clear-zone transcription notice, and inherited engineering limits alongside the review. These labels establish provenance, not engineering approval.

**The Local Project Rule.** Save downloads a versioned browser JSON file; Open validates and recalculates before replacing state. Retain malformed-import feedback, source-revision-change notice, project-replacement confirmation, and unsaved navigation/unload handling subject to browser support. Saving a PDF does not save the project. There is no cloud project storage or automatic recovery; DXF/LandXML remain outside this browser workflow.

## Do's and Don'ts

- **Do** preserve units, both exposure columns, source applicability, readable numeric alignment, and current-input export gating.
- **Do** keep the browser's responsive input-first reading order and accessible native controls.
- **Don't** transfer the desktop palette, window minimum, independent pane scrolling, or desktop export composition into this page.
- **Don't** treat local calculation processing as an offline-availability guarantee or browser-managed downloads as durable project storage.
- **Don't** expand source claims, engineering approval, or supported exports beyond the implemented integration.
