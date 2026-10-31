"""Read-only reports; indexed Bentley colors/weights are never guessed as RGB/mm."""

import csv
import hashlib
import io
import json
import re

from typicals.model import ROLES, number, text

WEIGHTS = {0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211}


def validate_catalog(catalog):
    if not isinstance(catalog, dict) or catalog.get("version") != 1 or catalog.get("format") != "vericivil.typicals.levels":
        raise ValueError("Expected a version 1 VeriCivil Typicals level catalog.")
    for key in ("source", "revision", "extraction_status"):
        if not text(catalog.get(key), f"Catalog {key}", 240):
            raise ValueError(f"Catalog {key} is required.")
    levels = catalog.get("levels")
    if not isinstance(levels, list) or not 1 <= len(levels) <= 2000:
        raise ValueError("Catalog needs 1 to 2000 TS_ levels.")
    seen = set()
    for level in levels:
        name = text(level.get("name"), "Level name", 120)
        if not re.fullmatch(r"TS_[A-Za-z0-9_$-]+", name) or name in seen:
            raise ValueError(f"Invalid or duplicate TS_ level: {name}.")
        seen.add(name)
        text(level.get("description", ""), "Level description")
        if level.get("rgb") is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(level["rgb"])):
            raise ValueError(f"{name}: RGB must be #RRGGBB, resolved using the source DGN color table.")
        if level.get("lineweight_mm") is not None:
            weight = number(level["lineweight_mm"], "DXF line weight", 0, 2.11)
            if round(weight * 100, 6) not in WEIGHTS:
                raise ValueError(f"{name}: lineweight_mm is not a supported DXF weight; supply an explicit approved mapping.")
        for key in ("bylevel_color", "bylevel_weight", "bylevel_style"):
            if level.get(key) is not None:
                text(str(level[key]), key, 120)
        style = level.get("dash_ft")
        if style is not None:
            if not isinstance(style, list) or len(style) > 16 or (style and (len(style) % 2 or not any(v > 0 for v in style))):
                raise ValueError("dash_ft must be an even draw/gap sequence or [] for continuous.")
            for i, v in enumerate(style):
                number(v, "Dash length in selected feet", -100, 100)
                if v == 0 or (v > 0) != (i % 2 == 0):
                    raise ValueError("dash_ft must alternate positive draws and negative gaps.")
        if type(level.get("plot", True)) is not bool:
            raise ValueError("Plot must be boolean.")
    return catalog


def import_report(content, source, revision):
    if not isinstance(content, str) or len(content.encode("utf-8")) > 4 * 1024 * 1024:
        raise ValueError("Level report must be UTF-8 CSV/JSON under 4 MiB.")
    content = content.lstrip("\ufeff")
    if content.lstrip().startswith("{"):
        return validate_catalog(json.loads(content))
    rows = csv.DictReader(io.StringIO(content))
    levels = []
    for raw in rows:
        row = {re.sub(r"[^a-z0-9]", "", str(k).lower()): v for k, v in raw.items() if k is not None}
        name = row.get("name", row.get("level", "")).strip()
        if not name.startswith("TS_"):
            continue
        def optional(key, transform=str):
            value = row.get(key, "").strip()
            return transform(value) if value else None
        levels.append({"name": name, "description": row.get("description", ""),
                       "bylevel_color": optional("bylevelcolor"), "bylevel_weight": optional("bylevelweight"),
                       "bylevel_style": optional("bylevelstyle"), "rgb": optional("rgb"),
                       "lineweight_mm": optional("lineweightmm", float),
                       "dash_ft": optional("dashft", json.loads),
                       "plot": row.get("plot", "1").strip().lower() not in ("0", "false", "no")})
    return validate_catalog({"format": "vericivil.typicals.levels", "version": 1, "source": source,
                             "revision": revision, "extraction_status": "report-imported",
                             "report_sha256": hashlib.sha256(content.encode()).hexdigest(), "levels": levels})


def mapping_issues(project):
    catalog = project.get("catalog")
    levels = {v["name"]: v for v in catalog["levels"]} if catalog else {}
    issues = []
    if not catalog or catalog["extraction_status"] != "report-imported":
        issues.append("Import a Bentley-generated report with resolved symbology; binary workspace extraction is unverified.")
    for role in ROLES:
        name = project["level_mappings"].get(role)
        level = levels.get(name)
        if not level:
            issues.append(f"{role}: select an imported TS_ level (currently {name or 'unmapped'}).")
        elif any(level.get(k) is None for k in ("rgb", "lineweight_mm", "dash_ft", "bylevel_color", "bylevel_weight", "bylevel_style")):
            issues.append(f"{name}: unresolved ByLevel color/weight/style or RGB/mm/dash mapping. See level-report procedure.")
    return list(dict.fromkeys(issues))
