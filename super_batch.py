from __future__ import annotations

import copy
import math
from typing import Iterable

import Super
import super_transition
import super_exports


def compound_pairs(curves: list[dict]) -> list[tuple[int, int]]:
    """Find adjoining circular arcs; a real intervening tangent stays independent."""
    pairs = []
    for index, (prior, following) in enumerate(zip(curves, curves[1:])):
        a, b = prior.get("results", {}), following.get("results", {})
        if (a.get("pt_ft") is not None and b.get("pc_ft") is not None
                and math.isclose(float(a["pt_ft"]), float(b["pc_ft"]), rel_tol=0, abs_tol=1e-7)
                and prior.get("meta", {}).get("curve_direction", "left") == following.get("meta", {}).get("curve_direction", "left")
                and prior.get("meta", {}).get("alignment_name", "") == following.get("meta", {}).get("alignment_name", "")
                and all(r.get("inputs", {}).get("alignment_type", "circular") == "circular" for r in (a, b))):
            pairs.append((index, index + 1))
    return pairs


def restore_compound_transitions(curves: list[dict]) -> None:
    for curve in curves:
        baseline = curve.get("results", {}).get("uncoordinated_compound_transition")
        if baseline is not None:
            curve["results"] = copy.deepcopy(baseline)


def coordinate_compound_curve_transitions(curves: Iterable[dict]) -> list[dict]:
    """Apply the project compound rule at the controlling curve's existing rate."""
    curves = copy.deepcopy(list(curves))
    restore_compound_transitions(curves)
    plans = {}
    for i, j in compound_pairs(curves):
        a, b = curves[i]["results"], curves[j]["results"]
        if any(r.get("normal_crown_only") and not r.get("section_transition") for r in (a, b)):
            raise ValueError("Compound curves require banked sections on both arcs; normal-crown compound transitions need a separate design.")
        if a.get("calculation_metadata", {}).get("criteria", {}).get("profile_id") != b.get("calculation_metadata", {}).get("criteria", {}).get("profile_id"):
            raise ValueError("Compound curves must use the same criteria profile.")
        section_a, section_b = a.get("section_definition") or {}, b.get("section_definition") or {}
        differences = [f"{key}: {section_a.get(key)!r} vs {section_b.get(key)!r}"
                       for key in sorted(section_a.keys() | section_b.keys())
                       if section_a.get(key) != section_b.get(key)]
        differences.extend(f"{key}: {a.get('inputs', {}).get(key)!r} vs {b.get('inputs', {}).get(key)!r}"
                           for key in ("facility", "lane_width_ft", "lanes_rotated", "normal_crown")
                           if a.get("inputs", {}).get(key) != b.get("inputs", {}).get(key))
        if differences:
            names = [curves[index].get("meta", {}).get("curve_name") or f"Curve {index + 1}" for index in (i, j)]
            raise ValueError(f"{names[0]} / {names[1]}: Compound curves must use the same cross section and rotation axis. Differences: {'; '.join(differences)}.")
        direction = curves[i].get("meta", {}).get("curve_direction", "left")
        outside = super_transition.outside_lane(direction)
        if any(super_transition._full_super_slopes(r, direction)[outside] <= 0 for r in (a, b)):
            raise ValueError("Compound transitions require both sections to bank toward the curve; an adverse initial section needs a separate design.")
        e1 = abs(super_transition._full_super_slopes(a, direction)[super_transition.outside_lane(direction)]) / 100
        e2 = abs(super_transition._full_super_slopes(b, direction)[super_transition.outside_lane(direction)]) / 100
        controlling = b if float(b["inputs"]["radius_ft"]) < float(a["inputs"]["radius_ft"]) else a
        magnitude = e2 if controlling is b else e1
        runoff = float(controlling["Lr"])
        # A favorable single-slope ramp's runoff starts at its initial bank.
        initial = controlling.get("section_transition", {}).get("initial_signed_slope", 0) if controlling.get("section_transition") else 0
        bank_sign = -1 if direction == "left" else 1
        runoff_change = magnitude - abs(initial) if initial * bank_sign > 0 else magnitude
        if runoff_change <= 0 or runoff <= 0:
            if abs(e2 - e1) > 1e-12:
                raise ValueError("The controlling compound curve needs a positive runoff rate.")
            rate = 0.0
        else:
            rate = runoff_change / runoff
        length = abs(e2 - e1) / rate if rate else 0.0
        p = controlling.get("runoff_tangent_fraction")
        if p is None:
            if controlling.get("transition_method") == "aashto_fixed_pivot":
                from aashto_superelevation import circular_runoff_fraction
                p = circular_runoff_fraction(float(controlling["inputs"]["runoff_tangent_percent"]),
                    controlling["inputs"].get("circular_placement_basis", "runoff"), float(controlling["Lr"]), float(controlling["Lt"]))
            elif controlling.get("transition_method") == "tdot_simple_curve_half_total":
                p = (runoff - float(controlling["Lt"])) / (2 * runoff)
            else:
                p = 0.7
        if not all(math.isfinite(v) for v in (e1, e2, rate, length, p)) or not 0 <= p <= 1:
            raise ValueError("Compound runoff rate and placement must be finite and valid.")
        before = p if controlling is b else 1 - p
        boundary = float(a["pt_ft"])
        plan = {"pair_id": f"compound-{i}-{j}", "boundary_ft": boundary,
                "start_ft": boundary - before * length, "end_ft": boundary + (1 - before) * length,
                "length_ft": length, "start_e": e1, "end_e": e2,
                "rate_pct_per_ft": rate * 100, "before_fraction": before,
                "controlling_curve_index": j if controlling is b else i,
                "rule": "Project compound transition; reduced slope change at the controlling curve's runoff rate"}
        plans[i, "exit"] = plans[j, "entry"] = plan

    for index, curve in enumerate(curves):
        entry, exit_plan = plans.get((index, "entry")), plans.get((index, "exit"))
        if entry is None and exit_plan is None:
            continue
        result = curve["results"]
        original = copy.deepcopy(result)
        result["uncoordinated_compound_transition"] = original
        result["compound_curve_transitions"] = {side: plan for side, plan in (("entry", entry), ("exit", exit_plan)) if plan}
        changes_bank = any(plan["length_ft"] > 1e-9 for plan in result["compound_curve_transitions"].values())
        result["normal_crown_only"] = bool(original.get("normal_crown_only")) and not changes_bank
        if "no_transition_required" in result:
            result["no_transition_required"] = bool(original["no_transition_required"]) and not changes_bank
        if result.get("section_transition"):
            result["section_transition"]["no_transition_required"] = result["no_transition_required"]
            result["section_transition"]["note"] = "Single-slope bank retained between the compound transitions. Cross-slope sign: + rises toward left; - rises toward right, looking ahead along increasing alignment station."
        if entry:
            result.update(pnc_ft=entry["start_ft"], reverse_crown_ft=entry["start_ft"], full_super_ft=entry["end_ft"])
        if exit_plan:
            result.update(full_super_out_ft=exit_plan["start_ft"], reverse_crown_out_ft=exit_plan["end_ft"], pnc_out_ft=exit_plan["end_ft"])
        if result["full_super_ft"] > result["full_super_out_ft"] + 1e-7:
            raise ValueError(f"Compound transitions overlap on Curve {index + 1}; the selected runoff rate and placement cannot attain its design bank.")
        direction = curve.get("meta", {}).get("curve_direction", "left")
        targets = super_transition._full_super_slopes(original, direction)

        def events_for(side, events, lane=None):
            rows = []
            if not entry:
                rows.extend(copy.deepcopy(event) for event in events if event["station_ft"] <= original["full_super_ft"] + 1e-7)
            if not exit_plan:
                rows.extend(copy.deepcopy(event) for event in events if event["station_ft"] >= original["full_super_out_ft"] - 1e-7)
            for plan in (entry, exit_plan):
                if plan is None:
                    continue
                controls = [("PCC", plan["boundary_ft"], "Compound junction")] if plan["length_ft"] <= 1e-9 else [
                    ("COMPOUND START", plan["start_ft"], "Compound runoff start"),
                    ("PCC", plan["boundary_ft"], "Compound junction"),
                    ("COMPOUND END", plan["end_ft"], "Compound runoff end")]
                for label, station, event_type in controls:
                    t = (station - plan["start_ft"]) / plan["length_ft"] if plan["length_ft"] else 0
                    bank = plan["start_e"] + t * (plan["end_e"] - plan["start_e"])
                    slope = bank * 100 * (1 if side == super_transition.outside_lane(direction) else -1)
                    event = super_transition._event(label, station, slope, plan["rule"], event_type, compound_pair_id=plan["pair_id"])
                    if lane:
                        signed_bank = bank * (-1 if direction == "left" else 1)
                        event.update(right_elevation_ft=signed_bank * lane["right_distance_from_pivot_ft"],
                                     left_elevation_ft=signed_bank * lane["left_distance_from_pivot_ft"])
                    rows.append(event)
            for label, station in (("PC", result["pc_ft"]), ("PT", result["pt_ft"])):
                if result["full_super_ft"] < station < result["full_super_out_ft"]:
                    event = super_transition._event(label, station, targets[side], "Full bank through the circular arc", label)
                    if lane:
                        bank = abs(targets[side]) / 100 * (-1 if direction == "left" else 1)
                        event.update(right_elevation_ft=bank * lane["right_distance_from_pivot_ft"], left_elevation_ft=bank * lane["left_distance_from_pivot_ft"])
                    rows.append(event)
            rows.sort(key=lambda event: event["station_ft"])
            return rows

        if original.get("section_lanes"):
            for lane in result["section_lanes"]:
                lane["events"] = events_for(lane["side"], lane["events"], lane)
            result["lane_events"] = {side: next((lane["events"] for lane in result["section_lanes"] if lane["side"] == side), []) for side in ("left", "right")}
        else:
            left, right = super_exports.build_lane_rows(original, direction, False)
            result["lane_events"] = {side: events_for(side, events) for side, events in (("left", left), ("right", right))}
        limits = result.get("alignment_station_range")
        if limits and (result["pnc_ft"] < limits[0] - 1e-7 or result["pnc_out_ft"] > limits[1] + 1e-7):
            raise ValueError("Compound transition extends beyond the established alignment.")
        for side, plan in result["compound_curve_transitions"].items():
            result["calculation_metadata"].setdefault("calculation_sources", []).append({"component": f"Compound {side}", "reference": plan["rule"], "mode": "project_input", **plan})
    return curves


