"""Platform-neutral application services shared by Tkinter and browser clients."""

from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

import Super
from app_info import APP_NAME, APP_VERSION, CALCULATION_ENGINE_VERSION
from commercial_entitlements import (
    Capability,
    LocalDevelopmentEntitlementProvider,
    commercial_manifest,
    require_capability,
    require_profile_access,
    snapshot_from_payload,
)
from criteria_info import MDOT_PROFILE_ID, AASHTO_PROFILE_ID, criteria_metadata, criteria_profiles, normalize_profile_id
import super_batch
import super_dxf
import super_exports
import super_landxml
from super_lane import lane_profile_points, parse_slope_percent, slope_at_station, slope_matches
import super_pdf
import super_project
import super_qa


DEFAULT_INPUTS = {
    "criteria_profile": MDOT_PROFILE_ID,
    "curve_direction": "left",
    "facility": "centerline",
    "area": "rural",
    "lane_width": "12",
    "lanes_rotated": "2",
    "normal_crown": "0.02",
    "station_format": True,
}


def application_manifest() -> dict[str, Any]:
    return {
        "name": APP_NAME,
        "application_version": APP_VERSION,
        "calculation_engine_version": CALCULATION_ENGINE_VERSION,
        "project_schema_version": super_project.PROJECT_VERSION,
        "commercial": commercial_manifest(),
        "criteria": criteria_metadata(),
        "criteria_profiles": criteria_profiles(),
        "defaults": dict(DEFAULT_INPUTS),
        "options": {
            "curve_direction": ["left", "right"],
            "facility": ["centerline", "outside edge"],
            "tdot_facility": ["undivided"],
            "area": ["rural", "urban", "local"],
            "speed": [str(value) for value in range(15, 85, 5)],
            "profiles": {
                AASHTO_PROFILE_ID: {"facility":["centerline","left_edge","right_edge"],"area":["rural","urban_freeway","urban_high_speed"],
                    "speed":[str(v) for v in range(15,86,5)], "max_superelevation":[4,6,8,10,12],
                    "roadway":["two_way","one_way"], "rotation_axis":["centerline","left_edge","right_edge"],
                    "initial_section":["crowned","single_slope"],"runout_placement":["on_tangent","in_spiral"],
                    "criteria_workbook_required":True},
                MDOT_PROFILE_ID: {
                    "facility": ["centerline", "outside edge"],
                    "area": ["rural", "urban", "local"],
                    "speed": [str(value) for value in range(15, 85, 5)],
                },
                "tdot-rd11-2026-04-30": {
                    "facility": ["undivided"],
                    "area": ["rural", "urban"],
                    "speed": [str(value) for value in range(20, 75, 5)],
                    "urban_speed": [str(value) for value in range(20, 65, 5)],
                },
            },
        },
    }


_OPERATION_CAPABILITIES = {
    "parse_landxml": Capability.LANDXML_WORKFLOWS,
    "build_all_landxml_curves": Capability.MULTI_CURVE_PROJECTS,
    "coordinate_reverse_curves": Capability.MULTI_CURVE_PROJECTS,
    "corridor_qa": Capability.LANDXML_WORKFLOWS,
    "plan_view": Capability.LANDXML_WORKFLOWS,
    "project_load": Capability.PROJECT_FILES,
    "project_save": Capability.PROJECT_FILES,
    "export_ord_csv": Capability.ORD_CSV_EXPORT,
    "export_pdf": Capability.PDF_REPORTS,
    "export_detail_dxf": Capability.OVERLAY_DXF_EXPORT,
    "export_overlay_dxf": Capability.OVERLAY_DXF_EXPORT,
}


def _station_equations(value: Any) -> list[dict]:
    if isinstance(value, list):
        return value
    equations: list[dict] = []
    for entry in str(value or "").split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError("Manual station equations must use Back=Ahead format.")
        back, ahead = (part.strip() for part in entry.split("=", 1))
        equations.append({"staBack": str(Super.parse_station(back)), "staAhead": str(Super.parse_station(ahead))})
    return equations


