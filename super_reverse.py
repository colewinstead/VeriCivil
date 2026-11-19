"""Station-free transition demand for two opposite circular curves."""
from __future__ import annotations

import math

import Super
import aashto_superelevation as aashto
from criteria_info import AASHTO_PROFILE_ID, MDOT_PROFILE_ID, criteria_metadata, normalize_profile_id


INPUT_FIELDS = (
    "criteria_profile", "speed", "curve_direction", "facility", "area", "lane_width", "lanes_rotated",
    "normal_crown", "max_superelevation", "roadway", "initial_section", "rotation_axis", "lane_widths",
    "crown_from_left", "left_normal_slope", "right_normal_slope", "initial_slope", "aashto_tables",
    "runoff_tangent_percent", "circular_placement_basis", "case_ii_placement_mode",
)
SIDE_FIELDS = ("lane_count", "lane_width", "pivot_offset", "initial_slope", "runoff_tangent_percent", "circular_placement_basis")
OVERRIDES = ("e_manual", "friction", "rel_grad", "Lr_manual", "Lt_manual")


def _positive(raw, label):
    try:
        value = float(raw)
    except (ValueError, TypeError):
        raise ValueError(f"{label} must be a positive finite number.") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive finite number.")
    return value


def _reject_overrides(values):
    if any(values.get(key) not in (None, "") for key in OVERRIDES) or values.get("override_standard_placement") not in (None, "", False):
        raise ValueError("Required reverse tangent uses automatic rates and lengths; manual overrides are not supported.")


def _placement(values):
    percent = aashto._number(values, "runoff_tangent_percent")
    basis = values.get("circular_placement_basis", "runoff")
    aashto.circular_runoff_fraction(percent, basis, 1, 0)
    return percent, basis


def _curve(values, radius, direction):
    profile = normalize_profile_id(values.get("criteria_profile"))
    request = {**values, "radius": radius, "curve_direction": direction, "alignment_type": "circular"}
    if profile == AASHTO_PROFILE_ID:
        result = aashto.calculate(request, lengths_only=True)
        if result.get("carriageways"):
            from aashto_divided import common_curve_demand
            coordinated = values.get("case_ii_placement_mode", "coordinated") == "coordinated"
            percent, basis = _placement(values) if coordinated else (None, None)
            full = common_curve_demand(result["carriageways"], percent, basis) if coordinated else None
            for side, child in result["carriageways"].items():
                p, b = (percent, basis) if coordinated else _placement(values["case_ii"][side])
                child["tangent_demand_ft"] = aashto.circular_length_demand(child, p, b, full)
            demands = {side: child["tangent_demand_ft"] for side, child in result["carriageways"].items()}
        else:
            p, b = _placement(values)
            result["tangent_demand_ft"] = aashto.circular_length_demand(result, p, b)
            demands = {"roadway": result["tangent_demand_ft"]}
    else:
        result = Super.calculate_superelevation("", "", str(values["speed"]), str(radius),
            str(values.get("facility", "centerline")), str(values.get("area", "rural")),
            str(values.get("lane_width", "12")), str(values.get("lanes_rotated", "2")), "", "", "",
            str(values.get("normal_crown", "0.02")), "", "", criteria_profile=profile, lengths_only=True)
        if result.get("below_minimum_radius"):
            raise ValueError(result["e_note"])
        demand = (result["segments"]["approx_0p7L"] + result["Lt"] if profile == MDOT_PROFILE_ID
                  else result["segments"]["half_total_transition"])
        result["tangent_demand_ft"] = 0.0 if result["normal_crown_only"] else demand
        demands = {"roadway": result["tangent_demand_ft"]}
    for child in result.get("carriageways", {"roadway": result}).values():
        if child.get("section_transition"):
            child["section_transition"] = Super.section_transition_presentation(child["section_transition"])
    return {**result, "result_type": "reverse_curve_length_check", "radius_ft": radius, "curve_direction": direction}, demands


