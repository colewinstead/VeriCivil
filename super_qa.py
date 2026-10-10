from __future__ import annotations

import math
from typing import Any

import Super
import super_exports
import super_landxml
from super_lane import lane_profile_points, slope_at_station


SEVERITY_RANK = {"pass": 0, "review": 1, "block": 2}


def _within(value: float, start: float, end: float, tolerance: float = 1e-7) -> bool:
    return min(start, end) - tolerance <= value <= max(start, end) + tolerance


def _reverse_lane_issue(
    lane: dict,
    tangent_start: float,
    tangent_end: float,
    expected_transition_start: float | None = None,
    expected_transition_end: float | None = None,
) -> str | None:
    try:
        outgoing_rate = float(lane["outgoing_rate_pct_per_ft"])
        incoming_rate = float(lane["incoming_rate_pct_per_ft"])
    except (KeyError, TypeError, ValueError):
        return "missing standard-rate metadata"
    try:
        transition_start = float(lane.get("transition_start_ft", tangent_start))
        transition_end = float(lane.get("transition_end_ft", tangent_end))
    except (TypeError, ValueError):
        return "full-super transition limits are invalid"
    if not all(math.isfinite(value) for value in (outgoing_rate, incoming_rate, transition_start, transition_end)):
        return "standard-rate or full-super metadata is non-finite"
    if expected_transition_start is not None and not math.isclose(
        transition_start, float(expected_transition_start), rel_tol=0.0, abs_tol=1e-7
    ):
        return "recorded transition start does not match the outgoing full-super station"
    if expected_transition_end is not None and not math.isclose(
        transition_end, float(expected_transition_end), rel_tol=0.0, abs_tol=1e-7
    ):
        return "recorded transition end does not match the incoming full-super station"
    if transition_end <= transition_start:
        return "full-super transition limits are reversed"
    hold = lane.get("normal_crown_hold")
    if hold:
        try:
            hold_start = float(hold["start_ft"])
            hold_end = float(hold["end_ft"])
            hold_length = float(hold["length_ft"])
        except (KeyError, TypeError, ValueError):
            return "normal-crown hold metadata is invalid"
        if hold_end < hold_start - 1e-7:
            return "normal-crown hold stations are reversed"
        if not math.isclose(hold_length, max(0.0, hold_end - hold_start), rel_tol=1e-7, abs_tol=1e-6):
            return "normal-crown hold length does not match its stations"
        if not _within(hold_start, transition_start, transition_end) or not _within(
            hold_end, transition_start, transition_end
        ):
            return "normal-crown hold is outside the full-super transition limits"
        # Older recorded engine results may include a reporting midpoint inside
        # the hold. It is ignored for validity; current results no longer
        # create or export that artificial event.
    else:
        try:
            handoff = float(lane["handoff_station_ft"])
            handoff_slope = float(lane["handoff_slope_pct"])
        except (KeyError, TypeError, ValueError):
            return "missing handoff metadata"
        if not math.isfinite(handoff) or not math.isfinite(handoff_slope):
            return "handoff metadata is non-finite"
        if not _within(handoff, transition_start, transition_end):
            return "handoff is outside the full-super transition limits"
    if outgoing_rate <= 0.0 or incoming_rate <= 0.0:
        return "recorded standard rate is not positive"

    raw_points: list[tuple[float, float]] = []
    for event in lane.get("profile_events", []) or []:
        try:
            station = float(event["station_ft"])
            slope = float(event["slope_pct"])
        except (KeyError, TypeError, ValueError):
            return "profile contains an invalid station or slope"
        if not math.isfinite(station) or not math.isfinite(slope):
            return "profile contains a non-finite station or slope"
        raw_points.append((station, slope))
    raw_points.sort()
    points: list[tuple[float, float]] = []
    for station, slope in raw_points:
        if points and math.isclose(station, points[-1][0], rel_tol=0.0, abs_tol=1e-7):
            if not math.isclose(slope, points[-1][1], rel_tol=0.0, abs_tol=1e-7):
                return "profile contains a slope discontinuity"
            continue
        points.append((station, slope))
    if len(points) < 2:
        return "profile does not contain enough events to verify"

    allowed_rates = (outgoing_rate, incoming_rate)
    for start, end in zip(points, points[1:]):
        distance = end[0] - start[0]
        if distance <= 0.0:
            return "profile stations are not strictly increasing"
        actual_rate = abs(end[1] - start[1]) / distance
        if actual_rate <= 1e-8:
            continue
        if not any(math.isclose(actual_rate, expected, rel_tol=1e-6, abs_tol=1e-7) for expected in allowed_rates):
            return f"profile segment uses nonstandard rate {actual_rate:.8f} %/ft"
    return None


def _source_map(results: dict) -> dict[str, dict]:
    criteria = results.get("calculation_metadata", {}).get("criteria", {}) or {}
    return {
        str(item.get("component", "")): {
            "component": str(item.get("component", "")),
            "reference": str(item.get("reference", "Not recorded")),
            "mode": str(item.get("mode", "automatic")),
        }
        for item in criteria.get("calculation_sources", []) or []
    }


