from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyproj import CRS

import Super
from super_spiral import SpiralSegment


NS = {"lx": "http://www.landxml.org/schema/LandXML-1.2"}


KNOWN_HORIZONTAL_COORDINATE_SYSTEMS = {
    "tn832011f": "EPSG:6576",
    "nad832011tennesseeftus": "EPSG:6576",
    "tn83f": "EPSG:2274",
    "nad83tennesseeftus": "EPSG:2274",
    "mdotms832011ef": "EPSG:6507",
    "ms832011ef": "EPSG:6507",
    "nad832011mississippieastftus": "EPSG:6507",
    "mdotms832011wf": "EPSG:6510",
    "ms832011wf": "EPSG:6510",
    "nad832011mississippiwestftus": "EPSG:6510",
}


def _normalized_crs_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


@dataclass(frozen=True)
class CoordinateSystemInfo:
    status: str
    authority: str | None
    code: str | None
    canonical_name: str | None
    detection_source: str | None
    name: str | None
    description: str | None
    horizontal_datum: str | None
    vertical_datum: str | None
    horizontal_coordinate_system_name: str | None
    file_location: str | None
    epsg_code: str | None
    ogc_wkt: str | None
    raw_attributes: dict[str, str]
    issues: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        if self.status == "missing":
            return "Not declared in LandXML"
        if self.status == "conflicting":
            return "Conflicting coordinate-system metadata"
        declared_name = self.horizontal_coordinate_system_name or self.name or self.description
        if self.status != "recognized":
            return f"Declared but not recognized: {declared_name}" if declared_name else "Declared but not recognized"
        label = self.canonical_name or declared_name or "Recognized coordinate system"
        authority_code = f"{self.authority}:{self.code}" if self.authority and self.code else ""
        if authority_code and authority_code.lower() not in label.lower():
            return f"{label} — {authority_code}"
        return label

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "display_name": self.display_name,
            "authority": self.authority,
            "code": self.code,
            "canonical_name": self.canonical_name,
            "detection_source": self.detection_source,
            "name": self.name,
            "description": self.description,
            "horizontal_datum": self.horizontal_datum,
            "vertical_datum": self.vertical_datum,
            "horizontal_coordinate_system_name": self.horizontal_coordinate_system_name,
            "file_location": self.file_location,
            "epsg_code": self.epsg_code,
            "issues": list(self.issues),
            "preserve_xy": True,
        }


def _missing_coordinate_system() -> CoordinateSystemInfo:
    return CoordinateSystemInfo(
        status="missing",
        authority=None,
        code=None,
        canonical_name=None,
        detection_source=None,
        name=None,
        description=None,
        horizontal_datum=None,
        vertical_datum=None,
        horizontal_coordinate_system_name=None,
        file_location=None,
        epsg_code=None,
        ogc_wkt=None,
        raw_attributes={},
    )


def coordinate_system_summary(info: CoordinateSystemInfo | None) -> dict[str, Any]:
    return (info or _missing_coordinate_system()).as_dict()


def _coordinate_system_node(root: ET.Element) -> ET.Element | None:
    for candidate in root.iter():
        if candidate.tag.rsplit("}", 1)[-1] == "CoordinateSystem":
            return candidate
    return None


def _crs_candidate(value: str, source: str, *, wkt: bool = False) -> tuple[str, str | None, str | None, str] | None:
    try:
        crs = CRS.from_wkt(value) if wkt else CRS.from_user_input(value)
    except Exception:
        return None
    authority = crs.to_authority()
    return crs.name, authority[0] if authority else None, authority[1] if authority else None, source


