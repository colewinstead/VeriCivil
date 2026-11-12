"""Validated JSON boundary; engineering and report behavior belong to upstream."""

from dataclasses import asdict
from datetime import date, datetime
import json
from pathlib import Path
import tempfile

from guardrail_design import (
    APP_VERSION, DEFAULT_L1_FT, DEFAULT_TERMINAL_SECTION_FT, DESIGN_REFERENCES,
    SUPPORTED_SPEEDS, SUPPORTED_FLARE_RATES, ClearZoneCriteria, ClearZoneSelection, HazardOffsetSource,
    ReportStyle, SideSlope,
)
from guardrail_engine import create_snapshot, resolve_clear_zone
from guardrail_models import CalculationInputs, HazardBarrierInputs, ProjectMetadata, ReportModel
from guardrail_parsing import parse_number
from guardrail_validation import create_roadway, lane_count

UPSTREAM = Path(__file__).with_name("upstream")
SOURCE = json.loads((UPSTREAM / "source.json").read_text(encoding="utf-8"))
MAX_PROJECT_BYTES = 64 * 1024
DEFAULTS = {
    "project": "", "route_location": "", "job_number": "", "prepared_by": "",
    "checked_by": "", "calculation_date": "", "facility": "two_lane_two_way",
    "speed": "60", "adt": "6000", "offset_source": "clearzone", "LA": "30",
    "slope": "6:1_or_flatter", "clear_zone_criteria": "new_construction",
    "clear_zone_selection": "mid", "custom_clear_zone": "",
    "L2": "10", "lane_width": "12", "lanes_this": "2", "lanes_opposing": "2",
    "median_width": "40", "opposing_distance_mode": "manual", "added_distance": "",
    "L1_mode": "standard", "L1": str(DEFAULT_L1_FT),
    "terminal_mode": "default", "terminal": str(DEFAULT_TERMINAL_SECTION_FT),
    "flare_rate": "30", "pdf_style": "3", "include_appendices": "yes",
}
LIMITATIONS = (
    f"Preserves Guardrail {APP_VERSION} behavior; regression parity is not independent engineering approval. "
    "The clear-zone tables, ADT boundaries, terminal contributions, minimum rail lengths, "
    "and opposing-hazard interpretation require project-specific verification against governing MDOT criteria. "
    "DXF and LandXML overlays are available only in the separate Windows application."
)


def application_manifest():
    return {"name": "Guardrail Length-of-Need Calculator", "calculation_engine_version": APP_VERSION,
            "source_commit": SOURCE["commit"], "defaults": DEFAULTS.copy(),
            "speeds": SUPPORTED_SPEEDS, "flare_rates": SUPPORTED_FLARE_RATES,
            "references": DESIGN_REFERENCES, "limitations": LIMITATIONS}


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return value


def _values(raw):
    values = _object(raw, "Inputs")
    if set(values) != set(DEFAULTS):
        raise ValueError("Project inputs are incomplete or contain unsupported fields.")
    for name, value in values.items():
        if not isinstance(value, str) or len(value) > 1000:
            raise ValueError(f"{name} must be text of at most 1,000 characters.")
    for name, choices in {
        "facility": ("two_lane_two_way", "divided_highway"),
        "offset_source": ("direct", "clearzone"), "slope": tuple(item.value for item in SideSlope),
        "clear_zone_criteria": tuple(item.value for item in ClearZoneCriteria),
        "clear_zone_selection": tuple(item.value for item in ClearZoneSelection),
        "opposing_distance_mode": ("manual", "calculated"), "L1_mode": ("standard", "custom"),
        "terminal_mode": ("default", "custom"), "pdf_style": ("1", "2", "3"),
        "include_appendices": ("yes", "no"),
    }.items():
        if values[name] not in choices:
            raise ValueError(f"Unsupported {name} selection.")
    if values["calculation_date"]:
        try:
            if date.fromisoformat(values["calculation_date"]).isoformat() != values["calculation_date"]:
                raise ValueError("Use the date input's YYYY-MM-DD format.")
        except ValueError:
            raise ValueError("Calculation date must be a valid YYYY-MM-DD date.") from None
    return values.copy()


