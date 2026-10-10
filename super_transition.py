"""Canonical MDOT lane-transition profiles.

This module owns the station/slope geometry used by the browser, engineering
lookup, QA, and every export.  Criteria lookup remains in :mod:`Super`; this
module only turns the recorded rate, runoff, runout, PC, and PT into piecewise
linear lane profiles.
"""

from __future__ import annotations

from typing import Any


EPSILON = 1e-9


def outside_lane(direction: str) -> str:
    return "left" if str(direction).strip().lower().startswith("r") else "right"


def _event(
    label: str,
    station_ft: float,
    slope_pct: float,
    note: str,
    event_type: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "label": label,
        "station_ft": float(station_ft),
        "slope_pct": float(slope_pct),
        "note": note,
        "event_type": event_type,
        **extra,
    }


def _linear_value(station: float, start_station: float, start_value: float, end_station: float, end_value: float) -> float:
    if end_station <= start_station + EPSILON:
        return float(end_value)
    fraction = max(0.0, min(1.0, (station - start_station) / (end_station - start_station)))
    return float(start_value) + fraction * (float(end_value) - float(start_value))


def _full_super_slopes(results: dict, direction: str) -> dict[str, float]:
    nc_pct = abs(float(results.get("inputs", {}).get("normal_crown", 0.02) or 0.02) * 100.0)
    e_pct = abs(float(results.get("e", 0.0) or 0.0) * 100.0)
    reverse_crown = str(results.get("crown_state", "")).lower().startswith("reverse")
    magnitude = nc_pct if reverse_crown else e_pct
    outside = outside_lane(direction)
    return {
        "left": magnitude if outside == "left" else -magnitude,
        "right": magnitude if outside == "right" else -magnitude,
    }


def _between(value: float, start: float, end: float, tolerance: float = 1e-7) -> bool:
    return min(start, end) - tolerance <= value <= max(start, end) + tolerance


def _line_value(station: float, origin_station: float, origin_slope: float, signed_rate: float) -> float:
    return float(origin_slope) + float(signed_rate) * (float(station) - float(origin_station))


def _zero_event_on_segment(
    start_station: float,
    start_slope: float,
    end_station: float,
    end_slope: float,
    *,
    pair_id: str,
) -> dict[str, Any] | None:
    if abs(start_slope) <= EPSILON or abs(end_slope) <= EPSILON:
        return None
    if start_slope * end_slope >= 0.0:
        return None
    fraction = -start_slope / (end_slope - start_slope)
    station = start_station + fraction * (end_station - start_station)
    return _event(
        "0%",
        station,
        0.0,
        "Zero-slope crossing on the standard-rate reverse transition",
        "Reverse curve zero",
        reverse_pair_id=pair_id,
        reverse_pair_critical=True,
    )