def _parse_coordinate_system(node: ET.Element | None) -> CoordinateSystemInfo:
    if node is None:
        return _missing_coordinate_system()

    attributes = {key.rsplit("}", 1)[-1]: value.strip() for key, value in node.attrib.items()}
    name = attributes.get("name") or None
    description = attributes.get("desc") or None
    horizontal_datum = attributes.get("horizontalDatum") or None
    vertical_datum = attributes.get("verticalDatum") or None
    horizontal_name = attributes.get("horizontalCoordinateSystemName") or None
    file_location = attributes.get("fileLocation") or None
    epsg_code = attributes.get("epsgCode") or None
    ogc_wkt = attributes.get("ogcWktCode") or None
    issues: list[str] = []
    candidates: list[tuple[str, str | None, str | None, str]] = []

    if epsg_code:
        match = re.fullmatch(r"(?:EPSG\s*[:_-]?\s*)?(\d+)", epsg_code, flags=re.IGNORECASE)
        candidate = _crs_candidate(f"EPSG:{match.group(1)}", "epsgCode") if match else None
        if candidate:
            candidates.append(candidate)
        else:
            issues.append(f"LandXML epsgCode '{epsg_code}' is not a valid EPSG coordinate reference system.")

    if ogc_wkt:
        candidate = _crs_candidate(ogc_wkt, "ogcWktCode", wkt=True)
        if candidate:
            candidates.append(candidate)
        else:
            issues.append("LandXML ogcWktCode could not be parsed as coordinate-system WKT.")

    for source, value in (
        ("horizontalCoordinateSystemName", horizontal_name),
        ("name", name),
        ("desc", description),
    ):
        if not value:
            continue
        epsg_match = re.search(r"\bEPSG\s*[:_-]?\s*(\d+)\b", value, flags=re.IGNORECASE)
        known_value = f"EPSG:{epsg_match.group(1)}" if epsg_match else KNOWN_HORIZONTAL_COORDINATE_SYSTEMS.get(_normalized_crs_name(value))
        if not known_value:
            continue
        candidate = _crs_candidate(known_value, source)
        if candidate:
            candidates.append(candidate)

    authority_codes = {
        (authority.upper(), code)
        for _, authority, code, _ in candidates
        if authority and code
    }
    if len(authority_codes) > 1:
        choices = ", ".join(f"{authority}:{code}" for authority, code in sorted(authority_codes))
        issues.append(f"LandXML coordinate-system fields disagree ({choices}).")
        status = "conflicting"
        selected = None
    elif candidates:
        status = "recognized"
        selected = candidates[0]
    else:
        status = "declared_unrecognized"
        selected = None

    canonical_name, authority, code, detection_source = selected or (None, None, None, None)
    return CoordinateSystemInfo(
        status=status,
        authority=authority,
        code=code,
        canonical_name=canonical_name,
        detection_source=detection_source,
        name=name,
        description=description,
        horizontal_datum=horizontal_datum,
        vertical_datum=vertical_datum,
        horizontal_coordinate_system_name=horizontal_name,
        file_location=file_location,
        epsg_code=epsg_code,
        ogc_wkt=ogc_wkt,
        raw_attributes=attributes,
        issues=tuple(issues),
    )


def _parse_point(text: str) -> tuple[float, float]:
    values = [float(value) for value in text.split()]
    if len(values)<2 or any(not math.isfinite(v) for v in values):
        raise ValueError("LandXML point requires finite Northing/Easting coordinates.")
    # LandXML stores horizontal coordinates as Northing, Easting. DXF/CAD
    # expects X=Easting and Y=Northing, so swap at the import boundary.
    return values[1], values[0]


def _normalized_angle(value: float) -> float:
    while value < 0:
        value += math.tau
    while value >= math.tau:
        value -= math.tau
    return value


@dataclass(frozen=True)
class LineSegment:
    start: tuple[float, float]
    end: tuple[float, float]
    length: float


@dataclass(frozen=True)
class ArcSegment:
    start: tuple[float, float]
    end: tuple[float, float]
    center: tuple[float, float]
    radius: float
    length: float
    rotation: str


