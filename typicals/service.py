"""Shared native/Pyodide operations; file bytes follow the existing base64 convention."""

import base64
import json
from typicals import ENGINE_VERSION
from typicals import model, exports
from typicals.drawing import drawing
from typicals.workspace import import_report
from typicals.components import library


def application_manifest():
    return {"engine_version": ENGINE_VERSION, "name": "VeriCivil Typicals"}


def dispatch(operation, payload_json="{}"):
    payload = json.loads(payload_json)
    if operation == "starter":
        return model.starter()
    if operation == "component_library":
        return library()
    if operation in ("component_save", "component_load"):
        if operation == "component_load":
            content = payload["content"]
            if not isinstance(content, str) or len(content.encode("utf-8")) > 256 * 1024:
                raise ValueError("Component presets must be UTF-8 JSON under 256 KiB.")
            preset = json.loads(content)
            if not isinstance(preset, dict) or preset.get("format") != "vericivil.typicals.component" or type(preset.get("version")) is not int or preset.get("version") != 1:
                raise ValueError("Select a version 1 VeriCivil Typicals component preset.")
            component = preset["component"]
        else:
            component = payload["component"]
        project = model.starter()
        project["left"], project["right"] = [component], []
        model.solve(project)
        if operation == "component_load":
            return component
        return {"content": json.dumps({"format": "vericivil.typicals.component", "version": 1, "component": component}, indent=2, allow_nan=False) + "\n"}
    if operation == "load":
        return model.loads(payload["content"])
    if operation == "import_levels":
        return import_report(payload["content"], payload["source"], payload["revision"])
    if operation == "draw":
        return drawing(payload["project"])
    if operation == "save":
        return {"content": model.dumps(payload["project"])}
    if operation in ("pdf", "svg", "dxf"):
        output = getattr(exports, operation)(payload["project"])
        data, report = output if operation == "dxf" else (output, None)
        return {"content_base64": base64.b64encode(data).decode(), "report": report}
    raise ValueError(f"Unsupported Typicals operation: {operation}")


def dispatch_safe(operation, payload_json="{}"):
    try:
        return {"ok": True, "result": dispatch(operation, payload_json)}
    except Exception as exc:
        return {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}