def _station_range(value: Any) -> tuple[float, float] | None:
    if value in (None, "", []):
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        start, end = float(value[0]), float(value[1])
    else:
        text = str(value)
        if "," not in text:
            raise ValueError("Internal alignment range must use Start,End format.")
        start_text, end_text = (part.strip() for part in text.split(",", 1))
        start, end = Super.parse_station(start_text), Super.parse_station(end_text)
    if end < start:
        raise ValueError("Internal alignment range end must be greater than its start.")
    return start, end


def calculate_curve(inputs: dict[str, Any]) -> dict[str, Any]:
    """Calculate one curve and return structured presentation data."""
    values = {**DEFAULT_INPUTS, **(inputs or {})}
    profile_id = normalize_profile_id(str(values.get("criteria_profile", MDOT_PROFILE_ID)))
    if values.get("alignment_type")=="spiral" and profile_id != AASHTO_PROFILE_ID:
        raise ValueError("Spiral transition calculations are currently supported only by the AASHTO profile.")
    if profile_id==AASHTO_PROFILE_ID and values.get("linear_unit") not in (None,"","foot","Foot","USSurveyFoot","internationalFoot"):
        raise ValueError("AASHTO calculations require foot-based stationing; metric LandXML geometry may be inspected but not used for this US-unit profile.")
    area = str(values.get("area", "rural"))
    facility = (
        "centerline"
        if profile_id == MDOT_PROFILE_ID and area.lower().startswith("local")
        else str(values.get("facility", "centerline"))
    )
    arguments = (
        str(values.get("pc", "")),
        str(values.get("pt", "")),
        str(values.get("speed", "")),
        str(values.get("radius", "")),
        facility,
        area,
        str(values.get("lane_width", "12")),
        str(values.get("lanes_rotated", "2")),
        str(values.get("e_manual", "")),
        str(values.get("friction", "")),
        str(values.get("rel_grad", "")),
        str(values.get("normal_crown", "0.02")),
        str(values.get("Lr_manual", "")),
        str(values.get("Lt_manual", "")),
        _station_equations(values.get("station_equations")),
        _station_range(values.get("alignment_station_range")),
        profile_id,
    )
    results = Super.calculate_superelevation(*arguments, profile_options=values)
    baseline_arguments = list(arguments)
    for index in (8, 9, 10, 12, 13):
        baseline_arguments[index] = ""
    try:
        baseline = Super.calculate_superelevation(*baseline_arguments, profile_options={**values, "e_manual":"", "Lr_manual":"", "Lt_manual":""})
    except ValueError:
        baseline = results
    direction = str(values.get("curve_direction", "left") or "left")
    station_format = bool(values.get("station_format", True))
    return {**present_results(results,direction,station_format), "baseline":baseline}


def present_results(results: dict, direction: str = "left", station_format: bool = True) -> dict[str, Any]:
    left_rows, right_rows = super_exports.build_lane_rows(results, direction, station_format)
    section_lanes=[]
    for lane in results.get("section_lanes",[]):
        rows=[{**event,"station":Super.format_result_station(results,event["station_ft"],station_format),
               "slope_label":super_exports.format_slope_label(event["slope_pct"])} for event in lane["events"]]
        section_lanes.append({**lane,"events":rows})
    return {
        "results": results,
        "baseline": results,
        "formatted_results": Super.format_results(results, station_format),
        "lanes": {"left": left_rows, "right": right_rows},
        "section_lanes": section_lanes,
    }


def calculate_with_entitlement(inputs: dict[str, Any], entitlement: Any = None) -> dict[str, Any]:
    """Authorize the requested profile, then call the unchanged calculation service."""
    values = {**DEFAULT_INPUTS, **(inputs or {})}
    profile_id = normalize_profile_id(str(values.get("criteria_profile", MDOT_PROFILE_ID)))
    require_profile_access(snapshot_from_payload(entitlement), profile_id)
    return calculate_curve(inputs)


def parse_landxml(content: str, filename: str = "alignment.xml") -> dict[str, Any]:
    data = super_landxml.parse_landxml_text(content, filename)
    source = super_project.make_landxml_source(filename, content)
    return {
        "source": source,
        "summary": {
            "filename": source["filename"],
            "alignment_name": data.alignment_name,
            "start_station": data.start_station,
            "alignment_length": data.alignment_length,
            "linear_unit": data.linear_unit,
            "coordinate_system": super_landxml.coordinate_system_summary(data.coordinate_system),
            "station_equation_count": len(data.station_equations),
            "curve_count": len(data.curves),
            "warnings": list(data.warnings),
        },
        "curve_presets": data.curve_records(),
    }


