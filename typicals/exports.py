"""Editable DXF and vector sheets from the same local-foot drawing scene."""

from collections import Counter
import io
from xml.sax.saxutils import escape, quoteattr

from typicals.drawing import drawing, plot_weight
from typicals.model import validate
from typicals.workspace import mapping_issues


def sheet_transform(p, scene):
    width, height = p["print"]["width_in"] * 72, p["print"]["height_in"] * 72
    x1, y1, x2, y2 = scene["bounds"]
    scale = 72 / p["drafting"]["scale_ft_per_in"]
    if (x2 - x1) * scale > width - 72 or (y2 - y1) * scale > height - 72:
        raise ValueError("Drawing exceeds the selected sheet at this scale. Increase ft/in or paper size; no automatic geometry scaling was applied.")
    return width, height, scale, width / 2 - (x1 + x2) * scale / 2, height / 2 - (y1 + y2) * scale / 2


def svg(project):
    p = validate(project)
    scene = drawing(p)
    w, h, s, ox, oy = sheet_transform(p, scene)
    def xy(pt):
        return ox + pt[0] * s, h - oy - pt[1] * s
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w / 72:g}in" height="{h / 72:g}in" viewBox="0 0 {w:g} {h:g}">',
             '<rect width="100%" height="100%" fill="white"/>', '<title>VeriCivil Typicals engineering sheet</title>']
    for item in scene["primitives"]:
        style = scene["styles"][item["role"]]
        if not style["plot"]:
            continue
        color = "#000000" if p["print"]["monochrome"] else style["rgb"]
        weight = max(.1, plot_weight(p, item["role"]) * 72 / 25.4)
        x, y = xy(item["a"])
        dash = " ".join(f"{abs(v) * s:g}" for v in style["dash_ft"])
        attrs = f'stroke="{color}" stroke-width="{weight:g}" fill="none" stroke-dasharray="{dash}"'
        if item["kind"] == "line":
            bx, by = xy(item["b"])
            parts.append(f'<line x1="{x:.8f}" y1="{y:.8f}" x2="{bx:.8f}" y2="{by:.8f}" {attrs}/>')
        elif item["kind"] == "circle":
            parts.append(f'<circle cx="{x:.8f}" cy="{y:.8f}" r="{item["radius"] * s:.8f}" {attrs}/>')
        elif item["kind"] == "polygon":
            points = " ".join(f"{xy(pt)[0]:.8f},{xy(pt)[1]:.8f}" for pt in item["points"])
            parts.append(f'<polygon points="{points}" fill="{color}"/>')
        else:
            font = {"Helvetica": "sans-serif", "Courier": "monospace", "Times-Roman": "serif"}[p["drafting"]["font"]]
            rotation = -item.get("rotation", 0)
            length = f' textLength="{item["text_width"] * s:.8f}" lengthAdjust="spacingAndGlyphs"' if item["text"] else ""
            parts.append(f'<text x="{x:.8f}" y="{y:.8f}" fill="{color}" font-family={quoteattr(font)} font-size="{item["height"] * s:.8f}" transform="rotate({rotation:g} {x:.8f} {y:.8f})"{length}>{escape(item["text"])}</text>')
    parts.append(f'<text x="36" y="{h - 22:g}" fill="black" font-size="8">1 in = {p["drafting"]["scale_ft_per_in"]:g} ft | {p["units"]} | Local section coordinates | Engineer review required</text>')
    parts.append('</svg>')
    return "\n".join(parts).encode()