def required_reverse_tangent(inputs, radius_1, radius_2):
    """Return transition space, never an overall agency-compliance minimum."""
    if not isinstance(inputs, dict):
        raise ValueError("Roadway inputs must be an object.")
    _reject_overrides(inputs)
    if inputs.get("landxml_source") or inputs.get("geometry_provenance"):
        raise ValueError("Required reverse tangent is a manual-input check; imported geometry is not supported.")
    if inputs.get("alignment_type", "circular") != "circular":
        raise ValueError("Required reverse tangent applies to circular curves without spirals.")
    if inputs.get("linear_unit") not in (None, "", "foot", "Foot", "USSurveyFoot", "internationalFoot"):
        raise ValueError("Required reverse tangent uses radii and roadway dimensions in feet.")
    values = {key: inputs[key] for key in INPUT_FIELDS if key in inputs}
    values["criteria_profile"] = normalize_profile_id(values.get("criteria_profile"))
    if values.get("roadway") == "divided_case_ii" and values["criteria_profile"] != AASHTO_PROFILE_ID:
        raise ValueError("Case II requires the AASHTO 2018 criteria profile.")
    values["speed"] = _positive(values.get("speed"), "Design speed")
    for key, label, default in (("lane_width", "Lane width", 12), ("lanes_rotated", "Lanes rotated", 2), ("normal_crown", "Normal crown", .02)):
        values[key] = _positive(values.get(key, default), label)
    direction = values.get("curve_direction", "left")
    if direction not in {"left", "right"}:
        raise ValueError("First curve direction must be left or right.")
    divided = values.get("roadway") == "divided_case_ii" and values["criteria_profile"] == AASHTO_PROFILE_ID
    if divided:
        if inputs.get("case_ii_geometry_mode", "shared_corridor") != "shared_corridor":
            raise ValueError("This two-radius check requires Case II baseline radii and pavement offsets.")
        definitions = inputs.get("case_ii")
        if not isinstance(definitions, dict) or set(definitions) != {"left", "right"}:
            raise ValueError("Case II requires both carriageway sections and offsets.")
        values["case_ii_geometry_mode"] = "shared_corridor"
        values.setdefault("case_ii_placement_mode", "coordinated")
        values["case_ii"] = {}
        for side, definition in definitions.items():
            if not isinstance(definition, dict):
                raise ValueError("Carriageway inputs must be an object.")
            _reject_overrides(definition)
            values["case_ii"][side] = {**{key: definition[key] for key in SIDE_FIELDS if key in definition}, "speed": values["speed"]}
    curves, demands = [], []
    for index, (raw, turn) in enumerate(((radius_1, direction), (radius_2, "right" if direction == "left" else "left")), 1):
        try:
            curve, demand = _curve(values, _positive(raw, f"Curve {index} radius"), turn)
        except ValueError as exc:
            exc.args = (f"Curve {index}: {exc}",)
            raise
        curves.append(curve)
        demands.append(demand)
    combined = {side: demands[0][side] + demands[1][side] for side in demands[0]}
    controlling = max(combined, key=combined.get)
    linked = None
    if values["criteria_profile"] == MDOT_PROFILE_ID and all(not c["normal_crown_only"] and c["e"] > 0 and c["Lr"] > 0 for c in curves):
        linked = sum(c["segments"]["approx_0p7L"] for c in curves)
    warnings = []
    for index, curve in enumerate(curves, 1):
        for child in curve.get("carriageways", {"roadway": curve}).values():
            warnings.extend(f"Curve {index}: {note}" for note in child.get("warnings", []))
            if child.get("e_note"):
                warnings.append(f"Curve {index}: {child['e_note']}")
    return {
        "result_type": "reverse_tangent_check", "curves": curves,
        "independent_tangent_ft": combined[controlling], "mdot_linked_tangent_ft": linked,
        "carriageway_demands_ft": combined, "governing_carriageway": controlling,
        "calculation_metadata": {"criteria": criteria_metadata(values["criteria_profile"]),
                                 "engine_version": Super.CALCULATION_ENGINE_VERSION},
        "agency_minimum_status": "not_evaluated", "signing_status": "not_evaluated",
        "warnings": warnings,
        "scope_note": "Transition space between the first circular curve's PT and the second curve's PC, returning to the initial tangent section. No additional tangent hold is included. Signing, sight distance, drainage, circular-arc length adequacy and a complete agency spacing minimum are not evaluated.",
    }