def build_all_landxml_curves(content: str, filename: str, shared_inputs: dict[str, Any]) -> list[dict]:
    data = super_landxml.parse_landxml_text(content, filename)
    normalized = dict(shared_inputs)
    return super_batch.build_curves_from_presets(data.curve_records(), normalized)


def coordinate_reverse_curves(
    curves: list[dict],
    enabled: bool = True,
    pairs: list[list[int]] | None = None,
) -> list[dict]:
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
    return super_batch.coordinate_reverse_curve_transitions(curves, enabled=bool(enabled), pairs=pairs)


def lookup(results: dict, direction: str, station_text: str = "", slope_text: str = "") -> dict[str, Any]:
    if not station_text.strip() and not slope_text.strip():
        raise ValueError("Enter a station, a super value, or both.")
    points = lane_profile_points(results, direction)
    if results.get("section_lanes"):
        points={lane["lane_name"]:[(event["station_ft"],event["slope_pct"]) for event in lane["events"]] for lane in results["section_lanes"]}
    response: dict[str, Any] = {"station": None, "slope": None, "lanes": {}}
    reference = float(results.get("reverse_crown_ft", 0.0))
    if station_text.strip():
        station = Super.parse_station_reference(station_text, results.get("station_equations"), results.get("alignment_station_range"))
        reference = station
        response["station"] = {
            "label": Super.format_result_station(results, station, True),
            "internal_ft": station,
            "slopes": {
                lane: {
                    "percent": slope_at_station(points[lane], station),
                    "label": super_exports.format_slope_label(slope_at_station(points[lane], station)),
                    "decimal": super_exports.slope_decimal(slope_at_station(points[lane], station)),
                }
                for lane in points
            },
        }
    if slope_text.strip():
        target = parse_slope_percent(slope_text)
        response["slope"] = {
            "percent": target,
            "label": super_exports.format_slope_label(target),
            "decimal": super_exports.slope_decimal(target),
        }
        for lane in points:
            matches = slope_matches(points[lane], target)
            rendered = []
            nearest = None
            if station_text.strip() and matches:
                nearest = min(
                    range(len(matches)),
                    key=lambda index: _distance_to_range(matches[index], reference),
                )
            point_indexes = [index for index, (start, end) in enumerate(matches) if abs(end - start) <= 1e-6]
            for index, (start, end) in enumerate(matches):
                if end - start > 1e-6:
                    rate = abs(float(results.get("e", 0.0))) * 100.0
                    label = "Full-super range" if abs(abs(target) - rate) <= 1e-6 else "Constant range"
                elif len(point_indexes) == 1:
                    label = "Station"
                elif index == point_indexes[0]:
                    label = "Entering"
                elif index == point_indexes[-1]:
                    label = "Exiting"
                else:
                    label = f"Match {point_indexes.index(index) + 1}"
                rendered.append(
                    {
                        "label": label,
                        "start": Super.format_result_station(results, start, True),
                        "end": Super.format_result_station(results, end, True),
                        "is_range": end - start > 1e-6,
                        "nearest": index == nearest,
                    }
                )
            response["lanes"][lane] = rendered
    if results.get("section_lanes") and response["station"]:
        response["station"]["edge_elevations"]={lane["lane_name"]:{edge:slope_at_station([(event["station_ft"],event[edge]) for event in lane["events"]],reference) for edge in ("right_elevation_ft","left_elevation_ft")} for lane in results["section_lanes"]}
    return response


def curve_diagram(results: dict, direction: str = "left") -> dict[str, Any]:
    return super_qa.curve_diagram(results, direction)


def corridor_diagram(curves: list[dict]) -> dict[str, Any]:
    return super_qa.corridor_diagram(curves)


def diagram_lookup(results: dict, direction: str, station: float) -> dict[str, Any]:
    return super_qa.diagram_lookup(results, direction, float(station))