def build_reverse_pair_plan(
    prior_results: dict,
    prior_direction: str,
    following_results: dict,
    following_direction: str,
    *,
    pair_id: str,
    exact_minimum: bool,
) -> dict[str, Any]:
    """Build a continuous lane-specific reverse transition at standard rates.

    The standard rate for each curve is ``e/Lr``.  The outgoing and incoming
    rate lines either intersect between zero and normal crown or reach normal
    crown with a level crown hold between them.
    """
    prior_full = float(prior_results["full_super_out_ft"])
    following_full = float(following_results["full_super_ft"])
    prior_pt = float(prior_results["pt_ft"])
    following_pc = float(following_results["pc_ft"])
    prior_runoff = float(prior_results["Lr"])
    following_runoff = float(following_results["Lr"])
    prior_targets = _full_super_slopes(prior_results, prior_direction)
    following_targets = _full_super_slopes(following_results, following_direction)
    prior_e = max(abs(float(value)) for value in prior_targets.values())
    following_e = max(abs(float(value)) for value in following_targets.values())
    prior_nc = abs(float(prior_results.get("inputs", {}).get("normal_crown", 0.02)) * 100.0)
    following_nc = abs(float(following_results.get("inputs", {}).get("normal_crown", 0.02)) * 100.0)
    if prior_runoff <= EPSILON or following_runoff <= EPSILON or prior_e <= EPSILON or following_e <= EPSILON:
        raise ValueError("Both curves must have positive runoff lengths and superelevation rates.")
    if abs(prior_nc - following_nc) > 1e-7:
        raise ValueError("Linked reverse curves must use the same normal-crown slope.")
    if following_full <= prior_full + EPSILON:
        raise ValueError("The following full-super station must be after the prior full-super station.")

    prior_rate = prior_e / prior_runoff
    following_rate = following_e / following_runoff
    normal_crown = -prior_nc
    lanes: dict[str, dict[str, Any]] = {}

    for side in ("left", "right"):
        start_slope = float(prior_targets[side])
        end_slope = float(following_targets[side])
        if abs(end_slope - start_slope) <= EPSILON:
            raise ValueError(f"The {side} lane has no reverse-transition slope change.")
        direction_sign = 1.0 if end_slope > start_slope else -1.0
        outgoing_signed_rate = direction_sign * prior_rate
        incoming_signed_rate = direction_sign * following_rate
        outgoing_zero = prior_full + abs(start_slope) / prior_rate
        incoming_zero = following_full - abs(end_slope) / following_rate
        outgoing_nc = prior_full + abs(normal_crown - start_slope) / prior_rate
        incoming_nc = following_full - abs(end_slope - normal_crown) / following_rate

        hold_start: float | None = None
        hold_end: float | None = None
        if exact_minimum:
            if abs(outgoing_zero - incoming_zero) > 1e-5:
                raise ValueError(f"The {side} lane does not retain a single zero point at the minimum tangent.")
            handoff = 0.5 * (outgoing_zero + incoming_zero)
            handoff_slope = 0.0
            mode = "single_zero"
        elif outgoing_nc <= incoming_nc + 1e-7:
            hold_start = outgoing_nc
            hold_end = max(outgoing_nc, incoming_nc)
            handoff = None
            handoff_slope = None
            mode = "normal_crown_hold"
        else:
            denominator = outgoing_signed_rate - incoming_signed_rate
            numerator = (
                end_slope
                - start_slope
                + outgoing_signed_rate * prior_full
                - incoming_signed_rate * following_full
            )
            if abs(denominator) <= EPSILON:
                outgoing_at_overlap = _line_value(
                    incoming_nc, prior_full, start_slope, outgoing_signed_rate
                )
                incoming_at_overlap = _line_value(
                    incoming_nc, following_full, end_slope, incoming_signed_rate
                )
                if abs(outgoing_at_overlap - incoming_at_overlap) > 1e-7:
                    raise ValueError(f"The {side} lane standard-rate lines are parallel and do not meet.")
                handoff = 0.5 * (incoming_nc + outgoing_nc)
            else:
                handoff = numerator / denominator
            handoff_slope = _line_value(handoff, prior_full, start_slope, outgoing_signed_rate)
            incoming_slope = _line_value(handoff, following_full, end_slope, incoming_signed_rate)
            if abs(handoff_slope - incoming_slope) > 1e-6:
                raise ValueError(f"The {side} lane standard-rate handoff is discontinuous.")
            overlap_start = max(min(outgoing_nc, outgoing_zero), min(incoming_nc, incoming_zero))
            overlap_end = min(max(outgoing_nc, outgoing_zero), max(incoming_nc, incoming_zero))
            if overlap_start > overlap_end + 1e-7 or not _between(handoff, overlap_start, overlap_end):
                raise ValueError(f"The {side} lane standard-rate handoff is outside the overlapping zero-to-normal-crown transitions.")
            if not _between(handoff_slope, normal_crown, 0.0):
                raise ValueError(f"The {side} lane handoff slope is outside zero-to-normal-crown.")
            mode = "standard_rate_intersection"

        # PT and PC are geometric reference points inside the two recorded
        # runoffs, not hard limits on a reverse-transition rate change.  When
        # unequal standard rates meet, their continuous intersection may fall
        # just before PT or just after PC.  The two unchanged full-super
        # stations are the actual transition limits.
        if handoff is not None and not _between(handoff, prior_full, following_full):
            raise ValueError(f"The {side} lane handoff is outside the full-super transition limits.")

        outgoing_end_station = hold_start if hold_start is not None else handoff
        outgoing_end_slope = normal_crown if hold_start is not None else handoff_slope
        incoming_start_station = hold_end if hold_end is not None else handoff
        incoming_start_slope = normal_crown if hold_end is not None else handoff_slope

        def coordinated_slope(station: float) -> float:
            if hold_start is not None and hold_end is not None:
                if station < hold_start:
                    return _line_value(station, prior_full, start_slope, outgoing_signed_rate)
                if station <= hold_end:
                    return normal_crown
                return _line_value(station, following_full, end_slope, incoming_signed_rate)
            if handoff is not None and station <= handoff:
                return _line_value(station, prior_full, start_slope, outgoing_signed_rate)
            return _line_value(station, following_full, end_slope, incoming_signed_rate)

        prior_events: list[dict[str, Any]] = []
        prior_zero = _zero_event_on_segment(
            prior_full,
            start_slope,
            outgoing_end_station,
            outgoing_end_slope,
            pair_id=pair_id,
        )
        prior_pt_slope = coordinated_slope(prior_pt)
        prior_events.append(
            _event(
                "PT",
                prior_pt,
                prior_pt_slope,
                "Point on the outgoing standard-rate reverse transition",
                "PT reverse-curve runoff",
                reverse_pair_id=pair_id,
                reverse_pair_critical=True,
            )
        )
        if prior_zero is not None:
            prior_events.append(prior_zero)
        if hold_start is not None:
            prior_events.append(
                _event(
                    "NC HOLD START",
                    hold_start,
                    normal_crown,
                    "Outgoing standard-rate rotation reaches normal crown",
                    "Normal crown hold start",
                    reverse_pair_id=pair_id,
                    reverse_pair_critical=True,
                )
            )
        following_events: list[dict[str, Any]] = []
        if handoff is not None and handoff_slope is not None:
            handoff_label = "0% / HANDOFF" if abs(handoff_slope) <= 1e-7 else "HANDOFF"
            handoff_event = _event(
                handoff_label,
                handoff,
                handoff_slope,
                "Continuous lane-specific handoff between the two standard-rate transitions",
                "Reverse handoff",
                reverse_pair_id=pair_id,
                reverse_pair_critical=True,
            )
            prior_events.append(handoff_event)
            following_events.append(dict(handoff_event))
        if hold_end is not None:
            following_events.append(
                _event(
                    "NC HOLD END",
                    hold_end,
                    normal_crown,
                    "Incoming standard-rate rotation departs normal crown",
                    "Normal crown hold end",
                    reverse_pair_id=pair_id,
                    reverse_pair_critical=True,
                )
            )
        following_zero = _zero_event_on_segment(
            incoming_start_station,
            incoming_start_slope,
            following_full,
            end_slope,
            pair_id=pair_id,
        )
        if following_zero is not None:
            following_events.append(following_zero)
        following_pc_slope = coordinated_slope(following_pc)
        following_events.extend(
            [
                _event(
                    "PC",
                    following_pc,
                    following_pc_slope,
                    "Point on the incoming standard-rate reverse transition",
                    "PC reverse-curve runoff",
                    reverse_pair_id=pair_id,
                    reverse_pair_critical=True,
                ),
                _event(
                    "FULL SUPER",
                    following_full,
                    end_slope,
                    "PC + 0.3Lr; end of the standard-rate reverse transition",
                    "Full super",
                    reverse_pair_id=pair_id,
                    reverse_pair_critical=True,
                ),
            ]
        )
        prior_events.sort(key=lambda item: (float(item["station_ft"]), str(item["label"])))
        following_events.sort(key=lambda item: (float(item["station_ft"]), str(item["label"])))
        profile_events = [
            _event(
                "FULL SUPER",
                prior_full,
                start_slope,
                "PT - 0.3Lr; start of the outgoing standard-rate reverse transition",
                "End full super",
                reverse_pair_id=pair_id,
                reverse_pair_critical=True,
            ),
            *[dict(event) for event in prior_events],
            *[dict(event) for event in following_events],
        ]
        profile_events.sort(key=lambda item: (float(item["station_ft"]), str(item["label"])))

        zero_stations = sorted(
            {
                float(event["station_ft"])
                for event in prior_events + following_events
                if abs(float(event["slope_pct"])) <= 1e-7
            }
        )
        lanes[side] = {
            "side": side,
            "mode": mode,
            "outgoing_rate_pct_per_ft": prior_rate,
            "incoming_rate_pct_per_ft": following_rate,
            "handoff_station_ft": handoff,
            "handoff_slope_pct": handoff_slope,
            "outgoing_distance_to_handoff_ft": None if handoff is None else handoff - prior_full,
            "remaining_incoming_distance_ft": None if handoff is None else following_full - handoff,
            "outgoing_rotation_length_ft": outgoing_end_station - prior_full,
            "remaining_incoming_rotation_length_ft": following_full - incoming_start_station,
            "transition_start_ft": prior_full,
            "transition_end_ft": following_full,
            "zero_stations_ft": zero_stations,
            "normal_crown_hold": (
                None
                if hold_start is None or hold_end is None
                else {
                    "start_ft": hold_start,
                    "end_ft": hold_end,
                    "length_ft": max(0.0, hold_end - hold_start),
                    "slope_pct": normal_crown,
                }
            ),
            "prior_events": prior_events,
            "following_events": following_events,
            "profile_events": profile_events,
        }

    return {
        "pair_id": pair_id,
        "status": "coordinated",
        "transition_rate_status": "standard",
        "prior_rate_pct_per_ft": prior_rate,
        "following_rate_pct_per_ft": following_rate,
        "lanes": lanes,
    }


