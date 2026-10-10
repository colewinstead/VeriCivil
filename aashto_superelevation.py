"""AASHTO transition solver; fixed-pivot sections and established alignments.

Lateral offsets increase to the left of alignment. Section heights are relative
to a fixed pivot. Lane slopes retain VeriCivil's outward-from-alignment signs.
"""

from __future__ import annotations
import math

import aashto_criteria as criteria

PROFILE_ID = criteria.PROFILE_ID


class TransitionError(ValueError):
    def __init__(self, message: str, findings: list[dict]):
        super().__init__(message)
        self.findings = findings


def _number(values, key, default=None):
    raw = values.get(key, default)
    if raw in (None, ""):
        if default is None:
            raise ValueError(f"{key.replace('_', ' ').capitalize()} is required.")
        raw = default
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite.")
    return value


def _true(value):
    return value is True or str(value).lower() in {"true", "1", "yes"}


def calculate(values: dict, station_equations=None, alignment_range=None) -> dict:
    import Super
    from app_info import CALCULATION_ENGINE_VERSION
    from criteria_info import criteria_metadata

    station_equations = Super.strict_station_equations(station_equations)
    if alignment_range is not None:
        alignment_range = tuple(float(s) for s in alignment_range)
        if (
            len(alignment_range) != 2
            or not all(math.isfinite(s) for s in alignment_range)
            or alignment_range[1] <= alignment_range[0]
        ):
            raise ValueError(
                "Alignment range requires finite, increasing internal stations."
            )
    direction = values.get("curve_direction", "left")
    if direction not in {"left", "right"}:
        raise ValueError("Curve direction must be left or right.")
    maximum = _number(values, "max_superelevation", 8)
    if maximum not in criteria.MAX_RATES:
        raise ValueError("Maximum superelevation must be 4, 6, 8, 10, or 12 percent.")
    speed, radius = _number(values, "speed"), _number(values, "radius")
    if radius <= 0:
        raise ValueError("Radius must be positive.")
    gradient = criteria.relative_gradient(speed)
    area = values.get("area", "rural")
    if area not in {"rural", "urban_freeway", "urban_high_speed"}:
        raise ValueError(
            "AASHTO low-speed urban Method 2 / Table 3-13 is outside this profile's verified scope. Select rural/high-speed Method 5 only where applicable."
        )
    if maximum == 4 and area == "rural":
        raise ValueError(
            "Table 3-8 limits 4% maximum to urban areas; select an applicable urban freeway/high-speed context."
        )
    if maximum == 4 and speed > 60:
        raise ValueError(
            "Table 3-8 publishes 4% maximum only through 60 mph; this selection is unsupported."
        )
    if area == "urban_high_speed" and speed <= 45:
        raise ValueError(
            "Low-speed urban streets require separate Method 2 applicability review; unsupported."
        )
    if any(values.get(key) not in (None, "") for key in ("friction", "rel_grad")):
        raise ValueError(
            "Friction and relative-gradient overrides are not supported by this AASHTO profile."
        )
    if values.get("linear_unit") not in (
        None,
        "",
        "foot",
        "Foot",
        "USSurveyFoot",
        "internationalFoot",
    ):
        raise ValueError(
            "AASHTO calculations require foot-based stationing; metric geometry is unsupported by this US-unit profile."
        )
    if values.get("geometry_provenance", {}).get(
        "source"
    ) == "LandXML" and not values.get("linear_unit"):
        raise ValueError(
            "LandXML must explicitly declare a supported foot unit before AASHTO calculations."
        )
    if values.get("alignment_type", "circular") not in {"circular", "spiral"}:
        raise ValueError(
            "Only circular and established spiral–circular–spiral alignments are supported."
        )
    roadway = values.get("roadway", "two_way")
    section = values.get("initial_section", "crowned")
    pivot = values.get("rotation_axis", "centerline")
    if (
        roadway not in {"two_way", "one_way"}
        or section not in {"crowned", "single_slope"}
        or pivot not in {"centerline", "left_edge", "right_edge"}
    ):
        raise ValueError("Unsupported roadway, cross section, or rotation axis.")
    widths = values.get("lane_widths", "12,12")
    widths = [
        float(w) for w in (widths.split(",") if isinstance(widths, str) else widths)
    ]
    if (
        not widths
        or len(widths) > 7
        or any(not math.isfinite(w) or w <= 0 for w in widths)
    ):
        raise ValueError("Supply 1–7 finite positive lane widths, in feet.")
    if max(widths) - min(widths) > 1e-9:
        raise ValueError(
            "Unequal lane widths require independently verified lane-adjustment criteria; unsupported in this profile."
        )
    if roadway == "two_way" and len(widths) < 2:
        raise ValueError("Two-way carriageways require at least two lanes.")
    width = sum(widths)
    crown = _number(values, "crown_from_left", width / 2)
    normal = _number(values, "normal_crown", 0.02)
    left_nc = _number(values, "left_normal_slope", normal)
    right_nc = _number(values, "right_normal_slope", normal)
    if not 0.015 <= left_nc <= 0.02 or not 0.015 <= right_nc <= 0.02:
        raise ValueError("Verified normal crown scope is 1.5–2.0 percent on each side.")
    if section == "crowned" and (
        abs(crown - width / 2) > 1e-9 or abs(left_nc - right_nc) > 1e-9
    ):
        raise ValueError(
            "Asymmetric crowns require a verified transition sequence; unsupported."
        )
    if section == "crowned":
        normal = left_nc
    boundaries = [-width / 2]
    for lane_width in reversed(widths):
        boundaries.append(boundaries[-1] + lane_width)
    if section == "crowned" and not any(abs(x) < 1e-9 for x in boundaries):
        raise ValueError("A crowned section must place the crown on a lane boundary.")
    initial = _number(values, "initial_slope", -0.02)
    if section == "single_slope" and (
        roadway != "one_way" or not 0.015 <= abs(initial) <= 0.02
    ):
        raise ValueError(
            "Single-slope scope is a one-way carriageway with signed 1.5–2.0 percent initial cross slope (positive rises to the left)."
        )
    pack = values.get("aashto_tables")
    manual = values.get("e_manual") not in (None, "")
    if manual:
        e = _number(values, "e_manual")
        if not 0.02 <= e <= maximum / 100:
            raise ValueError("Manual e must be between 2% and the selected maximum.")
        crown_state = "full"
        rate_source = {
            "reference": "Engineer-entered rate; automatic table applicability not established",
            "mode": "user_override",
        }
        if pack:
            criteria.check_radius(pack, int(maximum), speed, radius)
    else:
        e, crown_state, rate_source = criteria.rate(
            pack, int(maximum), speed, radius, normal
        )
        if section == "single_slope" and crown_state != "full":
            raise ValueError(
                "NC/RC table thresholds for uniform single-slope sections require separate review; supply an independently checked manual rate."
            )
    bank_sign = -1 if direction == "left" else 1
    pivot_x = {"centerline": 0.0, "left_edge": width / 2, "right_edge": -width / 2}[
        pivot
    ]
    farthest = max(abs(x - pivot_x) for x in boundaries)
    n = farthest / widths[0]
    # Table 3-15 is directly applicable to undivided highways. For one-way
    # ramps use the unadjusted Eq. 3-23 gradient, avoiding an unverified discount.
    bw = criteria.lane_factor(n) if roadway == "two_way" else 1.0
    allowed_gradient = gradient / bw

    def profile_height(x, bank):
        if section == "single_slope":
            return bank * x
        outside_x = width / 2 if direction == "right" else -width / 2
        outside = (x * outside_x) > 0
        if outside:
            return bank * x
        # Figure 3-8: inside plane retains normal slope until adverse crown
        # removal reaches the reverse-crown section, then both planes rotate.
        return (
            -normal * abs(x)
            if abs(bank) <= normal or bank * bank_sign < 0
            else bank * x
        )

    initial_bank = initial if section == "single_slope" else -bank_sign * normal
    if section == "single_slope" and initial * bank_sign > 0:
        if crown_state == "normal" or e <= abs(initial):
            raise ValueError(
                "Favorable single-slope sections with no additional bank require separate criteria review."
            )
        runout_change = 0.0
        zero_bank = initial
    else:
        runout_change = abs(initial_bank)
        zero_bank = 0.0

    def heights(bank):
        ref = profile_height(pivot_x, bank)
        return [profile_height(x, bank) - ref for x in boundaries]

    zero_heights, full_heights = heights(zero_bank), heights(bank_sign * e)
    nc_heights = heights(initial_bank)
    runoff_rise = max(abs(b - a) for a, b in zip(zero_heights, full_heights))
    if section == "crowned" and e > normal:
        reverse_heights = heights(bank_sign * normal)
        runoff_rise = max(
            max(abs(b - a) * e / normal for a, b in zip(zero_heights, reverse_heights)),
            max(
                abs(b - a) * e / (e - normal)
                for a, b in zip(reverse_heights, full_heights)
            ),
        )
    runout_rise = max(abs(b - a) for a, b in zip(nc_heights, zero_heights))
    Lr = runoff_rise / allowed_gradient if e else 0.0
    Lt = runout_rise / allowed_gradient if e else 0.0
    sources = [
        {"component": "Superelevation rate", **rate_source},
        {
            "component": "Runoff length",
            "reference": "AASHTO Equation 3-23; §3.3.8.2.1; Figure 3-8; actual fixed-pivot edge rise",
            "mode": "calculated",
        },
        {
            "component": "Tangent runout",
            "reference": "AASHTO Equation 3-24 / adverse edge rise at runoff relative gradient",
            "mode": "calculated",
        },
        {
            "component": "Lane adjustment",
            "reference": (
                "Table 3-15 unrounded footnote"
                if roadway == "two_way"
                else "Unadjusted gradient for one-way carriageway; no Table 3-15 discount"
            ),
            "mode": "calculated",
        },
    ]
    sources.append(
        {
            "component": "Relative gradient",
            "reference": "AASHTO §3.3.8.2.1; inverse relative slope",
            "mode": "interpolation" if speed in (25, 35, 45) else "published_criterion",
            "value": gradient,
        }
    )
    if crown_state == "normal":
        sources[1].update(
            mode="not_applicable", reference="§3.3.5.1 normal crown retained; no runoff"
        )
        sources[2].update(
            mode="not_applicable", reference="§3.3.5.1 normal crown retained; no runout"
        )
    elif runout_rise == 0:
        sources[2].update(
            mode="not_applicable",
            reference="Uniform favorable initial slope; no adverse slope removal / tangent runout",
        )
    published = None
    if (
        pack
        and roadway == "two_way"
        and section == "crowned"
        and pivot == "centerline"
        and widths[0] == 12
        and n in {1, 2}
        and crown_state != "normal"
    ):
        published = next(
            (
                row[1 + (int(speed) - 15) // 5 * 2 + (0 if n == 1 else 1)]
                for row in pack.get("runoff", [])
                if abs(row[0] / 100 - e) < 1e-10
            ),
            None,
        )
        if published is not None:
            Lr = float(published)
            Lt = Lr * normal / e
            sources[1] = {
                "component": "Runoff length",
                "reference": "AASHTO Table 3-16a; October 2019 errata",
                "mode": "published_table_lookup",
            }
    for key, name in [("Lr_manual", "runoff_length"), ("Lt_manual", "tangent_runout")]:
        if values.get(key) not in (None, ""):
            value = _number(values, key)
            if value < 0 or (key == "Lr_manual" and value <= 0):
                raise ValueError(
                    "Manual transition lengths must be positive (runout may be zero)."
                )
            if key == "Lr_manual":
                Lr = value
            else:
                Lt = value
            sources.append(
                {
                    "component": name,
                    "reference": "Engineer-entered length",
                    "mode": "user_override",
                }
            )
    # Published whole-foot rounding can reduce a length by < 1 ft; retain and
    # disclose it. Manual lengths cannot use that rounding allowance.
    if e and (
        Lr + (1 if published is not None and not values.get("Lr_manual") else 0)
        < runoff_rise / allowed_gradient - 1e-8
        or Lt + (1 if published is not None and not values.get("Lt_manual") else 0)
        < runout_rise / allowed_gradient - 1e-8
    ):
        message = "Transition length violates the applicable adjusted relative-gradient criterion."
        raise TransitionError(
            message,
            [
                {
                    "code": "GRADIENT_LIMIT",
                    "severity": "block",
                    "message": message,
                    "details": {
                        "actual_runoff_ft": Lr,
                        "required_runoff_ft": runoff_rise / allowed_gradient,
                        "actual_runout_ft": Lt,
                        "required_runout_ft": runout_rise / allowed_gradient,
                    },
                }
            ],
        )
    pc = Super.parse_station_reference(
        str(values.get("pc", "")), station_equations, alignment_range
    )
    pt = Super.parse_station_reference(
        str(values.get("pt", "")), station_equations, alignment_range
    )
    if not math.isfinite(pc) or not math.isfinite(pt) or pt <= pc:
        raise ValueError("PT/CS must follow PC/SC.")
    findings = []

    def finding(code, severity, message, start=None, end=None, **details):
        details["affected_lanes"] = [f"Lane {i}" for i in range(1, len(widths) + 1)]
        findings.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "station_start_ft": start,
                "station_end_ft": end,
                "details": details,
            }
        )

    spiral = values.get("alignment_type", "circular") == "spiral"
    holds = []
    if spiral:
        ts = Super.parse_station_reference(
            str(values.get("ts", "")), station_equations, alignment_range
        )
        st = Super.parse_station_reference(
            str(values.get("st", "")), station_equations, alignment_range
        )
        if not math.isfinite(ts) or not math.isfinite(st) or not ts < pc < pt < st:
            raise ValueError("Spiral stations must satisfy TS < SC < CS < ST.")
        placement = values.get("runout_placement", "on_tangent")
        if placement not in {"on_tangent", "in_spiral"}:
            raise ValueError("Runout placement must be on_tangent or in_spiral.")
        required = Lr + (Lt if placement == "in_spiral" else 0)
        for end_name, length, a, b in [
            ("entry", pc - ts, ts, pc),
            ("exit", st - pt, pt, st),
        ]:
            if length < required - 1e-7:
                finding(
                    "INSUFFICIENT_SPIRAL",
                    "block",
                    f"{end_name.title()} spiral: {length:.3f} ft available; {required:.3f} ft required; deficiency {required-length:.3f} ft.",
                    a,
                    b,
                    actual_ft=length,
                    required_ft=required,
                    side=end_name,
                )
            elif crown_state != "normal" and length > required + 1e-7:
                finding(
                    "EXCESS_SPIRAL",
                    "review",
                    f"{end_name.title()} spiral is {length-required:.3f} ft longer than required for superelevation; not a maximum spiral length violation.",
                    a,
                    b,
                    actual_ft=length,
                    required_ft=required,
                )
        run_start, run_end = pc - Lr, pt + Lr
        if placement == "on_tangent":
            start, zero_start, zero_end, end = ts - Lt, ts, st, st + Lt
            for side, a, b in [("entry", ts, run_start), ("exit", run_end, st)]:
                if crown_state != "normal" and b > a + 1e-7:
                    if zero_bank:
                        holds.append(
                            {
                                "start_ft": a,
                                "end_ft": b,
                                "length_ft": b - a,
                                "section": "initial",
                            }
                        )
                        continue
                    recommendation = (
                        "Consider moving tangent runout within the spiral, subject to governing agency requirements."
                        if (pc - ts if side == "entry" else st - pt) >= Lr + Lt
                        else f"In-spiral placement needs {Lr+Lt:.3f} ft; the existing spiral is insufficient."
                    )
                    message = f"Drainage review recommended: {side} zero-crown hold of {b-a:.3f} ft from {Super.station_input_label(a,station_equations,alignment_range)} to {Super.station_input_label(b,station_equations,alignment_range)}. {recommendation}"
                    holds.append(
                        {
                            "start_ft": a,
                            "end_ft": b,
                            "length_ft": b - a,
                            "section": "zero_crown",
                            "recommendation": recommendation,
                        }
                    )
                    finding(
                        "ZERO_CROWN_HOLD",
                        "review",
                        message,
                        a,
                        b,
                        length_ft=b - a,
                        recommendation=recommendation,
                    )
            if any(h["section"] == "zero_crown" for h in holds) and not _true(
                values.get("acknowledge_spiral_override")
            ):
                finding(
                    "PLACEMENT_ACKNOWLEDGEMENT_REQUIRED",
                    "block",
                    "Longer spiral with zero-crown hold requires explicit project-specific placement acknowledgement; not verified AASHTO standard placement.",
                    ts,
                    st,
                )
        else:
            start, zero_start, zero_end, end = (
                pc - Lr - Lt,
                run_start,
                run_end,
                pt + Lr + Lt,
            )
            holds = [
                {
                    "start_ft": ts,
                    "end_ft": start,
                    "length_ft": max(0, start - ts),
                    "section": "initial",
                },
                {
                    "start_ft": end,
                    "end_ft": st,
                    "length_ft": max(0, st - end),
                    "section": "initial",
                },
            ]
        anchors = {"TS": ts, "SC": pc, "CS": pt, "ST": st}
        standard = (
            placement == "on_tangent"
            and abs(pc - ts - Lr) < 1e-7
            and abs(st - pt - Lr) < 1e-7
        )
        sources.append(
            {
                "component": "Transition placement",
                "reference": (
                    "§3.3.8.4.6 equal runoff/spiral arrangement"
                    if standard
                    else "§3.3.8.4.6; project minimum-length SC/CS anchoring; in-spiral runout is a project placement choice"
                ),
                "mode": "published_method" if standard else "project_override",
            }
        )
    else:
        p = _number(values, "runoff_tangent_percent") / 100
        if not 0 <= p <= 1:
            raise ValueError("Runoff on tangent must be 0–100 percent.")
        if p in {0, 1} and e:
            finding(
                "EXTREME_RUNOFF_PLACEMENT",
                "review",
                "§3.3.8.2.3 recommends avoiding runoff entirely on tangent or curve; review this project placement.",
                pc,
                pt,
            )
        run_start, run_end = pc - p * Lr, pt + p * Lr
        start, zero_start, zero_end, end = (
            run_start - Lt,
            run_start,
            run_end,
            run_end + Lt,
        )
        pc_full, pt_full = pc + (1 - p) * Lr, pt - (1 - p) * Lr
        anchors = {"PC": pc, "PT": pt}
        sources.append(
            {
                "component": "Transition placement",
                "reference": "§3.3.8.2.3; explicit project runoff percentage",
                "mode": "project_input",
            }
        )
        if e:
            pc_bank = abs(zero_bank + p * (bank_sign * e - zero_bank))
            attained = pc_bank / e
            limit = 2.15 / (1 + attained) * speed**2 / (32.2 * radius)
            if pc_bank >= limit:
                finding(
                    "PC_BANK_LIMIT",
                    "block",
                    f"Superelevation at PC/PT ({pc_bank:.5f} ft/ft) fails Equation 3-25 (< {limit:.5f}); reduce tangent runoff proportion or review a spiral transition.",
                    pc,
                    pt,
                )
            sources.append(
                {
                    "component": "PC/PT bank check",
                    "reference": "AASHTO Equation 3-25 (US customary); actual attained bank / design rate",
                    "mode": "calculated",
                }
            )
    full_start, full_end = (pc, pt) if spiral else (pc_full, pt_full)
    if full_start > full_end + 1e-7:
        finding(
            "TRANSITION_OVERLAP",
            "block",
            "Entering/exiting runoffs overlap on the circular arc.",
            full_end,
            full_start,
        )
    if alignment_range and (
        start < alignment_range[0] - 1e-7 or end > alignment_range[1] + 1e-7
    ):
        finding(
            "INSUFFICIENT_TANGENT",
            "block",
            "Transition extends beyond the established alignment; available tangent/runout space is insufficient.",
            start,
            end,
        )
    geometry = values.get("geometry_provenance", {})
    tangent_demand = (
        Lt if spiral and placement == "on_tangent" else 0 if spiral else p * Lr + Lt
    )
    if e:
        for side, a, b in (
            ("entry", start, anchors.get("TS", pc)),
            ("exit", anchors.get("ST", pt), end),
        ):
            available = geometry.get(f"available_{side}_tangent_ft")
            if available is not None and (
                not math.isfinite(float(available)) or float(available) < 0
            ):
                raise ValueError(
                    "Available tangent length must be finite and nonnegative."
                )
            if available is not None and tangent_demand > float(available) + 1e-7:
                finding(
                    "INSUFFICIENT_TANGENT",
                    "block",
                    f"{side.title()} tangent: {float(available):.3f} ft available; {tangent_demand:.3f} ft required for selected runout/runoff placement.",
                    a,
                    b,
                    side=side,
                    actual_ft=float(available),
                    required_ft=tangent_demand,
                )
    if any(f["severity"] == "block" for f in findings):
        raise TransitionError(
            "; ".join(f["message"] for f in findings if f["severity"] == "block"),
            findings,
        )
    entry_knots = [
        (start, initial_bank),
        (zero_start, zero_bank),
        (run_start, zero_bank),
        (full_start, bank_sign * e),
    ]
    # Reverse crown is a real section breakpoint, not an extra length.
    if section == "crowned" and e > normal:
        entry_knots.append((run_start + Lr * normal / e, bank_sign * normal))
    exit_knots = [
        (full_end, bank_sign * e),
        (run_end, zero_bank),
        (zero_end, zero_bank),
        (end, initial_bank),
    ]
    if section == "crowned" and e > normal:
        exit_knots.append((run_end - Lr * normal / e, bank_sign * normal))
    knots = sorted(set(entry_knots + exit_knots))
    if crown_state == "normal":
        knots = [(pc, initial_bank), (pt, initial_bank)]
        Lr = Lt = 0.0
        start, zero_start, run_start, full_start = pc, pc, pc, pc
        full_end, run_end, zero_end, end = pt, pt, pt, pt
        holds = []

    def bank_at(station):
        if station <= knots[0][0]:
            return knots[0][1]
        for (a, va), (b, vb) in zip(knots, knots[1:]):
            if a <= station <= b:
                return vb if a == b else va + (vb - va) * (station - a) / (b - a)
        return knots[-1][1]

    stations = sorted(set([s for s, _ in knots] + list(anchors.values())))
    lane_events = []
    for index, (a, b) in enumerate(zip(boundaries, boundaries[1:]), 1):
        side = "left" if (a + b) / 2 > 0 else "right"
        sign = 1 if side == "left" else -1
        events = []
        for station in stations:
            bank = bank_at(station)
            edge = heights(bank)
            slope = (edge[index] - edge[index - 1]) / (b - a) * 100 * sign
            label = next(
                (name for name, s in anchors.items() if abs(s - station) < 1e-7), ""
            )
            if not label:
                if station in {start, end}:
                    label = (
                        "Normal section" if section == "crowned" else "Initial section"
                    )
                elif abs(bank) < 1e-9:
                    label = (
                        "Outside lane level"
                        if section == "crowned"
                        else "Level section"
                    )
                elif section == "crowned" and abs(bank - bank_sign * normal) < 1e-9:
                    label = "Reverse crown"
                elif station in {full_start, full_end}:
                    label = "Full super"
                else:
                    label = "Section transition"
            event_type = (
                "Full super"
                if abs(station - full_start) < 1e-7
                else (
                    "End full super"
                    if abs(station - full_end) < 1e-7
                    else (
                        ("Normal crown" if section == "crowned" else "Initial section")
                        if station in {start, end}
                        else "Section transition"
                    )
                )
            )
            if crown_state == "normal":
                event_type = "Initial section"
            events.append(
                {
                    "label": label,
                    "station_ft": station,
                    "slope_pct": slope,
                    "event_type": event_type,
                    "note": f"AASHTO fixed {pivot} pivot; lane {index}; elevations relative to pivot",
                    "right_elevation_ft": edge[index - 1],
                    "left_elevation_ft": edge[index],
                }
            )
        lane_events.append(
            {
                "lane_name": f"Lane {index}",
                "side": side,
                "left_offset_ft": b,
                "right_offset_ft": a,
                "width_ft": b - a,
                "left_distance_from_pivot_ft": b - pivot_x,
                "right_distance_from_pivot_ft": a - pivot_x,
                "events": events,
            }
        )
    side_events = {
        side: next((lane["events"] for lane in lane_events if lane["side"] == side), [])
        for side in ("left", "right")
    }
    warnings = [
        "Tables 3-17–3-20 and automatic horizontal alignment design are excluded; responsible PE must verify project applicability."
    ] + [f["message"] for f in findings]
    if manual:
        warnings.append(
            "Manual rate: published radius/rate applicability must be independently verified."
        )
    if roadway == "one_way":
        warnings.append(
            "One-way carriageway uses unadjusted relative gradient; no multilane runoff reduction is assumed for ramps."
        )
    if not geometry:
        warnings.append(
            "Manual station-only geometry: verify actual tangent availability and curve stations independently. Coordinate overlays require matching LandXML geometry."
        )
    result = {
        "inputs": {
            **values,
            "criteria_profile": criteria.PROFILE_ID,
            "speed_mph": speed,
            "radius_ft": radius,
            "lane_width_ft": widths[0],
            "lanes_rotated": len(widths),
            "area_type": area,
            "facility": pivot,
            "normal_crown": normal,
            "roadway": roadway,
            "initial_section": section,
            "rotation_axis": pivot,
            "lane_widths": ",".join(str(w) for w in widths),
            "crown_from_left": crown,
            "left_normal_slope": left_nc,
            "right_normal_slope": right_nc,
            "initial_slope": initial,
            "alignment_type": "spiral" if spiral else "circular",
            "runout_placement": (
                placement if spiral else values.get("runout_placement") or "on_tangent"
            ),
        },
        "calculation_metadata": {
            "engine_version": CALCULATION_ENGINE_VERSION,
            "criteria": criteria_metadata(criteria.PROFILE_ID),
            "manual_overrides": {
                "superelevation_rate": manual,
                "runoff_length": bool(values.get("Lr_manual")),
                "tangent_runout": bool(values.get("Lt_manual")),
                "placement": bool(e) and (not standard if spiral else True),
            },
            "calculation_sources": sources,
            "criteria_workbook": (
                {
                    "file_sha256": pack.get(
                        "file_sha256", "Original file hash unavailable"
                    ),
                    "source_version": "2018 / October 2019 errata",
                    "distribution_status": "Local user material; redistribution rights not established",
                }
                if pack
                else {}
            ),
        },
        "e": e,
        "e_max": maximum / 100,
        "e_source": rate_source["reference"],
        "e_note": rate_source.get("selection", ""),
        "Lr": Lr,
        "Lt": Lt,
        "bw": bw,
        "n1": n,
        "lanes_used": len(widths),
        "relative_gradient": gradient,
        "friction": None,
        "facility": pivot,
        "area_type": area,
        "crown_state": crown_state,
        "normal_crown_only": crown_state == "normal",
        "transition_method": "aashto_fixed_pivot",
        "pc_ft": pc,
        "pt_ft": pt,
        "pnc_ft": start,
        "reverse_crown_ft": run_start,
        "zero_crown_ft": zero_start,
        "full_super_ft": full_start,
        "full_super_out_ft": full_end,
        "reverse_crown_out_ft": run_end,
        "zero_crown_out_ft": zero_end,
        "pnc_out_ft": end,
        "lane_events": side_events,
        "section_lanes": lane_events,
        "pivot_offset_ft": pivot_x,
        "pivot_relationship": (
            "centerline"
            if pivot == "centerline"
            else "inside" if pivot.startswith(direction) else "outside"
        ),
        "section_definition": {
            "roadway": roadway,
            "initial_section": section,
            "lane_widths_ft": widths,
            "crown_from_left_ft": crown if section == "crowned" else None,
            "normal_slope": normal if section == "crowned" else None,
            "initial_signed_slope": initial if section == "single_slope" else None,
            "rotation_axis": pivot,
            "pivot_offset_ft": pivot_x,
        },
        "hold_intervals": holds,
        "alignment_anchors": anchors,
        "qa_findings": findings,
        "spiral_lengths": (
            {
                "entry_actual_ft": pc - ts,
                "exit_actual_ft": st - pt,
                "required_ft": required,
                "placement": placement,
            }
            if spiral
            else None
        ),
        "units": {
            "calculation": "US customary, foot-based inputs",
            "geometry": values.get("linear_unit")
            or "manual feet; exact foot definition not declared",
            "conversion": "No coordinate or station-unit conversion",
        },
        "warnings": warnings,
        "station_equations": station_equations or [],
        "alignment_station_range": list(alignment_range) if alignment_range else None,
        "segments": {"runoff": Lr, "runout": Lt, "total_transition": Lr + Lt},
        "runoff_note": (
            "Published Table 3-16a"
            if published is not None
            else "Calculated fixed-pivot edge rise / adjusted relative gradient; no display rounding applied."
        ),
    }
    from criteria_info import criteria_for_result

    result["calculation_metadata"]["criteria"] = criteria_for_result(result)
    return result


