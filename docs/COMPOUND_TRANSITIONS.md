# Compound superelevation transitions

Application 1.6.14 / calculation engine 1.4.0 implements the user's project rule for adjoining circular arcs in the same turn direction. Both desktop and browser use the shared Python engine. This placement rule is a project choice, not a claim that every agency prescribes the selected percentage at a compound junction.

## Rate and placement

The smaller-radius arc controls the transition rate and placement. For a conventional crowned section, its existing runoff rate is `e_control / Lr_control`, with slopes in ft/ft and lengths in feet. Between two already banked sections:

`L_compound = abs(e_following - e_prior) / (e_control / Lr_control)`

For 3% → 5%, with the sharper arc's reference runoff of 200 ft, the compound transition is 80 ft. A 70% before / 30% after placement develops 3% → 5% from 56 ft before to 24 ft after the junction. It never returns to normal crown or passes through zero cross slope. The reverse sequence mirrors the sharper arc's exit placement: 24 ft before and 56 ft after. Left → left and right → right use the same lengths with the established lane signs.

A favorable single-slope ramp's recorded runoff already starts at its initial bank. Its actual rate is `(e_control - e_initial) / Lr_control`; reducing it again using `e_control / Lr_control` would incorrectly increase the rate. Compound transitions retain that actual rate. An adverse initial section or a genuinely crowned normal-crown arc is not treated as an already banked plane.

Custom runoff percentages apply to the reduced length. MDOT retains its default 70/30 runoff placement. TDOT's default places half of the *total* runoff plus runout on each side of the boundary; the existing runoff proportion is `(Lr - Lt) / (2 Lr)`, not an assumed 50/50 runoff split. Its explicit project override uses the entered runoff percentage.

Equal-bank arcs hold their bank at the junction. Chains are supported provided each arc can attain its design bank between adjacent transitions. A chain whose reduced transitions overlap is rejected with the affected curve identified; the engine does not stretch lengths, increase rates, or move geometry to make it fit. Curves must share their criteria, cross section, and rotation axis. A real intervening tangent, opposite-direction arcs, and compound spirals retain their existing behavior.

## Calculation, QA, and exports

Build all selected LandXML curves to calculate the compound chain. Editing a saved curve recalculates its transition against its saved neighbors; Update Curve applies the resulting transition to the whole saved set. Removing a neighbor restores the remaining arc's independent transition. Missing source arcs do not become invented tangents.

Lookup, diagrams, ORD CSV, PDF, and DXF use the coordinated lane events. AASHTO actual-lane events include physical edge heights relative to the fixed pivot. Shared compound events are emitted once per exported lane. Results retain the independent baseline and record the controlling arc, actual slope rate, reduced length, placement, and project provenance. Export validation rederives the compound result from the current inputs and curve set, blocking stale, altered, or incomplete results.

AASHTO's normal tangent-availability and alignment-limit checks still apply at the outer ends. Internal compound sides are assessed against the coordinated bank transitions. Equation 3-25, discussed in §3.3.8.2.3, pp. 3-71–3-72, addresses the approach tangent to a simple horizontal curve; it is not reapplied as a tangent-entry limit at a PCC. This implementation does not establish independent agency approval of the compound placement.

## Regression evidence

Public synthetic tests cover 3% ↔ 5%, both turn directions, 0/50/70/100% placement, MDOT/TDOT/AASHTO defaults, equal-bank arcs, longer chains, insufficient length, unchanged tangent/reverse/spiral behavior, fixed-pivot heights, favorable ramp rates, editing, saved-result validation, QA, and exports. The same public checks run in Pyodide, with native/browser comparisons for batch calculation, editing, coordination, and QA.

The locally supplied `840 choice ramps.xml` is checked separately when present. At the user's 45 mph, AASHTO maximum 8%, one 12-ft lane, left-edge rotation, 2% initial drainage to the right, and 50% placement, source arcs 3–5 form the right-turn compound chain. The first two retain 2%; the final arc selects 4.8%. The bank transition is 63 ft, split 31.5 ft on each side of the junction. That selected chain passes Corridor QA and overlay export. Separate reverse-curve findings in the full alignment remain enforced. The user fixture is not required for the public tests.

This is mathematical and software regression evidence. Independent roadway-engineer review and an actual ORD import remain outside these checks.