def corridor_qa(content: str, filename: str, curves: list[dict], excluded_curve_indexes: list[int] | None = None,
                shared_inputs: dict | None = None) -> dict[str, Any]:
    data = super_landxml.parse_landxml_text(content, filename)
    return super_qa.analyze_corridor(data, curves, excluded_curve_indexes, shared_inputs)


def plan_view(content: str, filename: str, curves: list[dict]) -> dict[str, Any]:
    data = super_landxml.parse_landxml_text(content, filename)
    preview = super_dxf.overlay_preview_model(curves, data)
    errors, issue_warnings = super_dxf.overlay_export_issues(curves, data)
    warnings = list(dict.fromkeys([*preview.get("warnings", []), *issue_warnings]))
    return {
        **preview,
        "alignment_name": data.alignment_name,
        "coordinate_system": data.coordinate_system.as_dict() if data.coordinate_system else None,
        "linear_unit": data.linear_unit,
        "errors": errors,
        "warnings": warnings,
    }


def _distance_to_range(station_range: tuple[float, float], station: float) -> float:
    start, end = station_range
    if start <= station <= end:
        return 0.0
    return min(abs(station - start), abs(station - end))


def project_load(content: str) -> dict[str, Any]:
    data = super_project.loads_project(content)
    source = data.get("landxml_source")
    landxml = parse_landxml(source["content"], source["filename"]) if source else None
    return {"project": data, "landxml": landxml}


def project_save(data: dict[str, Any]) -> str:
    return super_project.dumps_project(data)


def export_ord_csv(curves: list[dict]) -> dict[str, Any]:
    handle = io.StringIO(newline="")
    warnings = super_exports.write_ord_csv(handle, curves)
    return {"content": handle.getvalue(), "warnings": warnings}


def _temporary_export(suffix: str, exporter: Callable[[str], Any]) -> tuple[bytes, list[str]]:
    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            path = handle.name
        result = exporter(path)
        warnings = result if isinstance(result, list) else []
        return Path(path).read_bytes(), warnings
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def _calculation_warnings(curves: list[dict]) -> list[str]:
    warnings: list[str] = []
    for curve in curves:
        for warning in (curve.get("results", {}) or {}).get("warnings", []) or []:
            if warning not in warnings:
                warnings.append(str(warning))
    return warnings


def export_pdf(curves: list[dict], corridor_qa_report: dict | None = None) -> dict[str, Any]:
    from aashto_superelevation import validate_export_curves
    if any(f.get("severity")=="block" for f in (corridor_qa_report or {}).get("findings",[])) and any(c.get("results",{}).get("transition_method")=="aashto_fixed_pivot" for c in curves):
        curves=[]  # Only diagnostics are emitted while affected calculations are blocked.
    validate_export_curves(curves)
    content, warnings = _temporary_export(
        ".pdf", lambda path: super_pdf.export_pdf(path, curves, corridor_qa_report)
    )
    return {"content": content, "warnings": list(dict.fromkeys(warnings + _calculation_warnings(curves)))}


def export_detail_dxf(curves: list[dict]) -> dict[str, Any]:
    from aashto_superelevation import validate_export_curves
    validate_export_curves(curves)
    content, warnings = _temporary_export(".dxf", lambda path: super_dxf.export_detail_dxf(path, curves))
    return {"content": content, "warnings": list(dict.fromkeys(warnings + _calculation_warnings(curves)))}


def export_overlay_dxf(curves: list[dict], landxml_source: dict[str, str]) -> dict[str, Any]:
    from aashto_superelevation import validate_export_curves
    validate_export_curves(curves)
    source = super_project.normalize_landxml_source(landxml_source)
    if not source:
        raise ValueError("Select LandXML before exporting an overlay DXF.")
    data = super_landxml.parse_landxml_text(source["content"], source["filename"])
    errors, diagnostic_warnings = super_dxf.overlay_export_issues(curves, data)
    if errors:
        raise ValueError("\n".join(errors))
    content, warnings = _temporary_export(".dxf", lambda path: super_dxf.export_overlay_dxf(path, curves, data))
    return {
        "content": content,
        "warnings": list(dict.fromkeys(diagnostic_warnings + warnings + _calculation_warnings(curves))),
    }


