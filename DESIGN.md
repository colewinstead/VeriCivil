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
