from __future__ import annotations

import json
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from app_info import APP_VERSION, CALCULATION_ENGINE_VERSION
from criteria_info import criteria_metadata


PROJECT_VERSION = 5


class ProjectFormatError(ValueError):
    """Raised when a project cannot be safely interpreted by this release."""


def calculation_provenance(curves: list[dict], last_results: dict | None = None) -> tuple[str, dict]:
    """Summarize the engines/criteria represented by saved calculation results."""
    results_list = [curve.get("results") for curve in curves if isinstance(curve, dict) and curve.get("results")]
    if not results_list and last_results:
        results_list = [last_results]
    if not results_list:
        return CALCULATION_ENGINE_VERSION, criteria_metadata()

    engines: set[str] = set()
    criteria_by_profile: dict[str, dict] = {}
    for results in results_list:
        metadata = results.get("calculation_metadata", {}) if isinstance(results, dict) else {}
        engine = str(metadata.get("engine_version") or "legacy-unversioned")
        criteria = metadata.get("criteria") if isinstance(metadata.get("criteria"), dict) else {}
        profile_id = str(criteria.get("profile_id") or "legacy-unversioned")
        engines.add(engine)
        criteria_by_profile.setdefault(
            profile_id,
            criteria or {"profile_id": profile_id, "source_status": "unknown"},
        )
    engine_summary = next(iter(engines)) if len(engines) == 1 else "mixed"
    if len(criteria_by_profile) == 1:
        criteria_summary = next(iter(criteria_by_profile.values()))
    else:
        criteria_summary = {
            "profile_id": "mixed",
            "profiles": sorted(criteria_by_profile),
            "source_status": "REVIEW REQUIRED: project contains calculations from multiple criteria profiles",
        }
    return engine_summary, criteria_summary


def curve_label(meta: dict, results: dict | None) -> str:
    alignment = meta.get("alignment_name", "Unnamed alignment")
    curve = meta.get("curve_name", "Unnamed curve")
    direction = meta.get("curve_direction", "left")
    inputs = (results or {}).get("inputs", {})
    pc = inputs.get("pc", "?")
    pt = inputs.get("pt", "?") or "n/a"
    speed = inputs.get("speed_mph", "?")
    radius = inputs.get("radius_ft", "?")
    if isinstance(speed, (int, float)) and float(speed).is_integer():
        speed = str(int(speed))
    if isinstance(radius, (int, float)) and float(radius).is_integer():
        radius = str(int(radius))
    return f"{alignment} | {curve} | {direction} | PC {pc} PT {pt} | V {speed} mph | R {radius} ft"


