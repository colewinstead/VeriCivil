from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Iterable, TextIO

import Super
import super_transition


ORD_HEADERS = [
    "SuperelevationLane",
    "Station",
    "CrossSlope",
    "PivotAbout",
    "PointType",
    "TransitionType",
    "NonLinearCurveLength",
]

@dataclass(frozen=True)
class ExportWarning:
    message: str


def format_slope_value(value: float, precision: int = 2) -> str:
    rounded = round(float(value), precision)
    if rounded > 0:
        return f"+{rounded:.{precision}f}"
    return f"{rounded:.{precision}f}"


def format_slope_label(value: float, precision: int = 2) -> str:
    return f"{format_slope_value(value, precision)}%"


def slope_decimal(value: float, precision: int = 4) -> str:
    return format_slope_value(float(value) / 100.0, precision)


def outside_lane(direction: str) -> str:
    return "left" if str(direction).strip().lower().startswith("r") else "right"


def inside_lane(direction: str) -> str:
    return "right" if outside_lane(direction) == "left" else "left"


def pivot_about_for_side(side: str) -> str:
    return "RS" if side == "left" else "LS"


def lane_name_for_side(side: str, curve: dict) -> str:
    meta = curve.get("meta", {}) or {}
    key = f"{side}_lane_name"
    if str(meta.get(key, "")).strip():
        return str(meta[key]).strip()
    return f"{side.title()} Lane"


def _format_station(value: float | None, station_format: bool) -> str:
    if value is None:
        return "n/a"
    return Super.format_station(value, station_format)


def _make_row(
    label: str,
    station: float | None,
    slope_pct: float,
    note: str,
    event_type: str,
    station_format: bool,
) -> dict:
    return {
        "label": label,
        "station": _format_station(station, station_format),
        "station_ft": station,
        "slope": format_slope_value(slope_pct),
        "slope_pct": float(slope_pct),
        "slope_decimal": float(slope_pct) / 100.0,
        "slope_label": format_slope_label(slope_pct),
        "note": note,
        "event_type": event_type,
    }


def _linear_slope_at_station(
    station: float,
    start_station: float,
    start_slope_pct: float,
    end_station: float,
    end_slope_pct: float,
) -> float:
    """Return the slope on the straight transition between two lane events."""
    if end_station <= start_station:
        return end_slope_pct
    fraction = max(0.0, min(1.0, (station - start_station) / (end_station - start_station)))
    return start_slope_pct + fraction * (end_slope_pct - start_slope_pct)


def _inside_rotation_offset(runoff_length: float, e_pct: float, normal_crown_pct: float) -> float:
    """Return MDOT SE-3A X1, where the inside lane begins or ends rotation."""
    if runoff_length <= 0.0 or e_pct <= 0.0:
        return 0.0
    return runoff_length * max(0.0, min(1.0, normal_crown_pct / e_pct))


