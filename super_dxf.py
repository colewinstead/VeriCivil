from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import super_exports
import super_landxml


DEFAULT_CONFIG = {
    "text_height": 8.0,
    "title_text_height": 14.0,
    "table_text_height": 7.0,
    "tick_length": 25.0,
    "overlay_leader_extension": 16.0,
    "overlay_text_clearance": 6.0,
    "overlay_pair_gap": 12.0,
    "overlay_label_gap": 220.0,
    "overlay_min_label_spacing": 55.0,
    "overlay_label_offset": 70.0,
    "overlay_title_offset": 118.0,
    "overlay_title_text_height": 11.0,
    "overlay_title_line_spacing": 14.0,
    "overlay_text_style": "Engineering Regular",
    "overlay_text_styles": {"Engineering Regular": "EngineeringRegular.ttf"},
    "detail_x_scale": 0.9,
    "detail_y_scale": 10.0,
    "detail_spacing": 320.0,
    "sheet_origin": (0.0, 0.0),
    "layers": {
        "axis": "SE_AXIS",
        "left": "SE_LEFT",
        "right": "SE_RIGHT",
        "label": "SE_LABEL",
        "table": "SE_TABLE",
        "alignment": "ALI_DESIGN_ML_CURVES",
        "overlay_leader": "ALI_DESIGN_ML_LABELS",
        "overlay_station": "ALI_DESIGN_ML_STA",
        "overlay_text": "ALI_DESIGN_ML_LABELS_TX",
    },
    "overlay_layer_styles": {
        "ALI_DESIGN_ML_CURVES": {"color": 8, "linetype": "CONTINUOUS", "lineweight": 40},
        "ALI_DESIGN_ML_LABELS": {"color": 10, "linetype": "CONTINUOUS", "lineweight": 40},
        "ALI_DESIGN_ML_STA": {"color": 7, "linetype": "CONTINUOUS", "lineweight": 40},
        "ALI_DESIGN_ML_LABELS_TX": {"color": 7, "linetype": "CONTINUOUS", "lineweight": 40},
    },
}

def overlay_export_issues(
    curves: Iterable[dict], landxml: super_landxml.LandXMLData
) -> tuple[list[str], list[str]]:
    """Return blocking errors and non-blocking warnings for an overlay DXF export."""
    errors: list[str] = []
    curves=list(curves)
    warnings = list(dict.fromkeys(landxml.warnings))

    if any(c.get("results",{}).get("transition_method")=="aashto_fixed_pivot" for c in curves):
        import super_qa
        report=super_qa.analyze_corridor(landxml,curves)
        errors.extend(f["message"] for f in report["findings"] if f["severity"]=="block" and f["code"]!="UNCALCULATED_CURVE")
    elif landxml.spirals:
        errors.append("Spiral geometry requires a supported AASHTO calculation; DOT circular placement cannot be overlaid on spirals.")

    start, end = landxml.station_range()
    for row in super_exports.build_normalized_rows(curves):
        station = row.get("station")
        if station is None:
            errors.append(
                f"{row.get('curve_name', 'Curve')} has an export event with no station. Recalculate that curve."
            )
            continue
        station = float(station)
        if start <= station <= end:
            continue
        location = "before" if station < start else "after"
        errors.append(
            f"{row.get('curve_name', 'Curve')} — {row.get('lane_name', 'lane')} "
            f"{row.get('event_type', 'event')} at {row.get('station_label', station)} is {location} "
            f"the alignment range ({start:.3f} to {end:.3f})."
        )

    return list(dict.fromkeys(errors)), warnings