def dispatch(operation: str, payload_json: str = "{}") -> Any:
    """Stable JSON bridge invoked by the Pyodide worker."""
    payload = json.loads(payload_json or "{}")
    entitlement = snapshot_from_payload(payload.get("entitlement"))
    required_capability = _OPERATION_CAPABILITIES.get(operation)
    if required_capability is not None:
        require_capability(entitlement, required_capability)
    if operation.startswith("export_") and operation!="export_pdf" and any(c.get("results",{}).get("transition_method")=="aashto_fixed_pivot" for c in payload.get("curves",[])):
        if any(f.get("severity")=="block" for f in (payload.get("corridor_qa") or {}).get("findings",[])):
            raise ValueError("AASHTO export blocked by Corridor QA; resolve the blocking findings.")
    operations: dict[str, Callable[..., Any]] = {
        "manifest": lambda: application_manifest(),
        "entitlement_snapshot": lambda: LocalDevelopmentEntitlementProvider(
            payload.get("plan", "free"), payload.get("status", "active")
        ).snapshot().as_dict(),
        "calculate": lambda: calculate_with_entitlement(
            payload.get("inputs", payload), payload.get("entitlement")
        ),
        "import_aashto_workbook": lambda: __import__("aashto_criteria").import_workbook(payload["content_base64"]),
        "present_results": lambda: present_results(
            payload["results"], payload.get("direction", "left"), bool(payload.get("station_format", True))
        ),
        "parse_landxml": lambda: parse_landxml(payload["content"], payload.get("filename", "alignment.xml")),
        "build_all_landxml_curves": lambda: build_all_landxml_curves(
            payload["content"], payload.get("filename", "alignment.xml"), payload.get("shared_inputs", {})
        ),
        "coordinate_reverse_curves": lambda: coordinate_reverse_curves(
            payload.get("curves", []), payload.get("enabled", True), payload.get("pairs")
        ),
        "lookup": lambda: lookup(
            payload["results"], payload.get("direction", "left"), payload.get("station", ""), payload.get("slope", "")
        ),
        "curve_diagram": lambda: curve_diagram(payload["results"], payload.get("direction", "left")),
        "corridor_diagram": lambda: corridor_diagram(payload.get("curves", [])),
        "diagram_lookup": lambda: diagram_lookup(
            payload["results"], payload.get("direction", "left"), payload["station"]
        ),
        "corridor_qa": lambda: corridor_qa(
            payload["content"], payload.get("filename", "alignment.xml"), payload.get("curves", []),
            payload.get("excluded_curve_indexes", []),
            payload.get("shared_inputs"),
        ),
        "plan_view": lambda: plan_view(
            payload["content"], payload.get("filename", "alignment.xml"), payload.get("curves", [])
        ),
        "project_load": lambda: project_load(payload["content"]),
        "project_save": lambda: project_save(payload["project"]),
        "export_ord_csv": lambda: export_ord_csv(payload["curves"]),
        "export_pdf": lambda: export_pdf(payload["curves"], payload.get("corridor_qa")),
        "export_detail_dxf": lambda: export_detail_dxf(payload["curves"]),
        "export_overlay_dxf": lambda: export_overlay_dxf(
            payload["curves"], payload["landxml_source"]
        ),
    }
    try:
        handler = operations[operation]
    except KeyError as exc:
        raise ValueError(f"Unsupported browser operation: {operation}") from exc
    return handler()


def dispatch_safe(operation: str, payload_json: str = "{}") -> dict[str, Any]:
    """Return browser-operation failures as concise structured messages."""
    try:
        return {"ok": True, "result": dispatch(operation, payload_json)}
    except Exception as exc:
        findings=getattr(exc,"findings",[])
        try:
            payload=json.loads(payload_json or "{}")
            values=payload.get("inputs",payload.get("shared_inputs",{}))
        except (ValueError,AttributeError):values={}
        if isinstance(exc,ValueError) and not findings and str(values.get("criteria_profile","")).startswith(("aashto",)):
            findings=[{"code":"INVALID_OR_UNSUPPORTED_INPUT","severity":"block","message":str(exc),"details":"Calculation and affected engineering exports are unavailable until resolved."}]
        return {
            "ok": False,
            "error": {"type": type(exc).__name__, "message": str(exc) or "Operation failed.", "findings": findings},
        }