def validate_export_curves(curves: list[dict]) -> None:
    """Recheck saved engineering results and overlaps before affected exports."""
    intervals = []
    for curve in curves:
        result = curve.get("results", {})
        is_aashto = result.get("transition_method") == "aashto_fixed_pivot"
        if is_aashto:
            expected = calculate(
                result.get("inputs", {}),
                result.get("station_equations"),
                result.get("alignment_station_range"),
            )
            for key in (
                "e",
                "Lr",
                "Lt",
                "pivot_offset_ft",
                "section_lanes",
                "alignment_anchors",
            ):
                if result.get(key) != expected.get(key):
                    raise ValueError(
                        "Saved AASHTO results differ from the current inputs/engine; recalculate before exporting."
                    )
        if (
            not result.get("normal_crown_only")
            and result.get("pnc_ft") is not None
            and result.get("pnc_out_ft") is not None
        ):
            intervals.append(
                (float(result["pnc_ft"]), float(result["pnc_out_ft"]), is_aashto)
            )
    intervals.sort()
    for a, b in zip(intervals, intervals[1:]):
        if (a[2] or b[2]) and a[1] > b[0] + 1e-7:
            raise ValueError(
                "AASHTO export blocked: adjacent transition intervals overlap; resolve Corridor QA findings."
            )


