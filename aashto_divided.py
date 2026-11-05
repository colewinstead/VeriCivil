"""AASHTO Case II: separate planes about level median-side travel-lane edges."""
from __future__ import annotations

import copy

import aashto_superelevation as section

PROFILE_ID = section.PROFILE_ID
METHOD = "aashto_case_ii"
SIDES = ("left", "right")
SIDE_FIELDS = {"speed", "radius", "lane_count", "lane_width", "initial_slope", "pivot_offset",
               "runoff_tangent_percent", "circular_placement_basis", "runout_placement",
               "override_standard_placement", "acknowledge_spiral_override", "e_manual", "Lr_manual", "Lt_manual"}


def is_case_ii(result: dict) -> bool:
    return result.get("transition_method") == METHOD


def calculate(values: dict, station_equations=None, alignment_range=None, *, lengths_only=False) -> dict:
    from app_info import CALCULATION_ENGINE_VERSION
    from criteria_info import criteria_metadata, normalize_profile_id

    if normalize_profile_id(values.get("criteria_profile")) != PROFILE_ID:
        raise ValueError("Case II requires the AASHTO 2018 criteria profile.")
    definitions = values.get("case_ii")
    if not isinstance(definitions, dict) or set(definitions) != set(SIDES):
        raise ValueError("Case II requires both left and right carriageway inputs.")
    geometry_mode = values.get("case_ii_geometry_mode", "explicit_radii")
    placement_mode = values.get("case_ii_placement_mode", "coordinated" if geometry_mode == "shared_corridor" else "independent")
    if geometry_mode not in {"explicit_radii", "shared_corridor"}:
        raise ValueError("Select shared-corridor or engineer-entered radius geometry.")
    if placement_mode not in {"independent", "coordinated"}:
        raise ValueError("Select coordinated or independent Case II placement.")
    if lengths_only and values.get("geometry_provenance", {}).get("source") == "LandXML":
        raise ValueError("Required spiral lengths is a manual-input check; use the imported alignment's established stations.")
    coordinated = placement_mode == "coordinated" and values.get("alignment_type", "circular") != "spiral"
    requests, radius_sources = {}, {}
    children, pivots, errors, findings = {}, {}, [], []
    common = {key: value for key, value in values.items()
              if key not in SIDE_FIELDS | {"case_ii", "lane_widths", "initial_slope", "roadway"}}
    for side in SIDES:
        definition = definitions[side]
        try:
            if not isinstance(definition, dict):
                raise ValueError("Carriageway inputs must be an object.")
            offset = (None if lengths_only and geometry_mode == "explicit_radii" and definition.get("pivot_offset") in (None, "")
                      else section._number(definition, "pivot_offset"))
            count = section._number(definition, "lane_count", 4)
            if not count.is_integer() or not 1 <= count <= 7:
                raise ValueError("Supply a whole lane count from 1 through 7 per carriageway.")
            width = section._number(definition, "lane_width", 12)
            if width <= 0:
                raise ValueError("Lane width must be positive.")
            if definition.get("initial_slope", 0) in (None, "", "-"):
                raise ValueError("Enter the initial slope magnitude and drainage direction.")
            definition = dict(definition)
            if geometry_mode == "shared_corridor":
                baseline_radius = section._number(values, "radius")
                if baseline_radius <= 0:
                    raise ValueError("Baseline radius must be positive.")
                direction = values.get("curve_direction", "left")
                if direction not in {"left", "right"}:
                    raise ValueError("Curve direction must be left or right.")
                left_edge, right_edge = ((offset - count * width, offset) if side == "left"
                                         else (offset, offset + count * width))
                controlling_offset = left_edge if direction == "left" else right_edge
                radius = baseline_radius + controlling_offset * (1 if direction == "left" else -1)
                if radius <= 0:
                    raise ValueError("The inside-curve pavement edge reaches or crosses the curve center; derived radius must be positive.")
                definition["radius"] = radius
                radius_sources[side] = {"source": "baseline_offset", "baseline_radius_ft": baseline_radius,
                    "controlling_edge_offset_ft": controlling_offset, "design_radius_ft": radius,
                    "reference": "AASHTO §3.3.3.3; inside edge of innermost travel lane; constant right-positive baseline offset"}
            else:
                radius_sources[side] = {"source": "engineer_entered", "design_radius_ft": section._number(definition, "radius"),
                    "reference": "Engineer-entered design radius; pavement reference not inferred"}
            # Each side extends away from its median-side pivot.
            child_values = {**common, **{key: value for key, value in definition.items() if key in SIDE_FIELDS},
                            "roadway": "one_way", "initial_section": "single_slope",
                            "rotation_axis": "right_edge" if side == "left" else "left_edge",
                            "lane_widths": ",".join([str(width)] * int(count)),
                            "initial_slope": definition.get("initial_slope", -.02 if side == "left" else .02)}
            if coordinated:
                child_values.update(runoff_tangent_percent=values.get("runoff_tangent_percent"),
                                    circular_placement_basis=values.get("circular_placement_basis", "runoff"))
            requests[side] = child_values
            child = section.calculate(child_values, station_equations, alignment_range,
                                      lengths_only=lengths_only or coordinated, _case_ii=True)
            children[side] = child
            # Input offsets are right-positive; shared section coordinates are left-positive.
            pivots[side] = {"x": -offset if offset is not None else None, "y": 0.0, "label": f"{side.title()} median-side travel-lane edge"}
        except (ValueError, TypeError, OverflowError) as exc:
            message = f"{side.title()} carriageway: {exc}"
            errors.append(message)
            for finding in getattr(exc, "findings", []) or [{"code": "INVALID_CASE_II_SIDE", "severity": "block", "message": str(exc)}]:
                findings.append({**finding, "message": f"{side.title()} carriageway: {finding['message']}", "carriageway": side})
    if errors:
        raise section.TransitionError("; ".join(errors), findings)
    positioned = all(pivots[side]["x"] is not None for side in SIDES)
    if positioned and pivots["left"]["x"] <= pivots["right"]["x"]:
        raise ValueError("The left carriageway pivot must lie left of the right pivot (positive right, negative left: left offset must be less than right offset).")

    full_anchors = None
    if coordinated and not lengths_only:
        import Super
        active = [child for child in children.values() if not child["no_transition_required"]]
        if active:
            percent = section._number(values, "runoff_tangent_percent")
            basis = values.get("circular_placement_basis", "runoff")
            demands = []
            for child in active:
                fraction = section.circular_runoff_fraction(percent, basis, child["Lr"], child["Lt"])
                # RC can have runout only; total-transition placement still has a curve-side demand.
                demand = ((1 - percent / 100) * (child["Lr"] + child["Lt"]) if basis == "runoff_runout"
                          else (1 - fraction) * child["Lr"])
                demands.append(demand)
            equations = Super.strict_station_equations(station_equations)
            full_anchors = (section._station(values, "pc", "PC", equations, alignment_range) + max(demands),
                            section._station(values, "pt", "PT", equations, alignment_range) - max(demands))
        for side in SIDES:
            try:
                children[side] = section.calculate(requests[side], station_equations, alignment_range,
                                                   _case_ii=True, _full_super_anchors=full_anchors)
            except (ValueError, TypeError, OverflowError) as exc:
                errors.append(f"{side.title()} carriageway: {exc}")
                findings.extend({**f, "message": f"{side.title()} carriageway: {f['message']}", "carriageway": side}
                                for f in getattr(exc, "findings", []) or [{"code": "INVALID_CASE_II_SIDE", "severity": "block", "message": str(exc)}])
        if errors:
            raise section.TransitionError("; ".join(errors), findings)
    for side, child in children.items():
        child.update(baseline_radius_ft=values.get("radius"), case_ii_side=side,
                     baseline_pivot_offset_ft=-pivots[side]["x"] if pivots[side]["x"] is not None else None,
                     radius_provenance=radius_sources[side], case_ii_placement_mode=placement_mode,
                     lane_adjustment_factor=section.criteria.lane_factor(float(definitions[side].get("lane_count", 4)), case_ii=True))
        source = radius_sources[side]
        child["calculation_metadata"]["calculation_sources"].append({"component": "Design radius", **source,
            "mode": "calculated" if geometry_mode == "shared_corridor" else "user_input",
            "reference": (f"{source['reference']}; baseline R={source['baseline_radius_ft']:g} ft, edge offset={source['controlling_edge_offset_ft']:+g} ft, design R={source['design_radius_ft']:g} ft"
                          if geometry_mode == "shared_corridor" else source["reference"])})

    first = children["left"]
    result = {"transition_method": METHOD, "inputs": copy.deepcopy(values), "carriageways": children,
              "case_ii_geometry_mode": geometry_mode, "case_ii_placement_mode": placement_mode,
              "coordinated_full_super": list(full_anchors) if full_anchors else None,
              "pivot_offset_convention": "right_positive",
              "pivots": pivots if positioned else {},
              "median_gap_ft": pivots["left"]["x"] - pivots["right"]["x"] if positioned else None,
              "calculation_metadata": {"engine_version": CALCULATION_ENGINE_VERSION,
                  "criteria": criteria_metadata(PROFILE_ID),
                  "calculation_sources": [{"component": "Case II rotation", "reference": "AASHTO §3.3.8.8.2; Figure 3-8; equal median-edge profile elevations", "mode": "calculated"}]},
              "section_definition": {"roadway": "divided_case_ii", "initial_section": "single_slope"},
              "station_equations": first.get("station_equations", station_equations or []),
              "alignment_station_range": first.get("alignment_station_range", alignment_range),
              "warnings": [f"{side.title()} carriageway: {warning}" for side, child in children.items() for warning in child.get("warnings", [])],
              "qa_findings": [{**finding, "carriageway": side, "message": f"{side.title()} carriageway: {finding['message']}"}
                              for side, child in children.items() for finding in child.get("qa_findings", [])],
              "scope_note": "Case II common profile reference; elevations are relative, not absolute. Travel lanes only; shoulders and median grading are not modeled. Design radii do not construct carriageway alignments."}
    if lengths_only:
        result["result_type"] = "spiral_length_check"
        return result
    result.update({key: copy.deepcopy(first[key]) for key in ("pc_ft", "pt_ft", "alignment_anchors", "units")})
    result["no_transition_required"] = all(child["no_transition_required"] for child in children.values())
    result["pnc_ft"] = min(child["pnc_ft"] for child in children.values())
    result["pnc_out_ft"] = max(child["pnc_out_ft"] for child in children.values())
    result["section_lanes"] = []
    for side, child in children.items():
        shift = pivots[side]["x"] - child["pivot_offset_ft"]
        for lane in child["section_lanes"]:
            item = copy.deepcopy(lane)
            item.update(lane_name=f"{side.title()} carriageway · {lane['lane_name']}", display_label=f"{side[0].upper()}{lane['lane_name'].split()[-1]}", carriageway=side, side=side,
                        left_offset_ft=lane["left_offset_ft"] + shift, right_offset_ft=lane["right_offset_ft"] + shift)
            for event in item["events"]:
                event["slope_pct"] = ((event["left_elevation_ft"] - event["right_elevation_ft"]) / item["width_ft"] * 100
                                      * (1 if side == "left" else -1))
                event["note"] = f"Case II {side} carriageway; baseline offset {child['baseline_pivot_offset_ft']:g} ft (right-positive); common pivot-relative datum"
            result["section_lanes"].append(item)
    result["lane_events"] = {side: next(lane["events"] for lane in result["section_lanes"] if lane["carriageway"] == side) for side in SIDES}
    return result