def _criterion_for_segment(results: dict, start: dict, end: dict) -> dict:
    sources = _source_map(results)
    if results.get("transition_method")=="aashto_fixed_pivot":
        station=(float(start["station_ft"])+float(end["station_ft"]))/2
        if results.get("normal_crown_only"):
            component,phase="Superelevation rate","Normal crown"
        elif results["full_super_ft"]<=station<=results["full_super_out_ft"]:
            component,phase="Superelevation rate","Full super"
        elif results["reverse_crown_ft"]<=station<=results["full_super_ft"] or results["full_super_out_ft"]<=station<=results["reverse_crown_out_ft"]:
            component,phase="Runoff length","Runoff"
        elif any(hold["start_ft"]<station<hold["end_ft"] for hold in results.get("hold_intervals",[])):
            hold=next(hold for hold in results["hold_intervals"] if hold["start_ft"]<station<hold["end_ft"])
            component,phase="Transition placement","Zero-crown hold" if hold["section"]=="zero_crown" else "Initial-section hold"
        else:
            component,phase="Tangent runout","Tangent runout"
        return {**sources.get(component,{"component":component,"reference":"Recorded fixed-pivot section","mode":"calculated"}),"phase":phase}
    y0 = float(start.get("slope_pct", 0.0))
    y1 = float(end.get("slope_pct", 0.0))
    nc = abs(float(results.get("inputs", {}).get("normal_crown", 0.02) or 0.02) * 100.0)
    rate = abs(float(results.get("e", 0.0) or 0.0) * 100.0)
    if math.isclose(y0, y1, abs_tol=1e-8) and math.isclose(abs(y0), rate, abs_tol=1e-6):
        component = "Superelevation rate"
        phase = "Full super"
    elif max(abs(y0), abs(y1)) <= nc + 1e-6 and (math.isclose(y0, 0.0, abs_tol=1e-8) or math.isclose(y1, 0.0, abs_tol=1e-8)):
        component = "Tangent runout"
        phase = "Tangent runout"
    elif math.isclose(y0, y1, abs_tol=1e-8) and math.isclose(abs(y0), nc, abs_tol=1e-6):
        component = "Crown thresholds"
        phase = "Normal crown"
    else:
        component = "Runoff length"
        phase = "Runoff"
    source = sources.get(component, {"component": component, "reference": "Recorded calculation inputs", "mode": "automatic"})
    return {**source, "phase": phase}


def curve_diagram(results: dict, direction: str) -> dict[str, Any]:
    left_rows, right_rows = super_exports.build_lane_rows(results, direction, station_format=True)
    row_sets = {"left": left_rows, "right": right_rows}
    profiles: dict[str, list[dict]] = {}
    intervals: dict[str, list[dict]] = {}
    markers: list[dict] = []
    marker_keys: set[tuple[str, float]] = set()

    for lane, rows in row_sets.items():
        usable = sorted((row for row in rows if row.get("station_ft") is not None), key=lambda row: float(row["station_ft"]))
        profiles[lane] = [
            {
                "station_ft": float(row["station_ft"]),
                "station": row["station"],
                "slope_pct": float(row["slope_pct"]),
                "label": row["label"],
                "event_type": row["event_type"],
            }
            for row in usable
        ]
        intervals[lane] = [
            {
                "start_ft": float(start["station_ft"]),
                "end_ft": float(end["station_ft"]),
                **_criterion_for_segment(results, start, end),
            }
            for start, end in zip(usable, usable[1:])
            if float(end["station_ft"]) > float(start["station_ft"])
        ]
        for row in usable:
            station = float(row["station_ft"])
            key = (str(row["label"]), round(station, 6))
            if key not in marker_keys:
                marker_keys.add(key)
                markers.append({
                    "kind": str(row["label"]),
                    "label": str(row["label"]),
                    "station_ft": station,
                    "station": str(row["station"]),
                })

    for equation in Super.normalize_station_equations(results.get("station_equations")):
        station = float(equation["internal"])
        markers.append({
            "kind": "STATION EQUATION",
            "label": f"EQ {Super.format_station(equation['back'])} = {Super.format_station(equation['ahead'])}",
            "station_ft": station,
            "station": Super.format_result_station(results, station, True),
        })

    all_stations = [point["station_ft"] for profile in profiles.values() for point in profile]
    alignment_range = results.get("alignment_station_range")
    snap_groups: dict[float, dict[str, Any]] = {}
    for lane, profile in profiles.items():
        for point in profile:
            key = round(float(point["station_ft"]), 6)
            group = snap_groups.setdefault(key, {"station_ft": float(point["station_ft"]), "labels": set(), "lanes": set()})
            group["labels"].add(str(point["label"]))
            group["lanes"].add(lane)
    for marker in markers:
        key = round(float(marker["station_ft"]), 6)
        group = snap_groups.setdefault(key, {"station_ft": float(marker["station_ft"]), "labels": set(), "lanes": set()})
        group["labels"].add(str(marker["label"]))
    snap_points = [
        {
            "station_ft": group["station_ft"],
            "station": Super.format_result_station(results, group["station_ft"], True),
            "labels": sorted(group["labels"]),
            "lanes": sorted(group["lanes"]),
        }
        for group in sorted(snap_groups.values(), key=lambda item: item["station_ft"])
    ]
    return {
        "profiles": profiles,
        "section_profiles":[{"key":f"Lane{i}","name":lane["lane_name"],"side":lane["side"],"points":lane["events"]} for i,lane in enumerate(results.get("section_lanes",[]))],
        "intervals": intervals,
        "markers": sorted(markers, key=lambda marker: (marker["station_ft"], marker["label"])),
        "snap_points": snap_points,
        "domain": {
            "start_ft": min(all_stations) if all_stations else 0.0,
            "end_ft": max(all_stations) if all_stations else 0.0,
        },
        "alignment_range": list(alignment_range) if alignment_range else None,
        "criteria_profile": results.get("calculation_metadata", {}).get("criteria", {}).get("profile_id", "legacy-unversioned"),
    }