_ENTRY_TRANSITION_KEYS = ("pnc_ft", "reverse_crown_ft", "full_super_ft")
_EXIT_TRANSITION_KEYS = ("full_super_out_ft", "reverse_crown_out_ft", "pnc_out_ft")


def _restore_reverse_curve_transitions(curves: list[dict]) -> None:
    for curve in curves:
        results = curve.get("results", {}) or {}
        originals = results.pop("uncoordinated_reverse_curve_transition", {}) or {}
        for key, value in originals.get("entry", {}).items():
            results[key] = value
        for key, value in originals.get("exit", {}).items():
            results[key] = value
        results.pop("reverse_curve_entry_zero_ft", None)
        results.pop("reverse_curve_exit_zero_ft", None)
        results.pop("reverse_curve_transitions", None)
        results.pop("reverse_curve_coordination", None)


def _normalized_pairs(
    curves: list[dict],
    pairs: Iterable[Iterable[int]] | None,
) -> list[tuple[int, int]]:
    if pairs is None:
        return []
    normalized: list[tuple[int, int]] = []
    used: set[int] = set()
    for raw_pair in pairs:
        values = list(raw_pair)
        if len(values) != 2:
            raise ValueError("Each reverse-curve pair must contain exactly two curve indexes.")
        try:
            prior_index, following_index = (int(values[0]), int(values[1]))
        except (TypeError, ValueError) as exc:
            raise ValueError("Reverse-curve pair indexes must be integers.") from exc
        if prior_index < 0 or following_index >= len(curves):
            raise ValueError("Reverse-curve pair indexes are outside the calculated curve set.")
        if following_index != prior_index + 1:
            raise ValueError("Reverse-curve pairs must contain adjacent curves in increasing order.")
        if prior_index in used or following_index in used:
            raise ValueError("A curve cannot belong to more than one reverse-curve pair.")
        used.update((prior_index, following_index))
        normalized.append((prior_index, following_index))
    return sorted(set(normalized))


