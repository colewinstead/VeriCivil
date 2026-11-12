"""Authoritative calculator catalog and browser-runtime bundle definitions."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from app_info import CALCULATION_ENGINE_VERSION
from calculators.crushed_stone_base.engine import ENGINE_VERSION as STONE_ENGINE_VERSION


_SUPER_MODULES = [
    "vericivil_service.py",
    "Super.py",
    "app_info.py",
    "commercial_entitlements.py",
    "criteria_info.py",
    "tdot_criteria.py",
    "aashto_criteria.py",
    "aashto_tables.py",
    "aashto_superelevation.py",
    "aashto_divided.py",
    "super_spiral.py",
    "super_batch.py",
    "super_dxf.py",
    "super_exports.py",
    "super_landxml.py",
    "super_lane.py",
    "super_cross_section.py",
    "super_pdf.py",
    "super_project.py",
    "super_qa.py",
    "super_service.py",
    "super_transition.py",
    "super_ui.py",
]

_STONE_MODULES = [
    "vericivil_service.py",
    "calculators/__init__.py",
    "calculators/crushed_stone_base/__init__.py",
    "calculators/crushed_stone_base/engine.py",
    "calculators/crushed_stone_base/service.py",
]

_GUARDRAIL_ROOT = "calculators/guardrail/upstream/"
_GUARDRAIL_SOURCE = json.loads((Path(__file__).parent / "guardrail/upstream/source.json").read_text())
_GUARDRAIL_MODULES = [
    "vericivil_service.py", "calculators/__init__.py", "calculators/guardrail/__init__.py",
    "calculators/guardrail/service.py", _GUARDRAIL_ROOT + "source.json",
    *[_GUARDRAIL_ROOT + name for name in _GUARDRAIL_SOURCE["sha256"] if name.endswith(".py")],
]


CALCULATORS: tuple[dict[str, Any], ...] = (
    {
        "id": "superelevation",
        "slug": "superelevation",
        "title": "Superelevation Calculator",
        "short_title": "Superelevation",
        "description": "Calculate roadway superelevation transitions, review lane slopes, and create traceable engineering exports.",
        "category": "Roadway Geometry",
        "status": "available",
        "access": "Free + Pro",
        "engine_version": CALCULATION_ENGINE_VERSION,
        "route": "/calculators/superelevation",
        "runtime": {
            "modules": _SUPER_MODULES,
            "pyodide_packages": ["micropip", "pyproj", "numpy", "fonttools", "Pillow"],
            "micropip_packages": ["reportlab==4.4.7", "ezdxf==1.4.4"],
        },
    },
    {
        "id": "crushed_stone_base",
        "slug": "crushed-stone-base",
        "title": "Crushed Stone Base Tonnage Calculator",
        "short_title": "Crushed Stone Base",
        "description": "Estimate compacted roadway base volume and order tonnage across multiple construction segments.",
        "category": "Construction Quantities",
        "status": "available",
        "access": "Free",
        "engine_version": STONE_ENGINE_VERSION,
        "route": "/calculators/crushed-stone-base",
        "runtime": {
            "modules": _STONE_MODULES,
            "pyodide_packages": [],
            "micropip_packages": [],
        },
    },
    {
        "id": "guardrail", "slug": "guardrail", "title": "Guardrail Length-of-Need Calculator",
        "short_title": "Guardrail", "description": "Calculate near-side and opposing-side guardrail lengths, save a project, and download a calculation-sheet PDF with optional MDOT references.",
        "category": "Roadside Design", "status": "available", "access": "Free",
        "engine_version": _GUARDRAIL_SOURCE["version"], "route": "/calculators/guardrail",
        "runtime": {
            "modules": _GUARDRAIL_MODULES,
            "assets": [_GUARDRAIL_ROOT + name for name in _GUARDRAIL_SOURCE["sha256"] if name.endswith(".pdf")],
            "pyodide_packages": ["micropip", "Pillow", "fonttools", "matplotlib"],
            "micropip_packages": ["reportlab==4.4.7", "pypdf==5.9.0"],
        },
    },
)


def calculator_catalog() -> list[dict[str, Any]]:
    """Return public, presentation-safe calculator metadata."""
    return [{key: deepcopy(value) for key, value in item.items() if key != "runtime"} for item in CALCULATORS]


def browser_runtime_manifest() -> dict[str, Any]:
    """Return explicit browser bundles keyed by calculator identifier."""
    return {
        "calculators": {
            item["id"]: deepcopy(item["runtime"])
            for item in CALCULATORS
        }
    }