def _append_entry(
    rows: list[dict[str, Any]],
    results: dict,
    side: str,
    target_slope: float,
    coordinated: dict | None,
) -> None:
    pc = float(results["pc_ft"])
    full = float(results["full_super_ft"])
    runoff = float(results.get("Lr", 0.0) or 0.0)
    runout = float(results.get("Lt", 0.0) or 0.0)
    zero = float(results.get("reverse_crown_ft", pc - 0.7 * runoff))
    nc_pct = abs(float(results.get("inputs", {}).get("normal_crown", 0.02) or 0.02) * 100.0)
    outside = outside_lane(str(results.get("curve_direction", "left")))

    lane_coordination = (coordinated or {}).get("lanes", {}).get(side) if coordinated else None
    if lane_coordination:
        rows.extend(dict(event) for event in lane_coordination.get("events", []))
        return

    pnc = float(results.get("pnc_ft", zero - runout))
    rows.append(_event("NC", pnc, -nc_pct, "Start of tangent runout", "Normal crown"))
    if side == outside:
        rows.append(_event("0%", zero, 0.0, "End of tangent runout; start of runoff", "Reverse crown"))
        pc_slope = _linear_value(pc, zero, 0.0, full, target_slope)
    else:
        target_magnitude = abs(target_slope)
        if target_magnitude <= nc_pct + EPSILON:
            rotation_start = full
        else:
            rotation_start = zero + runoff * nc_pct / target_magnitude
        rows.append(_event("BEGIN ROTATION", rotation_start, -nc_pct, "MDOT SE-3A X1 = Lr(NC/e)", "Inside-lane rotation"))
        pc_slope = _linear_value(pc, rotation_start, -nc_pct, full, target_slope)
    fraction = results.get("runoff_tangent_fraction",0.7)
    rows.append(_event("PC", pc, pc_slope, f"{fraction*100:g}% of runoff occurs before PC", "PC 70% runoff" if fraction==0.7 else "PC project placement"))
    rows.append(_event("FULL SUPER", full, target_slope, "PC + 0.3Lr" if fraction==0.7 else f"PC + {(1-fraction):g}Lr", "Full super"))


