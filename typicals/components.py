"""Editable component library. Defaults are generic geometry, never agency designs."""

from copy import deepcopy


def field(label, default, minimum, maximum):
    return {"label": label, "default": default, "minimum": minimum, "maximum": maximum}


WIDTH = field("Width (ft)", 12, .01, 200)
SLOPE = field("Cross slope (%; positive rises outward)", -2, -100, 100)
LIBRARY = {
    "lane": {"label": "Travel lane", "paved": True, "fields": {"width_ft": WIDTH, "slope_pct": SLOPE}},
    "auxiliary_lane": {"label": "Auxiliary lane", "paved": True, "fields": {"width_ft": WIDTH, "slope_pct": SLOPE}},
    "shoulder": {"label": "Shoulder", "paved": True, "fields": {"width_ft": field("Width (ft)", 6, .01, 200), "slope_pct": field("Cross slope (%)", -4, -100, 100)}},
    "median": {"label": "Median", "paved": False, "fields": {"width_ft": field("Width (ft)", 8, .01, 200), "slope_pct": field("Cross slope (%)", 0, -100, 100)}},
    "sidewalk": {"label": "Sidewalk", "paved": True, "fields": {"width_ft": field("Width (ft)", 5, .01, 200), "slope_pct": SLOPE}},
    "curb_gutter": {"label": "Curb and gutter", "fields": {
        "gutter_width_ft": field("Gutter width (ft)", 2, .01, 20), "gutter_slope_pct": SLOPE,
        "curb_width_ft": field("Curb top width (ft)", .5, .01, 10), "curb_height_in": field("Curb rise (in)", 6, .01, 48)}},
    "ditch": {"label": "Ditch", "fields": {
        "depth_ft": field("Foreslope drop (ft)", 2, .01, 100), "foreslope_hv": field("Foreslope H:1V", 3, .1, 100),
        "bottom_width_ft": field("Bottom width (ft; 0 for V ditch)", 2, 0, 200),
        "backslope_hv": field("Backslope H:1V", 3, .1, 100), "back_rise_ft": field("Backslope rise (ft)", 2, 0, 100)}},
    "slope": {"label": "Side slope", "fields": {"hv": field("Side slope H:1V", 3, .1, 100), "rise_ft": field("Rise (ft; negative for fill)", -3, -100, 100)}},
    "barrier": {"label": "Barrier", "fields": {"width_ft": field("Footprint width (ft)", 2, .01, 20),
        "height_ft": field("Height (ft)", 3.5, .01, 30), "top_width_ft": field("Top width (ft)", .75, .01, 20)}},
    "guardrail": {"label": "Guardrail (schematic)", "fields": {"width_ft": field("Footprint width (ft)", 2, .01, 20),
        "height_ft": field("Top height (ft)", 2.5, .01, 30), "rail_depth_ft": field("Rail depth (ft)", .5, .01, 5),
        "post_width_ft": field("Post width (ft)", .25, .01, 5)}},
    "retaining_wall": {"label": "Retaining wall", "fields": {"width_ft": field("Wall thickness (ft)", 1, .01, 30),
        "height_ft": field("Grade step (ft; signed)", 4, -100, 100)}},
    "custom": {"label": "Custom point profile", "paved": False, "fields": {}},
}
PLANAR = {"lane", "auxiliary_lane", "shoulder", "median", "sidewalk"}


def template(kind, identifier):
    definition = LIBRARY[kind]
    value = {"id": identifier, "end_point": identifier, "name": definition["label"], "kind": kind,
             "paved": definition.get("paved", False),
             "params": {key: item["default"] for key, item in definition["fields"].items()}}
    if kind == "custom":
        value["points"] = [[0, 0], [4, -.08]]
    return value


def library():
    return [{"kind": kind, **deepcopy(definition), "template": template(kind, kind)} for kind, definition in LIBRARY.items()]


def role(component, side):
    kind = component["kind"]
    if kind in {"lane", "auxiliary_lane", "shoulder"}:
        return "surface"
    return f"{side}_slope" if kind == "slope" else kind


def profile(component, start, sign, inch_to_ft):
    """Return connected end point and native polyline paths, with no display scaling."""
    kind, v = component["kind"], component["params"]
    if kind in PLANAR:
        local = [[0, 0], [v["width_ft"], v["width_ft"] * v["slope_pct"] / 100]]
    elif kind == "slope":
        local = [[0, 0], [abs(v["rise_ft"]) * v["hv"], v["rise_ft"]]]
    elif kind == "ditch":
        fore = v["depth_ft"] * v["foreslope_hv"]
        flat = fore + v["bottom_width_ft"]
        local = [[0, 0], [fore, -v["depth_ft"]], [flat, -v["depth_ft"]],
                 [flat + v["back_rise_ft"] * v["backslope_hv"], -v["depth_ft"] + v["back_rise_ft"]]]
    elif kind == "curb_gutter":
        width = v["gutter_width_ft"]
        gutter_y = width * v["gutter_slope_pct"] / 100
        local = [[0, 0], [width, gutter_y], [width, gutter_y + v["curb_height_in"] * inch_to_ft],
                 [width + v["curb_width_ft"], gutter_y + v["curb_height_in"] * inch_to_ft]]
    elif kind == "barrier":
        inset = (v["width_ft"] - v["top_width_ft"]) / 2
        local = [[0, 0], [inset, v["height_ft"]], [v["width_ft"] - inset, v["height_ft"]], [v["width_ft"], 0]]
    elif kind == "retaining_wall":
        local = [[0, 0], [v["width_ft"], 0], [v["width_ft"], v["height_ft"]], [0, v["height_ft"]], [0, 0]]
    elif kind == "guardrail":
        mid = v["width_ft"] / 2
        half = v["post_width_ft"] / 2
        post = [[mid - half, 0], [mid - half, v["height_ft"]], [mid + half, v["height_ft"]], [mid + half, 0]]
        local = [[0, v["height_ft"] - v["rail_depth_ft"]], [v["width_ft"], v["height_ft"] - v["rail_depth_ft"]],
                 [v["width_ft"], v["height_ft"]], [0, v["height_ft"]], [0, v["height_ft"] - v["rail_depth_ft"]]]
    else:
        local = component["points"]
    def world(points):
        return [[start[0] + sign * x, start[1] + y] for x, y in points]
    paths = [world(local)]
    if kind == "barrier":
        paths[0].append(list(start))
    if kind == "guardrail":
        paths.append(world(post))
    if kind in {"barrier", "guardrail"}:
        end = world([[v["width_ft"], 0]])[0]
    elif kind == "retaining_wall":
        end = world([[v["width_ft"], v["height_ft"]]])[0]
    else:
        end = paths[0][-1]
    return end, paths