def _pair_ineligibility(prior: dict, following: dict) -> str | None:
    prior_results = prior.get("results", {}) or {}
    following_results = following.get("results", {}) or {}
    prior_profile = str(prior_results.get("calculation_metadata", {}).get("criteria", {}).get("profile_id", ""))
    following_profile = str(following_results.get("calculation_metadata", {}).get("criteria", {}).get("profile_id", ""))
    prior_direction = str(prior.get("meta", {}).get("curve_direction", "left")).lower()
    following_direction = str(following.get("meta", {}).get("curve_direction", "left")).lower()
    if not prior_profile.startswith("mdot") or not following_profile.startswith("mdot"):
        return "Both linked curves must use an MDOT criteria profile."
    if prior_results.get("runoff_tangent_fraction") is not None or following_results.get("runoff_tangent_fraction") is not None:
        return "Custom runoff placement is not eligible for the MDOT 0.7Lr reverse-curve coordination rule."
    if prior_direction == following_direction:
        return "Linked reverse curves must turn in opposite directions."
    if prior_results.get("normal_crown_only") or following_results.get("normal_crown_only"):
        return "Normal-crown-only curves cannot use reverse-curve coordination."
    if prior_results.get("pt_ft") is None or following_results.get("pc_ft") is None:
        return "Both linked curves must have a PT/PC tangent boundary."
    if float(prior_results.get("Lr", 0.0) or 0.0) <= 0.0 or float(following_results.get("Lr", 0.0) or 0.0) <= 0.0:
        return "Both linked curves must have positive runoff lengths."

    def effective_transition_magnitude(results: dict) -> float:
        if str(results.get("crown_state", "")).lower().startswith("reverse"):
            return abs(float(results.get("inputs", {}).get("normal_crown", 0.02) or 0.02))
        return abs(float(results.get("e", 0.0) or 0.0))

    if effective_transition_magnitude(prior_results) <= 0.0 or effective_transition_magnitude(following_results) <= 0.0:
        return (
            "Both linked curves must require a positive cross-slope transition; "
            "a 0% superelevation curve does not need reverse-curve coordination."
        )
    return None