def normalize_project(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ProjectFormatError("Project root must be a JSON object.")
    try:
        version = int(data.get("version", 1) or 1)
    except (TypeError, ValueError) as exc:
        raise ProjectFormatError("Project schema version must be an integer.") from exc
    if version < 1:
        raise ProjectFormatError(f"Project schema version {version} is invalid.")
    if version > PROJECT_VERSION:
        raise ProjectFormatError(
            f"This project uses schema version {version}, but this application supports up to version "
            f"{PROJECT_VERSION}. Install a newer application release to open it safely."
        )

    vars_data = dict(data.get("vars", {})) if isinstance(data.get("vars", {}), dict) else {}
    vars_data.pop("coordinate_reverse_curves", None)
    curves = []
    raw_curves = data.get("curves", []) or []
    if not isinstance(raw_curves, list):
        raise ProjectFormatError("Project 'curves' must be a list.")
    for curve in raw_curves:
        if not isinstance(curve, dict):
            continue
        curves.append(
            {
                "results": curve.get("results"),
                "meta": curve.get("meta", {}) or {},
                "notes": curve.get("notes", ""),
            }
        )

    legacy = version < PROJECT_VERSION
    landxml_source = normalize_landxml_source(data.get("landxml_source"))
    raw_excluded = data.get("excluded_landxml_curve_indexes", []) or []
    if not isinstance(raw_excluded, list):
        raise ProjectFormatError("Project 'excluded_landxml_curve_indexes' must be a list.")
    excluded_curve_indexes: set[int] = set()
    for index in raw_excluded:
        try:
            normalized_index = int(index)
        except (TypeError, ValueError) as exc:
            raise ProjectFormatError("Excluded LandXML curve indexes must be integers.") from exc
        if normalized_index >= 0:
            excluded_curve_indexes.add(normalized_index)

    migration_warnings: list[str] = []
    raw_pairs = data.get("reverse_curve_pairs")
    if raw_pairs is None and version < 5:
        inferred: set[tuple[int, int]] = set()
        for curve in curves:
            coordination = ((curve.get("results") or {}).get("reverse_curve_coordination") or {})
            for check in coordination.get("checks", []) or []:
                indexes = check.get("paired_curve_indexes")
                if isinstance(indexes, list) and len(indexes) == 2:
                    try:
                        inferred.add((int(indexes[0]), int(indexes[1])))
                    except (TypeError, ValueError):
                        continue
        raw_pairs = [list(pair) for pair in sorted(inferred)]
    if raw_pairs is None:
        raw_pairs = []
    if not isinstance(raw_pairs, list):
        raise ProjectFormatError("Project 'reverse_curve_pairs' must be a list.")
    reverse_curve_pairs: list[list[int]] = []
    paired_indexes: set[int] = set()
    for raw_pair in raw_pairs:
        if not isinstance(raw_pair, (list, tuple)) or len(raw_pair) != 2:
            raise ProjectFormatError("Each reverse-curve pair must contain exactly two curve indexes.")
        try:
            prior_index, following_index = int(raw_pair[0]), int(raw_pair[1])
        except (TypeError, ValueError) as exc:
            raise ProjectFormatError("Reverse-curve pair indexes must be integers.") from exc
        if prior_index < 0 or following_index >= len(curves):
            raise ProjectFormatError("Reverse-curve pair indexes are outside the calculated curve set.")
        if following_index != prior_index + 1:
            raise ProjectFormatError("Reverse-curve pairs must contain adjacent curves in increasing order.")
        if prior_index in paired_indexes or following_index in paired_indexes:
            if version < 5:
                migration_warnings.append(
                    f"Legacy reverse-curve link {prior_index + 1}-{following_index + 1} was not restored "
                    "because one curve already belongs to another pair."
                )
                continue
            raise ProjectFormatError("A curve cannot belong to more than one reverse-curve pair.")
        paired_indexes.update((prior_index, following_index))
        reverse_curve_pairs.append([prior_index, following_index])
    return {
        "version": PROJECT_VERSION,
        "source_version": version,
        "application_version": data.get("application_version") or ("legacy-unversioned" if legacy else APP_VERSION),
        "calculation_engine_version": data.get("calculation_engine_version")
        or ("legacy-unversioned" if legacy else CALCULATION_ENGINE_VERSION),
        "criteria": data.get("criteria") or ({"profile_id": "legacy-unversioned", "source_status": "unknown"} if legacy else criteria_metadata()),
        "vars": vars_data,
        "curves": curves,
        "last_results": data.get("last_results"),
        "last_meta": data.get("last_meta", {}) or {},
        "project_notes": data.get("project_notes", ""),
        "landxml_source": landxml_source,
        "excluded_landxml_curve_indexes": sorted(excluded_curve_indexes),
        "reverse_curve_pairs": reverse_curve_pairs,
        "migration_warnings": migration_warnings,
    }


def make_landxml_source(filename: str, content: str, alignment_index: int = 0) -> dict[str, Any]:
    """Create the portable, integrity-checked LandXML record introduced in schema v4."""
    if not isinstance(content, str) or not content.strip():
        raise ProjectFormatError("Embedded LandXML content must be non-empty text.")
    if type(alignment_index) is not int or alignment_index < 0:
        raise ProjectFormatError("LandXML alignment index must be a nonnegative integer.")
    safe_name = Path(str(filename or "alignment.xml")).name or "alignment.xml"
    return {
        "filename": safe_name,
        "encoding": "utf-8",
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
        "alignment_index": alignment_index,
    }


def normalize_landxml_source(value: object) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise ProjectFormatError("Project 'landxml_source' must be an object or null.")
    encoding = str(value.get("encoding") or "utf-8").lower()
    if encoding != "utf-8":
        raise ProjectFormatError("Embedded LandXML must use UTF-8 encoding.")
    source = make_landxml_source(str(value.get("filename") or "alignment.xml"), value.get("content"),
                                 value.get("alignment_index", 0))
    supplied_hash = str(value.get("sha256") or "").lower()
    if supplied_hash and supplied_hash != source["sha256"]:
        raise ProjectFormatError("Embedded LandXML failed its SHA-256 integrity check.")
    return source


def loads_project(content: str) -> dict[str, Any]:
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProjectFormatError(
            f"The project is not valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc
    return normalize_project(raw)


def dumps_project(data: dict[str, Any]) -> str:
    payload = normalize_project(data)
    payload["source_version"] = PROJECT_VERSION
    return json.dumps(payload, indent=2) + "\n"


def load_project(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        return loads_project(handle.read())


def save_project(path: str | Path, data: dict[str, Any]) -> None:
    file_path = Path(path)
    serialized = dumps_project(data)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=file_path.parent, prefix=f".{file_path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temp_name = handle.name
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, file_path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