class DxfWriter:
    def __init__(self) -> None:
        self.entities: list[str] = []
        self._records: list[tuple] = []
        self._preview_metadata: dict[int, dict] = {}
        self._next_handle_value = 0x100

    def _next_handle(self) -> str:
        handle = format(self._next_handle_value, "X")
        self._next_handle_value += 1
        return handle

    def _append(self, *pairs: object) -> None:
        for value in pairs:
            self.entities.append(str(value))

    def add_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        layer: str,
        *,
        preview: dict | None = None,
    ) -> None:
        record_index = len(self._records)
        self._records.append(("LINE", float(x1), float(y1), float(x2), float(y2), str(layer)))
        if preview is not None:
            self._preview_metadata[record_index] = dict(preview)
        self._append(
            0,
            "LINE",
            5,
            self._next_handle(),
            100,
            "AcDbEntity",
            8,
            layer,
            100,
            "AcDbLine",
            10,
            round(x1, 6),
            20,
            round(y1, 6),
            30,
            0,
            11,
            round(x2, 6),
            21,
            round(y2, 6),
            31,
            0,
        )

    def add_text(
        self,
        x: float,
        y: float,
        text: str,
        height: float,
        layer: str,
        rotation: float = 0.0,
        alignment: str = "LEFT",
        text_style: str = "Standard",
        *,
        preview: dict | None = None,
    ) -> None:
        safe_text = str(text).replace("\n", " ")
        record_index = len(self._records)
        self._records.append(
            (
                "TEXT",
                float(x),
                float(y),
                safe_text,
                float(height),
                str(layer),
                float(rotation),
                str(alignment).upper(),
                str(text_style),
            )
        )
        if preview is not None:
            self._preview_metadata[record_index] = dict(preview)
        self._append(
            0,
            "TEXT",
            5,
            self._next_handle(),
            100,
            "AcDbEntity",
            8,
            layer,
            100,
            "AcDbText",
            10,
            round(x, 6),
            20,
            round(y, 6),
            30,
            0,
            40,
            round(height, 6),
            1,
            safe_text,
            50,
            round(rotation, 6),
        )

    def add_polyline(self, points: list[tuple[float, float]], layer: str) -> None:
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            self.add_line(x1, y1, x2, y2, layer)

    def save(
        self,
        path: str | Path,
        insunits: int = 0,
        layer_styles: dict | None = None,
        text_styles: dict | None = None,
    ) -> None:
        try:
            import ezdxf
        except ImportError as exc:
            raise RuntimeError("DXF export requires ezdxf. Install the project requirements and try again.") from exc

        document = ezdxf.new("R2000", setup=False)
        document.header["$INSUNITS"] = int(insunits)
        modelspace = document.modelspace()
        for style_name, font_file in (text_styles or {}).items():
            if not document.styles.has_entry(style_name):
                document.styles.add(style_name, font=str(font_file))
            # The font filename alone can be interpreted as SHX by ORD. The
            # ACAD extended family data explicitly identifies this as a
            # regular TrueType face available through the MDOT font path.
            document.styles.get(style_name).set_extended_font_data(
                family=style_name,
                italic=False,
                bold=False,
            )
        layers = {record[5] for record in self._records}
        for layer in sorted(layers):
            style = (layer_styles or {}).get(layer, {})
            attributes = {
                "color": int(style.get("color", 7)),
                "linetype": str(style.get("linetype", "CONTINUOUS")),
                "lineweight": int(style.get("lineweight", -3)),
            }
            if not document.layers.has_entry(layer):
                document.layers.add(
                    name=layer,
                    color=attributes["color"],
                    linetype=attributes["linetype"],
                )
            layer_entry = document.layers.get(layer)
            layer_entry.dxf.color = attributes["color"]
            layer_entry.dxf.linetype = attributes["linetype"]
            layer_entry.dxf.lineweight = attributes["lineweight"]
        for record in self._records:
            if record[0] == "LINE":
                _, x1, y1, x2, y2, layer = record
                modelspace.add_line((x1, y1, 0.0), (x2, y2, 0.0), dxfattribs={"layer": layer})
            else:
                from ezdxf.enums import TextEntityAlignment

                _, x, y, text, height, layer, rotation, alignment, text_style = record
                entity = modelspace.add_text(
                    text,
                    dxfattribs={
                        "height": height,
                        "rotation": rotation,
                        "layer": layer,
                        "style": text_style,
                    },
                )
                entity.set_placement(
                    (x, y, 0.0),
                    align=TextEntityAlignment.RIGHT if alignment == "RIGHT" else TextEntityAlignment.LEFT,
                )
        document.saveas(path)


def dxf_insunits(linear_unit: str) -> int:
    """Return the AutoCAD INSUNITS code for the LandXML linear unit."""
    unit = "".join(str(linear_unit or "").lower().split())
    if "ussurveyfoot" in unit or "usfoot" in unit:
        return 21
    if "foot" in unit or unit in {"ft", "feet"}:
        return 2
    if "millimeter" in unit or unit == "mm":
        return 4
    if "centimeter" in unit or unit == "cm":
        return 5
    if "meter" in unit or unit in {"m", "metre", "metres"}:
        return 6
    return 0