def _profile_point(results: dict, event: dict) -> dict[str, Any]:
    station = float(event["station_ft"])
    return {
        "station_ft": station,
        "station": Super.format_result_station(results, station, True),
        "slope_pct": float(event["slope_pct"]),
        "label": str(event.get("label") or event.get("event_type") or "Reverse transition"),
        "event_type": str(event.get("event_type") or "Reverse transition"),
    }


def _dedupe_profile(points: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    for point in sorted(points, key=lambda item: float(item["station_ft"])):
        if deduped and math.isclose(
            float(point["station_ft"]),
            float(deduped[-1]["station_ft"]),
            rel_tol=0.0,
            abs_tol=1e-7,
        ):
            if not math.isclose(
                float(point["slope_pct"]),
                float(deduped[-1]["slope_pct"]),
                rel_tol=0.0,
                abs_tol=1e-7,
            ):
                raise ValueError("Reverse-pair plot profile contains a slope discontinuity.")
            continue
        deduped.append(point)
    return deduped


def _refresh_diagram_navigation(diagram: dict) -> None:
    all_points = [
        point
        for lane in ("left", "right")
        for point in diagram.get("profiles", {}).get(lane, [])
    ]
    diagram["domain"] = {
        "start_ft": min((float(point["station_ft"]) for point in all_points), default=0.0),
        "end_ft": max((float(point["station_ft"]) for point in all_points), default=0.0),
    }
    groups: dict[float, dict[str, Any]] = {}
    for lane in ("left", "right"):
        for point in diagram.get("profiles", {}).get(lane, []):
            key = round(float(point["station_ft"]), 6)
            group = groups.setdefault(
                key,
                {
                    "station_ft": float(point["station_ft"]),
                    "station": str(point["station"]),
                    "labels": set(),
                    "lanes": set(),
                },
            )
            group["labels"].add(str(point["label"]))
            group["lanes"].add(lane)
    for marker in diagram.get("markers", []):
        key = round(float(marker["station_ft"]), 6)
        group = groups.setdefault(
            key,
            {
                "station_ft": float(marker["station_ft"]),
                "station": str(marker["station"]),
                "labels": set(),
                "lanes": set(),
            },
        )
        group["labels"].add(str(marker["label"]))
    diagram["snap_points"] = [
        {
            **group,
            "labels": sorted(group["labels"]),
            "lanes": sorted(group["lanes"]),
        }
        for group in sorted(groups.values(), key=lambda item: item["station_ft"])
    ]


def _coordinate_corridor_plot_profiles(diagrams: list[dict], curves: list[dict]) -> None:
    diagrams_by_index = {
        int(diagram["curve_index"]): diagram
        for diagram in diagrams
    }
    seen_pairs: set[str] = set()
    for curve in curves:
        results = curve.get("results", {}) or {}
        for check in (results.get("reverse_curve_coordination", {}) or {}).get("checks", []) or []:
            pair_id = str(check.get("pair_id") or "")
            if not pair_id or pair_id in seen_pairs or check.get("status") != "coordinated":
                continue
            seen_pairs.add(pair_id)
            indexes = list(check.get("paired_curve_indexes", []))
            if len(indexes) != 2:
                continue
            prior_index, following_index = int(indexes[0]), int(indexes[1])
            if (
                prior_index not in diagrams_by_index
                or following_index not in diagrams_by_index
                or not (0 <= prior_index < len(curves))
                or not (0 <= following_index < len(curves))
            ):
                continue
            prior_diagram = diagrams_by_index[prior_index]
            following_diagram = diagrams_by_index[following_index]
            prior_results = curves[prior_index].get("results", {}) or {}
            following_results = curves[following_index].get("results", {}) or {}

            for lane_name in ("left", "right"):
                lane = (check.get("lanes", {}) or {}).get(lane_name, {}) or {}
                canonical = _dedupe_profile([
                    _profile_point(prior_results, event)
                    for event in lane.get("profile_events", []) or []
                ])
                if not canonical:
                    continue
                transition_start = float(lane.get("transition_start_ft", canonical[0]["station_ft"]))
                transition_end = float(lane.get("transition_end_ft", canonical[-1]["station_ft"]))
                hold = lane.get("normal_crown_hold") or {}
                handoff = lane.get("handoff_station_ft")
                if hold:
                    split = float(hold["end_ft"])
                elif handoff is not None:
                    split = float(handoff)
                else:
                    continue
                prior_original = prior_diagram["profiles"][lane_name]
                following_original = following_diagram["profiles"][lane_name]
                prior_diagram["profiles"][lane_name] = _dedupe_profile([
                    *[
                        point for point in prior_original
                        if float(point["station_ft"]) < transition_start - 1e-7
                    ],
                    *[
                        point for point in canonical
                        if float(point["station_ft"]) <= split + 1e-7
                    ],
                ])
                following_diagram["profiles"][lane_name] = _dedupe_profile([
                    *[
                        point for point in canonical
                        if float(point["station_ft"]) >= split - 1e-7
                    ],
                    *[
                        point for point in following_original
                        if float(point["station_ft"]) > transition_end + 1e-7
                    ],
                ])

            _refresh_diagram_navigation(prior_diagram)
            _refresh_diagram_navigation(following_diagram)


def corridor_diagram(curves: list[dict]) -> dict[str, Any]:
    diagrams: list[dict[str, Any]] = []
    for index, curve in enumerate(curves):
        results = curve.get("results", {}) or {}
        if not results:
            continue
        meta = curve.get("meta", {}) or {}
        diagram = curve_diagram(results, str(meta.get("curve_direction", "left")))
        diagram.update({
            "curve_index": index,
            "source_index": meta.get("landxml_curve_index", index),
            "curve_name": str(meta.get("curve_name") or f"Curve {index + 1}"),
            "alignment_name": str(meta.get("alignment_name") or "Unnamed alignment"),
            "direction": str(meta.get("curve_direction", "left")),
        })
        diagrams.append(diagram)

    _coordinate_corridor_plot_profiles(diagrams, curves)
    starts = [diagram["domain"]["start_ft"] for diagram in diagrams]
    ends = [diagram["domain"]["end_ft"] for diagram in diagrams]
    return {
        "curves": diagrams,
        "curve_count": len(diagrams),
        "domain": {
            "start_ft": min(starts) if starts else 0.0,
            "end_ft": max(ends) if ends else 0.0,
        },
    }


def plan_view(data: super_landxml.LandXMLData, curves: list[dict]) -> dict[str, Any]:
    alignment: list[dict[str, float]] = []
    curve_paths: list[dict[str, Any]] = []
    station = data.start_station
    source_curve_index = 0
    for segment in data._segments:
        sample_count = max(2, min(240, int(math.ceil(segment.length / 25.0))))
        points = []
        for sample_index in range(sample_count + 1):
            sample_station = station + segment.length * sample_index / sample_count
            x, y = data.xy_at_station(sample_station)
            point = {"x": x, "y": y, "station_ft": sample_station}
            points.append(point)
            if not alignment or sample_index > 0:
                alignment.append(point)
        if isinstance(segment, super_landxml.ArcSegment):
            curve_paths.append({
                "source_index": source_curve_index,
                "curve_name": f"Curve {source_curve_index + 1}",
                "start_station_ft": station,
                "end_station_ft": station + segment.length,
                "points": points,
            })
            source_curve_index += 1
        station += segment.length

    events: list[dict[str, Any]] = []
    alignment_start, alignment_end = data.station_range()
    for curve_index, curve in enumerate(curves):
        meta = curve.get("meta", {}) or {}
        grouped: dict[float, dict[str, Any]] = {}
        for row in super_exports.build_normalized_rows([curve]):
            event_station = float(row["station"])
            if event_station < alignment_start or event_station > alignment_end:
                continue
            key = round(event_station, 6)
            event = grouped.setdefault(key, {
                "curve_index": curve_index,
                "source_index": meta.get("landxml_curve_index", curve_index),
                "curve_name": meta.get("curve_name") or row.get("curve_name") or f"Curve {curve_index + 1}",
                "station_ft": event_station,
                "station": row.get("station_label") or Super.format_result_station(curve.get("results", {}), event_station, True),
                "event_types": set(),
                "slopes": {},
            })
            event["event_types"].add(str(row.get("event_type") or "Lane event"))
            event["slopes"][str(row.get("side", ""))] = str(row.get("slope_label", ""))
        for event in grouped.values():
            x, y = data.xy_at_station(event["station_ft"])
            tx, ty = data.tangent_at_station(event["station_ft"])
            events.append({
                **event,
                "event_types": sorted(event["event_types"]),
                "x": x,
                "y": y,
                "tangent_x": tx,
                "tangent_y": ty,
            })

    coordinates = [(point["x"], point["y"]) for point in alignment]
    return {
        "alignment_name": data.alignment_name or "Unnamed alignment",
        "alignment": alignment,
        "curve_paths": curve_paths,
        "events": sorted(events, key=lambda event: (event["station_ft"], event["curve_index"])),
        "bounds": {
            "min_x": min((point[0] for point in coordinates), default=0.0),
            "max_x": max((point[0] for point in coordinates), default=1.0),
            "min_y": min((point[1] for point in coordinates), default=0.0),
            "max_y": max((point[1] for point in coordinates), default=1.0),
        },
        "coordinate_system": data.coordinate_system.as_dict() if data.coordinate_system else None,
    }


def diagram_lookup(results: dict, direction: str, station: float) -> dict[str, Any]:
    diagram = curve_diagram(results, direction)
    if results.get("section_lanes"):
        lanes={}
        for lane in results["section_lanes"]:
            events=lane["events"]
            slope=slope_at_station([(e["station_ft"],e["slope_pct"]) for e in events],station)
            pair=next(((a,b) for a,b in zip(events,events[1:]) if a["station_ft"]<=station<=b["station_ft"]),None)
            criterion=_criterion_for_segment(results,*pair) if pair else {"component":"Initial section","reference":"Recorded fixed-pivot section","mode":"calculated","phase":"Transition endpoint"}
            lanes[lane["lane_name"]]={"slope_pct":slope,"slope_label":super_exports.format_slope_label(slope),"slope_decimal":super_exports.slope_decimal(slope),"phase":criterion["phase"],"criterion":criterion}
        return {"station_ft":float(station),"station":Super.format_result_station(results,station,True),"lanes":lanes}
    points = lane_profile_points(results, direction)
    lanes: dict[str, dict] = {}
    for lane in ("left", "right"):
        pair_lane = next(
            (
                (check.get("lanes", {}) or {}).get(lane)
                for check in (results.get("reverse_curve_coordination", {}) or {}).get("checks", []) or []
                if check.get("status") == "coordinated"
                and (check.get("lanes", {}) or {}).get(lane)
                and float((check["lanes"][lane]).get("transition_start_ft", math.inf)) - 1e-7
                <= station
                <= float((check["lanes"][lane]).get("transition_end_ft", -math.inf)) + 1e-7
            ),
            None,
        )
        interval = next(
            (item for item in diagram["intervals"][lane] if item["start_ft"] - 1e-8 <= station <= item["end_ft"] + 1e-8),
            None,
        )
        if pair_lane:
            pair_points = _dedupe_profile([
                _profile_point(results, event)
                for event in pair_lane.get("profile_events", []) or []
            ])
            slope = slope_at_station(
                [
                    (float(point["station_ft"]), float(point["slope_pct"]))
                    for point in pair_points
                ],
                station,
            )
            hold = pair_lane.get("normal_crown_hold") or {}
            in_hold = bool(
                hold
                and float(hold["start_ft"]) - 1e-7
                <= station
                <= float(hold["end_ft"]) + 1e-7
            )
            source = _source_map(results).get(
                "Crown thresholds" if in_hold else "Runoff length",
                {
                    "component": "Crown thresholds" if in_hold else "Runoff length",
                    "reference": "Recorded reverse-curve calculation",
                    "mode": "automatic",
                },
            )
            interval = {
                **source,
                "phase": "Normal crown hold" if in_hold else "Reverse curve runoff",
            }
        else:
            slope = slope_at_station(points[lane], station)
        lanes[lane] = {
            "slope_pct": slope,
            "slope_label": super_exports.format_slope_label(slope),
            "slope_decimal": super_exports.slope_decimal(slope),
            "phase": (interval or {}).get("phase", "Transition endpoint"),
            "criterion": {
                "component": (interval or {}).get("component", "Source geometry"),
                "reference": (interval or {}).get("reference", "Calculated lane event"),
                "mode": (interval or {}).get("mode", "automatic"),
            },
        }
    return {
        "station_ft": float(station),
        "station": Super.format_result_station(results, station, True),
        "lanes": lanes,
    }


def _finding(code: str, severity: str, message: str, curve_indexes: list[int] | None = None,
             start_ft: float | None = None, end_ft: float | None = None, details: str = "") -> dict:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "details": details,
        "curve_indexes": curve_indexes or [],
        "start_ft": start_ft,
        "end_ft": end_ft,
    }