def pdf(project):
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.colors import HexColor
    p = validate(project)
    scene = drawing(p)
    w, h, s, ox, oy = sheet_transform(p, scene)
    output = io.BytesIO()
    canvas = Canvas(output, pagesize=(w, h), invariant=1)
    canvas.setTitle(p["metadata"]["title"])
    for item in scene["primitives"]:
        style = scene["styles"][item["role"]]
        if not style["plot"]:
            continue
        color = HexColor("#000000" if p["print"]["monochrome"] else style["rgb"])
        canvas.setStrokeColor(color)
        canvas.setFillColor(color)
        canvas.setLineWidth(max(.1, plot_weight(p, item["role"]) * 72 / 25.4))
        canvas.setDash([abs(v) * s for v in style["dash_ft"]])
        x, y = ox + item["a"][0] * s, oy + item["a"][1] * s
        if item["kind"] == "line":
            canvas.line(x, y, ox + item["b"][0] * s, oy + item["b"][1] * s)
        elif item["kind"] == "circle":
            canvas.circle(x, y, item["radius"] * s)
        elif item["kind"] == "polygon":
            path = canvas.beginPath()
            path.moveTo(x, y)
            for px, py in item["points"][1:]:
                path.lineTo(ox + px * s, oy + py * s)
            path.close()
            canvas.drawPath(path, fill=1, stroke=0)
        else:
            try:
                item["text"].encode("cp1252")
            except UnicodeEncodeError as exc:
                raise ValueError("PDF built-in fonts support Western text only; use SVG for other scripts.") from exc
            canvas.saveState()
            canvas.translate(x, y)
            canvas.rotate(item.get("rotation", 0))
            text = canvas.beginText()
            text.setFont(p["drafting"]["font"], item["height"] * s)
            text.setHorizScale(item.get("width_factor", 1) * 100)
            text.textOut(item["text"])
            canvas.drawText(text)
            canvas.restoreState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(HexColor("#000000"))
    canvas.drawString(36, 22, f"1 in = {p['drafting']['scale_ft_per_in']:g} ft | {p['units']} | Local section coordinates | Engineer review required")
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def dxf(project):
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    p = validate(project)
    scene = drawing(p)
    issues = scene["warnings"]
    if issues:
        raise ValueError("DXF blocked: " + " ".join(issues))
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 21 if p["units"] == "us_survey_foot" else 2
    document.header["$MEASUREMENT"] = 0
    document.header["$LUNITS"] = 2
    document.header["$LUPREC"] = 8
    ms = document.modelspace()
    mapped = p["level_mappings"]
    for name in sorted({mapped[role] for role in scene["styles"]}):
        level = next(v for v in p["catalog"]["levels"] if v["name"] == name)
        dash = level["dash_ft"]
        line_style = "CONTINUOUS"
        if dash:
            line_style = f"VC_{len(document.linetypes)}"
            document.linetypes.new(line_style, dxfattribs={"description": f"Explicit report mapping for {name}", "pattern": [sum(abs(v) for v in dash), *dash]})
        layer = document.layers.new(name, dxfattribs={"color": 7, "true_color": int(level["rgb"][1:], 16),
                    "lineweight": round(level["lineweight_mm"] * 100), "linetype": line_style, "plot": int(level["plot"])})
        layer.description = level.get("description", "")
    document.styles.new("Typicals", dxfattribs={"font": "txt"})
    for item in scene["primitives"]:
        if item.get("dimension"):
            continue
        attrs = {"layer": mapped[item["role"]], "color": 256, "lineweight": -1, "linetype": "BYLAYER"}
        if item["kind"] == "line":
            ms.add_line(item["a"], item["b"], dxfattribs=attrs)
        elif item["kind"] == "circle":
            ms.add_circle(item["a"], item["radius"], dxfattribs=attrs)
        elif item["kind"] == "polygon":
            ms.add_solid(item["points"], dxfattribs=attrs)
        else:
            entity = ms.add_text(item["text"], dxfattribs={**attrs, "height": item["height"], "style": "Typicals",
                                "width": item.get("width_factor", 1), "rotation": item.get("rotation", 0)})
            entity.set_placement(item["a"], align=TextEntityAlignment.LEFT)
    h = p["drafting"]["scale_ft_per_in"] * p["drafting"]["text_height_in"]
    for dim in scene["dimensions"]:
        override = {"dimtxt": h, "dimasz": h * .65, "dimexo": h * .3, "dimexe": h * .5,
                    "dimtad": 1, "dimdec": p["drafting"]["precision"], "dimtzin": 8,
                    "dimpost": "<>' PAVED" if dim["id"].startswith("dim_paved") else "<>'", "dimtxsty": "Typicals",
                    "dimclrd": 0, "dimclre": 0, "dimclrt": 0}
        entity = ms.add_linear_dim(base=(dim["a"][0], dim["y"]), p1=dim["a"], p2=dim["b"], angle=0,
                                   override=override, dxfattribs={"layer": mapped["dimensions"]})
        if dim["id"] in p["annotations"]:
            dx, dy = p["annotations"][dim["id"]]
            entity.set_location(((dim["a"][0] + dim["b"][0]) / 2 + dx, dim["y"] + h + dy))
        entity.render()
        for part in document.blocks[entity.dimension.dxf.geometry]:
            part.dxf.layer = mapped["dimension_text"] if part.dxftype() in ("TEXT", "MTEXT") else mapped["dimensions"]
            part.dxf.color = 256
            part.dxf.lineweight = -1
            part.dxf.linetype = "BYLAYER"
    output = io.StringIO()
    document.write(output)
    report = {"format": "DXF R2018", "units": p["units"], "insunits": document.header["$INSUNITS"],
              "coordinate_system": "Local section X=offset, Y=elevation; no map CRS", "engine_version": scene["geometry"]["engine_version"],
              "entities": dict(Counter(v.dxftype() for v in ms)), "level_mappings": mapped,
              "catalog_source": p["catalog"]["source"], "catalog_revision": p["catalog"]["revision"],
              "report_sha256": p["catalog"].get("report_sha256", "Not supplied"),
              "warnings": ["Report values require CAD administrator verification in the target workspace.",
                           "DGN indexed colors are represented by explicit RGB true color; do not equate DGN indices with AutoCAD ACI.",
                           "RSC custom styles require explicit simple dash mappings; complex symbols are not reproduced.",
                           "DXF text uses txt font; select the licensed workspace text style after import. PDF/SVG font is separate.",
                           "Dimensions are editable CAD dimensions, not linked back to the JSON constraint engine.",
                           "No DGN, ITL, corridor model, MDOT approval, or receiving-application compatibility claim."]}
    return output.getvalue().encode("utf-8"), report
