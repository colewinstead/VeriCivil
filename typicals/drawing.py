"""DOT-style annotation scene; coordinates remain the analytical model's feet."""

import math
import textwrap
from reportlab.pdfbase.pdfmetrics import stringWidth
from typicals.model import solve
from typicals.workspace import mapping_issues

PREVIEW_COLORS = {"surface": "#68dfc2", "pavement": "#f1b866", "ground": "#9baea0", "centerline": "#ec92cc"}
PRINT_WEIGHTS = {"surface": .5, "pavement": .25, "left_slope": .35, "right_slope": .35,
                 "ground": .18, "centerline": .13, "dimensions": .13, "dimension_text": .13,
                 "slopes": .18, "callouts": .18, "text": .18}


def plot_weight(project, role):
    return project["print"].get("lineweights_mm", {}).get(role, PRINT_WEIGHTS[role])


def drawing(project):
    geometry = solve(project)
    p, d = project, project["drafting"]
    h = d["text_height_in"] * d["scale_ft_per_in"]
    gap = max(d["dimension_gap_in"] * d["scale_ft_per_in"], 3 * h)
    primitives, dimensions, boxes = [], [], []
    width_factor = .78

    def line(a, b, role, component="", dimension=False):
        primitives.append({"kind": "line", "a": list(a), "b": list(b), "role": role, "component": component, "dimension": dimension})

    def label(key, xy, value, role="text", size=1, align="left", rotation=0, avoid=False, dimension=False):
        offset = p["annotations"].get(key, [0, 0])
        x, y = xy[0] + offset[0], xy[1] + offset[1]
        height = h * size
        width = stringWidth(value, d["font"], height) * width_factor
        x -= width / 2 if align == "center" else width if align == "right" else 0
        if avoid and key not in p["annotations"] and rotation == 0:
            for _ in range(100):
                box = [x - .2 * h, y - height * .3, x + width + .2 * h, y + height]
                if not any(box[0] < b[2] and box[2] > b[0] and box[1] < b[3] and box[3] > b[1] for b in boxes):
                    break
                y += height * 1.5
        boxes.append([x, y - height * .3, x + width, y + height])
        primitives.append({"kind": "text", "a": [x, y], "text": value, "height": height, "text_width": width,
                           "width_factor": width_factor, "rotation": rotation, "role": role,
                           "component": key, "dimension": dimension})

    def arrow(tip, direction, role, component="", dimension=False):
        length = math.hypot(*direction)
        if not length:
            return
        ux, uy = direction[0] / length, direction[1] / length
        size = h * .95
        base = [tip[0] - ux * size, tip[1] - uy * size]
        vertices = [list(tip), [base[0] + uy * size * .16, base[1] - ux * size * .16],
                    [base[0] - uy * size * .16, base[1] + ux * size * .16]]
        primitives.append({"kind": "polygon", "a": list(tip), "points": vertices, "role": role,
                           "component": component, "dimension": dimension})

    def feet(value):
        value = f"{value:.{d['precision']}f}"
        return (value.rstrip("0").rstrip(".") if "." in value else value) + "'"

    def dimension(key, a, b, y, suffix=""):
        left, right = sorted((a, b))
        value = feet(right[0] - left[0]) + suffix
        dimensions.append({"id": key, "a": left, "b": right, "y": y, "text": value})
        for pt in (left, right):
            line([pt[0], pt[1] + h * .65], [pt[0], y + .9 * h], "dimensions", key, True)
        line([left[0], y], [right[0], y], "dimensions", key, True)
        arrow([left[0], y], [-1, 0], "dimensions", key, True)
        arrow([right[0], y], [1, 0], "dimensions", key, True)
        label(key, [(left[0] + right[0]) / 2, y + .4 * h], value, "dimension_text", align="center", dimension=True)

    def interpolate(chain, x):
        for a, b in zip(chain, chain[1:]):
            if a[0] <= x <= b[0]:
                return [x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])]
        raise ValueError("Annotation anchor lies outside its pavement boundary.")

    points = geometry["points"]
    x0, y0 = points["CL"]
    surface_max = max(v[1] for k, v in points.items() if not k.endswith("toe"))
    dimension_y = surface_max + gap * 2.4
    for component in geometry["components"]:
        a, b, key = component["a"], component["b"], component["id"]
        line(a, b, component["role"], key)
        midpoint = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
        if "width_ft" in component:
            dimension(f"dim_{key}", a, b, dimension_y)
            words = ["TRAVEL", "LANE"] if key.endswith("lane") else ["SHLDR"]
            if key.endswith("shoulder") and not p[key.split("_")[0]]["shoulder_paved"]:
                words = ["UNPAVED", "SHLDR"]
            for i, word in enumerate(words):
                label(f"component_{key}_{i}", [midpoint[0], dimension_y - (i + 1.2) * h * 1.35], word, align="center")
            slope = component["slope_pct"]
            value = f"{abs(slope):.{d['precision']}f}".rstrip("0").rstrip(".") if d["precision"] else f"{abs(slope):.0f}"
            label(f"slope_{key}", [midpoint[0], midpoint[1] + 1.25 * h], (value or "0") + "%", "slopes", align="center", avoid=True)
            direction = 1 if b[0] > a[0] else -1
            if slope > 0:
                direction *= -1
            run = min(abs(b[0] - a[0]) * .65, 4.5 * h)
            start = [midpoint[0] - direction * run / 2, midpoint[1] + .65 * h]
            end = [midpoint[0] + direction * run / 2, midpoint[1] + .65 * h]
            line(start, end, "slopes", key)
            if slope:
                arrow(end, [direction, 0], "slopes", key)
        else:
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy)
            if not length:
                continue
            ux, uy = dx / length, dy / length
            nx, ny = (-uy, ux) if ux > 0 else (uy, -ux)
            angle = math.degrees(math.atan2(dy, dx))
            if angle > 90 or angle <= -90:
                angle += -180 if angle > 90 else 180
            pos = [midpoint[0] + nx * 1.5 * h, midpoint[1] + ny * 1.5 * h]
            label(f"slope_{key}", pos, f"{component['hv']:g}:1", "slopes", align="center", rotation=angle)
            direction = -1 if dy > 0 else 1
            center = [midpoint[0] + nx * .8 * h, midpoint[1] + ny * .8 * h]
            start = [center[0] - ux * direction * 1.6 * h, center[1] - uy * direction * 1.6 * h]
            end = [center[0] + ux * direction * 1.6 * h, center[1] + uy * direction * 1.6 * h]
            line(start, end, "slopes", key)
            arrow(end, [ux * direction, uy * direction], "slopes", key)
    dimension("dim_carriageway", points["left_lane"], points["right_lane"], dimension_y + 2 * gap)
    dimension("dim_total", points["left_shoulder"], points["right_shoulder"], dimension_y + 3 * gap)
    for side in ("left", "right"):
        edge = points[f"{side}_{'shoulder' if p[side]['shoulder_paved'] else 'lane'}"]
        dimension(f"dim_paved_{side}", points["CL"], edge, dimension_y + gap, " PAVED")
    for layer in geometry["layers"]:
        for a, b in zip(layer["bottom"], layer["bottom"][1:]):
            line(a, b, "pavement", layer["id"])
        for a, b in ((layer["top"][0], layer["bottom"][0]), (layer["top"][-1], layer["bottom"][-1])):
            line(a, b, "pavement", layer["id"])
    # Ground coordinates remain exact; short hatches only annotate its exterior portions.
    for a, b in zip(p["ground"], p["ground"][1:]):
        line(a, b, "ground", "ground")
        dx, dy = b[0] - a[0], b[1] - a[1]
        count = min(200, max(1, int(math.hypot(dx, dy) / (h * .9))))
        for i in range(count):
            t = (i + .5) / count
            x, y = a[0] + t * dx, a[1] + t * dy
            if x < points["left_toe"][0] or x > points["right_toe"][0]:
                line([x, y], [x + .3 * h, y - .65 * h], "ground", "ground")
    for side, anchor in (("left", p["ground"][0]), ("right", p["ground"][-1])):
        sign = -1 if side == "left" else 1
        label_x, label_y = anchor[0] - sign * h, anchor[1] - 4 * h
        line(anchor, [label_x - sign * h, label_y + 1.5 * h], "callouts", "ground")
        arrow(anchor, [anchor[0] - label_x + sign * h, anchor[1] - label_y - 1.5 * h], "callouts", "ground")
        label(f"ground_label_{side}", [label_x, label_y], "ORIGINAL GROUND LINE", align="left" if side == "left" else "right")
    bottom = min(v[1] for v in geometry["layers"][-1]["bottom"])
    line([x0, bottom - .8 * h], [x0, dimension_y - 3.4 * h], "centerline", "CL")
    line([x0, dimension_y - 2 * h], [x0, dimension_y + .8 * gap], "centerline", "CL")
    label("centerline_symbol", [x0, dimension_y - 2.7 * h], "CL", size=1.15, align="center")
    # Material leaders attach at separate sampled points on actual layer boundaries.
    bubble_y = bottom - 2.8 * h
    n = len(geometry["layers"])
    available = p["left"]["lane_width_ft"] * .72
    bubble_step = min(2.8 * h, available / max(1, min(n, 5) - 1))
    bubble_start = x0 - available
    for i, layer in enumerate(geometry["layers"]):
        bx = bubble_start + (i % 5) * bubble_step
        pt = interpolate(layer["bottom"], bx)
        bubble = [bx, bubble_y - (i // 5) * 2.4 * h]
        line(pt, [bx, bubble[1] + .8 * h], "callouts", layer["id"])
        primitives.append({"kind": "circle", "a": bubble, "radius": .8 * h, "role": "callouts", "component": layer["id"]})
        label(f"bubble_{i}", [bx, bubble[1] - .4 * h], str(i + 1), "callouts", size=1.25, align="center")
    depth = geometry["layers"][-1]["depth_ft"]
    dimension_x = x0 + 2.5 * h
    line([dimension_x, y0], [dimension_x, y0 - depth], "callouts", "structure")
    arrow([dimension_x, y0], [0, -1], "callouts", "structure")
    arrow([dimension_x, y0 - depth], [0, 1], "callouts", "structure")
    tx, ty = x0 + 6 * h, bottom - 3.7 * h
    line([dimension_x, y0 - depth / 2], [tx - .6 * h, ty + .6 * h], "callouts", "structure")
    for i, word in enumerate([f"{sum(v['thickness_in'] for v in p['layers']):g}\"", "STRUCTURE", "THICKNESS"]):
        label(f"structure_{i}", [tx, ty - 1.2 * h * i], word, size=1.05)
    pg_x, pg_y = x0 - 2.5 * h, bottom - 5.5 * h
    line([x0, y0], [pg_x + .5 * h, pg_y + h], "callouts", "plan_grade")
    arrow([x0, y0], [x0 - pg_x - .5 * h, y0 - pg_y - h], "callouts", "plan_grade")
    label("plan_grade_1", [pg_x, pg_y], "PLAN", size=1.1, align="center")
    label("plan_grade_2", [pg_x, pg_y - 1.4 * h], "GRADE", size=1.1, align="center")
    title_y = bottom - max(10 * h, (n // 5) * 2.4 * h + 8 * h)
    for i, value in enumerate([p["metadata"]["title"].upper(), p["metadata"]["construction"].upper(), p["metadata"]["route"].upper()]):
        label(f"title_{i}", [x0, title_y - i * 1.9 * h], value, size=1.6, align="center")
    for i, station in enumerate(p["metadata"]["stations"].split(";")):
        label(f"station_{i}", [x0, title_y - (6 + i * 1.7) * h], station.strip().upper(), size=1.3, align="center")
    left_x = min(p["ground"][0][0], points["left_toe"][0])
    legend_y = min(bubble_y - 3 * h, min(pt[1] for pt in p["ground"]) - 5 * h)
    column_chars = max(14, int((x0 - 9 * h - left_x) / (.42 * h)))
    rows = ["PAVEMENT STRUCTURE"]
    for i, layer in enumerate(p["layers"]):
        rows.extend(textwrap.wrap(f"{i + 1}. {layer['thickness_in']:g}\" {layer['name'].upper()} - {layer['material']}", column_chars))
    rows += [""]
    for note in p["metadata"]["notes"]:
        rows.extend(textwrap.wrap(note, column_chars))
    for i, row in enumerate(rows):
        label(f"legend_{i}", [left_x, legend_y - i * 1.2 * h], row, size=.82)
    coords = []
    for item in primitives:
        x, y = item["a"]
        if item["kind"] == "text":
            angle = math.radians(item["rotation"])
            for px, py in ((0, -item["height"] * .3), (0, item["height"]), (item["text_width"], -item["height"] * .3), (item["text_width"], item["height"])):
                coords.append([x + px * math.cos(angle) - py * math.sin(angle), y + px * math.sin(angle) + py * math.cos(angle)])
        elif item["kind"] == "circle":
            r = item["radius"]
            coords.extend([[x - r, y - r], [x + r, y + r]])
        elif item["kind"] == "polygon":
            coords.extend(item["points"])
        else:
            coords.extend([item["a"], item["b"]])
    bounds = [min(v[0] for v in coords) - 1.5 * h, min(v[1] for v in coords) - 1.5 * h,
              max(v[0] for v in coords) + 1.5 * h, max(v[1] for v in coords) + 1.5 * h]
    levels = {v["name"]: v for v in (p["catalog"] or {}).get("levels", [])}
    styles = {}
    for role in (v["role"] for v in primitives):
        level = levels.get(p["level_mappings"].get(role), {})
        styles[role] = {"name": level.get("name", "Unmapped"), "rgb": level.get("rgb") or PREVIEW_COLORS.get(role, "#d1dfec"),
                        "lineweight_mm": level.get("lineweight_mm") if level.get("lineweight_mm") is not None else PRINT_WEIGHTS[role],
                        "dash_ft": level.get("dash_ft") if level.get("dash_ft") is not None else ([1, -.35, .15, -.35] if role == "centerline" else [1, -.5] if role == "ground" else []),
                        "resolved": bool(level) and all(level.get(k) is not None for k in ("rgb", "lineweight_mm", "dash_ft")),
                        "plot": level.get("plot", True)}
    return {"geometry": geometry, "primitives": primitives, "dimensions": dimensions,
            "bounds": bounds, "styles": styles, "warnings": mapping_issues(p)}