def build_lane_rows(results: dict, direction: str, station_format: bool = True) -> tuple[list[dict], list[dict]]:
    if results.get("lane_events") is not None:
        def render(events):
            return [{**event, **_make_row(event["label"], event["station_ft"], event["slope_pct"], event["note"], event["event_type"], station_format),
                     "station": Super.format_result_station(results,event["station_ft"],station_format)} for event in events]
        return render(results["lane_events"].get("left",[])), render(results["lane_events"].get("right",[]))
    if results.get("transition_method") == "mdot_70_30_runoff":
        left_events, right_events = super_transition.build_mdot_lane_events(results, direction)

        def format_events(events: list[dict]) -> list[dict]:
            formatted: list[dict] = []
            for event in events:
                row = _make_row(
                    str(event["label"]),
                    float(event["station_ft"]),
                    float(event["slope_pct"]),
                    str(event["note"]),
                    str(event["event_type"]),
                    station_format,
                )
                for key in ("reverse_pair_id", "reverse_pair_critical"):
                    if key in event:
                        row[key] = event[key]
                formatted.append(row)
            return formatted

        return format_events(left_events), format_events(right_events)

    direction_text = (direction or "left").strip().lower() or "left"
    outside = outside_lane(direction_text)

    L = float(results.get("Lr", 0.0) or 0.0)
    Lt = float(results.get("Lt", 0.0) or 0.0)
    e = float(results.get("e", 0.0) or 0.0)
    normal_crown = float(results.get("inputs", {}).get("normal_crown", 0.02) or 0.02)
    reverse_crown = float(results.get("reverse_crown_ft", 0.0) or 0.0)
    reverse_crown_out = results.get("reverse_crown_out_ft")
    reverse_crown_out = None if reverse_crown_out is None else float(reverse_crown_out)

    pc = float(results.get("pc_ft", reverse_crown + 0.7 * L) or 0.0)
    full_super_pc = float(results.get("full_super_ft", 0.0) or 0.0)
    full_super_pt = results.get("full_super_out_ft")
    full_super_pt = None if full_super_pt is None else float(full_super_pt)
    stored_pt = results.get("pt_ft")
    pt = (
        float(stored_pt)
        if stored_pt is not None
        else (reverse_crown_out - 0.7 * L if reverse_crown_out is not None else None)
    )

    nc_pct = normal_crown * 100.0
    e_pct = e * 100.0
    reverse_curve_entry_zero = results.get("reverse_curve_entry_zero_ft")
    reverse_curve_entry_zero = None if reverse_curve_entry_zero is None else float(reverse_curve_entry_zero)
    reverse_curve_exit_zero = results.get("reverse_curve_exit_zero_ft")
    reverse_curve_exit_zero = None if reverse_curve_exit_zero is None else float(reverse_curve_exit_zero)

    reverse_crown_case = (
        str(results.get("crown_state", "")).lower().startswith("reverse")
        or str(results.get("e_source", "")).lower().startswith("reverse")
    )
    normal_crown_only = bool(results.get("normal_crown_only"))

    def finish(rows: list[dict]) -> list[dict]:
        for row in rows:
            row["station"] = Super.format_result_station(results, row.get("station_ft"), station_format)
        return rows

    def lane_rows(side: str) -> list[dict]:
        final_sign = 1.0 if side == outside else -1.0
        rows: list[dict] = []

        if normal_crown_only:
            rows.append(
                _make_row(
                    "NC",
                    pc,
                    -nc_pct,
                    "Normal crown maintained; no superelevation transition required",
                    "Normal crown",
                    station_format,
                )
            )
            if pt is not None and pt != pc:
                rows.append(
                    _make_row(
                        "NC",
                        pt,
                        -nc_pct,
                        "Normal crown maintained through curve",
                        "Normal crown",
                        station_format,
                    )
                )
            return finish(rows)

        if results.get("transition_method") == "tdot_simple_curve_half_total":
            start = float(results.get("pnc_ft", pc) or pc)
            zero = float(results.get("zero_crown_ft", reverse_crown) or reverse_crown)
            reverse_section = float(results.get("reverse_section_ft", zero + Lt) or (zero + Lt))
            end = results.get("pnc_out_ft")
            end = None if end is None else float(end)
            zero_out = results.get("zero_crown_out_ft")
            zero_out = None if zero_out is None else float(zero_out)
            reverse_section_out = results.get("reverse_section_out_ft")
            reverse_section_out = None if reverse_section_out is None else float(reverse_section_out)

            if side == outside:
                pc_fraction = 0.0 if L <= 0 else max(0.0, min(1.0, (pc - zero) / L))
                rows.extend(
                    [
                        _make_row("NC", start, -nc_pct, "Start of total transition", "Normal crown", station_format),
                        _make_row("0%", zero, 0.0, "Start of runoff", "Reverse crown", station_format),
                        _make_row("RC", reverse_section, nc_pct, "Reverse-crown section", "Reverse crown section", station_format),
                        _make_row("PC", pc, final_sign * e_pct * pc_fraction, "Simple curve", "PC", station_format),
                        _make_row("FULL SUPER", full_super_pc, final_sign * e_pct, "One-half total transition after PC", "Full super", station_format),
                    ]
                )
                if pt is not None and full_super_pt is not None and zero_out is not None and end is not None:
                    pt_fraction = 0.0 if L <= 0 else max(0.0, min(1.0, (zero_out - pt) / L))
                    rows.extend(
                        [
                            _make_row("FULL SUPER", full_super_pt, final_sign * e_pct, "One-half total transition before PT", "End full super", station_format),
                            _make_row("PT", pt, final_sign * e_pct * pt_fraction, "Simple curve", "PT", station_format),
                        ]
                    )
                    if reverse_section_out is not None:
                        rows.append(_make_row("RC", reverse_section_out, nc_pct, "Reverse-crown section", "Reverse crown section", station_format))
                    rows.extend(
                        [
                            _make_row("0%", zero_out, 0.0, "End of runoff", "End runoff", station_format),
                            _make_row("NC", end, -nc_pct, "End of total transition", "Back to normal crown", station_format),
                        ]
                    )
            else:
                pc_fraction = 0.0
                if full_super_pc > reverse_section:
                    pc_fraction = max(0.0, min(1.0, (pc - reverse_section) / (full_super_pc - reverse_section)))
                pc_slope = -nc_pct + (-e_pct + nc_pct) * pc_fraction
                rows.extend(
                    [
                        _make_row("NC", start, -nc_pct, "Start of total transition", "Normal crown", station_format),
                        _make_row("RC", reverse_section, -nc_pct, "Reverse-crown section", "Reverse crown section", station_format),
                        _make_row("PC", pc, pc_slope, "Simple curve", "PC", station_format),
                        _make_row("FULL SUPER", full_super_pc, -e_pct, "One-half total transition after PC", "Full super", station_format),
                    ]
                )
                if pt is not None and full_super_pt is not None and end is not None:
                    exit_reverse = reverse_section_out if reverse_section_out is not None else end
                    pt_fraction = 0.0
                    if exit_reverse > full_super_pt:
                        pt_fraction = max(0.0, min(1.0, (pt - full_super_pt) / (exit_reverse - full_super_pt)))
                    pt_slope = -e_pct + (-nc_pct + e_pct) * pt_fraction
                    rows.extend(
                        [
                            _make_row("FULL SUPER", full_super_pt, -e_pct, "One-half total transition before PT", "End full super", station_format),
                            _make_row("PT", pt, pt_slope, "Simple curve", "PT", station_format),
                            _make_row("NC", exit_reverse, -nc_pct, "Reverse-crown section", "Back to normal crown", station_format),
                            _make_row("NC", end, -nc_pct, "End of total transition", "Back to normal crown", station_format),
                        ]
                    )
            rows.sort(key=lambda row: float(row.get("station_ft") or 0.0))
            return rows

        if reverse_crown_case:
            start_station = reverse_crown - Lt
            end_station = reverse_crown_out + Lt if reverse_crown_out is not None else None
            if side == outside:
                rows.append(_make_row("NC", start_station, -nc_pct, "Sta = PC - 0.7L - Lt", "Normal crown", station_format))
                rows.append(_make_row("0%", reverse_crown, 0.0, "Sta = PC - 0.7L", "Reverse crown", station_format))
                rows.append(_make_row("PC", pc, final_sign * nc_pct * 0.7, "70% super", "PC 70% super", station_format))
                rows.append(
                    _make_row("FULL SUPER", full_super_pc, final_sign * nc_pct, "Sta = PC + 0.3L", "Full super", station_format)
                )
                if pt is not None and full_super_pt is not None and reverse_crown_out is not None:
                    rows.append(
                        _make_row(
                            "FULL SUPER",
                            full_super_pt,
                            final_sign * nc_pct,
                            "Sta = PT - 0.3L",
                            "End full super",
                            station_format,
                        )
                    )
                    rows.append(_make_row("PT", pt, final_sign * nc_pct * 0.7, "70% super", "PT 70% super", station_format))
                    rows.append(_make_row("0%", reverse_crown_out, 0.0, "Sta = PT + 0.7L", "End runoff", station_format))
                if end_station is not None:
                    rows.append(_make_row("NC", end_station, -nc_pct, "0% + runout", "Back to normal crown", station_format))
            else:
                rows.append(_make_row("NC", start_station, -nc_pct, "Sta = PC - 0.7L - Lt", "Normal crown", station_format))
                rows.append(_make_row("PC", pc, -nc_pct * 0.7, "70% super", "PC 70% super", station_format))
                rows.append(
                    _make_row("FULL SUPER", full_super_pc, -nc_pct, "Sta = PC + 0.3L", "Full super", station_format)
                )
                if pt is not None and full_super_pt is not None:
                    rows.append(
                        _make_row("FULL SUPER", full_super_pt, -nc_pct, "Sta = PT - 0.3L", "End full super", station_format)
                    )
                    rows.append(_make_row("PT", pt, -nc_pct * 0.7, "70% super", "PT 70% super", station_format))
                if end_station is not None:
                    rows.append(_make_row("NC", end_station, -nc_pct, "Sta = PT + 0.7L + Lt", "Back to normal crown", station_format))
            return finish(rows)

        if reverse_curve_entry_zero is not None:
            rows.append(_make_row("0%", reverse_curve_entry_zero, 0.0, "Stored reverse-curve zero-slope station", "Reverse curve zero", station_format))
            pc_slope = _linear_slope_at_station(
                pc,
                reverse_curve_entry_zero,
                0.0,
                full_super_pc,
                final_sign * e_pct,
            )
        else:
            inside_rotation_start = reverse_crown + _inside_rotation_offset(L, e_pct, nc_pct)
            if side == outside:
                rows.append(_make_row("NC", reverse_crown - Lt, -nc_pct, "Sta = PC - 0.7L - Lt", "Normal crown", station_format))
                rows.append(_make_row("0%", reverse_crown, 0.0, "Sta = PC - 0.7L", "Reverse crown", station_format))
                rows.append(_make_row(f"{nc_pct:g}%", inside_rotation_start, nc_pct, "MDOT SE-3A X1 = L(NC/e)", "Normal-crown slope", station_format))
                pc_slope = _linear_slope_at_station(
                    pc, reverse_crown, 0.0, full_super_pc, final_sign * e_pct
                )
            else:
                rows.append(_make_row("NC", reverse_crown - Lt, -nc_pct, "Normal crown through tangent runout", "Normal crown", station_format))
                rows.append(_make_row("BEGIN ROTATION", inside_rotation_start, -nc_pct, "MDOT SE-3A X1 = L(NC/e)", "Inside-lane rotation", station_format))
                pc_slope = _linear_slope_at_station(
                    pc, inside_rotation_start, -nc_pct, full_super_pc, final_sign * e_pct
                )

        rows.append(_make_row("PC", pc, pc_slope, "70% runoff" if reverse_curve_entry_zero is None else "Reverse-curve runoff", "PC 70% super" if reverse_curve_entry_zero is None else "PC reverse-curve runoff", station_format))
        rows.append(_make_row("FULL SUPER", full_super_pc, final_sign * e_pct, "Sta = PC + 0.3L", "Full super", station_format))
        if pt is not None and full_super_pt is not None and reverse_crown_out is not None:
            rows.append(_make_row("FULL SUPER", full_super_pt, final_sign * e_pct, "Sta = PT - 0.3L", "End full super", station_format))
            if reverse_curve_exit_zero is not None:
                pt_slope = _linear_slope_at_station(
                    pt,
                    full_super_pt,
                    final_sign * e_pct,
                    reverse_curve_exit_zero,
                    0.0,
                )
                rows.append(_make_row("PT", pt, pt_slope, "Reverse-curve runoff", "PT reverse-curve runoff", station_format))
                rows.append(_make_row("0%", reverse_curve_exit_zero, 0.0, "Stored reverse-curve zero-slope station", "Reverse curve zero", station_format))
            else:
                inside_rotation_end = reverse_crown_out - _inside_rotation_offset(L, e_pct, nc_pct)
                if side == outside:
                    pt_slope = _linear_slope_at_station(
                        pt, full_super_pt, final_sign * e_pct, reverse_crown_out, 0.0
                    )
                else:
                    pt_slope = _linear_slope_at_station(
                        pt, full_super_pt, final_sign * e_pct, inside_rotation_end, -nc_pct
                    )
                rows.append(_make_row("PT", pt, pt_slope, "70% runoff", "PT 70% super", station_format))
                if side == outside:
                    rows.append(_make_row(f"{nc_pct:g}%", inside_rotation_end, nc_pct, "MDOT SE-3A X1 = L(NC/e)", "Normal-crown slope", station_format))
                    rows.append(_make_row("0%", reverse_crown_out, 0.0, "Sta = PT + 0.7L", "End runoff", station_format))
                    rows.append(_make_row("NC", reverse_crown_out + Lt, -nc_pct, "0% + runout", "Back to normal crown", station_format))
                else:
                    rows.append(_make_row("END ROTATION", inside_rotation_end, -nc_pct, "MDOT SE-3A X1 = L(NC/e)", "Inside-lane rotation", station_format))
                    rows.append(_make_row("NC", reverse_crown_out + Lt, -nc_pct, "Normal crown through tangent runout", "Back to normal crown", station_format))
        rows.sort(key=lambda row: float(row.get("station_ft") or 0.0))
        return rows

    return finish(lane_rows("left")), finish(lane_rows("right"))