def _append_exit(
    rows: list[dict[str, Any]],
    results: dict,
    side: str,
    target_slope: float,
    coordinated: dict | None,
) -> None:
    pt_value = results.get("pt_ft")
    full_value = results.get("full_super_out_ft")
    if pt_value is None or full_value is None:
        return
    pt = float(pt_value)
    full = float(full_value)
    runoff = float(results.get("Lr", 0.0) or 0.0)
    runout = float(results.get("Lt", 0.0) or 0.0)
    zero = float(results.get("reverse_crown_out_ft", pt + 0.7 * runoff))
    nc_pct = abs(float(results.get("inputs", {}).get("normal_crown", 0.02) or 0.02) * 100.0)
    outside = outside_lane(str(results.get("curve_direction", "left")))

    lane_coordination = (coordinated or {}).get("lanes", {}).get(side) if coordinated else None
    if lane_coordination:
        pair_id = next(
            (
                str(event.get("reverse_pair_id"))
                for event in lane_coordination.get("events", [])
                if event.get("reverse_pair_id")
            ),
            "",
        )
        rows.append(
            _event(
                "FULL SUPER",
                full,
                target_slope,
                "PT - 0.3Lr; start of the outgoing standard-rate reverse transition",
                "End full super",
                reverse_pair_id=pair_id,
                reverse_pair_critical=True,
            )
        )
        rows.extend(dict(event) for event in lane_coordination.get("events", []))
        return
    rows.append(_event("FULL SUPER", full, target_slope, "PT - 0.3Lr", "End full super"))

    if side == outside:
        rotation_end = zero
        end_slope = 0.0
    else:
        target_magnitude = abs(target_slope)
        if target_magnitude <= nc_pct + EPSILON:
            rotation_end = full
        else:
            rotation_end = zero - runoff * nc_pct / target_magnitude
        end_slope = -nc_pct
    pt_slope = _linear_value(pt, full, target_slope, rotation_end, end_slope)
    fraction = results.get("runoff_tangent_fraction",0.7)
    rows.append(_event("PT", pt, pt_slope, f"{fraction*100:g}% of runoff occurs after PT", "PT 70% runoff" if fraction==0.7 else "PT project placement"))
    if side == outside:
        rows.append(_event("0%", zero, 0.0, "End of runoff; start of tangent runout", "End runoff"))
    else:
        rows.append(_event("END ROTATION", rotation_end, -nc_pct, "MDOT SE-3A X1 = Lr(NC/e)", "Inside-lane rotation"))
    rows.append(_event("NC", zero + runout, -nc_pct, "End of tangent runout", "Back to normal crown"))