def _cfg(config: dict | None) -> dict:
    if not config:
        return DEFAULT_CONFIG
    merged = dict(DEFAULT_CONFIG)
    merged.update(config)
    merged_layers = dict(DEFAULT_CONFIG["layers"])
    merged_layers.update(config.get("layers", {}))
    merged["layers"] = merged_layers
    return merged


def _lane_points(rows: list[dict], station_origin: float, x_scale: float, y_scale: float, y_origin: float) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for row in rows:
        station = row.get("station_ft")
        if station is None:
            continue
        points.append(((float(station) - station_origin) * x_scale, y_origin + float(row["slope_pct"]) * y_scale))
    return points


def _upright_text_axis(vx: float, vy: float) -> tuple[float, float, float]:
    angle = math.degrees(math.atan2(vy, vx))
    if angle > 90.0 or angle <= -90.0:
        vx, vy = -vx, -vy
        angle = math.degrees(math.atan2(vy, vx))
    return vx, vy, angle


def _overlay_rows(curve: dict) -> list[dict]:
    return sorted(
        super_exports.build_normalized_rows([curve]),
        key=lambda row: (float(row["station"]), 0 if row["side"] == "left" else 1),
    )


def _draw_profile(
    writer: DxfWriter,
    title: str,
    rows: list[dict],
    origin_x: float,
    axis_y: float,
    station_origin: float,
    station_end: float,
    x_scale: float,
    y_scale: float,
    line_layer: str,
    label_layer: str,
    table_layer: str,
    text_height: float,
    table_text_height: float,
) -> None:
    writer.add_text(origin_x, axis_y + 18.0, title, text_height, label_layer)
    writer.add_line(origin_x, axis_y, origin_x + (station_end - station_origin) * x_scale, axis_y, line_layer)
    profile_points = _lane_points(rows, station_origin, x_scale, y_scale, axis_y)
    writer.add_polyline(profile_points, line_layer)
    for index, row in enumerate(rows):
        station = row.get("station_ft")
        if station is None:
            continue
        x = origin_x + (float(station) - station_origin) * x_scale
        writer.add_line(x, axis_y - 6.0, x, axis_y + 6.0, label_layer)
        label_y = axis_y - 18.0 if index % 2 == 0 else axis_y - 30.0
        writer.add_text(x - 10.0, label_y, row["station"], table_text_height, table_layer)
        writer.add_text(x - 8.0, axis_y + 8.0, row["slope_label"], table_text_height, table_layer)


