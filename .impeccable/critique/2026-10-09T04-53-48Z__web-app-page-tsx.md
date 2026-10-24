---
target: VeriCivil homepage and RoadStation marketing hierarchy
total_score: 24
max_score: 28
na_heuristics: 7,9,10
p0_count: 0
p1_count: 0
target_identity: "file:/Users/colewinstead/1Python/VeriCivil/web/app/page.tsx"
target_fingerprint: "sha256:395113142fd6aeead123fa8aec79fe2f04256b6ac239cfd2a618c4eac3150764"
target_path: /Users/colewinstead/1Python/VeriCivil/web/app/page.tsx
timestamp: 2026-10-09T04-53-48Z
slug: web-app-page-tsx
---
Method: dual-agent (A: /root/design_review; B: /root/detector_review)

# Focused VeriCivil marketing critique

Targets: web/app/page.tsx and web/app/roadstation/page.tsx. Preserve incumbent visual system; assess brand hierarchy, product hierarchy, CTA prominence, consistency and desktop/mobile.

## Design specificity

Product-specific and cohesive: authentic engineering captures, dark green/amber/teal palette and concrete station/offset language earn credibility. VeriCivil presents the product family; RoadStation by VeriCivil stays distinct. No redesign warranted.

## Heuristics

| Heuristic | Score | Evidence |
|---|---:|---|
| Status visibility | 4 | Release preparation and sample limits visible |
| Real-world match | 4 | LandXML, CRS, station and offset fit practical work |
| User control | 3 | Normal product/family navigation |
| Consistency | 4 | Shared visual system and matching hero/end CTAs |
| Error prevention | 4 | Professional-review and positioning limits retained |
| Recognition | 3 | Hero screenshot still emphasizes Superelevation |
| Flexibility | n/a | Marketing surface |
| Minimalism | 2 | Repeated assurance and video placeholder |
| Error recovery | n/a | No assessed form/error flow |
| Help/documentation | n/a | Marketing surface; support remains available |
| Total | 24/28 | Good, 86% |

## Strengths

- Family and product distinction is clear without splitting the visual identity.
- Four-step field workflow and honest fictional/manual captures support trust.
- Mobile headings and 48px primary CTAs fit without observed horizontal overflow.

## Applied worthwhile refinements

- P1 resolved: homepage primary CTA was nearly invisible because --marketing-teal was undefined on the platform shell. Reused existing teal token; confirmed corrected desktop/mobile appearance.
- P2 resolved: mobile navigation links were approximately 16px high. Enlarged existing hit areas to 44px; confirmed width 390px equals document scroll width and visible product/support/privacy links have 44px height.

## Deferred assets and observations

- Superelevation screenshots remain in homepage hero. Family copy and RoadStation section sufficiently explain the product scope for this focused pass.
- Replace RoadStation's truthful video placeholder with the real demo video when supplied.
- Add a verified App Store link only when available; no fabricated destination or TestFlight promotion.
- Existing web/public/og.png still contains the old calculation tagline; needs refreshed marketing artwork.

## Cognitive load, emotional journey and personas

Two hero actions are manageable. Desktop navigation duplication does not justify restructuring. Engineering evidence, practical workflow and explicit limits establish trust; the empty video placeholder is the weakest moment. First-time users see clear actions; skeptical engineers receive bounded claims; mobile users benefit from larger navigation hit areas.

## Detector and run notes

Installed impeccable detect --json returned [] for each target (exit 0, zero findings). No ignore list. Assessments were isolated; A source/visual review and B detector/browser evidence were synthesized only after A finished. Live source changed during B to repair the confirmed CTA token, and the initial capture is superseded. Screenshots inspected at 1280x720 and 390x844. Browser mutation is unavailable under the documented read-only evaluate API; no injected detector overlay or helper server was used or claimed. Browser viewport restored; assessment tabs closed. Parent preview server stopped after verification. No comprehensive screen-reader, physical-device or commercial-flow audit performed.

Questions skipped: scope and worthwhile refinements were already explicitly authorized by the user; no new design decision is required.