@dataclass
class LandXMLData:
    path: Path
    alignment_name: str
    start_station: float
    alignment_length: float
    linear_unit: str
    lines: list[LineSegment]
    curves: list[ArcSegment]
    spirals: list[dict]
    station_equations: list[dict]
    superelevation_nodes: list[dict]
    coordinate_system: CoordinateSystemInfo | None
    warnings: list[str]
    _segments: list[LineSegment | ArcSegment | SpiralSegment]

    def station_range(self) -> tuple[float, float]:
        return self.start_station, self.start_station + sum(segment.length for segment in self._segments)

    def _arc_sweep_sign(self, segment: ArcSegment) -> int:
        expected = segment.length / segment.radius if segment.radius else 0.0
        start_angle = math.atan2(segment.start[1] - segment.center[1], segment.start[0] - segment.center[0])
        end_angle = math.atan2(segment.end[1] - segment.center[1], segment.end[0] - segment.center[0])
        ccw = _normalized_angle(end_angle - start_angle)
        cw = _normalized_angle(start_angle - end_angle)
        return 1 if abs(ccw - expected) <= abs(cw - expected) else -1

    def validate_station(self, station: float) -> None:
        start, end = self.station_range()
        if station < start or station > end:
            raise ValueError(f"Station {station:.3f} is outside alignment limits {start:.3f} to {end:.3f}.")

    def xy_at_station(self, station: float) -> tuple[float, float]:
        self.validate_station(station)
        remaining = station - self.start_station
        for segment in self._segments:
            if remaining <= segment.length + 1e-9:
                if isinstance(segment, SpiralSegment):
                    return segment.xy(max(0.0, remaining))
                if isinstance(segment, LineSegment):
                    ratio = 0.0 if segment.length == 0 else remaining / segment.length
                    x = segment.start[0] + (segment.end[0] - segment.start[0]) * ratio
                    y = segment.start[1] + (segment.end[1] - segment.start[1]) * ratio
                    return x, y
                angle = remaining / segment.radius
                start_angle = math.atan2(segment.start[1] - segment.center[1], segment.start[0] - segment.center[0])
                current_angle = start_angle + (self._arc_sweep_sign(segment) * angle)
                x = segment.center[0] + segment.radius * math.cos(current_angle)
                y = segment.center[1] + segment.radius * math.sin(current_angle)
                return x, y
            remaining -= segment.length
        last = self._segments[-1]
        return last.end if isinstance(last, LineSegment) else last.end

    def tangent_at_station(self, station: float) -> tuple[float, float]:
        self.validate_station(station)
        remaining = station - self.start_station
        for segment in self._segments:
            if remaining <= segment.length + 1e-9:
                if isinstance(segment, SpiralSegment):
                    return segment.tangent(max(0.0, remaining))
                if isinstance(segment, LineSegment):
                    dx = segment.end[0] - segment.start[0]
                    dy = segment.end[1] - segment.start[1]
                    length = math.hypot(dx, dy) or 1.0
                    return dx / length, dy / length
                angle = remaining / segment.radius
                start_angle = math.atan2(segment.start[1] - segment.center[1], segment.start[0] - segment.center[0])
                sign = self._arc_sweep_sign(segment)
                current_angle = start_angle + (sign * angle)
                if sign < 0:
                    return math.sin(current_angle), -math.cos(current_angle)
                return -math.sin(current_angle), math.cos(current_angle)
            remaining -= segment.length
        last = self._segments[-1]
        if isinstance(last, LineSegment):
            dx = last.end[0] - last.start[0]
            dy = last.end[1] - last.start[1]
            length = math.hypot(dx, dy) or 1.0
            return dx / length, dy / length
        return self.tangent_at_station(self.station_range()[1] - 0.001)

    def curve_records(self) -> list[dict]:
        records: list[dict] = []
        station = self.start_station
        curve_index = 1
        for segment_index, segment in enumerate(self._segments):
            if not isinstance(segment, ArcSegment):
                station += segment.length
                continue
            pc_station = station
            pt_station = station + segment.length
            # Infer turn direction along increasing station after converting
            # LandXML Northing/Easting to CAD X/Y.
            direction = "left" if self._arc_sweep_sign(segment) > 0 else "right"
            records.append(
                {
                    "landxml_curve_index": curve_index - 1,
                    "landxml_curve_id": f"curve-{curve_index}",
                    "alignment_name": self.alignment_name or "Unnamed alignment",
                    "curve_name": f"Curve {curve_index}",
                    "curve_direction": direction,
                    "pc_station_ft": pc_station,
                    "pc_station_label": Super.station_input_label(pc_station,self.station_equations,self.station_range()),
                    "pt_station_ft": pt_station,
                    "pt_station_label": Super.station_input_label(pt_station,self.station_equations,self.station_range()),
                    # LandXML commonly serializes exact design radii with
                    # floating-point noise (for example 3499.9999999999995).
                    # Use the intended three-decimal design value for lookup
                    # calculations while retaining segment.radius for geometry.
                    "radius_ft": round(segment.radius, 3),
                    "curve_length_ft": segment.length,
                    "rotation": segment.rotation,
                    "station_equations": self.station_equations,
                    "alignment_station_range": self.station_range(),
                }
            )
            before = self._segments[segment_index - 1] if segment_index else None
            after = self._segments[segment_index + 1] if segment_index + 1 < len(self._segments) else None
            if isinstance(before, SpiralSegment) or isinstance(after, SpiralSegment):
                if not isinstance(before, SpiralSegment) or not isinstance(after, SpiralSegment):
                    raise ValueError("A circular curve with spirals requires both entry and exit clothoids.")
                signed_curvature=self._arc_sweep_sign(segment)/segment.radius
                if abs(before.end_curvature-signed_curvature)>1e-8 or abs(after.start_curvature-signed_curvature)>1e-8:
                    raise ValueError("Spiral curvature does not match its circular curve.")
                records[-1].update({"alignment_type": "spiral", "ts_station_ft": pc_station - before.length,
                                    "sc_station_ft": pc_station, "cs_station_ft": pt_station,
                                    "st_station_ft": pt_station + after.length,
                                    "entering_spiral_length_ft": before.length, "exiting_spiral_length_ft": after.length})
                records[-1]["ts_station_label"]=Super.station_input_label(pc_station-before.length,self.station_equations,self.station_range())
                records[-1]["st_station_label"]=Super.station_input_label(pt_station+after.length,self.station_equations,self.station_range())
            records[-1]["linear_unit"]=self.linear_unit
            tangent_before=self._segments[segment_index-2] if records[-1].get("alignment_type")=="spiral" and segment_index>=2 else before
            tangent_after=self._segments[segment_index+2] if records[-1].get("alignment_type")=="spiral" and segment_index+2<len(self._segments) else after
            records[-1]["available_entry_tangent_ft"]=tangent_before.length if isinstance(tangent_before,LineSegment) else 0.0
            records[-1]["available_exit_tangent_ft"]=tangent_after.length if isinstance(tangent_after,LineSegment) else 0.0
            curve_index += 1
            station = pt_station
        return records