def coordinate_reverse_curve_transitions(
    curves: Iterable[dict],
    enabled: bool = True,
    pairs: Iterable[Iterable[int]] | None = None,
) -> list[dict]:
    """Coordinate explicitly paired MDOT reverse curves at standard rates."""
    coordinated = copy.deepcopy(list(curves))
    restore_compound_transitions(coordinated)
    _restore_reverse_curve_transitions(coordinated)
    if not enabled:
        return coordinate_compound_curve_transitions(coordinated)

    for prior_index, following_index in _normalized_pairs(coordinated, pairs):
        prior = coordinated[prior_index]
        following = coordinated[following_index]
        prior_results = prior.get("results", {}) or {}
        following_results = following.get("results", {}) or {}
        prior_direction = str(prior.get("meta", {}).get("curve_direction", "left")).lower()
        following_direction = str(following.get("meta", {}).get("curve_direction", "left")).lower()
        pair_id = f"reverse-pair-{prior_index}-{following_index}"
        ineligibility = _pair_ineligibility(prior, following)
        prior_pt = float(prior_results.get("pt_ft", 0.0) or 0.0)
        following_pc = float(following_results.get("pc_ft", 0.0) or 0.0)
        prior_runoff = float(prior_results.get("Lr", 0.0) or 0.0)
        following_runoff = float(following_results.get("Lr", 0.0) or 0.0)
        available = following_pc - prior_pt
        required = 0.7 * prior_runoff + 0.7 * following_runoff
        check = {
            "pair_id": pair_id,
            "paired_curve_indexes": [prior_index, following_index],
            "tangent_start_ft": prior_pt,
            "tangent_end_ft": following_pc,
            "available_tangent_ft": available,
            "minimum_tangent_ft": required,
            "deficit_ft": max(0.0, required - available),
            "rule": "Tmin = 0.7Lr(exit) + 0.7Lr(entry)",
            "status": "invalid_pair" if ineligibility else (
                "coordinated" if available + 1e-7 >= required else "short_tangent"
            ),
            "transition_rate_status": "standard",
            "failure_reason": ineligibility or "",
        }
        prior_coordination = prior_results.setdefault("reverse_curve_coordination", {"checks": []})
        following_coordination = following_results.setdefault("reverse_curve_coordination", {"checks": []})
        if check["status"] in {"invalid_pair", "short_tangent"}:
            prior_coordination.setdefault("checks", []).append(copy.deepcopy(check))
            following_coordination.setdefault("checks", []).append(copy.deepcopy(check))
            continue

        try:
            plan = super_transition.build_reverse_pair_plan(
                prior_results,
                prior_direction,
                following_results,
                following_direction,
                pair_id=pair_id,
                exact_minimum=abs(available - required) <= 1e-7,
            )
        except (KeyError, TypeError, ValueError) as exc:
            check["status"] = "invalid_handoff"
            check["failure_reason"] = str(exc)
            prior_coordination.setdefault("checks", []).append(copy.deepcopy(check))
            following_coordination.setdefault("checks", []).append(copy.deepcopy(check))
            continue

        check.update({
            "prior_rate_pct_per_ft": plan["prior_rate_pct_per_ft"],
            "following_rate_pct_per_ft": plan["following_rate_pct_per_ft"],
            "lanes": copy.deepcopy(plan["lanes"]),
        })
        prior_coordination.setdefault("checks", []).append(copy.deepcopy(check))
        following_coordination.setdefault("checks", []).append(copy.deepcopy(check))
        prior_exit = {
            "pair_id": pair_id,
            "paired_curve_index": following_index,
            "runoff_length_ft": prior_runoff,
            "lanes": {
                side: {"events": copy.deepcopy(plan["lanes"][side]["prior_events"])}
                for side in ("left", "right")
            },
        }
        following_entry = {
            "pair_id": pair_id,
            "paired_curve_index": prior_index,
            "runoff_length_ft": following_runoff,
            "lanes": {
                side: {"events": copy.deepcopy(plan["lanes"][side]["following_events"])}
                for side in ("left", "right")
            },
        }
        prior_coordination["exit"] = prior_exit
        following_coordination["entry"] = following_entry
        prior_results.setdefault("reverse_curve_transitions", []).append({"role": "exit", **prior_exit})
        following_results.setdefault("reverse_curve_transitions", []).append({"role": "entry", **following_entry})

    for curve in coordinated:
        coordination = (curve.get("results", {}) or {}).get("reverse_curve_coordination")
        if not coordination:
            continue
        statuses = {check.get("status") for check in coordination.get("checks", [])}
        coordination["status"] = next(iter(statuses), "coordinated")
    return coordinate_compound_curve_transitions(coordinated)