def _curve_match(preset: dict, curve: dict, used: set[int], curve_index: int) -> bool:
    meta = curve.get("meta", {}) or {}
    source_index = meta.get("landxml_curve_index")
    if source_index is not None:
        return int(source_index) == curve_index
    results = curve.get("results", {}) or {}
    inputs = results.get("inputs", {}) or {}
    return (
        str(meta.get("alignment_name", "")) == str(preset.get("alignment_name", ""))
        and math.isclose(float(results.get("pc_ft", -1)), float(preset.get("pc_station_ft", -2)), abs_tol=0.01)
        and math.isclose(float(inputs.get("radius_ft", -1)), float(preset.get("radius_ft", -2)), abs_tol=0.01)
    )


def _transition_bounds(curve: dict) -> tuple[float, float] | None:
    results = curve.get("results", {}) or {}
    direction = curve.get("meta", {}).get("curve_direction", "left")
    points = lane_profile_points(results, direction)
    stations = [station for lane_points in points.values() for station, _ in lane_points]
    return (min(stations), max(stations)) if stations else None


def _normal_crown_only(curve: dict) -> bool:
    return bool((curve.get("results", {}) or {}).get("normal_crown_only"))


def _zero_event(curve: dict, entering: bool) -> float | None:
    results = curve.get("results", {}) or {}
    direction = curve.get("meta", {}).get("curve_direction", "left")
    pc = float(results.get("pc_ft", 0.0))
    pt = results.get("pt_ft")
    reference = pc if entering else (float(pt) if pt is not None else pc)
    points = lane_profile_points(results, direction)
    matches = [station for lane in points.values() for station, slope in lane if math.isclose(slope, 0.0, abs_tol=1e-7)]
    candidates = [station for station in matches if station <= reference + 1e-7] if entering else [station for station in matches if station >= reference - 1e-7]
    return max(candidates) if entering and candidates else (min(candidates) if candidates else None)