def _ord_point_type(event_type: str, side: str, direction: str) -> str:
    outside = outside_lane(direction)
    suffix = "OUT" if side == outside else "IN"
    if event_type in {"Normal crown", "Back to normal crown"}:
        return f"NC{suffix}"
    if event_type in {"Reverse crown", "End runoff"}:
        return f"RC{suffix}"
    if event_type in {"Full super", "End full super"}:
        return f"FS{suffix}"
    return "U"


def _station_region(station: float, equations: list[dict] | None) -> int:
    """Return ORD station region number (R1 before equations, then R2, R3...)."""
    region = 1
    for equation in sorted(equations or [], key=lambda item: float(item.get("internal", item.get("staInternal", 0.0)))):
        internal = float(equation.get("internal", equation.get("staInternal", 0.0)))
        if station + 1e-9 >= internal:
            region += 1
        else:
            break
    return region


def build_normalized_rows(curves: Iterable[dict], station_format: bool = True) -> list[dict]:
    rows: list[dict] = []
    emitted_reverse_events: set[tuple[str, str, str, float, float]] = set()
    for curve_index, curve in enumerate(curves):
        results = curve.get("results") or {}
        meta = curve.get("meta", {}) or {}
        direction = meta.get("curve_direction", "left")
        left_rows, right_rows = build_lane_rows(results, direction, station_format)

        lane_sets = [(side,lane_name_for_side(side,curve),lane_rows) for side,lane_rows in (("left",left_rows),("right",right_rows))]
        if results.get("section_lanes"):
            lane_sets=[]
            for lane in results["section_lanes"]:
                rendered=[{**event,**_make_row(event["label"],event["station_ft"],event["slope_pct"],event["note"],event["event_type"],station_format),
                           "station":Super.format_result_station(results,event["station_ft"],station_format)} for event in lane["events"]]
                lane_sets.append((lane["side"],lane["lane_name"],rendered))
        for side, lane_name, lane_rows in lane_sets:
            section_lane=next((lane for lane in results.get("section_lanes",[]) if lane["lane_name"]==lane_name),None)
            pivot_about=None
            if section_lane:
                pivot=float(results["pivot_offset_ft"])
                if abs(pivot-section_lane["left_offset_ft"])<1e-8:pivot_about="LS"
                elif abs(pivot-section_lane["right_offset_ft"])<1e-8:pivot_about="RS"
            for row in lane_rows:
                station_ft = row.get("station_ft")
                if station_ft is None:
                    continue
                reverse_pair_id = str(row.get("reverse_pair_id") or "")
                reverse_critical = bool(row.get("reverse_pair_critical") and reverse_pair_id)
                if reverse_critical:
                    reverse_key = (
                        reverse_pair_id,
                        side,
                        str(row.get("event_type") or ""),
                        round(float(station_ft), 7),
                        round(float(row["slope_pct"]), 7),
                    )
                    if reverse_key in emitted_reverse_events:
                        continue
                    emitted_reverse_events.add(reverse_key)
                rows.append(
                    {
                        "project_name": str(meta.get("project_name", "") or ""),
                        "route_name": str(meta.get("route_name", "") or ""),
                        "alignment_name": str(meta.get("alignment_name", "") or ""),
                        "curve_name": str(meta.get("curve_name", "") or ""),
                        "curve_index": curve_index,
                        "curve_direction": str(direction or ""),
                        "station": station_ft,
                        "station_label": row["station"],
                        "side": side,
                        "lane_name": lane_name,
                        "fixed_pivot": section_lane is not None,
                        "pivot_about": pivot_about,
                        "ord_slope_percent": float(row["slope_pct"])*(1 if side=="left" else -1)*(-1 if pivot_about=="LS" else 1) if section_lane else float(row["slope_pct"]),
                        "slope_percent": float(row["slope_pct"]),
                        "slope_decimal": float(row["slope_decimal"]),
                        "slope_label": row["slope_label"],
                        "event_type": row["event_type"],
                        "reverse_pair_id": reverse_pair_id or None,
                        "reverse_pair_critical": reverse_critical,
                        "notes": row["note"] if not curve.get("notes") else f"{row['note']}; {curve['notes']}",
                        "station_region": _station_region(float(station_ft), results.get("station_equations")),
                    }
                )
    return rows