def build_curve_from_preset(preset: dict, shared_inputs: dict[str, str], *, compound_sides=()) -> dict:
    results = Super.calculate_superelevation(
        str(preset["pc_station_label"]),
        str(preset.get("pt_station_label", "") or ""),
        str(shared_inputs.get("speed", "")),
        str(preset["radius_ft"]),
        str(shared_inputs.get("facility", "centerline")),
        str(shared_inputs.get("area", "rural")),
        str(shared_inputs.get("lane_width", "12")),
        str(shared_inputs.get("lanes_rotated", "2")),
        str(shared_inputs.get("e_manual", "")),
        str(shared_inputs.get("friction", "")),
        str(shared_inputs.get("rel_grad", "")),
        str(shared_inputs.get("normal_crown", "0.02")),
        str(shared_inputs.get("Lr_manual", "")),
        str(shared_inputs.get("Lt_manual", "")),
        preset.get("station_equations"),
        preset.get("alignment_station_range"),
        str(shared_inputs.get("criteria_profile", "mdot-rdsd-2026-04-22")),
        profile_options={**shared_inputs,"curve_direction":preset.get("curve_direction","left"),
                         "alignment_type":preset.get("alignment_type","circular"),
                         "ts":preset.get("ts_station_label",""), "st":preset.get("st_station_label",""),
                         "linear_unit":preset.get("linear_unit"),
                         "geometry_provenance":{"source":"LandXML","alignment":preset.get("alignment_name"),"curve_id":preset.get("landxml_curve_id"),"linear_unit":preset.get("linear_unit"),"available_entry_tangent_ft":preset.get("available_entry_tangent_ft"),"available_exit_tangent_ft":preset.get("available_exit_tangent_ft")}},
        compound_sides=compound_sides,
    )
    return {
        "results": results,
        "meta": {
            "landxml_curve_index": preset.get("landxml_curve_index"),
            "landxml_curve_id": str(preset.get("landxml_curve_id", "") or ""),
            "project_name": str(shared_inputs.get("project_name", "") or ""),
            "route_name": str(shared_inputs.get("route_name", "") or ""),
            "alignment_name": str(preset.get("alignment_name", "") or ""),
            "curve_name": str(preset.get("curve_name", "") or ""),
            "curve_direction": str(preset.get("curve_direction", "left") or "left"),
        },
        "notes": str(shared_inputs.get("curve_notes", "") or ""),
    }