def export_detail_dxf(path: str | Path, curves: Iterable[dict], config: dict | None = None) -> list[str]:
    from aashto_superelevation import validate_export_curves
    curves=list(curves)
    validate_export_curves(curves)
    cfg = _cfg(config)
    writer = DxfWriter()
    warnings: list[str] = []
    base_x, base_y = cfg["sheet_origin"]

    for index, curve in enumerate(curves):
        meta = curve.get("meta", {}) or {}
        results = curve.get("results") or {}
        direction = meta.get("curve_direction", "left")
        left_rows, right_rows = super_exports.build_lane_rows(results, direction, True)
        station_values = [row["station_ft"] for row in left_rows + right_rows if row.get("station_ft") is not None]
        if not station_values:
            warnings.append(f"Skipped detail export for {meta.get('curve_name', 'curve')} because no station data was available.")
            continue

        origin_x = base_x
        origin_y = base_y - index * cfg["detail_spacing"]
        station_origin = min(float(value) for value in station_values)
        station_end = max(float(value) for value in station_values)
        x_scale = cfg["detail_x_scale"]
        y_scale = cfg["detail_y_scale"]
        left_axis_y = origin_y + 50.0
        right_axis_y = origin_y - 40.0
        table_x = origin_x + (station_end - station_origin) * x_scale + 80.0
        table_y = origin_y + 70.0

        writer.add_text(origin_x, origin_y + 110.0, "Superelevation Detail", cfg["title_text_height"], cfg["layers"]["label"])
        writer.add_text(
            origin_x,
            origin_y + 94.0,
            f"{meta.get('project_name', '')} | {meta.get('route_name', '')} | {meta.get('alignment_name', '')} | {meta.get('curve_name', '')}",
            cfg["text_height"],
            cfg["layers"]["label"],
        )
        _draw_profile(
            writer,
            "Left Lane Profile",
            left_rows,
            origin_x,
            left_axis_y,
            station_origin,
            station_end,
            x_scale,
            y_scale,
            cfg["layers"]["left"],
            cfg["layers"]["label"],
            cfg["layers"]["table"],
            cfg["text_height"],
            cfg["table_text_height"],
        )
        _draw_profile(
            writer,
            "Right Lane Profile",
            right_rows,
            origin_x,
            right_axis_y,
            station_origin,
            station_end,
            x_scale,
            y_scale,
            cfg["layers"]["right"],
            cfg["layers"]["label"],
            cfg["layers"]["table"],
            cfg["text_height"],
            cfg["table_text_height"],
        )

        writer.add_text(table_x, table_y, "Key Stations", cfg["text_height"], cfg["layers"]["label"])
        row_y = table_y - 14.0
        for title, rows in (("Left", left_rows), ("Right", right_rows)):
            writer.add_text(table_x, row_y, f"{title} lane", cfg["table_text_height"], cfg["layers"]["label"])
            row_y -= 10.0
            for row in rows:
                writer.add_text(
                    table_x,
                    row_y,
                    f"{row['event_type']} | {row['station']} | {row['slope_label']}",
                    cfg["table_text_height"],
                    cfg["layers"]["table"],
                )
                row_y -= 8.0
            row_y -= 6.0

    writer.save(path)
    return warnings


def _pack_overlay_label_stations(
    rows: list[dict], minimum_spacing: float, cluster_gap: float, start: float, end: float
) -> None:
    """Assign non-overlapping label stations independently for each lane side."""
    for side in ("left", "right"):
        side_rows = sorted((row for row in rows if row.get("side") == side), key=lambda row: float(row["station"]))
        cluster: list[dict] = []

        def pack_cluster(items: list[dict]) -> None:
            if not items:
                return
            actual = [float(item["station"]) for item in items]
            packed = [actual[0]]
            for station in actual[1:]:
                packed.append(max(station, packed[-1] + minimum_spacing))
            # Share the displacement across both ends of the cluster instead
            # of pushing every close label toward increasing station.
            shift = (packed[-1] - actual[-1]) * 0.5
            packed = [station - shift for station in packed]
            if packed[0] < start:
                packed = [station + (start - packed[0]) for station in packed]
            if packed[-1] > end:
                packed = [station - (packed[-1] - end) for station in packed]
            for item, station in zip(items, packed):
                item["_label_station"] = min(max(station, start), end)

        for row in side_rows:
            if cluster and float(row["station"]) - float(cluster[-1]["station"]) > cluster_gap:
                pack_cluster(cluster)
                cluster = []
            cluster.append(row)
        pack_cluster(cluster)


def _overlay_station_label(row: dict, curve: dict) -> str:
    """Prefix callouts located at the curve PC or PT."""
    label = str(row.get("station_label", ""))
    station = float(row["station"])
    results = curve.get("results") or {}
    runoff = float(results.get("Lr", 0.0) or 0.0)
    reverse_crown = results.get("reverse_crown_ft")
    stored_pc = results.get("pc_ft")
    pc = (
        float(stored_pc)
        if stored_pc is not None
        else (None if reverse_crown is None else float(reverse_crown) + 0.7 * runoff)
    )
    pt = results.get("pt_ft")
    tolerance = 0.0015
    if pc is not None and abs(station - pc) <= tolerance:
        return f"PC {label}"
    if pt is not None and abs(station - float(pt)) <= tolerance:
        return f"PT {label}"
    return label


def _reverse_station_label(row: dict, curve: dict) -> str:
    """Use the normal compact callout text for a reverse-pair control."""
    label = _overlay_station_label(row, curve)
    event_type = str(row.get("event_type") or "").upper()
    if event_type.startswith("PC ") and not label.startswith("PC "):
        return f"PC {label}"
    if event_type.startswith("PT ") and not label.startswith("PT "):
        return f"PT {label}"
    return label


