"""Deterministic outward dependency chains. All coordinates are section-local feet."""

from copy import deepcopy
import json
import math
import re

from typicals import ENGINE_VERSION
from typicals.components import LIBRARY, PLANAR, profile, role, template

ROLES = ("surface", "pavement", "left_slope", "right_slope", "ground", "centerline",
         "dimensions", "dimension_text", "slopes", "callouts", "text", "median", "sidewalk",
         "curb_gutter", "ditch", "barrier", "guardrail", "retaining_wall", "custom")
FOOT_METRES = {"international_foot": 0.3048, "us_survey_foot": 1200 / 3937}


def starter():
    return upgrade({
        "format": "vericivil.typicals", "version": 1, "units": "international_foot",
        "metadata": {"title": "TYPICAL SECTION", "route": "Route / project", "construction": "New construction",
                     "stations": "Station range", "notes": ["Generic rural starter; not an approved MDOT standard."]},
        "origin": [0.0, 0.0],
        "left": {"lane_width_ft": 12.0, "lane_slope_pct": -2.0, "shoulder_width_ft": 6.0,
                 "shoulder_slope_pct": -4.0, "shoulder_paved": True, "roadside_hv": 3.0, "roadside_height_ft": -3.0},
        "right": {"lane_width_ft": 12.0, "lane_slope_pct": -2.0, "shoulder_width_ft": 6.0,
                  "shoulder_slope_pct": -4.0, "shoulder_paved": True, "roadside_hv": 4.0, "roadside_height_ft": -3.0},
        "layers": [{"id": "wearing", "name": "Surface course", "material": "Project-specified asphalt", "thickness_in": 3.0},
                   {"id": "base", "name": "Base course", "material": "Project-specified base", "thickness_in": 8.0}],
        "ground": [[-36.0, -3.8], [-20.0, -3.2], [0.0, -3.0], [20.0, -3.3], [36.0, -4.0]],
        "constraints": {"locked_points": {}},
        "drafting": {"scale_ft_per_in": 5.0, "text_height_in": 0.14, "dimension_gap_in": 0.42,
                     "font": "Helvetica", "precision": 2},
        "print": {"monochrome": True, "width_in": 17.0, "height_in": 11.0},
        "annotations": {}, "presentation": {}, "level_mappings": {}, "catalog": None,
    })


def upgrade(project):
    if not isinstance(project, dict) or project.get("format") != "vericivil.typicals" or type(project.get("version")) is not int or project.get("version") not in (1, 2):
        raise ValueError("Select a VeriCivil Typicals version 1 or 2 project.")
    p = deepcopy(project)
    if p["version"] == 1:
        for side in ("left", "right"):
            old = p[side]
            if not isinstance(old, dict) or set(old) != {"lane_width_ft", "lane_slope_pct", "shoulder_width_ft", "shoulder_slope_pct", "shoulder_paved", "roadside_hv", "roadside_height_ft"}:
                raise ValueError("Version 1 side properties are incomplete or unknown; the original project was not modified.")
            lane = template("lane", f"{side}_lane")
            lane["params"] = {"width_ft": old["lane_width_ft"], "slope_pct": old["lane_slope_pct"]}
            shoulder = template("shoulder", f"{side}_shoulder")
            shoulder["paved"] = old["shoulder_paved"]
            shoulder["params"] = {"width_ft": old["shoulder_width_ft"], "slope_pct": old["shoulder_slope_pct"]}
            slope = template("slope", f"{side}_slope")
            slope["end_point"] = f"{side}_toe"
            slope["params"] = {"hv": old["roadside_hv"], "rise_ft": old["roadside_height_ft"]}
            p[side] = [lane, shoulder, slope]
        p["version"] = 2
    return p


def base_role(project, key):
    if key.startswith("component:"):
        for side in ("left", "right"):
            for component in project[side]:
                if key == "component:" + component["id"]:
                    return role(component, side)
        raise ValueError(f"Level mapping refers to a missing component: {key}.")
    return key


def component_role(project, component, side):
    key = "component:" + component["id"]
    return key if project["level_mappings"].get(key) else role(component, side)


def required_roles(project):
    p = upgrade(project)
    return sorted(set(ROLES[:11]) | {component_role(p, c, side) for side in ("left", "right") for c in p[side]})


def number(value, label, low=-1e6, high=1e6):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be a finite number between {low} and {high}.")
    return float(value)


def text(value, label, limit=240):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} must be text of at most {limit} characters without control characters.")
    return value


def point(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} needs [offset, elevation] in the selected feet.")
    return [number(v, label) for v in value]


