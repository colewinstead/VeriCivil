from __future__ import annotations

import copy
from typing import Iterable

import Super
import super_transition


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
    _restore_reverse_curve_transitions(coordinated)
    if not enabled:
        return coordinated

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
    return coordinated


def build_curve_from_preset(preset: dict, shared_inputs: dict[str, str]) -> dict:
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


def build_curves_from_presets(presets: Iterable[dict], shared_inputs: dict[str, str]) -> list[dict]:
    """Build independent curves; reverse coordination is an explicit pair action."""
    curves=[]
    for index,preset in enumerate(presets):
        try:
            curves.append(build_curve_from_preset(preset,shared_inputs))
        except ValueError as exc:
            for finding in getattr(exc,"findings",[]):
                finding["curve_indexes"]=[index]
                finding["message"]=f"{preset.get('curve_name',f'Curve {index+1}')}: {finding['message']}"
            raise
    return curves