def build_mdot_lane_events(results: dict, direction: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build the canonical piecewise-linear MDOT lane profiles."""
    direction_text = (direction or "left").strip().lower() or "left"
    working = dict(results)
    working["curve_direction"] = direction_text
    pc = float(working.get("pc_ft", 0.0) or 0.0)
    pt_value = working.get("pt_ft")
    nc_pct = abs(float(working.get("inputs", {}).get("normal_crown", 0.02) or 0.02) * 100.0)

    if working.get("normal_crown_only"):
        left = [_event("NC", pc, -nc_pct, "Normal crown maintained", "Normal crown")]
        right = [_event("NC", pc, -nc_pct, "Normal crown maintained", "Normal crown")]
        if pt_value is not None and not abs(float(pt_value) - pc) <= EPSILON:
            left.append(_event("NC", float(pt_value), -nc_pct, "Normal crown maintained through curve", "Normal crown"))
            right.append(_event("NC", float(pt_value), -nc_pct, "Normal crown maintained through curve", "Normal crown"))
        return left, right

    coordination = working.get("reverse_curve_coordination", {}) or {}
    entry = coordination.get("entry")
    exit_transition = coordination.get("exit")
    targets = _full_super_slopes(working, direction_text)
    lane_rows: dict[str, list[dict[str, Any]]] = {"left": [], "right": []}
    for side in ("left", "right"):
        _append_entry(lane_rows[side], working, side, targets[side], entry)
        _append_exit(lane_rows[side], working, side, targets[side], exit_transition)
        lane_rows[side].sort(key=lambda item: (float(item["station_ft"]), item["label"]))
    return lane_rows["left"], lane_rows["right"]