def write_ord_csv(handle: TextIO, curves: Iterable[dict]) -> list[str]:
    curve_list = list(curves)
    from aashto_superelevation import validate_export_curves
    validate_export_curves(curve_list)
    rows=build_normalized_rows(curve_list)
    if any(row.get("fixed_pivot") and row.get("pivot_about") is None for row in rows):
        raise ValueError("ORD CSV cannot represent this fixed pivot with the verified lane-edge LS/RS mapping. Supported AASHTO CSV sections: two lanes about their common edge, or one single-slope lane about a pavement edge. PDF and geometry DXF remain available; real ORD validation is required for other pivots.")
    warnings = [
        "ORD CSV format follows Bentley Import Superelevation documentation. Verify lane names match existing ORD superelevation lanes before import.",
        "Stations after alignment equations use ORD region suffixes R2, R3, and so on.",
        "This export is schema-confirmed but still needs real in-ORD round-trip validation.",
    ]
    if any(row.get("fixed_pivot") for row in rows):
        warnings.append("AASHTO controls use PointType U (undefined) with recorded stations and pivot-relative slopes; engineering section/event classifications remain in the project and PDF. Verify the imported lane pivots in ORD.")
    for curve in curve_list:
        for warning in (curve.get("results", {}) or {}).get("warnings", []) or []:
            if warning not in warnings:
                warnings.append(str(warning))
    writer = csv.DictWriter(handle, fieldnames=ORD_HEADERS)
    writer.writeheader()
    for row in rows:
        if not row["station_label"] or row["station_label"] == "n/a":
            continue
        station_label = str(row["station_label"])
        station_region = int(row.get("station_region", 1) or 1)
        if station_region > 1 and not station_label.endswith(f"R{station_region}"):
            station_label = f"{station_label}R{station_region}"
        writer.writerow(
            {
                "SuperelevationLane": row["lane_name"],
                "Station": station_label,
                "CrossSlope": slope_decimal(row["ord_slope_percent"]),
                "PivotAbout": row.get("pivot_about") or pivot_about_for_side(str(row["side"])),
                "PointType": "U" if row.get("fixed_pivot") else _ord_point_type(str(row["event_type"]), str(row["side"]), str(row["curve_direction"])),
                "TransitionType": "L",
                "NonLinearCurveLength": "0",
            }
        )
    return warnings
