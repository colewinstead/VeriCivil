from __future__ import annotations

import base64
import io
import os
import subprocess
import sys
from typing import Iterable
from xml.sax.saxutils import escape

import Super
from app_info import APP_VERSION
from criteria_info import applicable_drawings_label, calculation_sources_label, criteria_for_result, criteria_metadata
from super_lane import build_lane_rows


CHARCOAL = "#263238"
INK = "#1F2933"
MUTED = "#5F6B73"
LIGHT_GRAY = "#F2F4F5"
MID_GRAY = "#D5DADD"
ORANGE = "#D96521"
ORANGE_TINT = "#FFF2E8"
WHITE = "#FFFFFF"


def _asset_constants() -> tuple[str, dict[str, str]]:
    import super_ui

    return (
        getattr(super_ui, "DIAGRAM_PNG_B64", ""),
        getattr(super_ui, "STAMP_PNG_B64", {}),
    )


def _decode_asset(value: str) -> bytes | None:
    if not value:
        return None
    try:
        return base64.b64decode(value)
    except Exception:
        return None


def stamp_images() -> dict[str, bytes]:
    _, stamp_b64 = _asset_constants()
    images: dict[str, bytes] = {}
    for key, value in stamp_b64.items():
        decoded = _decode_asset(value)
        if decoded:
            images[key] = decoded
    return images


def select_stamps(results: dict) -> list[str]:
    _, stamp_b64 = _asset_constants()
    inputs = results.get("inputs", {})
    profile_id = str(((results.get("calculation_metadata", {}) or {}).get("criteria", {}) or {}).get("profile_id", ""))
    if profile_id.startswith(("tdot", "aashto")):
        return []
    area = str(inputs.get("area_type", "")).lower()
    facility = str(inputs.get("facility", "")).lower()
    speed = inputs.get("speed_mph", 0)
    stamps: list[str] = []

    if area.startswith("local"):
        if "SE-1" in stamp_b64:
            stamps.append("SE-1")
    elif area.startswith("urban"):
        if speed <= 45 and "center" in facility:
            if "SE-2E" in stamp_b64:
                stamps.append("SE-2E")
        elif speed == 50 and "center" in facility:
            if "SE-2C" in stamp_b64:
                stamps.append("SE-2C")
        elif speed == 50 and "edge" in facility:
            if "SE-2D" in stamp_b64:
                stamps.append("SE-2D")
    elif "edge" in facility:
        if "SE-2B" in stamp_b64:
            stamps.append("SE-2B")
        if "SE-3B" in stamp_b64:
            stamps.append("SE-3B")
    else:
        if "SE-2A" in stamp_b64:
            stamps.append("SE-2A")
        if "SE-3A" in stamp_b64:
            stamps.append("SE-3A")
    return stamps


def open_file(path: str) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def _text(value: object, fallback: str = "Not provided") -> str:
    rendered = str(value).strip() if value is not None else ""
    return escape(rendered or fallback)


def _number(value: object, digits: int = 2, suffix: str = "") -> str:
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "Not provided"


def _station(results: dict, value: object) -> str:
    if value is None:
        return "Not provided"
    return Super.format_result_station(results, float(value), True)


def _curve_status(results: dict) -> str:
    if results.get("warnings"):
        return "Review"
    overrides = ((results.get("calculation_metadata", {}) or {}).get("manual_overrides", {}) or {}).values()
    if any(overrides):
        return "Override"
    if results.get("normal_crown_only"):
        return "Normal crown"
    return "Calculated"


def _shared_meta(curves: list[dict], key: str) -> str:
    values = {
        str((curve.get("meta", {}) or {}).get(key, "")).strip()
        for curve in curves
        if str((curve.get("meta", {}) or {}).get(key, "")).strip()
    }
    if not values:
        return "Not provided"
    if len(values) > 1:
        return "Mixed - see curve index"
    return values.pop()