def snapshot(values):
    def number(name):
        try:
            return parse_number(values[name])
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from None
    speed = number("speed")
    if speed not in SUPPORTED_SPEEDS:
        raise ValueError("Design speed must match a Table 9-6-A speed.")
    flare = number("flare_rate")
    if flare not in SUPPORTED_FLARE_RATES:
        raise ValueError("Select a supported flare rate or non-flared.")
    adt = number("adt")
    source = HazardOffsetSource(values["offset_source"])
    clearzone = source == HazardOffsetSource.CLEAR_ZONE
    LA = (resolve_clear_zone(speed, adt, values["slope"], values["clear_zone_selection"],
                            number("custom_clear_zone") if values["clear_zone_selection"] == "custom" else None,
                            criteria=values["clear_zone_criteria"])
          if clearzone else number("LA"))
    divided = values["facility"] == "divided_highway"
    road = create_roadway(
        values["facility"], number("L2"), number("lane_width"),
        lane_count(number("lanes_this"), "lanes_this") if divided else 1,
        lane_count(number("lanes_opposing"), "lanes_opposing") if divided else 1,
        number("median_width") if divided else 0,
        number("added_distance") if divided and values["opposing_distance_mode"] == "manual" else None,
    )
    barrier = HazardBarrierInputs(
        LA, DEFAULT_L1_FT if values["L1_mode"] == "standard" else number("L1"),
        DEFAULT_TERMINAL_SECTION_FT if values["terminal_mode"] == "default" else number("terminal"),
        flare, source, SideSlope(values["slope"]) if clearzone else None,
        ClearZoneSelection(values["clear_zone_selection"]) if clearzone else None,
        clear_zone_criteria=ClearZoneCriteria(values["clear_zone_criteria"]),
    )
    project = ProjectMetadata(**{name: values[name].strip() for name in asdict(ProjectMetadata())})
    if not project.calculation_date:
        project = ProjectMetadata(**{**asdict(project), "calculation_date": date.today().isoformat()})
    return create_snapshot(project, CalculationInputs(int(speed), adt, road, barrier))


def calculate(values):
    accepted = snapshot(values)
    return {"results": accepted.result.as_dict(), "roadway": accepted.inputs.roadway.as_dict(),
            "LA": accepted.inputs.barrier.LA, "L1": accepted.inputs.barrier.L1,
            "terminal": accepted.inputs.barrier.terminal, "engine_version": APP_VERSION,
            "source_commit": SOURCE["commit"], "limitations": LIMITATIONS}


def dispatch(operation, payload_json="{}"):
    payload = _object(json.loads(payload_json), "Request")
    if operation == "manifest":
        return application_manifest()
    if operation == "project_load":
        content = payload.get("content")
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_PROJECT_BYTES:
            raise ValueError("Choose a Guardrail JSON project smaller than 64 KiB.")
        project = _object(json.loads(content), "Project")
        if (project.get("format") != "vericivil.guardrail" or type(project.get("version")) is not int
                or project["version"] != 1):
            raise ValueError("Unsupported Guardrail project format or version.")
        stored_values = _object(project.get("values"), "Inputs").copy()
        # Projects saved before V9 used only the new-construction table.
        stored_values.setdefault("clear_zone_criteria", "new_construction")
        values = _values(stored_values)
        result = calculate(values)
        return {"values": values, "calculation": result,
                "engine_changed": project.get("source_commit") != SOURCE["commit"]}
    values = _values(payload.get("values"))
    if operation == "calculate":
        return calculate(values)
    if operation == "project_save":
        snapshot(values)
        return {"filename": "guardrail-project.json", "mime": "application/json",
                "content": json.dumps({"format": "vericivil.guardrail", "version": 1,
                                       "engine_version": APP_VERSION, "source_commit": SOURCE["commit"],
                                       "values": values}, indent=2, allow_nan=False)}
    if operation == "export_pdf":
        from guardrail_pdf_files import appendix_manifest, write_report
        from guardrail_report import report_payload

        report = ReportModel(snapshot(values), ReportStyle(int(values["pdf_style"])),
                             datetime.now().strftime("%Y-%m-%d %H:%M"))
        include = values["include_appendices"] == "yes"
        if include and any(not Path(path).is_file() for _, _, path in appendix_manifest(report_payload(report))):
            raise ValueError("A bundled MDOT reference is missing. Reload the calculator and try again.")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "guardrail-calculations.pdf"
            complete = write_report(str(path), report, auto_open=False, include_appendix=include)
            if include and not complete:
                raise ValueError("The PDF references could not be included. Try downloading again.")
            return {"filename": path.name, "mime": "application/pdf", "content": path.read_bytes()}
    raise ValueError(f"Unsupported Guardrail operation: {operation}")


def dispatch_safe(operation, payload_json="{}"):
    try:
        return {"ok": True, "result": dispatch(operation, payload_json)}
    except Exception as exc:
        return {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc) or "Operation failed."}}
