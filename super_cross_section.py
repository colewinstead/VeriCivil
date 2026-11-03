"""Presentation of recorded sections; no transition criteria are calculated here."""
from __future__ import annotations

import math

import super_exports
from super_lane import lane_profile_points, slope_at_station


def _unavailable(message: str) -> dict:
    return {"mode": "unavailable", "message": message, "segments": []}


def section_model(results: dict, direction: str) -> dict:
    """Stable drawing bounds and geometry provenance for the entire curve."""
    if results.get("section_lanes") or results.get("transition_method") == "aashto_fixed_pivot":
        if results.get("transition_method") != "aashto_fixed_pivot":
            return _unavailable("This section model does not yet provide cross-section geometry.")
        try:
            definition = results["section_definition"]
            if definition["roadway"] not in {"two_way", "one_way"} or definition["rotation_axis"] not in {"centerline", "left_edge", "right_edge"}:
                raise ValueError
            lanes = results["section_lanes"]
            coordinates = [float(results["pivot_offset_ft"])]
            heights = [0.0]
            for lane in lanes:
                right, left = float(lane["right_offset_ft"]), float(lane["left_offset_ft"])
                width = float(lane["width_ft"])
                if (right >= left or not lane["events"] or not math.isfinite(width)
                        or not math.isclose(width, left - right, rel_tol=0, abs_tol=1e-9)
                        or lane["side"] not in {"left", "right"} or not lane["lane_name"]):
                    raise ValueError
                coordinates.extend([right, left])
                for event in lane["events"]:
                    heights.extend([float(event["left_elevation_ft"]), float(event["right_elevation_ft"])])
                    if not all(math.isfinite(float(event[key])) for key in ("station_ft", "slope_pct")):
                        raise ValueError
                if any(a["station_ft"] > b["station_ft"] for a, b in zip(lane["events"], lane["events"][1:])):
                    raise ValueError
            if not lanes or not all(math.isfinite(value) for value in coordinates + heights):
                raise ValueError
            return {"mode": "physical", "title": "Two-way undivided" if definition["roadway"] == "two_way" else "One-way / ramp",
                    "initial_section": definition["initial_section"].replace("_", " "),
                    "pivot": {"x": coordinates[0], "y": 0.0, "label": definition["rotation_axis"].replace("_", " ")},
                    "bounds": {"x_min": min(coordinates), "x_max": max(coordinates), "y_min": min(heights), "y_max": max(heights)},
                    "message": "Travel lanes only. Edge heights are relative to the fixed pivot, not absolute elevations. Shoulders and medians are not modeled."}
        except (KeyError, TypeError, ValueError, OverflowError):
            return _unavailable("Recorded section geometry is incomplete or invalid. Recalculate this curve.")
    profile = results.get("calculation_metadata", {}).get("criteria", {}).get("profile_id", "")
    if profile and not profile.startswith(("mdot-", "tdot-")):
        return _unavailable("This criteria profile does not yet provide cross-section geometry.")
    points = lane_profile_points(results, direction)
    values = [slope / 100 for lane in points.values() for _, slope in lane]
    if not values or not all(math.isfinite(value) for value in values):
        return _unavailable("Calculate lane profiles before viewing a cross section.")
    return {"mode": "schematic", "title": "Left/right slope schematic",
            "bounds": {"x_min": -1.0, "x_max": 1.0, "y_min": min(0.0, *values), "y_max": max(0.0, *values)},
            "message": "Schematic only: equal display spans show calculated slopes. Lane distribution, physical widths, and pivot geometry are not defined by these inputs."}


def section_at_station(results: dict, direction: str, station: float, slopes: dict, model: dict, domain: dict) -> dict:
    """Interpolate the recorded edge heights, preserving their piecewise breakpoints."""
    if model["mode"] == "unavailable":
        return model
    if not math.isfinite(station) or not domain["start_ft"] <= station <= domain["end_ft"]:
        return _unavailable("Choose a station within this curve's calculated profile range.")
    segments = []
    if model["mode"] == "physical":
        for lane in sorted(results["section_lanes"], key=lambda lane: -lane["left_offset_ft"]):
            events = lane["events"]
            def height(edge):
                return slope_at_station([(event["station_ft"], event[edge]) for event in events], station)
            segments.append({"name": lane["lane_name"], "side": lane["side"], "width_ft": lane["width_ft"],
                             "left": {"x": lane["left_offset_ft"], "y": height("left_elevation_ft")},
                             "right": {"x": lane["right_offset_ft"], "y": height("right_elevation_ft")},
                             "slope_label": slopes[lane["lane_name"]]["slope_label"]})
    else:
        for side in ("left", "right"):
            slope = float(slopes[side]["slope_pct"])
            edge = {"x": 1.0 if side == "left" else -1.0, "y": slope / 100}
            center = {"x": 0.0, "y": 0.0}
            segments.append({"name": f"{side.capitalize()} slope plane", "side": side,
                             "left": edge if side == "left" else center,
                             "right": center if side == "left" else edge,
                             "slope_label": super_exports.format_slope_label(slope)})
    return {**model, "segments": segments}