def report_curves(curves):
    """Expand a validated pair only at presentation boundaries, retaining side labels."""
    for curve_index, curve in enumerate(curves):
        result = curve.get("results", {}) or {}
        if not is_case_ii(result):
            yield {**curve, "meta": {**(curve.get("meta") or {}), "report_curve_number": curve_index + 1}}
            continue
        for side, original in result["carriageways"].items():
            child = {**original, "section_lanes": [lane for lane in result["section_lanes"] if lane["carriageway"] == side],
                     "pivot_offset_ft": result["pivots"][side]["x"],
                     "lane_events": {key: result["lane_events"][key] if key == side else [] for key in SIDES}}
            meta = curve.get("meta", {})
            yield {**curve, "results": child, "meta": {**meta,
                   "curve_name": f"{meta.get('curve_name', 'Curve')} — Case II {side} carriageway (pivot {original['baseline_pivot_offset_ft']:+g} ft, right-positive)",
                   "case_ii_side": side, "report_curve_number": curve_index + 1}}


def validate_curves(curves):
    """Recompute pairs and check adjacency only within the same carriageway."""
    intervals = {}
    for index, curve in enumerate(curves):
        result = curve.get("results", {}) or {}
        if not is_case_ii(result):
            continue
        if result.get("result_type") == "spiral_length_check":
            raise ValueError("A Case II length check has no established stations and cannot be exported as a calculated curve.")
        expected = calculate(result["inputs"], result.get("station_equations"), result.get("alignment_station_range"))
        for key in ("carriageways", "section_lanes", "lane_events", "pivots", "pivot_offset_convention", "median_gap_ft",
                    "alignment_anchors", "pc_ft", "pt_ft", "pnc_ft", "pnc_out_ft", "no_transition_required", "calculation_metadata",
                    "case_ii_geometry_mode", "case_ii_placement_mode", "coordinated_full_super"):
            if result.get(key) != expected.get(key):
                raise ValueError("Saved Case II results differ from current inputs/engine; recalculate both carriageways before exporting.")
        alignment = curve.get("meta", {}).get("alignment_name", "")
        for side, child in result["carriageways"].items():
            if not child["no_transition_required"]:
                intervals.setdefault((alignment, side), []).append((child["pnc_ft"], child["pnc_out_ft"], index))
    for (_, side), windows in intervals.items():
        windows.sort()
        for prior, following in zip(windows, windows[1:]):
            if prior[1] > following[0] + 1e-7:
                raise ValueError(f"Case II {side} carriageway transition intervals overlap; automatic reverse/compound coordination is unsupported.")