def _parse_landxml_root(root: ET.Element, source_name: str) -> LandXMLData:
    file_path = Path(source_name)

    alignment = root.find(".//lx:Alignment", NS)
    if alignment is None:
        raise ValueError("No Alignment node found in LandXML.")

    coord_geom = alignment.find("lx:CoordGeom", NS)
    if coord_geom is None:
        raise ValueError("Alignment has no CoordGeom definition.")

    units_node = root.find(".//lx:Units/lx:Imperial", NS)
    if units_node is None:
        units_node = root.find(".//lx:Units/lx:Metric", NS)
    linear_unit = units_node.get("linearUnit", "") if units_node is not None else ""
    warnings: list[str] = []
    if not linear_unit:
        warnings.append("LandXML does not declare linear units.")

    lines: list[LineSegment] = []
    curves: list[ArcSegment] = []
    segments: list[LineSegment | ArcSegment | SpiralSegment] = []
    spirals = []
    unsupported=[]

    for child in list(coord_geom):
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "Line":
            line = LineSegment(
                start=_parse_point(child.findtext("lx:Start", namespaces=NS, default="0 0 0")),
                end=_parse_point(child.findtext("lx:End", namespaces=NS, default="0 0 0")),
                length=float(child.get("length", "0") or 0.0),
            )
            lines.append(line)
            segments.append(line)
        elif tag == "Curve":
            curve = ArcSegment(
                start=_parse_point(child.findtext("lx:Start", namespaces=NS, default="0 0 0")),
                end=_parse_point(child.findtext("lx:End", namespaces=NS, default="0 0 0")),
                center=_parse_point(child.findtext("lx:Center", namespaces=NS, default="0 0 0")),
                radius=float(child.get("radius", "0") or 0.0),
                length=float(child.get("length", "0") or 0.0),
                rotation=str(child.get("rot", "ccw") or "ccw"),
            )
            curves.append(curve)
            segments.append(curve)
        elif tag == "Spiral":
            spirals.append(dict(child.attrib))
            if child.get("spiType", "").lower() != "clothoid":
                raise ValueError("Only explicitly defined LandXML clothoids are supported.")
            if not segments:
                raise ValueError("A clothoid requires a preceding tangent or circular arc to establish orientation.")
            length = float(child.get("length", "0"))
            start = _parse_point(child.findtext("lx:Start", namespaces=NS, default=""))
            end = _parse_point(child.findtext("lx:End", namespaces=NS, default=""))
            def curvature(value):
                if str(value).upper() in {"INF", "INFINITY"}:
                    return 0.0
                radius = float(value)
                if not math.isfinite(radius) or radius <= 0:
                    raise ValueError("Clothoid radius must be positive or INF.")
                return 1 / radius
            k0, k1 = curvature(child.get("radiusStart")), curvature(child.get("radiusEnd"))
            if not math.isfinite(length) or length <= 0 or (k0 == 0) == (k1 == 0):
                raise ValueError("Only finite positive tangent-to-circle or circle-to-tangent clothoids are supported.")
            prior = segments[-1]
            if math.dist(prior.end, start) > 0.001:
                raise ValueError("Disconnected clothoid start; alignment geometry was not modified.")
            if isinstance(prior, LineSegment):
                heading = math.atan2(prior.end[1] - prior.start[1], prior.end[0] - prior.start[0])
            elif isinstance(prior, SpiralSegment):
                raise ValueError("Adjacent compound spirals are unsupported.")
            else:
                probe = LandXMLData(file_path, "", 0, 0, "", [], [], [], [], [], None, [], [prior])
                tx, ty = probe.tangent_at_station(prior.length)
                heading = math.atan2(ty, tx)
            candidates = [SpiralSegment(start, end, length, heading, sign*k0, sign*k1, str(child.get("rot", ""))) for sign in (-1, 1)]
            matches = [s for s in candidates if math.dist(s.xy(length), end) <= 0.001]
            if len(matches) != 1 or child.get("rot") not in {"cw", "ccw"}:
                raise ValueError("Clothoid endpoint/length/direction constraints are inconsistent or ambiguous.")
            spiral = matches[0]
            convention = ("EN" if (spiral.end_curvature or spiral.start_curvature) * (1 if child.get("rot") == "ccw" else -1) > 0 else "NE")
            if spirals[0].get("verified_rotation_convention", convention) != convention:
                raise ValueError("Mixed LandXML spiral rotation conventions are unsupported.")
            spirals[-1]["verified_rotation_convention"] = convention
            segments.append(spiral)
        else:
            unsupported.append(tag)
    if spirals:
        if unsupported:raise ValueError(f"Unsupported geometry elements in spiral alignment: {', '.join(unsupported)}.")
        for prior, following in zip(segments, segments[1:]):
            if math.dist(prior.end, following.start) > 0.001:
                raise ValueError("Disconnected spiral alignment; geometry was not modified.")
            for segment in (prior,following):
                if not math.isfinite(segment.length) or segment.length<=0:
                    raise ValueError("Spiral alignment segments require finite positive lengths.")
                if isinstance(segment,ArcSegment):
                    if not math.isfinite(segment.radius) or segment.radius<=0:
                        raise ValueError("Spiral alignment arcs require finite positive radii.")
                    probe=LandXMLData(file_path,"",0,0,"",[],[],[],[],[],None,[],[segment])
                    if math.dist(probe.xy_at_station(segment.length),segment.end)>.001 or abs(math.dist(segment.start,segment.center)-segment.radius)>.001:
                        raise ValueError("Circular arc endpoint/length/radius constraints are inconsistent.")
                    sign=probe._arc_sweep_sign(segment)
                    expected=(1 if segment.rotation=="ccw" else -1)*(1 if spirals[0]["verified_rotation_convention"]=="EN" else -1)
                    if segment.rotation not in {"cw","ccw"} or sign!=expected:
                        raise ValueError("Circular/spiral rotation conventions conflict.")
            probe=LandXMLData(file_path,"",0,0,"",[],[],[],[],[],None,[],[prior])
            a=probe.tangent_at_station(prior.length)
            probe._segments=[following]
            b=probe.tangent_at_station(0)
            if isinstance(prior,SpiralSegment) or isinstance(following,SpiralSegment):
                if math.dist(a,b)>1e-5:
                    raise ValueError("Clothoid tangent discontinuity; geometry was not modified.")
                def curvature(segment,at_end):
                    if isinstance(segment,LineSegment):return 0.0
                    if isinstance(segment,SpiralSegment):return segment.end_curvature if at_end else segment.start_curvature
                    return probe._arc_sweep_sign(segment)/segment.radius
                if abs(curvature(prior,True)-curvature(following,False))>1e-8:
                    raise ValueError("Clothoid curvature discontinuity; compound/partial definitions are unsupported.")
        warnings.append("Clothoids evaluated without endpoint adjustment; adaptive integration tolerance 1e-7 native units per axis; endpoint consistency checked within 0.001 native units. Rotation convention verified from geometry.")

    station_equations = [dict(node.attrib) for node in alignment.findall("lx:StaEquation", NS)]
    if spirals:
        Super.strict_station_equations(station_equations)
    if station_equations:
        warnings.append("Station equations found; displayed civil stationing will be applied to inputs and export labels.")

    superelevation_nodes = [dict(node.attrib) for node in root.findall(".//lx:Superelevation", NS)]
    coordinate_system = _parse_coordinate_system(_coordinate_system_node(root))
    if coordinate_system.status == "missing":
        warnings.append("LandXML does not declare a coordinate system; overlay DXF coordinates will be preserved unchanged.")
    elif coordinate_system.status == "declared_unrecognized":
        warnings.append("LandXML declares a coordinate system that could not be identified; overlay DXF coordinates will be preserved unchanged.")
    elif coordinate_system.status == "conflicting":
        warnings.append("LandXML contains conflicting coordinate-system metadata; overlay DXF coordinates will be preserved unchanged.")
    warnings.extend(coordinate_system.issues)

    return LandXMLData(
        path=file_path,
        alignment_name=str(alignment.get("name", "") or ""),
        start_station=float(alignment.get("staStart", "0") or 0.0),
        alignment_length=float(alignment.get("length", "0") or 0.0),
        linear_unit=linear_unit,
        lines=lines,
        curves=curves,
        spirals=spirals,
        station_equations=station_equations,
        superelevation_nodes=superelevation_nodes,
        coordinate_system=coordinate_system,
        warnings=warnings,
        _segments=segments,
    )


def parse_landxml_text(content: str, source_name: str = "alignment.xml") -> LandXMLData:
    """Parse LandXML already held in memory, as required by browser clients."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"The LandXML is not valid XML (line {exc.position[0]}, column {exc.position[1]}).") from exc
    return _parse_landxml_root(root, source_name)


def load_landxml(path: str | Path) -> LandXMLData:
    file_path = Path(path)
    try:
        tree = ET.parse(file_path)
    except ET.ParseError as exc:
        raise ValueError(f"The LandXML is not valid XML (line {exc.position[0]}, column {exc.position[1]}).") from exc
    return _parse_landxml_root(tree.getroot(), str(file_path))