def analyze_corridor(data: super_landxml.LandXMLData, curves: list[dict], excluded_curve_indexes: list[int] | None = None) -> dict[str, Any]:
    presets = data.curve_records()
    excluded = {int(index) for index in (excluded_curve_indexes or []) if 0 <= int(index) < len(presets)}
    findings: list[dict] = []
    matched: list[dict | None] = []
    used: set[int] = set()

    for index, segment in enumerate(data._segments):
        if segment.length <= 0 or (isinstance(segment, super_landxml.ArcSegment) and segment.radius <= 0):
            findings.append(_finding(
                "INVALID_GEOMETRY", "block", f"Geometry segment {index + 1} has a missing or non-positive length/radius.",
                details="Correct the source LandXML geometry before corridor review.",
            ))
    for index, (prior, following) in enumerate(zip(data._segments, data._segments[1:])):
        gap = math.hypot(prior.end[0] - following.start[0], prior.end[1] - following.start[1])
        if gap > 0.05:
            findings.append(_finding(
                "GEOMETRY_GAP", "block", f"LandXML geometry is discontinuous between segments {index + 1} and {index + 2}.",
                details=f"Endpoint gap is {gap:.3f} source units.",
            ))

    for index, preset in enumerate(presets):
        if index in excluded:
            matched.append(None)
            continue
        match_index = next((i for i, curve in enumerate(curves) if i not in used and _curve_match(preset, curve, used, index)), None)
        if match_index is None:
            matched.append(None)
            findings.append(_finding(
                "UNCALCULATED_CURVE", "block", f"{preset['curve_name']} has no matching calculation.", [index],
                preset["pc_station_ft"], preset["pt_station_ft"], "Calculate or add this LandXML curve before corridor review.",
            ))
        else:
            used.add(match_index)
            matched.append(curves[match_index])

    for index in sorted(set(range(len(curves))) - used):
        findings.append(_finding(
            "UNMATCHED_CALCULATION", "block",
            f"{curves[index].get('meta', {}).get('curve_name', f'Curve {index + 1}')} does not match a LandXML curve.",
            details="Confirm alignment, PC, PT, radius, and source curve selection.",
        ))

    alignment_start, alignment_end = data.station_range()
    for index, curve in enumerate(matched):
        if curve is None:
            continue
        results = curve.get("results", {}) or {}
        if presets[index].get("alignment_type")=="spiral" and results.get("inputs",{}).get("alignment_type")!="spiral":
            findings.append(_finding("UNSUPPORTED_SPIRAL","block",f"Curve {index+1} has established spirals but circular transition placement.",[index],presets[index]["pc_station_ft"],presets[index]["pt_station_ft"],"Recalculate using the supported AASHTO spiral method."))
        if results.get("transition_method")=="aashto_fixed_pivot":
            preset=presets[index]
            expected={"PC":preset["pc_station_ft"],"PT":preset["pt_station_ft"]}
            if preset.get("alignment_type")=="spiral":
                expected={"TS":preset["ts_station_ft"],"SC":preset["sc_station_ft"],"CS":preset["cs_station_ft"],"ST":preset["st_station_ft"]}
            actual=results.get("alignment_anchors",{})
            valid=actual.keys()==expected.keys() and all(abs(float(actual.get(key,0))-value)<0.01 for key,value in expected.items())
            valid=valid and abs(float(results.get("inputs",{}).get("radius_ft",0))-preset["radius_ft"])<0.01 and curve.get("meta",{}).get("curve_direction")==preset["curve_direction"]
            if not valid:
                findings.append(_finding("ESTABLISHED_GEOMETRY_MISMATCH","block",f"Curve {index+1} calculation does not match its established LandXML stations, radius, or direction.",[index],preset["pc_station_ft"],preset["pt_station_ft"],"Reapply the imported curve; horizontal geometry is not modified."))
            else:
                # Recheck actual source space, even for manually entered or restored calculations.
                import aashto_superelevation
                values={**results["inputs"],"linear_unit":data.linear_unit,
                        "geometry_provenance":{"source":"LandXML",**{key:preset[key] for key in ("available_entry_tangent_ft","available_exit_tangent_ft")}}}
                try:
                    aashto_superelevation.calculate(values,data.station_equations,data.station_range())
                except ValueError as exc:
                    for item in getattr(exc,"findings",[]) or [{"code":"INVALID_IMPORTED_TRANSITION","severity":"block","message":str(exc)}]:
                        if item["severity"]=="block":
                            findings.append(_finding(item["code"],"block",item["message"],[index],item.get("station_start_ft"),item.get("station_end_ft"),str(item.get("details",""))))
        for item in results.get("qa_findings",[]) or []:
            findings.append(_finding(item["code"],item["severity"],item["message"],[index],
                                     item.get("station_start_ft"),item.get("station_end_ft"),str(item.get("details",""))))
        bounds = _transition_bounds(curve)
        if _normal_crown_only(curve):
            for warning in results.get("warnings", []) or []:
                findings.append(_finding(
                    "CALCULATION_WARNING", "review", f"Curve {index + 1}: {warning}", [index],
                    bounds[0] if bounds else None, bounds[1] if bounds else None,
                ))
            continue
        if not bounds:
            findings.append(_finding("MISSING_TRANSITION_EVENTS", "block", f"Curve {index + 1} has no lane transition events.", [index]))
            continue
        if bounds[0] < alignment_start - 1e-6 or bounds[1] > alignment_end + 1e-6:
            findings.append(_finding(
                "OUT_OF_ALIGNMENT", "block", f"Curve {index + 1} has transition events outside the alignment limits.", [index],
                bounds[0], bounds[1], "Revise transition placement or confirm the alignment station range.",
            ))
        for warning in results.get("warnings", []) or []:
            findings.append(_finding("CALCULATION_WARNING", "review", f"Curve {index + 1}: {warning}", [index], bounds[0], bounds[1]))

    for prior_index in range(len(matched) - 1):
        next_index = prior_index + 1
        prior = matched[prior_index]
        following = matched[next_index]
        if prior is None or following is None:
            continue
        if _normal_crown_only(prior) or _normal_crown_only(following):
            continue
        prior_coordination = (prior.get("results", {}) or {}).get("reverse_curve_coordination", {}) or {}
        pair_check = next(
            (
                check for check in prior_coordination.get("checks", [])
                if check.get("paired_curve_indexes") == [prior_index, next_index]
            ),
            None,
        )
        coordinated_pair = bool(pair_check and pair_check.get("status") == "coordinated")
        prior_bounds = _transition_bounds(prior)
        next_bounds = _transition_bounds(following)
        prior_direction = str(prior.get("meta", {}).get("curve_direction", "left"))
        next_direction = str(following.get("meta", {}).get("curve_direction", "left"))
        if pair_check and pair_check.get("status") == "short_tangent":
            findings.append(_finding(
                "SHORT_REVERSE_TANGENT",
                "block",
                f"Curves {prior_index + 1} and {next_index + 1} do not meet the minimum reverse-curve tangent length.",
                [prior_index, next_index],
                float(pair_check.get("tangent_start_ft", 0.0)),
                float(pair_check.get("tangent_end_ft", 0.0)),
                (
                    f"Available {float(pair_check.get('available_tangent_ft', 0.0)):.2f} ft; "
                    f"minimum {float(pair_check.get('minimum_tangent_ft', 0.0)):.2f} ft from "
                    "Tmin = 0.7Lr(exit) + 0.7Lr(entry). Runoff was not shifted or shortened."
                ),
            ))
            continue
        if pair_check and pair_check.get("status") == "invalid_pair":
            findings.append(_finding(
                "INVALID_REVERSE_PAIR",
                "block",
                f"Curves {prior_index + 1} and {next_index + 1} are not eligible for reverse-curve coordination.",
                [prior_index, next_index],
                float(pair_check.get("tangent_start_ft", 0.0)),
                float(pair_check.get("tangent_end_ft", 0.0)),
                str(pair_check.get("failure_reason") or "Review the linked curves and criteria profiles."),
            ))
            continue
        if pair_check and pair_check.get("status") == "invalid_handoff":
            findings.append(_finding(
                "INVALID_REVERSE_HANDOFF",
                "block",
                f"Curves {prior_index + 1} and {next_index + 1} do not produce a valid continuous standard-rate handoff.",
                [prior_index, next_index],
                float(pair_check.get("tangent_start_ft", 0.0)),
                float(pair_check.get("tangent_end_ft", 0.0)),
                str(pair_check.get("failure_reason") or "Review the lane transition geometry."),
            ))
            continue
        if coordinated_pair:
            lanes = pair_check.get("lanes", {}) or {}
            tangent_start = float(pair_check.get("tangent_start_ft", 0.0))
            tangent_end = float(pair_check.get("tangent_end_ft", 0.0))
            transition_start = float(prior.get("results", {}).get("full_super_out_ft", tangent_start))
            transition_end = float(following.get("results", {}).get("full_super_ft", tangent_end))
            invalid_lane = next(
                (
                    (side, "missing lane transition metadata")
                    if side not in lanes
                    else (side, issue)
                    for side in ("left", "right")
                    if side not in lanes
                    or (
                        issue := _reverse_lane_issue(
                            lanes[side],
                            tangent_start,
                            tangent_end,
                            transition_start,
                            transition_end,
                        )
                    ) is not None
                ),
                None,
            )
            if pair_check.get("transition_rate_status") != "standard":
                invalid_lane = ("pair", "transition rate is not recorded as standard")
            if invalid_lane is not None:
                invalid_side, invalid_reason = invalid_lane
                findings.append(_finding(
                    "NONSTANDARD_REVERSE_TRANSITION",
                    "block",
                    f"Curves {prior_index + 1} and {next_index + 1} contain invalid {invalid_side}-lane reverse-transition metadata.",
                    [prior_index, next_index],
                    tangent_start,
                    tangent_end,
                    f"{invalid_reason}. Recalculate the pair with the current calculation engine.",
                ))
            continue
        if prior_bounds and next_bounds and prior_bounds[1] > next_bounds[0] + 1e-6 and not coordinated_pair:
            findings.append(_finding(
                "TRANSITION_OVERLAP", "block" if any(c.get("results",{}).get("transition_method")=="aashto_fixed_pivot" for c in (prior,following)) else "review",
                f"Curves {prior_index + 1} and {next_index + 1} have overlapping transition envelopes.",
                [prior_index, next_index], next_bounds[0], prior_bounds[1], "Coordinate the adjacent lane-slope transitions.",
            ))
        if prior_direction != next_direction:
            demand_end = _zero_event(prior, entering=False)
            demand_start = _zero_event(following, entering=True)
            demand_name = "zero-slope reverse-curve recovery"
        else:
            demand_end = prior_bounds[1] if prior_bounds else None
            demand_start = next_bounds[0] if next_bounds else None
            demand_name = "normal-crown recovery"
        if demand_end is None or demand_start is None:
            findings.append(_finding(
                "MISSING_TRANSITION_DEMAND", "block",
                f"Curves {prior_index + 1} and {next_index + 1} lack events needed to verify {demand_name}.",
                [prior_index, next_index], details="Review the lane events and adjacent-curve transition method.",
            ))
        elif demand_end > demand_start + 1e-6:
            findings.append(_finding(
                "SHORT_TANGENT", "review",
                f"Curves {prior_index + 1} and {next_index + 1} do not provide enough station length for {demand_name}.",
                [prior_index, next_index], demand_start, demand_end,
                "Reverse curves are checked from exit 0% to the next entry 0%; same-direction curves require normal crown.",
            ))

    calculated = [curve for curve in matched if curve is not None]
    speeds = {float(curve.get("results", {}).get("inputs", {}).get("speed_mph", 0.0)) for curve in calculated}
    if len(speeds) > 1:
        findings.append(_finding("INCONSISTENT_SPEED", "review", "Calculated curves use inconsistent design speeds.", list(range(len(presets))), details=f"Speeds: {', '.join(f'{speed:g}' for speed in sorted(speeds))} mph."))
    profiles = {str(curve.get("results", {}).get("calculation_metadata", {}).get("criteria", {}).get("profile_id", "legacy-unversioned")) for curve in calculated}
    if len(profiles) > 1:
        findings.append(_finding("MIXED_CRITERIA", "review", "Calculated curves use mixed criteria profiles.", list(range(len(presets))), details=", ".join(sorted(profiles))))
    override_signatures = {
        tuple(sorted(key for key, enabled in (curve.get("results", {}).get("calculation_metadata", {}).get("manual_overrides", {}) or {}).items() if enabled))
        for curve in calculated
    }
    if len(override_signatures) > 1:
        findings.append(_finding("MIXED_OVERRIDES", "review", "Manual override usage is inconsistent across the corridor.", list(range(len(presets))), details="Review overridden and automatic values curve by curve."))

    for finding in findings:
        for key in ("start", "end"):
            station = finding.get(f"{key}_ft")
            finding[key] = (
                Super.format_station(Super.internal_to_civil_station(float(station), data.station_equations), True)
                if station is not None else None
            )

    curve_statuses = []
    for index, preset in enumerate(presets):
        if index in excluded:
            curve_statuses.append({"curve_index": index, "curve_name": preset["curve_name"], "status": "excluded", "finding_count": 0})
            continue
        relevant = [finding for finding in findings if index in finding["curve_indexes"]]
        status = max((finding["severity"] for finding in relevant), key=lambda value: SEVERITY_RANK[value], default="pass")
        curve_statuses.append({"curve_index": index, "curve_name": preset["curve_name"], "status": status, "finding_count": len(relevant)})
    status = max((finding["severity"] for finding in findings), key=lambda value: SEVERITY_RANK[value], default="pass")
    counts = {severity: sum(1 for item in curve_statuses if item["status"] == severity) for severity in ("pass", "review", "block")}
    return {
        "status": status,
        "counts": counts,
        "curve_count": len(presets) - len(excluded),
        "source_curve_count": len(presets),
        "excluded_count": len(excluded),
        "excluded_curve_indexes": sorted(excluded),
        "curve_statuses": curve_statuses,
        "findings": findings,
    }