def build_curves_from_presets(presets: Iterable[dict], shared_inputs: dict[str, str], curve_inputs: dict[int, dict] | None = None) -> list[dict]:
    """Coordinate adjoining compound arcs; reverse coordination remains explicit."""
    presets = list(presets)
    adjacency = [{"results": {"pc_ft": Super.parse_station_reference(str(p["pc_station_label"]), p.get("station_equations"), p.get("alignment_station_range")),
                               "pt_ft": Super.parse_station_reference(str(p["pt_station_label"]), p.get("station_equations"), p.get("alignment_station_range")) if p.get("pt_station_label") else None,
                               "inputs": {"alignment_type": p.get("alignment_type", "circular")}},
                  "meta": p} for p in presets]
    sides = {}
    for i, j in compound_pairs(adjacency):
        sides.setdefault(i, []).append("exit")
        sides.setdefault(j, []).append("entry")
    curves=[]
    for index,preset in enumerate(presets):
        try:
            values = {**shared_inputs, **(curve_inputs or {}).get(preset.get("landxml_curve_index", index), {})}
            curves.append(build_curve_from_preset(preset,values,compound_sides=tuple(sides.get(index, []))))
        except ValueError as exc:
            curve_name = preset.get("curve_name") or f"Curve {index+1}"
            exc.args = (f"{curve_name}: {exc}",)
            for finding in getattr(exc,"findings",[]):
                finding["curve_indexes"]=[preset.get("landxml_curve_index", index)]
                finding["message"]=f"{preset.get('curve_name',f'Curve {index+1}')}: {finding['message']}"
            raise
    return coordinate_compound_curve_transitions(curves)