def override_circular_placement(result: dict, percent: float) -> dict:
    """Only station placement changes; existing DOT rate and lane model survive."""
    percent = float(percent)
    if not math.isfinite(percent) or not 0 <= percent <= 100:
        raise ValueError("Runoff on tangent must be 0–100 percent.")
    if result.get("normal_crown_only"):
        raise ValueError("Normal-crown-only curves do not have runoff placement.")
    p = percent / 100
    L = result["Lr"]
    Lt = result["Lt"]
    pc = result["pc_ft"]
    pt = result.get("pt_ft")
    result.update(
        reverse_crown_ft=pc - p * L,
        zero_crown_ft=pc - p * L,
        pnc_ft=pc - p * L - Lt,
        full_super_ft=pc + (1 - p) * L,
    )
    if pt is not None:
        result.update(
            reverse_crown_out_ft=pt + p * L,
            zero_crown_out_ft=pt + p * L,
            pnc_out_ft=pt + p * L + Lt,
            full_super_out_ft=pt - (1 - p) * L,
        )
        if result["full_super_ft"] > result["full_super_out_ft"]:
            raise ValueError("Circular transition placement overlaps on the curve.")
    if result.get("reverse_section_ft") is not None:
        result["reverse_section_ft"] = result["zero_crown_ft"] + Lt
        if pt is not None:
            result["reverse_section_out_ft"] = result["zero_crown_out_ft"] - Lt
    result["inputs"]["runoff_tangent_percent"] = percent
    result["inputs"]["override_standard_placement"] = True
    result["calculation_metadata"]["manual_overrides"]["placement"] = True
    result.setdefault("warnings", []).append(
        f"Project placement override: {percent:g}% of runoff on tangent; governing DOT placement replaced."
    )
    result["runoff_tangent_fraction"] = p
    return result