def validate(project):
    p = upgrade(project)
    if p.get("units") not in FOOT_METRES:
        raise ValueError("Choose international_foot or us_survey_foot explicitly.")
    point(p["origin"], "Origin")
    identifiers, names = set(), {"CL"}
    for side in ("left", "right"):
        if not isinstance(p[side], list) or len(p[side]) > 60:
            raise ValueError(f"{side.title()} side must contain at most 60 components.")
        for c in p[side]:
            if not isinstance(c, dict):
                raise ValueError("Each roadway component must be an object.")
            identifier = text(c.get("id"), "Component ID", 64)
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", identifier) or identifier in identifiers:
                raise ValueError("Component IDs must be unique letters, digits, hyphens or underscores.")
            identifiers.add(identifier)
            name = text(c.get("end_point"), "End point name", 80)
            if not name or ":" in name or name in names:
                raise ValueError("Named end points must be unique, nonempty, and contain no colon.")
            names.add(name)
            text(c.get("name"), "Component name", 80)
            kind = c.get("kind")
            if kind not in LIBRARY:
                raise ValueError(f"Unsupported component kind: {kind}.")
            fields = LIBRARY[kind]["fields"]
            if not isinstance(c.get("params"), dict) or set(c["params"]) != set(fields):
                raise ValueError(f"{c['name']}: provide exactly the required component parameters.")
            for key, definition in fields.items():
                number(c["params"][key], f"{c['name']} {definition['label']}", definition["minimum"], definition["maximum"])
            if type(c.get("paved")) is not bool or (c["paved"] and kind not in PLANAR | {"custom"}):
                raise ValueError("Pavement structure is supported on lanes, shoulders, medians, sidewalks and custom graded profiles.")
            v = c["params"]
            if kind == "barrier" and v["top_width_ft"] > v["width_ft"]:
                raise ValueError("Barrier top width cannot exceed its footprint width.")
            if kind == "guardrail" and (v["rail_depth_ft"] > v["height_ft"] or v["post_width_ft"] > v["width_ft"]):
                raise ValueError("Guardrail rail depth / post width exceeds its height / footprint.")
            if kind == "custom":
                pts = c.get("points")
                if not isinstance(pts, list) or not 2 <= len(pts) <= 40:
                    raise ValueError("Custom profile needs 2 to 40 [outward offset, elevation] points.")
                pts = [point(value, "Custom point") for value in pts]
                if pts[0] != [0, 0] or pts[-1][0] < 0 or (c["paved"] and any(b[0] <= a[0] for a, b in zip(pts, pts[1:]))):
                    raise ValueError("Custom profile starts at [0,0] and ends at a nonnegative outward offset; paved profiles require strictly increasing offsets.")
    if not isinstance(p["layers"], list) or not 1 <= len(p["layers"]) <= 12:
        raise ValueError("Provide 1 to 12 pavement layers.")
    ids = set()
    for layer in p["layers"]:
        name = text(layer["id"], "Layer ID", 40)
        if not name or name in ids:
            raise ValueError("Pavement layer IDs must be nonempty and unique.")
        ids.add(name)
        text(layer["name"], "Layer name", 80)
        text(layer["material"], "Material", 120)
        number(layer["thickness_in"], "Vertical layer thickness (international inches)", 0.01, 120)
    if not isinstance(p["ground"], list) or not 2 <= len(p["ground"]) <= 200:
        raise ValueError("Ground needs 2 to 200 points in increasing offset order.")
    ground = [point(v, "Ground point") for v in p["ground"]]
    if any(a[0] >= b[0] for a, b in zip(ground, ground[1:])):
        raise ValueError("Ground offsets must be strictly increasing.")
    for key in ("title", "route", "construction", "stations"):
        text(p["metadata"][key], key, 120)
    notes = p["metadata"]["notes"]
    if not isinstance(notes, list) or len(notes) > 12:
        raise ValueError("Provide at most 12 notes.")
    for note in notes:
        text(note, "Note", 120)
    d = p["drafting"]
    number(d["scale_ft_per_in"], "Annotation / sheet scale", 1, 100)
    number(d["text_height_in"], "Paper text height", 0.06, 0.25)
    number(d["dimension_gap_in"], "Paper dimension spacing", 0.25, 1)
    if d["font"] not in ("Helvetica", "Courier", "Times-Roman"):
        raise ValueError("Use Helvetica, Courier, or Times-Roman; proprietary fonts are not bundled.")
    if type(d["precision"]) is not int or not 0 <= d["precision"] <= 4:
        raise ValueError("Label precision must be 0 to 4 decimals.")
    for key in ("width_in", "height_in"):
        number(p["print"][key], "Paper size", 8, 48)
    if type(p["print"]["monochrome"]) is not bool:
        raise ValueError("Monochrome must be true or false.")
    weights = p["print"].get("lineweights_mm", {})
    if not isinstance(weights, dict) or any(key not in ROLES for key in weights):
        raise ValueError("Unknown print lineweight role.")
    for value in weights.values():
        number(value, "Print lineweight (mm)", 0, 2.11)
    locks = p["constraints"].get("locked_points")
    if set(p["constraints"]) != {"locked_points"} or not isinstance(locks, dict):
        raise ValueError("Only named-point locks are supported.")
    if len(locks) > 500:
        raise ValueError("Provide at most 500 named-point locks.")
    for name, value in locks.items():
        text(name, "Locked point name", 100)
        point(value, name)
    if not isinstance(p["annotations"], dict) or len(p["annotations"]) > 200:
        raise ValueError("Annotation overrides must be an object with at most 200 offsets.")
    for key, value in p["annotations"].items():
        text(key, "Annotation ID", 80)
        point(value, "Annotation offset")
    if not isinstance(p["level_mappings"], dict) or any(k not in ROLES and k not in {"component:" + i for i in identifiers} for k in p["level_mappings"]):
        raise ValueError("Unknown geometric level-mapping role.")
    for name in p["level_mappings"].values():
        text(name, "Mapped level", 120)
    if p["catalog"] is not None:
        from typicals.workspace import validate_catalog
        p["catalog"] = validate_catalog(p["catalog"])
    return p