def _reverse_callout_key(row: dict) -> tuple[str, str, float, float]:
    return (
        str(row.get("reverse_pair_id") or ""),
        str(row.get("side") or ""),
        round(float(row["station"]), 6),
        round(float(row["slope_percent"]), 6),
    )


def _compact_reverse_callouts(rows: list[dict]) -> list[dict]:
    """Collapse reverse events that would render the same station/slope callout."""
    compact: dict[tuple[str, str, float, float], dict] = {}

    def priority(row: dict) -> int:
        event_type = str(row.get("event_type") or "").upper()
        if event_type.startswith(("PC ", "PT ")):
            return 0
        if event_type in {"REVERSE HANDOFF", "REVERSE CURVE ZERO"}:
            return 1
        return 2

    for row in rows:
        key = _reverse_callout_key(row)
        current = compact.get(key)
        if current is None or priority(row) < priority(current):
            compact[key] = row
    return sorted(
        compact.values(),
        key=lambda row: (
            str(row.get("side") or ""),
            float(row["station"]),
        ),
    )


def build_overlay_drawing(
    curves: Iterable[dict],
    landxml: super_landxml.LandXMLData,
    config: dict | None = None,
) -> tuple[DxfWriter, dict, list[str]]:
    """Build the single authoritative entity source used by overlay export and preview."""
    cfg = _cfg(config)
    writer = DxfWriter()
    warnings = list(landxml.warnings)
    curve_list = list(curves)
    drawn_reverse_events: set[tuple[str, str, float, float]] = set()

    for segment in landxml._segments:
        if isinstance(segment, super_landxml.LineSegment):
            start_x, start_y = segment.start
            end_x, end_y = segment.end
            writer.add_line(start_x, start_y, end_x, end_y, cfg["layers"]["alignment"])
        else:
            samples = max(int(math.ceil(segment.length / 50.0)), 8)
            if isinstance(segment, super_landxml.SpiralSegment):
                max_curvature=max(abs(segment.start_curvature),abs(segment.end_curvature))
                samples=max(8, math.ceil(segment.length / math.sqrt(0.08/max_curvature)))
                warnings.append("Clothoid DXF sampled with chord-error bound 0.01 source units; authoritative coordinates use numerical clothoid evaluation.")
            points: list[tuple[float, float]] = []
            start_station = landxml.start_station
            for prior in landxml._segments:
                if prior is segment:
                    break
                start_station += prior.length
            for idx in range(samples + 1):
                station = start_station + segment.length * (idx / samples)
                points.append(landxml.xy_at_station(station))
            writer.add_polyline(points, cfg["layers"]["alignment"])

    alignment_start, alignment_end = landxml.station_range()
    all_rows = super_exports.build_normalized_rows(curve_list)
    reverse_rows = _compact_reverse_callouts([
        row
        for row in all_rows
        if row.get("reverse_pair_critical") and row.get("reverse_pair_id")
    ])
    _pack_overlay_label_stations(
        reverse_rows,
        float(cfg["overlay_min_label_spacing"]),
        float(cfg["overlay_label_gap"]),
        alignment_start,
        alignment_end,
    )
    reverse_label_stations = {
        _reverse_callout_key(row): float(row.get("_label_station", row["station"]))
        for row in reverse_rows
    }
    visible_reverse_keys = set(reverse_label_stations)

    for curve_index, curve in enumerate(curve_list):
        meta = curve.get("meta", {}) or {}
        rows = sorted(
            (
                row for row in all_rows
                if int(row.get("curve_index", -1)) == curve_index
            ),
            key=lambda row: (
                float(row["station"]),
                0 if row.get("side") == "left" else 1,
            ),
        )
        if not rows:
            warnings.append(f"Skipped overlay export for {meta.get('curve_name', 'curve')} because no station data was available.")
            continue
        _pack_overlay_label_stations(
            rows,
            float(cfg["overlay_min_label_spacing"]),
            float(cfg["overlay_label_gap"]),
            alignment_start,
            alignment_end,
        )
        curve_title_drawn = False

        for row_index, row in enumerate(rows):
            station = float(row["station"])
            reverse_pair_id = str(row.get("reverse_pair_id") or "")
            reverse_critical = bool(row.get("reverse_pair_critical") and reverse_pair_id)
            if reverse_critical:
                reverse_key = _reverse_callout_key(row)
                if (
                    reverse_key not in visible_reverse_keys
                    or reverse_key in drawn_reverse_events
                ):
                    continue
                drawn_reverse_events.add(reverse_key)
                row["_label_station"] = reverse_label_stations.get(
                    reverse_key,
                    float(row["station"]),
                )
            try:
                x, y = landxml.xy_at_station(station)
                tx, ty = landxml.tangent_at_station(station)
                label_station = float(row.get("_label_station", station))
                label_x, label_y = landxml.xy_at_station(label_station)
            except ValueError as exc:
                warnings.append(str(exc))
                continue

            lane_side = str(row["side"])
            lane_sign = 1.0 if lane_side == "left" else -1.0
            nx = -ty * lane_sign
            ny = tx * lane_sign
            ux, uy, rotation = _upright_text_axis(nx, ny)
            station_label = (
                _reverse_station_label(row, curve)
                if reverse_critical
                else _overlay_station_label(row, curve)
            )
            leader_layer = cfg["layers"]["overlay_leader"]
            station_layer = cfg["layers"]["overlay_station"]
            text_layer = cfg["layers"]["overlay_text"]
            callout_preview = {
                "group_id": f"curve-{curve_index}-row-{row_index}",
                "curve_index": curve_index,
                "curve_name": str(meta.get("curve_name", row["curve_name"])),
                "station": str(row["station_label"]),
                "station_ft": station,
                "label_station_ft": label_station,
                "side": lane_side,
                "slope": str(row["slope_label"]),
                "event_type": str(row["event_type"]),
                "reverse_pair_id": reverse_pair_id or None,
                "reverse_pair_critical": reverse_critical,
            }

            elbow_x = x + nx * float(cfg["tick_length"])
            elbow_y = y + ny * float(cfg["tick_length"])
            end_x = label_x + nx * float(cfg["overlay_label_offset"])
            end_y = label_y + ny * float(cfg["overlay_label_offset"])
            writer.add_line(
                x,
                y,
                elbow_x,
                elbow_y,
                leader_layer,
                preview=callout_preview,
            )
            if math.hypot(end_x - elbow_x, end_y - elbow_y) > 0.001:
                writer.add_line(
                    elbow_x,
                    elbow_y,
                    end_x,
                    end_y,
                    leader_layer,
                    preview=callout_preview,
                )

            cross_x = -uy
            cross_y = ux
            text_anchor_x = end_x + nx * cfg["overlay_text_clearance"]
            text_anchor_y = end_y + ny * cfg["overlay_text_clearance"]
            text_alignment = "LEFT" if (ux * nx + uy * ny) >= 0.0 else "RIGHT"
            station_x = text_anchor_x - cross_x * cfg["overlay_pair_gap"] * 0.5
            station_y = text_anchor_y - cross_y * cfg["overlay_pair_gap"] * 0.5
            slope_x = text_anchor_x + cross_x * cfg["overlay_pair_gap"] * 0.5
            slope_y = text_anchor_y + cross_y * cfg["overlay_pair_gap"] * 0.5

            writer.add_text(
                station_x,
                station_y,
                station_label,
                cfg["text_height"],
                station_layer,
                rotation=rotation,
                alignment=text_alignment,
                text_style=cfg["overlay_text_style"],
                preview=callout_preview,
            )
            writer.add_text(
                slope_x,
                slope_y,
                row["slope_label"],
                cfg["text_height"],
                text_layer,
                rotation=rotation,
                alignment=text_alignment,
                text_style=cfg["overlay_text_style"],
                preview=callout_preview,
            )

            if not curve_title_drawn:
                radius = (curve.get("results") or {}).get("inputs", {}).get("radius_ft")
                title_text = f"{meta.get('curve_name', row['curve_name'])} ({meta.get('curve_direction', row['curve_direction'])})"
                title_x_axis, title_y_axis, title_rotation = _upright_text_axis(tx, ty)
                title_x = text_anchor_x + nx * cfg["overlay_title_offset"]
                title_y = text_anchor_y + ny * cfg["overlay_title_offset"]
                title_preview = {
                    "group_id": f"curve-{curve_index}-title",
                    "curve_index": curve_index,
                    "curve_name": str(meta.get("curve_name", row["curve_name"])),
                }
                writer.add_text(
                    title_x,
                    title_y,
                    title_text,
                    cfg["overlay_title_text_height"],
                    cfg["layers"]["overlay_text"],
                    rotation=title_rotation,
                    alignment="LEFT",
                    text_style=cfg["overlay_text_style"],
                    preview=title_preview,
                )
                if radius is not None:
                    # Stack the radius on the next readable line beneath the
                    # title, regardless of the alignment bearing.
                    down_x = title_y_axis
                    down_y = -title_x_axis
                    writer.add_text(
                        title_x + down_x * cfg["overlay_title_line_spacing"],
                        title_y + down_y * cfg["overlay_title_line_spacing"],
                        f"R={float(radius):,.3f}'",
                        cfg["overlay_title_text_height"],
                        cfg["layers"]["overlay_text"],
                        rotation=title_rotation,
                        alignment="LEFT",
                        text_style=cfg["overlay_text_style"],
                        preview=title_preview,
                    )
                curve_title_drawn = True

    unique_warnings = []
    for warning in warnings:
        if warning not in unique_warnings:
            unique_warnings.append(warning)
    return writer, cfg, unique_warnings