def export_pdf(path: str, curves: Iterable[dict], corridor_qa: dict | None = None) -> None:
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.graphics.shapes import Drawing, Line, String
    from reportlab.platypus import (
        BaseDocTemplate,
        Flowable,
        Frame,
        Image,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    class ContextMarker(Flowable):
        """Record the footer context for the current page without consuming space."""

        def __init__(self, context: str) -> None:
            super().__init__()
            self.context = context

        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            return 0, 0

        def draw(self) -> None:
            self.canv._report_context = self.context

    class NumberedCanvas(Canvas):
        def __init__(self, *args: object, report_info: dict[str, str], **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            self._saved_page_states: list[dict] = []
            self._report_info = report_info
            self._report_context = "Report summary"
            self.setPageCompression(0)
            self.setTitle(f"Superelevation Calculation Report - Application {APP_VERSION}")
            self.setAuthor("Superelevation Calculator")
            self.setSubject("Superelevation calculation report with project summary, criteria, and curve details")
            self.setKeywords(
                f"application={APP_VERSION}; calculation_engines={report_info['engines']}; criteria={report_info['criteria']}"
            )

        def showPage(self) -> None:
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            page_count = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_footer(page_count)
                Canvas.showPage(self)
            Canvas.save(self)

        def _draw_footer(self, page_count: int) -> None:
            page_width, page_height = self._pagesize
            self.saveState()
            self.setFillColor(HexColor(ORANGE))
            self.rect(0, page_height - 0.11 * inch, page_width, 0.11 * inch, fill=1, stroke=0)
            self.setFillColor(HexColor(MUTED))
            self.setFont("Helvetica-Bold", 6.7)
            self.drawString(0.58 * inch, page_height - 0.42 * inch, "SUPERELEVATION CALCULATION REPORT")
            self.setFont("Helvetica", 6.7)
            self.drawRightString(page_width - 0.58 * inch, page_height - 0.42 * inch, self._report_info["project"])
            self.setStrokeColor(HexColor(MID_GRAY))
            self.setLineWidth(0.5)
            self.line(0.58 * inch, 0.48 * inch, page_width - 0.58 * inch, 0.48 * inch)
            self.setFillColor(HexColor(MUTED))
            self.setFont("Helvetica", 6.5)
            project_route = f"{self._report_info['project']} | {self._report_info['route']}"
            if len(project_route) > 58:
                project_route = f"{project_route[:55]}..."
            self.drawString(0.58 * inch, 0.3 * inch, project_route)
            context = str(getattr(self, "_report_context", "Report summary"))
            if len(context) > 52:
                context = f"{context[:49]}..."
            self.drawCentredString(page_width / 2, 0.3 * inch, context)
            self.drawRightString(page_width - 0.58 * inch, 0.3 * inch, f"Page {self._pageNumber} of {page_count}")
            self.restoreState()

    curve_list = list(curves)
    from aashto_superelevation import validate_export_curves
    validate_export_curves(curve_list)
    diagram_b64, _ = _asset_constants()
    diagram_bytes = _decode_asset(diagram_b64)
    stamps = stamp_images()

    engine_versions = sorted(
        {
            str((curve.get("results") or {}).get("calculation_metadata", {}).get("engine_version") or "legacy-unversioned")
            for curve in curve_list
        }
    ) or [(corridor_qa or {}).get("calculation_engine_version") or "legacy-unversioned"]
    criteria_ids = sorted(
        {
            str(criteria_for_result(curve.get("results") or {}).get("profile_id") or "legacy-unversioned")
            for curve in curve_list
        }
    ) or [(corridor_qa or {}).get("criteria_profile") or "legacy-unversioned"]
    report_info = {"engines": ", ".join(engine_versions), "criteria": ", ".join(criteria_ids)}

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=27, textColor=HexColor(INK), spaceAfter=8, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="ReportSubtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, textColor=HexColor(MUTED), spaceAfter=14))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=HexColor(INK), spaceBefore=8, spaceAfter=5))
    styles.add(ParagraphStyle(name="CurveTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=HexColor(INK), spaceAfter=3))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=9.2, textColor=HexColor(INK)))
    styles.add(ParagraphStyle(name="SmallMuted", parent=styles["Small"], textColor=HexColor(MUTED)))
    styles.add(ParagraphStyle(name="Tiny", parent=styles["Normal"], fontName="Helvetica", fontSize=6.3, leading=8, textColor=HexColor(MUTED)))
    styles.add(ParagraphStyle(name="TableHeader", parent=styles["Small"], fontName="Helvetica-Bold", textColor=HexColor(WHITE), alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="TableHeaderRight", parent=styles["TableHeader"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="TableCell", parent=styles["Small"], alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="TableCellRight", parent=styles["Small"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="LaneHeader", parent=styles["TableHeader"], fontSize=6.4, leading=7.2))
    styles.add(ParagraphStyle(name="LaneHeaderRight", parent=styles["LaneHeader"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="LaneCell", parent=styles["TableCell"], fontSize=6.4, leading=7.5))
    styles.add(ParagraphStyle(name="LaneCellRight", parent=styles["LaneCell"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="KpiLabel", parent=styles["Tiny"], fontName="Helvetica-Bold", textColor=HexColor(MUTED), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="KpiValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=HexColor(INK), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="AgencyBadge", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=16, leading=18, textColor=HexColor(WHITE), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="AgencyDetail", parent=styles["Small"], leading=10))
    styles.add(ParagraphStyle(name="Alert", parent=styles["Small"], fontName="Helvetica-Bold", textColor=HexColor(INK)))
    styles.add(ParagraphStyle(name="Provenance", parent=styles["Tiny"], backColor=HexColor(LIGHT_GRAY), borderColor=HexColor(MID_GRAY), borderWidth=0.5, borderPadding=6, spaceBefore=5))

    width, height = letter
    margin = 0.58 * inch
    top_margin = 0.7 * inch
    bottom_margin = 0.58 * inch
    document = BaseDocTemplate(
        path,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title=f"Superelevation Calculation Report - Application {APP_VERSION}",
        author="Superelevation Calculator",
        subject="Superelevation calculation report with project summary, criteria, and curve details",
        keywords=f"application={APP_VERSION}; calculation_engines={report_info['engines']}; criteria={report_info['criteria']}",
    )

    report_info["project"] = _shared_meta(curve_list, "project_name")
    report_info["route"] = _shared_meta(curve_list, "route_name")

    frame = Frame(margin, bottom_margin, width - 2 * margin, height - top_margin - bottom_margin, id="report-frame", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    document.addPageTemplates([PageTemplate(id="report", frames=[frame])])

    story: list[object] = [ContextMarker("Report summary")]

    story.extend(
        [
            Spacer(1, 0.2 * inch),
            Paragraph("Superelevation Calculation Report", styles["ReportTitle"]),
            Paragraph("Project summary and curve-by-curve transition review", styles["ReportSubtitle"]),
        ]
    )

    summary_data = [
        [Paragraph("PROJECT", styles["Tiny"]), Paragraph("ROUTE", styles["Tiny"]), Paragraph("ALIGNMENT", styles["Tiny"]), Paragraph("CURVES", styles["Tiny"])],
        [Paragraph(_text(_shared_meta(curve_list, "project_name")), styles["KpiValue"]), Paragraph(_text(_shared_meta(curve_list, "route_name")), styles["KpiValue"]), Paragraph(_text(_shared_meta(curve_list, "alignment_name")), styles["KpiValue"]), Paragraph(str(len(curve_list)), styles["KpiValue"])],
    ]
    summary = Table(summary_data, colWidths=[1.85 * inch, 1.7 * inch, 2.25 * inch, 0.95 * inch], rowHeights=[0.24 * inch, 0.52 * inch])
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(LIGHT_GRAY)),
        ("TEXTCOLOR", (0, 0), (-1, -1), HexColor(INK)),
        ("BOX", (0, 0), (-1, -1), 0.6, HexColor(MID_GRAY)),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, HexColor(MID_GRAY)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([summary, Spacer(1, 0.2 * inch)])

    report_criteria = [criteria_for_result(curve.get("results") or {}) for curve in curve_list]
    if not report_criteria and (corridor_qa or {}).get("criteria_profile"):
        report_criteria=[criteria_metadata(corridor_qa["criteria_profile"])]
    agency_codes = sorted(
        {
            str(criteria.get("profile_id") or "legacy").split("-", 1)[0].upper()
            for criteria in report_criteria
        }
    ) or ["LEGACY"]
    agency_names = sorted(
        {
            str(criteria.get("governing_authority") or "Governing agency not recorded")
            for criteria in report_criteria
        }
    ) or ["Governing agency not recorded"]
    profile_names = sorted(
        {str(criteria.get("profile_name") or "Legacy criteria") for criteria in report_criteria}
    ) or ["Legacy criteria"]
    drawing_labels = sorted(
        {
            applicable_drawings_label(criteria)
            for criteria in report_criteria
            if applicable_drawings_label(criteria)
        }
    ) or ["No standard drawing identified"]
    agency_badge = agency_codes[0] if len(agency_codes) == 1 else "MULTI-DOT"
    governing_detail = (
        f"<b>{_text(' / '.join(agency_names))}</b><br/>"
        f"{_text(' / '.join(profile_names))}<br/>"
        f"<font color='{MUTED}'>Applicable standards: {_text(' / '.join(drawing_labels))}</font>"
    )
    governing_standard = Table(
        [[Paragraph(_text(agency_badge), styles["AgencyBadge"]), Paragraph(governing_detail, styles["AgencyDetail"])]],
        colWidths=[1.25 * inch, 5.5 * inch],
    )
    governing_standard.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), HexColor(CHARCOAL)),
        ("BACKGROUND", (1, 0), (1, 0), HexColor(LIGHT_GRAY)),
        ("BOX", (0, 0), (-1, -1), 0.6, HexColor(MID_GRAY)),
        ("LINEABOVE", (0, 0), (-1, 0), 2.5, HexColor(ORANGE)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([Paragraph("Governing standard", styles["Section"]), governing_standard, Spacer(1, 0.14 * inch), Paragraph("Curve index", styles["Section"])])

    index_headers = ["#", "Curve", "Direction", "PC - PT", "Speed", "Radius", "e", "Status"]
    index_data = [[Paragraph(header, styles["TableHeaderRight"] if header in {"Speed", "Radius", "e"} else styles["TableHeader"]) for header in index_headers]]
    for index, curve in enumerate(curve_list, start=1):
        results = curve.get("results", {}) or {}
        inputs = results.get("inputs", {}) or {}
        meta = curve.get("meta", {}) or {}
        index_data.append([
            Paragraph(str(index), styles["TableCell"]),
            Paragraph(_text(meta.get("curve_name")), styles["TableCell"]),
            Paragraph(_text(meta.get("curve_direction", "left")).title(), styles["TableCell"]),
            Paragraph(f"{_text(inputs.get('pc'))} - {_text(inputs.get('pt'), 'N/A')}", styles["TableCell"]),
            Paragraph(_number(inputs.get("speed_mph"), 0, " mph"), styles["TableCellRight"]),
            Paragraph(_number(inputs.get("radius_ft"), 0, " ft"), styles["TableCellRight"]),
            Paragraph(_number(results.get("e"), 4), styles["TableCellRight"]),
            Paragraph(_curve_status(results), styles["TableCell"]),
        ])
    if not curve_list:
        index_data.append([Paragraph("No calculated curves are available.", styles["TableCell"])] + [""] * 7)
    curve_index = Table(index_data, colWidths=[0.3 * inch, 1.0 * inch, 0.65 * inch, 1.65 * inch, 0.7 * inch, 0.78 * inch, 0.62 * inch, 1.05 * inch], repeatRows=1)
    index_style = [
        ("BACKGROUND", (0, 0), (-1, 0), HexColor(CHARCOAL)),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(WHITE)),
        ("BOX", (0, 0), (-1, -1), 0.6, HexColor(MID_GRAY)),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, HexColor(MID_GRAY)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for row_index in range(1, len(index_data)):
        index_style.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.white if row_index % 2 else HexColor(LIGHT_GRAY)))
    curve_index.setStyle(TableStyle(index_style))
    story.append(curve_index)
    if (corridor_qa or {}).get("findings"):
        story.extend([Spacer(1,0.12*inch),Paragraph("Corridor QA findings",styles["Section"])])
        if any(f.get("severity")=="block" for f in corridor_qa["findings"]):
            story.append(Paragraph("BLOCKED: Resolve findings before using affected engineering outputs. This report retains diagnostic evidence.",styles["Small"]))
        for finding in corridor_qa["findings"]:
            story.append(Paragraph(f"<b>{_text(finding.get('severity','review')).upper()} · {_text(finding.get('code'))}</b>: {_text(finding.get('message'))}<br/>{_text(finding.get('details'))}",styles["Small"]))

    def key_value_table(rows: list[tuple[str, str]], width_value: float = 2.15 * inch) -> object:
        data = [[Paragraph(_text(label), styles["Tiny"]), Paragraph(value, styles["Small"])] for label, value in rows]
        table = Table(data, colWidths=[1.15 * inch, width_value])
        commands = [
            ("BACKGROUND", (0, 0), (0, -1), HexColor(LIGHT_GRAY)),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor(MID_GRAY)),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor(MID_GRAY)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        table.setStyle(TableStyle(commands))
        return table

    def lane_table(title: str, rows: list[dict]) -> object:
        edges=bool(rows and "left_elevation_ft" in rows[0])
        data = [
            [Paragraph(title.upper(), styles["LaneHeader"]), "", "", ""],
            [Paragraph("POINT", styles["LaneHeader"]), Paragraph("STATION", styles["LaneHeader"]), Paragraph("SLOPE", styles["LaneHeaderRight"]), Paragraph("NOTE", styles["LaneHeader"])],
        ]
        if edges:
            data[0].extend(["", ""])
            data[1].extend([Paragraph("LEFT EDGE (ft)",styles["LaneHeaderRight"]),Paragraph("RIGHT EDGE (ft)",styles["LaneHeaderRight"])])
        for row in rows:
            data.append([
                Paragraph(_text(row.get("label")), styles["LaneCell"]),
                Paragraph(_text(row.get("station")), styles["LaneCell"]),
                Paragraph(_text(row.get("slope")), styles["LaneCellRight"]),
                Paragraph(_text(row.get("note")), styles["LaneCell"]),
            ])
            if edges:
                data[-1].extend([Paragraph(f"{row[key]:+.4f}",styles["LaneCellRight"]) for key in ("left_elevation_ft","right_elevation_ft")])
        widths=[1.15,1.05,.65,2,.85,.85] if edges else [.55,.9,.55,1.25]
        table = Table(data, colWidths=[w*inch for w in widths], repeatRows=2, splitByRow=1)
        commands = [
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 1), HexColor(CHARCOAL)),
            ("TEXTCOLOR", (0, 0), (-1, 1), HexColor(WHITE)),
            ("BOX", (0, 0), (-1, -1), 0.6, HexColor(MID_GRAY)),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, HexColor(MID_GRAY)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for row_index in range(2, len(data)):
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.white if row_index % 2 else HexColor(LIGHT_GRAY)))
        table.setStyle(TableStyle(commands))
        return table

    def reverse_profile_drawing(check: dict) -> object:
        drawing = Drawing(486, 178)
        lane_data = check.get("lanes", {}) or {}
        points_by_side: dict[str, list[tuple[float, float]]] = {}
        for side in ("left", "right"):
            lane = lane_data.get(side, {}) or {}
            events = list(lane.get("profile_events", []) or [])
            if not events:
                events = list(lane.get("prior_events", []) or []) + list(lane.get("following_events", []) or [])
            points_by_side[side] = sorted(
                {
                    (float(event["station_ft"]), float(event["slope_pct"]))
                    for event in events
                }
            )
        all_points = [point for points in points_by_side.values() for point in points]
        if not all_points:
            drawing.add(String(12, 84, "No coordinated lane events are available.", fontSize=8, fillColor=HexColor(MUTED)))
            return drawing
        station_start = min(point[0] for point in all_points)
        station_end = max(point[0] for point in all_points)
        slope_min = min(point[1] for point in all_points)
        slope_max = max(point[1] for point in all_points)
        if station_end <= station_start:
            station_end = station_start + 1.0
        if slope_max <= slope_min:
            slope_max = slope_min + 1.0
        left_margin, bottom, width, height = 38.0, 26.0, 430.0, 132.0

        def xy(station: float, slope: float) -> tuple[float, float]:
            return (
                left_margin + (station - station_start) / (station_end - station_start) * width,
                bottom + (slope - slope_min) / (slope_max - slope_min) * height,
            )

        drawing.add(Line(left_margin, bottom, left_margin + width, bottom, strokeColor=HexColor(MID_GRAY), strokeWidth=0.5))
        if slope_min <= 0.0 <= slope_max:
            _, zero_y = xy(station_start, 0.0)
            drawing.add(Line(left_margin, zero_y, left_margin + width, zero_y, strokeColor=HexColor(MID_GRAY), strokeWidth=0.6))
            drawing.add(String(4, zero_y - 3, "0%", fontSize=6.5, fillColor=HexColor(MUTED)))
        for side, color in (("left", HexColor("#128A83")), ("right", HexColor("#D77A19"))):
            points = points_by_side[side]
            for start, end in zip(points, points[1:]):
                x0, y0 = xy(*start)
                x1, y1 = xy(*end)
                drawing.add(Line(x0, y0, x1, y1, strokeColor=color, strokeWidth=1.8))
            lane = lane_data.get(side, {}) or {}
            for station in lane.get("zero_stations_ft", []) or []:
                x, y = xy(float(station), 0.0)
                drawing.add(Line(x, y - 4, x, y + 4, strokeColor=color, strokeWidth=1.0))
            handoff = lane.get("handoff_station_ft")
            if handoff is not None and not lane.get("normal_crown_hold"):
                x, y = xy(float(handoff), float(lane.get("handoff_slope_pct") or 0.0))
                drawing.add(Line(x, y - 6, x, y + 6, strokeColor=color, strokeWidth=1.2))
                drawing.add(String(x + 2, y + 7, f"{side[0].upper()} handoff", fontSize=6, fillColor=color))
        drawing.add(String(left_margin, 8, Super.format_station(station_start, True), fontSize=6.5, fillColor=HexColor(MUTED)))
        drawing.add(String(left_margin + width - 44, 8, Super.format_station(station_end, True), fontSize=6.5, fillColor=HexColor(MUTED)))
        drawing.add(String(left_margin + 142, 163, "Lane-specific standard-rate reverse transition", fontSize=8, fillColor=HexColor(INK)))
        return drawing

    pair_checks: dict[str, dict] = {}
    for curve in curve_list:
        coordination = ((curve.get("results") or {}).get("reverse_curve_coordination") or {})
        for check in coordination.get("checks", []) or []:
            pair_id = str(check.get("pair_id") or "")
            if pair_id:
                pair_checks.setdefault(pair_id, check)

    for pair_id, check in sorted(
        pair_checks.items(),
        key=lambda item: tuple(item[1].get("paired_curve_indexes", [0, 0])),
    ):
        indexes = list(check.get("paired_curve_indexes", [0, 0]))
        prior_index, following_index = int(indexes[0]), int(indexes[1])
        prior_curve = curve_list[prior_index]
        following_curve = curve_list[following_index]
        prior_results = prior_curve.get("results", {}) or {}
        following_results = following_curve.get("results", {}) or {}
        prior_meta = prior_curve.get("meta", {}) or {}
        following_meta = following_curve.get("meta", {}) or {}
        prior_effective_slope = (
            float(check.get("prior_rate_pct_per_ft", 0.0) or 0.0)
            * float(prior_results.get("Lr", 0.0) or 0.0)
            / 100.0
        )
        following_effective_slope = (
            float(check.get("following_rate_pct_per_ft", 0.0) or 0.0)
            * float(following_results.get("Lr", 0.0) or 0.0)
            / 100.0
        )
        pair_rows = [
            ("Pair", f"{_text(prior_meta.get('curve_name', f'Curve {prior_index + 1}'))} ({_text(prior_meta.get('curve_direction')).title()}) to {_text(following_meta.get('curve_name', f'Curve {following_index + 1}'))} ({_text(following_meta.get('curve_direction')).title()})"),
            ("PT to PC", f"{_station(prior_results, prior_results.get('pt_ft'))} to {_station(following_results, following_results.get('pc_ft'))}"),
            ("Available / minimum", f"{_number(check.get('available_tangent_ft'), 2, ' ft')} / {_number(check.get('minimum_tangent_ft'), 2, ' ft')}"),
            ("Status", _text(check.get("status")).replace("_", " ")),
            ("Rule", _text(check.get("rule"))),
            ("Outgoing effective slope / Lr / rate", f"{_number(prior_effective_slope, 4)} / {_number(prior_results.get('Lr'), 2, ' ft')} / {_number(check.get('prior_rate_pct_per_ft'), 6, ' %/ft')}"),
            ("Incoming effective slope / Lr / rate", f"{_number(following_effective_slope, 4)} / {_number(following_results.get('Lr'), 2, ' ft')} / {_number(check.get('following_rate_pct_per_ft'), 6, ' %/ft')}"),
        ]
        story.extend([
            PageBreak(),
            ContextMarker(f"Reverse curve pair {prior_index + 1}-{following_index + 1}"),
            Paragraph(f"Reverse Curve Pair {prior_index + 1}-{following_index + 1}", styles["CurveTitle"]),
            Paragraph("Lane-specific standard-rate transition record", styles["ReportSubtitle"]),
            key_value_table(pair_rows, width_value=5.6 * inch),
            Paragraph(
                "Effective slope is the full lane-rotation magnitude used to establish the "
                "standard rate. For reverse-crown cases, this may equal normal crown even "
                "when the criteria-table superelevation value is zero.",
                styles["Small"],
            ),
            Spacer(1, 0.12 * inch),
            reverse_profile_drawing(check),
            Spacer(1, 0.08 * inch),
        ])
        lane_summary: list[list[object]] = [[
            Paragraph("LANE", styles["TableHeader"]),
            Paragraph("CONTROL", styles["TableHeader"]),
            Paragraph("SLOPE", styles["TableHeaderRight"]),
            Paragraph("OUTGOING USED", styles["TableHeaderRight"]),
            Paragraph("INCOMING REMAINING", styles["TableHeaderRight"]),
            Paragraph("CROWN HOLD", styles["TableHeader"]),
            Paragraph("ZERO CROSSINGS", styles["TableHeader"]),
        ]]
        for side in ("left", "right"):
            lane = (check.get("lanes", {}) or {}).get(side, {}) or {}
            hold = lane.get("normal_crown_hold") or {}
            zeros = ", ".join(
                Super.format_station(float(value), True)
                for value in lane.get("zero_stations_ft", []) or []
            ) or "None"
            hold_text = (
                f"{Super.format_station(float(hold['start_ft']), True)} to "
                f"{Super.format_station(float(hold['end_ft']), True)} ({float(hold['length_ft']):.2f} ft)"
                if hold else "None"
            )
            handoff = lane.get("handoff_station_ft")
            if hold:
                control_text = "Normal-crown hold"
                control_slope = float(hold.get("slope_pct", -2.0))
            elif handoff is not None:
                control_text = Super.format_station(float(handoff), True)
                control_slope = float(lane.get("handoff_slope_pct") or 0.0)
            else:
                control_text = "Not recorded"
                control_slope = 0.0
            lane_summary.append([
                Paragraph(side.title(), styles["TableCell"]),
                Paragraph(control_text, styles["TableCell"]),
                Paragraph(f"{control_slope:+.2f}%", styles["TableCellRight"]),
                Paragraph(f"{float(lane.get('outgoing_rotation_length_ft', 0.0)):.2f} ft", styles["TableCellRight"]),
                Paragraph(f"{float(lane.get('remaining_incoming_rotation_length_ft', 0.0)):.2f} ft", styles["TableCellRight"]),
                Paragraph(hold_text, styles["TableCell"]),
                Paragraph(zeros, styles["TableCell"]),
            ])
        pair_table = Table(
            lane_summary,
            colWidths=[0.42 * inch, 0.78 * inch, 0.52 * inch, 0.72 * inch, 0.88 * inch, 1.45 * inch, 1.25 * inch],
            repeatRows=1,
        )
        pair_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(CHARCOAL)),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(WHITE)),
            ("BOX", (0, 0), (-1, -1), 0.6, HexColor(MID_GRAY)),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, HexColor(MID_GRAY)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([Paragraph("Lane transition controls", styles["Section"]), pair_table])
        related_findings = [
            finding for finding in (corridor_qa or {}).get("findings", []) or []
            if set(finding.get("curve_indexes", []) or []) == {prior_index, following_index}
        ]
        if related_findings:
            story.extend([
                Spacer(1, 0.08 * inch),
                Paragraph("Corridor QA", styles["Section"]),
                Paragraph(
                    "<br/>".join(
                        f"<b>{_text(finding.get('severity', 'review')).upper()} - {_text(finding.get('code'))}:</b> "
                        f"{_text(finding.get('message'))} {_text(finding.get('details'))}"
                        for finding in related_findings
                    ),
                    styles["Small"],
                ),
            ])

    for curve_index_number, curve in enumerate(curve_list, start=1):
        results = curve.get("results", {}) or {}
        inputs = results.get("inputs", {}) or {}
        segments = results.get("segments", {}) or {}
        meta = curve.get("meta", {}) or {}
        criteria = criteria_for_result(results)
        profile_id = str(criteria.get("profile_id") or "legacy-unversioned")
        profile_name = str(criteria.get("profile_name") or "Legacy criteria")
        curve_name = str(meta.get("curve_name") or f"Curve {curve_index_number}")

        story.extend([
            PageBreak(),
            ContextMarker(f"Curve {curve_index_number:02d} | {profile_name}"),
            Paragraph(f"Curve {curve_index_number:02d} / {_text(curve_name)}", styles["CurveTitle"]),
            Paragraph(
                f"{_text(meta.get('route_name'))} | {_text(meta.get('alignment_name'))} | {_text(meta.get('curve_direction', 'left')).title()} curve",
                styles["ReportSubtitle"],
            ),
        ])

        kpis = [
            ("SUPERELEVATION RATE", f"{_number(results.get('e'), 4)} ft/ft"),
            ("RUNOFF LENGTH", _number(results.get("Lr"), 2, " ft")),
            ("TANGENT RUNOUT", _number(results.get("Lt"), 2, " ft")),
            ("TOTAL TRANSITION", _number(segments.get("total_transition"), 2, " ft")),
        ]
        kpi_data = [[Paragraph(label, styles["KpiLabel"]) for label, _ in kpis], [Paragraph(value, styles["KpiValue"]) for _, value in kpis]]
        kpi_table = Table(kpi_data, colWidths=[1.69 * inch] * 4, rowHeights=[0.27 * inch, 0.47 * inch])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor(LIGHT_GRAY)),
            ("BOX", (0, 0), (-1, -1), 0.7, HexColor(MID_GRAY)),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, HexColor(MID_GRAY)),
            ("LINEABOVE", (0, 0), (-1, 0), 2.5, HexColor(ORANGE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.extend([kpi_table, Spacer(1, 0.12 * inch)])

        warnings = [str(value) for value in (results.get("warnings", []) or []) if value]
        if results.get("normal_crown_only"):
            warnings.insert(0, "Normal crown is maintained; no superelevation transition is required.")
        if warnings:
            alert_text = "<br/>".join(f"- {_text(value)}" for value in warnings)
            alert = Table([[Paragraph(f"REVIEW NOTICE<br/>{alert_text}", styles["Alert"])]], colWidths=[6.75 * inch])
            alert.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(ORANGE_TINT)),
                ("BOX", (0, 0), (-1, -1), 0.8, HexColor(ORANGE)),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
            story.extend([alert, Spacer(1, 0.1 * inch)])

        input_rows = [
            ("SC station" if inputs.get("alignment_type")=="spiral" else "PC station", _text(inputs.get("pc"))),
            ("CS station" if inputs.get("alignment_type")=="spiral" else "PT station", _text(inputs.get("pt"), "N/A")),
            ("Design speed", _number(inputs.get("speed_mph"), 0, " mph")),
            ("Curve radius", _number(inputs.get("radius_ft"), 2, " ft")),
            ("Facility / area", f"{_text(inputs.get('facility'))} / {_text(inputs.get('area_type'))}"),
            ("Lane configuration", f"{_number(inputs.get('lane_width_ft'), 2, ' ft')} / {_number(inputs.get('lanes_rotated'), 0, ' rotated')}"),
            ("Rate source", _text(results.get("e_source"))),
        ]

        if results.get("normal_crown_only"):
            station_rows = [("Normal crown begins", _station(results, results.get("reverse_crown_ft"))), ("Normal crown ends", _station(results, results.get("pt_ft")))]
        elif results.get("transition_method") == "aashto_fixed_pivot" or results.get("runoff_tangent_fraction") is not None:
            station_rows=[(label,_station(results,results.get(key))) for label,key in [("Start transition","pnc_ft"),("Start runoff","reverse_crown_ft"),("Full super entry","full_super_ft"),("Full super exit","full_super_out_ft"),("End runoff","reverse_crown_out_ft"),("End transition","pnc_out_ft")]]
            input_rows.extend([("Roadway / section",_text(f"{inputs.get('roadway','')} / {inputs.get('initial_section','')}")),
                               ("Rotation axis",_text(f"{inputs.get('rotation_axis',results.get('facility'))} / {results.get('pivot_relationship','')}")),
                               ("Placement",_text(inputs.get("runout_placement") if inputs.get("alignment_type")=="spiral" else f"{inputs.get('runoff_tangent_percent')}% runoff on tangent")),
                               ("Criteria data",_text(results.get("calculation_metadata",{}).get("criteria_workbook",{}).get("storage","Manual rate"))),
                               ("Source workbook SHA-256",_text(results.get("calculation_metadata",{}).get("criteria_workbook",{}).get("file_sha256","Manual rate")))])
            if results.get("section_lanes"):
                input_rows.extend([("Actual lanes",_text(len(results["section_lanes"]))),("Rotated width / lane factor",_text(f"n1={results['n1']:g}, bw={results['bw']:.8f}")),("Units",_text("; ".join(str(v) for v in results.get("units",{}).values()))), ("Geometry source",_text(inputs.get("geometry_provenance","Manual station-only")))])
                station_rows.extend((name,_station(results,station)) for name,station in results.get("alignment_anchors",{}).items())
                if results.get("spiral_lengths"):
                    lengths=results["spiral_lengths"]
                    input_rows.append(("Spiral actual / required",_text(f"Entry {lengths['entry_actual_ft']:.3f} ft; exit {lengths['exit_actual_ft']:.3f} ft; required {lengths['required_ft']:.3f} ft ({lengths['placement']})")))
        elif results.get("transition_method") == "tdot_simple_curve_half_total":
            station_rows = [
                ("Start normal crown", _station(results, results.get("pnc_ft"))),
                ("Zero crown / start runoff", _station(results, results.get("zero_crown_ft"))),
                ("Reverse-crown section", _station(results, results.get("reverse_section_ft"))),
                ("Full super near PC", _station(results, results.get("full_super_ft"))),
                ("Full super near PT", _station(results, results.get("full_super_out_ft"))),
                ("Zero crown / end runoff", _station(results, results.get("zero_crown_out_ft"))),
                ("Normal crown restored", _station(results, results.get("pnc_out_ft"))),
            ]
        else:
            station_rows = []
            coordination = results.get("reverse_curve_coordination", {}) or {}
            if coordination.get("entry"):
                station_rows.extend([
                    ("Full super after PC (PC + 0.3Lr)", _station(results, results.get("full_super_ft"))),
                ])
                entry_lanes = coordination["entry"].get("lanes", {}) or {}
                for side in ("left", "right"):
                    events = entry_lanes.get(side, {}).get("events", []) or []
                    handoff = next((event for event in events if event.get("event_type") == "Reverse handoff"), None)
                    if handoff:
                        station_rows.append((
                            f"{side.title()}-lane reverse handoff",
                            f"{_station(results, handoff.get('station_ft'))} at {float(handoff.get('slope_pct', 0.0)):+.2f}%",
                        ))
            else:
                station_rows.extend([
                    ("Point of normal crown", _station(results, results.get("pnc_ft"))),
                    ("Point of reverse crown", _station(results, results.get("reverse_crown_ft"))),
                    ("Full super near PC", _station(results, results.get("full_super_ft"))),
                ])
            if coordination.get("exit"):
                station_rows.extend([
                    ("Full super before PT (PT - 0.3Lr)", _station(results, results.get("full_super_out_ft"))),
                ])
                exit_lanes = coordination["exit"].get("lanes", {}) or {}
                for side in ("left", "right"):
                    events = exit_lanes.get(side, {}).get("events", []) or []
                    handoff = next((event for event in events if event.get("event_type") == "Reverse handoff"), None)
                    if handoff:
                        station_rows.append((
                            f"{side.title()}-lane reverse handoff",
                            f"{_station(results, handoff.get('station_ft'))} at {float(handoff.get('slope_pct', 0.0)):+.2f}%",
                        ))
            else:
                station_rows.extend([
                    ("Full super near PT", _station(results, results.get("full_super_out_ft"))),
                    ("Reverse crown out", _station(results, results.get("reverse_crown_out_ft"))),
                    ("Normal crown out", _station(results, results.get("pnc_out_ft"))),
                ])

            if coordination.get("checks"):
                check = coordination["checks"][0]
                station_rows.extend([
                    ("Available reverse-curve tangent", _number(check.get("available_tangent_ft"), 2, " ft")),
                    ("Minimum reverse-curve tangent", _number(check.get("minimum_tangent_ft"), 2, " ft")),
                    ("Transition-rate status", _text(check.get("transition_rate_status", "standard")).replace("_", " ")),
                    ("Reverse-curve rule", _text(check.get("rule"))),
                ])

        note_parts = [
            results.get("friction_note"),
            results.get("rel_grad_note"),
            results.get("lanes_note"),
            results.get("r_note"),
            results.get("e_note"),
            results.get("runoff_note"),
            results.get("extra_width_note"),
        ]
        calculation_notes = "; ".join(str(part) for part in note_parts if part)
        curve_notes = str(curve.get("notes") or "").strip()
        notes_in_reference = len(calculation_notes) + len(curve_notes) <= 1_200

        left_column = [Paragraph("Inputs", styles["Section"]), key_value_table(input_rows), Paragraph("Station references", styles["Section"]), key_value_table(station_rows)]
        reference_elements: list[object] = [Paragraph("Criteria reference", styles["Section"])]
        reference_elements.append(Paragraph(f"<b>Applicable:</b> {_text(applicable_drawings_label(criteria))}", styles["Small"]))
        reference_elements.append(Spacer(1, 0.05 * inch))
        reference_elements.append(Paragraph(f"<b>Sources:</b> {_text(calculation_sources_label(criteria))}", styles["Tiny"]))
        is_tdot = profile_id.startswith("tdot")
        if diagram_bytes and not is_tdot and not profile_id.startswith("aashto"):
            reference_elements.extend([Spacer(1, 0.08 * inch), Image(io.BytesIO(diagram_bytes), width=2.25 * inch, height=1.18 * inch, kind="proportional")])
        for stamp_key in select_stamps(results):
            asset = stamps.get(stamp_key)
            if asset:
                reference_elements.extend([Spacer(1, 0.05 * inch), Paragraph(f"Reference sheet {stamp_key}", styles["Tiny"]), Image(io.BytesIO(asset), width=1.48 * inch, height=0.55 * inch, kind="proportional")])
        if is_tdot:
            reference_elements.extend([Spacer(1, 0.12 * inch), Paragraph("TDOT criteria pages intentionally omit MDOT reference artwork.", styles["SmallMuted"])])
        if notes_in_reference:
            reference_elements.extend([
                Spacer(1, 0.12 * inch),
                Paragraph("<b>Notes and provenance</b>", styles["Small"]),
                Spacer(1, 0.04 * inch),
                Paragraph(f"<b>Calculation:</b> {_text(calculation_notes)}", styles["Tiny"]),
                Spacer(1, 0.03 * inch),
                Paragraph(f"<b>Curve:</b> {_text(curve_notes)}", styles["Tiny"]),
                Spacer(1, 0.03 * inch),
                Paragraph(f"<b>Design standard:</b> {_text(profile_name)}", styles["Tiny"]),
            ])

        detail_columns = Table([[left_column, reference_elements]], colWidths=[3.55 * inch, 3.05 * inch], hAlign="LEFT")
        detail_columns.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 8),
            ("LEFTPADDING", (1, 0), (1, 0), 8),
            ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ("LINEBEFORE", (1, 0), (1, 0), 0.6, HexColor(MID_GRAY)),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.extend([detail_columns, Spacer(1, 0.08 * inch)])

        left_rows, right_rows = build_lane_rows(results, meta.get("curve_direction", "left"), True)
        lane_columns = Table(
            [[lane_table("Left lane", left_rows), lane_table("Right lane", right_rows)]],
            colWidths=[3.3 * inch, 3.3 * inch],
            hAlign="LEFT",
        )
        lane_columns.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 4),
            ("LEFTPADDING", (1, 0), (1, 0), 4),
            ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        if results.get("section_lanes"):
            story.append(Paragraph("Lane transitions",styles["Section"]))
            story.append(Paragraph("Slope signs follow the recorded lane side, outward from alignment. Edge heights are physical left/right, relative to the fixed pivot.",styles["SmallMuted"]))
            for lane in results["section_lanes"]:
                rows=[{**event,"station":Super.format_result_station(results,event["station_ft"],True),
                       "slope":f"{event['slope_pct']:.3f}","slope_label":f"{event['slope_pct']:+.3f}%"} for event in lane["events"]]
                story.extend([lane_table(lane["lane_name"],rows),Spacer(1,.08*inch)])
        else:
            story.extend([Paragraph("Lane transitions", styles["Section"]), lane_columns])

        if not notes_in_reference:
            provenance_text = (
                f"<b>NOTES AND PROVENANCE</b><br/>"
                f"<b>Calculation:</b> {_text(calculation_notes)}<br/>"
                f"<b>Curve:</b> {_text(curve_notes)}<br/>"
                f"<b>Design standard:</b> {_text(profile_name)}"
            )
            story.append(Paragraph(provenance_text, styles["Provenance"]))

    def canvas_factory(*args: object, **kwargs: object) -> NumberedCanvas:
        return NumberedCanvas(*args, report_info=report_info, **kwargs)

    document.build(story, canvasmaker=canvas_factory)