def solve(project):
    p = validate(project)
    points = {"CL": list(p["origin"])}
    components, runs = [], []
    edges = {"platform": {}, "travel": {}, "outer": {}}
    inch_to_ft = 0.0254 / FOOT_METRES[p["units"]]
    for side, sign in (("left", -1), ("right", 1)):
        a = points["CL"]
        current = []
        edges["platform"][side] = edges["travel"][side] = a
        for c in p[side]:
            b, paths = profile(c, a, sign, inch_to_ft)
            points[c["end_point"]] = b
            for j, path in enumerate(paths):
                for k, xy in enumerate(path):
                    points[f"{c['id']}:v{j}_{k}"] = xy
            components.append({**c, "side": side, "role": component_role(p, c, side), "a": a, "b": b, "paths": paths,
                               "width_ft": abs(b[0] - a[0])})
            if c["kind"] in {"lane", "auxiliary_lane"}:
                edges["travel"][side] = b
            if c["kind"] not in {"slope", "ditch", "retaining_wall"}:
                edges["platform"][side] = b
            if c["paved"]:
                current = current + paths[0][1:] if current else paths[0][:]
            elif current:
                runs.append(list(reversed(current)) if sign < 0 else current)
                current = []
            a = b
        if current:
            runs.append(list(reversed(current)) if sign < 0 else current)
        edges["outer"][side] = a
    for name, target in p["constraints"]["locked_points"].items():
        if name not in points:
            raise ValueError(f"Constraint conflict: locked point {name} no longer exists. Unlock it before removing or renaming its component.")
        if math.dist(points[name], target) > 1e-9:
            raise ValueError(f"Constraint conflict: {name} is locked at {target}; computed {points[name]}. Unlock it or restore its dependent inputs.")
    joined = []
    for run in sorted(runs, key=lambda chain: chain[0][0]):
        if joined and math.dist(joined[-1][-1], run[0]) < 1e-9:
            joined[-1].extend(run[1:])
        else:
            joined.append(run)
    runs = joined
    layers = []
    depth = 0.0
    tops = deepcopy(runs)
    for layer in p["layers"]:
        thickness = layer["thickness_in"] * inch_to_ft
        depth += thickness
        bottoms = [[[x, y - thickness] for x, y in top] for top in tops]
        layers.append({**layer, "top": tops[0] if tops else [], "bottom": bottoms[0] if bottoms else [],
                       "runs": [{"top": top, "bottom": bottom} for top, bottom in zip(tops, bottoms)], "depth_ft": depth})
        tops = bottoms
    return {"engine_version": ENGINE_VERSION, "points": points, "components": components, "layers": layers,
            "paved_runs": runs, "edges": edges, "ground": p["ground"]}


def dumps(project):
    p = validate(project)
    solve(p)
    return json.dumps(p, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def loads(content):
    if not isinstance(content, str) or len(content.encode("utf-8")) > 4 * 1024 * 1024:
        raise ValueError("Typicals projects must be UTF-8 JSON under 4 MiB.")
    p = validate(json.loads(content))
    solve(p)
    return p
