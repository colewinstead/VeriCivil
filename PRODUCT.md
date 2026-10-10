# VeriCivil

<!-- impeccable:product-schema 1 -->

## Platform

web

This repository owns VeriCivil's website and browser calculators, including product pages for RoadStation. The product context covers the whole VeriCivil family. RoadStation is a separate native iPhone app maintained in `../Road-Stationing-App`; its repository remains authoritative for native implementation and validation.

## Users

Roadway engineers and inspectors doing practical roadway work. Designers need calculations they can review and carry into design deliverables. Field users need to locate themselves relative to a supplied roadway alignment and understand the limits of the displayed position.

## Product Purpose

Provide focused roadway tools whose results can be verified. Success means moving from project inputs to useful design deliverables or field alignment context while keeping assumptions, units, source criteria, and limitations visible.

## Positioning

VeriCivil connects focused engineering calculations to practical design and field workflows. Superelevation's priority is its calculation reports, overlay DXF exports, and OpenRoads Designer CSV exports. RoadStation's priority is LandXML import and satellite views with station and LT/RT offset. These priorities were confirmed by the owner during initialization.

## Operating Context

- **Superelevation:** enter curve data or import supported LandXML, calculate transitions, review lane slopes and stations, save a project, and export PDF reports, ORD CSV, or overlay DXF. Review the deliverables against project criteria and in OpenRoads Designer or MicroStation before production use.
- **Crushed Stone Base:** estimate compacted roadway base volume and order tonnage across construction segments using the focused browser calculator.
- **RoadStation:** import supported LandXML from iOS Files, confirm project CRS and exact units, select an alignment, and read approximate station and LT/RT offset in the field. Satellite is the default map context; street maps and an engineering-grid fallback are available. Saved projects support return visits; manual inspection works without live location permission.

## Capabilities and Constraints

- Browser calculators run deterministic Python engines locally through Pyodide workers. Preserve the shared calculation engine rather than duplicating calculation logic in the interface.
- Calculation inputs, project files, and LandXML are processed locally in the browser. Hosted authentication, entitlements, billing, and anonymous usage analytics are separate server-side functions; local calculation processing is not a claim that every site function is offline or network-free.
- Superelevation supports versioned MDOT and TDOT criteria profiles, lane-event review, station equations, project persistence, and supported exports. The AASHTO 2018 profile adds a limited, locally supplied criteria-workbook workflow, fixed pivots, one-way sections, and established clothoid transitions; it requires independent engineering review and excludes unverified rate interpolation. See `docs/AASHTO_2018.md` for licensing and validation limits. The calculator catalog and entitlement implementation define current availability and plan boundaries; do not invent commercial promises or broader DOT coverage.
- Overlay DXF is a graphics handoff, not a native Bentley civil model. Preserve explicit export warnings and lane/station/coordinate context.
- RoadStation uses its own Swift geometry engine for horizontal lines, circular curves, clothoids, and station equations. Map samples and imagery provide display context; they do not determine station or offset.
- RoadStation requires explicit CRS readiness before live positioning. Preserve exact unit distinctions, GPS accuracy and freshness, stale/invalid status, and ambiguity information. Phone GPS is approximate and not survey-grade; imagery is not surveyed control.
- RoadStation's README reports implemented MapKit and saved-project features, with physical field-placement and saved-project lifecycle acceptance still outstanding. App Store distribution remains a separate release gate. Future surfaces/TIN, AR, LiDAR, and RTK concepts are not current capabilities.
- Engineering formulas, tables, stationing, ORD mappings, coordinate transforms, and generated results remain frozen unless a clear defect is identified and explained. Never infer missing CRS, datum, axis order, or exact foot type from coordinate magnitude or filenames.
- Browser releases and website publishing are separate steps. Desktop distribution is paused. Use the existing Site identified by `web/.openai/hosting.json` for authorized publishing.

## Brand Commitments

VeriCivil is a brand of CW Aerial Media LLC, the operating legal entity behind the website and RoadStation.

Use VeriCivil as the family name, Superelevation Calculator for the design workspace, and RoadStation by VeriCivil for the iPhone product. Existing public copy emphasizes “Roadway software you can verify.” Keep product language concrete about engineering work, assumptions, and limitations. Do not imply certification or survey-grade accuracy.

## Evidence on Hand

- `README.md`: Superelevation workflow, exports, engineering boundaries, and browser architecture.
- `calculators/catalog.py`: authoritative browser calculator inventory and runtime bundles.
- `web/app/page.tsx` and `web/app/roadstation/page.tsx`: current family positioning and RoadStation public claims.
- `web/public/showcase/`: existing Superelevation workspace and output captures.
- `web/public/roadstation/`: RoadStation captures using a fictional sample. Permission-denied and manual-query screenshots are not live GPS accuracy evidence.
- `../Road-Stationing-App/README.md`: native capabilities, roadmap, and validation limits. It reports 30/30 real ORD comparison cases at 0.001 US survey foot tolerance; that is a specific dataset result, not general field accuracy or certification.
- `AGENTS.md` and engineering/readiness documents under `docs/`: calculation-preservation and release guidance. Recheck these sources before changing claims or shipping.

## Product Principles

1. Prioritize usable engineering deliverables and field station/offset workflows.
2. Keep methods, assumptions, units, provenance, and uncertainty connected to results.
3. Preserve deterministic engineering behavior and require independent professional review.
4. Keep engineering files local while stating the boundaries of account and network services accurately.
5. Keep each tool focused, and distinguish implemented capabilities from roadmap and unverified release claims.

## Open Decisions

No additional accessibility standard, audience expansion, pricing commitment, or native roadmap priority was established during this initialization. Existing implementation and authoritative product documents govern until the owner confirms a change.