def _preview_text_corners(record: tuple) -> list[tuple[float, float]]:
    _, x, y, text, height, _layer, rotation, alignment, _text_style = record
    width = len(text) * height * 0.62
    x_start, x_end = (-width, 0.0) if alignment == "RIGHT" else (0.0, width)
    angle = math.radians(rotation)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    corners = []
    for local_x, local_y in ((x_start, 0.0), (x_end, 0.0), (x_end, height), (x_start, height)):
        corners.append((x + local_x * cosine - local_y * sine, y + local_x * sine + local_y * cosine))
    return corners


def overlay_preview_model(
    curves: Iterable[dict],
    landxml: super_landxml.LandXMLData,
    config: dict | None = None,
) -> dict:
    writer, cfg, warnings = build_overlay_drawing(curves, landxml, config)
    entities: list[dict] = []
    points: list[tuple[float, float]] = []
    used_layers: set[str] = set()

    for index, record in enumerate(writer._records):
        preview_metadata = writer._preview_metadata.get(index)
        preview = dict(preview_metadata) if preview_metadata is not None else None
        if record[0] == "LINE":
            _, x1, y1, x2, y2, layer = record
            entity = {
                "id": index,
                "type": "LINE",
                "layer": layer,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "preview": preview,
            }
            points.extend(((x1, y1), (x2, y2)))
        else:
            _, x, y, text, height, layer, rotation, alignment, text_style = record
            entity = {
                "id": index,
                "type": "TEXT",
                "layer": layer,
                "x": x,
                "y": y,
                "text": text,
                "height": height,
                "rotation": rotation,
                "alignment": alignment,
                "text_style": text_style,
                "preview": preview,
            }
            points.extend(_preview_text_corners(record))
        entities.append(entity)
        used_layers.add(layer)

    layer_styles = cfg.get("overlay_layer_styles", {})
    layers = {
        layer: {
            "color": int(style.get("color", 7)),
            "linetype": str(style.get("linetype", "CONTINUOUS")),
            "lineweight": int(style.get("lineweight", -3)),
        }
        for layer, style in layer_styles.items()
    }
    for layer in sorted(used_layers - layers.keys()):
        layers[layer] = {"color": 7, "linetype": "CONTINUOUS", "lineweight": -3}
    if points:
        xs, ys = zip(*points)
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
    else:
        min_x = min_y = 0.0
        max_x = max_y = 1.0
    if max_x <= min_x:
        max_x = min_x + 1.0
    if max_y <= min_y:
        max_y = min_y + 1.0

    return {
        "background": "#101010",
        "entities": entities,
        "layers": layers,
        "bounds": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
        "warnings": warnings,
    }


def export_overlay_dxf(path: str | Path, curves: Iterable[dict], landxml: super_landxml.LandXMLData, config: dict | None = None) -> list[str]:
    from aashto_superelevation import validate_export_curves
    curves=list(curves)
    validate_export_curves(curves)
    writer, cfg, warnings = build_overlay_drawing(curves, landxml, config)
    writer.save(
        path,
        dxf_insunits(landxml.linear_unit),
        cfg.get("overlay_layer_styles"),
        cfg.get("overlay_text_styles"),
    )
    return warnings
