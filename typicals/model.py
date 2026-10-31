"""Deterministic outward dependency chains. All coordinates are section-local feet."""

from copy import deepcopy
import json
import math

from typicals import ENGINE_VERSION

ROLES = ("surface", "pavement", "left_slope", "right_slope", "ground", "centerline",
         "dimensions", "dimension_text", "slopes", "callouts", "text")
FOOT_METRES = {"international_foot": 0.3048, "us_survey_foot": 1200 / 3937}


def starter():
    return {
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
    }


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
    if not isinstance(project, dict) or project.get("format") != "vericivil.typicals" or project.get("version") != 1:
        raise ValueError("Select a VeriCivil Typicals version 1 project.")
    p = deepcopy(project)
    if p.get("units") not in FOOT_METRES:
        raise ValueError("Choose international_foot or us_survey_foot explicitly.")
    point(p["origin"], "Origin")
    for side in ("left", "right"):
        s = p[side]
        for key in ("lane_width_ft", "shoulder_width_ft"):
            number(s[key], f"{side} {key}", 0.01, 100)
        for key in ("lane_slope_pct", "shoulder_slope_pct"):
            number(s[key], f"{side} {key}", -100, 100)
        number(s["roadside_hv"], f"{side} H:V", 0.1, 100)
        number(s["roadside_height_ft"], f"{side} roadside rise", -100, 100)
        if not isinstance(s["shoulder_paved"], bool):
            raise ValueError("Shoulder paved must be true or false.")
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
    if not isinstance(weights, dict) or any(role not in ROLES for role in weights):
        raise ValueError("Unknown print lineweight role.")
    for value in weights.values():
        number(value, "Print lineweight (mm)", 0, 2.11)
    locks = p["constraints"].get("locked_points")
    if set(p["constraints"]) != {"locked_points"} or not isinstance(locks, dict):
        raise ValueError("Only named-point locks are supported in version 1.")
    for name, value in locks.items():
        if name not in {"CL", "left_lane", "left_shoulder", "left_toe", "right_lane", "right_shoulder", "right_toe"}:
            raise ValueError(f"Unknown locked point: {name}.")
        point(value, name)
    if not isinstance(p["annotations"], dict) or len(p["annotations"]) > 200:
        raise ValueError("Annotation overrides must be an object with at most 200 offsets.")
    for key, value in p["annotations"].items():
        text(key, "Annotation ID", 80)
        point(value, "Annotation offset")
    if not isinstance(p["level_mappings"], dict) or any(k not in ROLES for k in p["level_mappings"]):
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
    components = []
    surfaces = {}
    for side, sign in (("left", -1), ("right", 1)):
        s = p[side]
        a = points["CL"]
        surfaces[side] = [a]
        for kind in ("lane", "shoulder"):
            width, slope = s[f"{kind}_width_ft"], s[f"{kind}_slope_pct"]
            b = [a[0] + sign * width, a[1] + width * slope / 100]
            name = f"{side}_{kind}"
            points[name] = b
            components.append({"id": name, "name": name.replace("_", " ").title(), "role": "surface", "a": a, "b": b,
                               "width_ft": width, "slope_pct": slope})
            surfaces[side].append(b)
            a = b
        height = s["roadside_height_ft"]
        b = [a[0] + sign * abs(height) * s["roadside_hv"], a[1] + height]
        points[f"{side}_toe"] = b
        components.append({"id": f"{side}_slope", "name": f"{side.title()} roadside", "role": f"{side}_slope", "a": a, "b": b,
                           "hv": s["roadside_hv"], "rise_ft": height})
    for name, target in p["constraints"]["locked_points"].items():
        if math.dist(points[name], target) > 1e-9:
            raise ValueError(f"Constraint conflict: {name} is locked at {target}; computed {points[name]}. Unlock it or restore its dependent inputs.")
    top = list(reversed(surfaces["left"] if p["left"]["shoulder_paved"] else surfaces["left"][:2]))
    top += (surfaces["right"][1:] if p["right"]["shoulder_paved"] else surfaces["right"][1:2])
    layers = []
    depth = 0.0
    # Inches are international inches even when section coordinates use US survey feet.
    inch_to_ft = 0.0254 / FOOT_METRES[p["units"]]
    for layer in p["layers"]:
        thickness = layer["thickness_in"] * inch_to_ft
        depth += thickness
        bottom = [[x, y - thickness] for x, y in top]
        layers.append({**layer, "top": top, "bottom": bottom, "depth_ft": depth})
        top = bottom
    return {"engine_version": ENGINE_VERSION, "points": points, "components": components, "layers": layers, "ground": p["ground"]}


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
