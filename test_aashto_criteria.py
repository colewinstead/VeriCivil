"""Independent equation/geometry checks and reviewed criteria validation."""

import base64
import copy
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import aashto_criteria as criteria
import aashto_superelevation as aashto
import super_exports
import super_landxml
import super_pdf
import super_project
import super_qa
import super_service
from super_spiral import SpiralSegment


def inputs(**changes):
    return {
        "criteria_profile": criteria.PROFILE_ID,
        "pc": "1000",
        "pt": "2000",
        "speed": "60",
        "radius": "2000",
        "e_manual": "0.06",
        "area": "rural",
        "runoff_tangent_percent": "70",
        "normal_crown": "0.02",
        "lane_widths": "12,12",
        "curve_direction": "left",
        **changes,
    }


def synthetic_alignment(entering=200, exiting=200, direction="left"):
    # Independent power-series integration of theta = s²/(2LR).
    length, radius = entering, 1000
    sign = 1 if direction == "left" else -1
    alpha = 1 / (2 * length * radius)
    x = sum(
        (-1) ** n
        * alpha ** (2 * n)
        * length ** (4 * n + 1)
        / (math.factorial(2 * n) * (4 * n + 1))
        for n in range(12)
    )
    y = sum(
        (-1) ** n
        * alpha ** (2 * n + 1)
        * length ** (4 * n + 3)
        / (math.factorial(2 * n + 1) * (4 * n + 3))
        for n in range(12)
    )
    theta = sign * length / (2 * radius)
    start = (500, 0)
    sc = (500 + x, sign * y)
    center = (
        sc[0] - sign * radius * math.sin(theta),
        sc[1] + sign * radius * math.cos(theta),
    )
    arc_length = 400
    phi = theta + sign * arc_length / radius
    cs = (
        center[0] + sign * radius * math.sin(phi),
        center[1] - sign * radius * math.cos(phi),
    )
    alpha = 1 / (2 * exiting * radius)
    x = sum(
        (-1) ** n
        * alpha ** (2 * n)
        * exiting ** (4 * n + 1)
        / (math.factorial(2 * n) * (4 * n + 1))
        for n in range(12)
    )
    y = sign * sum(
        (-1) ** n
        * alpha ** (2 * n + 1)
        * exiting ** (4 * n + 3)
        / (math.factorial(2 * n + 1) * (4 * n + 3))
        for n in range(12)
    )
    final = phi + sign * exiting / (2 * radius)
    st = (
        cs[0] + x * math.cos(final) + y * math.sin(final),
        cs[1] + x * math.sin(final) - y * math.cos(final),
    )
    end = (st[0] + 500 * math.cos(final), st[1] + 500 * math.sin(final))

    def point(p):
        return f"{p[1]:.12f} {p[0]:.12f}"

    rot = "ccw" if sign == 1 else "cw"
    xml = f"""<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2"><Units><Imperial linearUnit="USSurveyFoot"/></Units><Alignments><Alignment name="Synthetic" staStart="0" length="{1400+entering+exiting}"><CoordGeom>
    <Line length="500"><Start>0 0</Start><End>{point(start)}</End></Line>
    <Spiral spiType="clothoid" length="{entering}" radiusStart="INF" radiusEnd="1000" rot="{rot}"><Start>{point(start)}</Start><End>{point(sc)}</End></Spiral>
    <Curve radius="1000" length="400" rot="{rot}"><Start>{point(sc)}</Start><Center>{point(center)}</Center><End>{point(cs)}</End></Curve>
    <Spiral spiType="clothoid" length="{exiting}" radiusStart="1000" radiusEnd="INF" rot="{rot}"><Start>{point(cs)}</Start><End>{point(st)}</End></Spiral>
    <Line length="500"><Start>{point(st)}</Start><End>{point(end)}</End></Line>
    </CoordGeom></Alignment></Alignments></LandXML>"""
    return xml, sc, cs, st


class AASHTOTests(unittest.TestCase):
    def result(self, **changes):
        return super_service.calculate_curve(inputs(**changes))["results"]

    def test_manual_length_check_all_maxima_without_spiral_stations(self):
        for maximum in criteria.MAX_RATES:
            values = inputs(e_manual="", speed=40, radius=1824.076, max_superelevation=maximum,
                            area="urban_freeway" if maximum == 4 else "rural", pc="", pt="", ts="", st="", runoff_tangent_percent="")
            original = copy.deepcopy(values)
            check = super_service.required_spiral_lengths(values)
            established = self.result(**{**values, "pc":"1000", "pt":"2000", "alignment_type":"spiral", "ts":"500", "st":"2500", "acknowledge_spiral_override":True})
            self.assertEqual((check["e"], check["Lr"], check["Lt"]), (established["e"], established["Lr"], established["Lt"]))
            self.assertEqual(check["minimum_spiral_on_tangent_ft"], established["Lr"])
            self.assertEqual(check["minimum_spiral_in_spiral_ft"], established["Lr"] + established["Lt"])
            self.assertNotIn("alignment_anchors", check)
            self.assertNotIn("section_lanes", check)
            self.assertEqual(values, original)
            self.assertEqual(check["calculation_metadata"]["criteria_workbook"]["storage"], "embedded_python")

    def test_manual_length_check_screenshot_case_and_sections(self):
        check = super_service.required_spiral_lengths(inputs(e_manual="", pc="10+00", pt="15+00", ts="", st="", speed="65", radius="3000", max_superelevation="10", alignment_type="spiral"))
        established = self.result(e_manual="", pc="10+00", pt="15+00", ts="500", st="2000", speed="65", radius="3000", max_superelevation="10", alignment_type="spiral", acknowledge_spiral_override=True)
        self.assertEqual((check["e"], check["Lr"], check["Lt"]), (established["e"], established["Lr"], established["Lt"]))
        for changes in ({"rotation_axis":"left_edge"}, {"rotation_axis":"right_edge"},
                        {"roadway":"one_way", "lane_widths":"12", "initial_section":"single_slope", "initial_slope":"-0.02"}):
            check = super_service.required_spiral_lengths(inputs(**changes))
            actual = self.result(**changes)
            self.assertEqual((check["e"], check["Lr"], check["Lt"]), (actual["e"], actual["Lr"], actual["Lt"]))
        self.assertEqual(check["Lt"], 0)
        normal = super_service.required_spiral_lengths(inputs(e_manual="", speed=40, radius=20000))
        self.assertEqual((normal["crown_state"], normal["Lr"], normal["Lt"]), ("normal", 0, 0))
        with self.assertRaisesRegex(aashto.TransitionError, "gradient"):
            super_service.required_spiral_lengths(inputs(Lr_manual="1"))

    def test_manual_length_check_scope_entitlement_and_export_block(self):
        for changes in ({"criteria_profile":"mdot"}, {"landxml_source":{"content":"<LandXML/>"}},
                        {"geometry_provenance":{"source":"LandXML"}}):
            with self.assertRaises(ValueError):
                super_service.required_spiral_lengths(inputs(**changes))
        denied = super_service.dispatch_safe("required_spiral_lengths", json.dumps({"inputs":inputs(), "entitlement":{"plan":"free", "status":"active"}}))
        self.assertFalse(denied["ok"])
        result = super_service.dispatch("required_spiral_lengths", json.dumps({"inputs":inputs(), "entitlement":{"plan":"pro", "status":"active"}}))
        for operation in ("export_pdf", "export_ord_csv", "export_detail_dxf"):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, "length check"):
                getattr(super_service, operation)([{"results":result}])
        project = super_service.project_load(super_service.project_save({"vars":inputs(manual_spiral_length_check=True), "curves":[]}))["project"]
        self.assertTrue(project["vars"]["manual_spiral_length_check"])
        self.assertFalse(project["curves"])

    def test_station_input_errors_name_the_field_without_raw_float_error(self):
        for key, label in (("pc", "SC"), ("pt", "CS"), ("ts", "TS"), ("st", "ST")):
            for invalid in ("", "not-a-station", "nan"):
                with self.subTest(key=key, invalid=invalid):
                    payload = {"inputs":{**inputs(alignment_type="spiral", ts="500", st="2500"), key:invalid}, "entitlement":{"plan":"pro", "status":"active"}}
                    response = super_service.dispatch_safe("calculate", json.dumps(payload))
                    self.assertFalse(response["ok"])
                    self.assertIn(label + " station", response["error"]["message"])
                    self.assertNotIn("could not convert", response["error"]["message"])

    def test_all_maximum_rates_and_equation_3_23(self):
        for maximum in criteria.MAX_RATES:
            r = self.result(
                max_superelevation=maximum,
                e_manual=str(maximum / 100),
                radius=1500,
                area="urban_freeway" if maximum == 4 else "rural",
            )
            self.assertAlmostEqual(r["Lr"], 12 * (maximum / 100) / 0.005)
            self.assertAlmostEqual(r["Lt"], 48)
        with self.assertRaisesRegex(ValueError, "Maximum"):
            self.result(max_superelevation=5)

    def test_relative_gradients_and_unrounded_lane_factor_footnote(self):
        for speed, inverse in (
            (15, 125),
            (20, 125),
            (25, 137.5),
            (30, 150),
            (35, 162.5),
            (40, 175),
            (45, 187.5),
            (50, 200),
            (85, 200),
        ):
            self.assertEqual(criteria.relative_gradient(speed), 1 / inverse)
        for n, increase in (
            (1, 1),
            (1.5, 1.25),
            (2, 1.5),
            (2.5, 1.75),
            (3, 2),
            (3.5, 2.25),
        ):
            self.assertAlmostEqual(n * criteria.lane_factor(n), increase)
        for width_count in (4, 6):
            r = self.result(lane_widths=",".join(["12"] * width_count))
            self.assertAlmostEqual(r["bw"], criteria.lane_factor(width_count / 2))

    def test_explicit_circular_placement_and_overlap(self):
        with self.assertRaisesRegex(ValueError, "required"):
            self.result(runoff_tangent_percent="")
        for p in (0, 25, 50, 70, 100):
            r = self.result(runoff_tangent_percent=p)
            self.assertAlmostEqual(r["reverse_crown_ft"], 1000 - p / 100 * 144)
            self.assertAlmostEqual(r["full_super_out_ft"], 2000 - (1 - p / 100) * 144)
        with self.assertRaises(aashto.TransitionError):
            self.result(pt="1100", runoff_tangent_percent=0)

    def test_pivots_edge_elevations_and_no_geometry_change(self):
        for pivot in ("centerline", "left_edge", "right_edge"):
            for direction in ("left", "right"):
                r = self.result(rotation_axis=pivot, curve_direction=direction)
                self.assertEqual((r["pc_ft"], r["pt_ft"]), (1000, 2000))
                self.assertEqual(len(r["section_lanes"]), 2)
                for lane in r["section_lanes"]:
                    for a, b in zip(lane["events"], lane["events"][1:]):
                        length = b["station_ft"] - a["station_ft"]
                        if length > 1e-7:
                            for edge in ("right_elevation_ft", "left_elevation_ft"):
                                gradient = abs(b[edge] - a[edge]) / length
                                self.assertLessEqual(gradient, 0.005 / r["bw"] + 1e-8)

    def test_one_way_single_lane_has_one_ord_lane(self):
        r = self.result(
            roadway="one_way",
            initial_section="single_slope",
            lane_widths="12",
            initial_slope="0.02",
        )
        rows = super_exports.build_normalized_rows(
            [{"results": r, "meta": {"curve_direction": "left"}}]
        )
        self.assertEqual({row["lane_name"] for row in rows}, {"Lane 1"})
        self.assertEqual(len(r["section_lanes"]), 1)
        self.assertAlmostEqual(r["bw"], 1)
        favorable = self.result(
            roadway="one_way",
            initial_section="single_slope",
            lane_widths="12",
            initial_slope="-0.02",
        )
        self.assertEqual(favorable["Lt"], 0)
        self.assertAlmostEqual(favorable["Lr"], 48)

    def test_unsupported_sections_and_nonfinite_inputs(self):
        for change in (
            {"lane_widths": "10,12"},
            {"crown_from_left": 10},
            {"left_normal_slope": 0.015},
            {"radius": "nan"},
            {"runoff_tangent_percent": "inf"},
            {"area": "urban"},
            {"max_superelevation": 4},
            {"friction": 0.1},
            {"alignment_type": "compound"},
            {"linear_unit": "meter"},
            {"rotation_axis": "moving"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.result(**change)

    def test_spiral_anchors_holds_recommendations(self):
        for placement in ("on_tangent", "in_spiral"):
            r = self.result(
                alignment_type="spiral",
                ts="700",
                st="2250",
                runout_placement=placement,
                acknowledge_spiral_override=True,
            )
            self.assertEqual((r["full_super_ft"], r["full_super_out_ft"]), (1000, 2000))
            self.assertEqual(r["reverse_crown_ft"], 856)
            self.assertEqual(r["reverse_crown_out_ft"], 2144)
            self.assertEqual(
                sum(f["code"] == "EXCESS_SPIRAL" for f in r["qa_findings"]), 2
            )
            if placement == "on_tangent":
                self.assertEqual(r["hold_intervals"][0]["length_ft"], 156)
                self.assertIn(
                    "Consider moving", r["hold_intervals"][0]["recommendation"]
                )
            else:
                self.assertTrue(
                    all(h["section"] == "initial" for h in r["hold_intervals"])
                )

    def test_short_spiral_and_missing_acknowledgement_preserve_diagnostics(self):
        for changes in ({"ts": "900"}, {"ts": "800", "runout_placement": "on_tangent"}):
            v = inputs(alignment_type="spiral", st="2200", **changes)
            reply = super_service.dispatch_safe(
                "calculate",
                json.dumps(
                    {"inputs": v, "entitlement": {"plan": "pro", "status": "active"}}
                ),
            )
            self.assertFalse(reply["ok"])
            self.assertTrue(reply["error"]["findings"])
        xml, *_ = synthetic_alignment(50, 50)
        reply = super_service.dispatch_safe(
            "build_all_landxml_curves",
            json.dumps(
                {
                    "entitlement": {"plan": "pro", "status": "active"},
                    "content": xml,
                    "shared_inputs": inputs(speed=30),
                }
            ),
        )
        self.assertFalse(reply["ok"])
        finding = reply["error"]["findings"][0]
        self.assertEqual(finding["curve_indexes"], [0])
        self.assertIn("Curve 1", finding["message"])
        project = super_project.normalize_project(
            {
                "version": super_project.PROJECT_VERSION,
                "vars": {"diagnostic_findings": reply["error"]["findings"]},
                "curves": [],
            }
        )
        self.assertEqual(
            project["vars"]["diagnostic_findings"], reply["error"]["findings"]
        )

    def test_exact_spiral_no_hold_and_recommendation_length_gate(self):
        r = self.result(alignment_type="spiral", ts="856", st="2144")
        self.assertFalse(r["hold_intervals"])
        r = self.result(
            alignment_type="spiral",
            ts="840",
            st="2160",
            acknowledge_spiral_override=True,
        )
        self.assertIn("insufficient", r["hold_intervals"][0]["recommendation"])

    def test_spiral_geometry_independent_series_and_groups(self):
        xml, sc, cs, st = synthetic_alignment()
        data = super_landxml.parse_landxml_text(xml)
        self.assertEqual(data.station_range(), (0, 1800))
        for station, expected in [(700, sc), (1100, cs), (1300, st)]:
            self.assertLess(math.dist(data.xy_at_station(station), expected), 1e-7)
        preset = data.curve_records()[0]
        self.assertEqual(preset["ts_station_ft"], 500)
        self.assertEqual(preset["st_station_ft"], 1300)
        curves = super_service.build_all_landxml_curves(
            xml,
            "synthetic.xml",
            inputs(
                pc="700",
                pt="1100",
                speed="30",
                radius="1000",
                acknowledge_spiral_override=True,
            ),
        )
        report = super_qa.analyze_corridor(data, curves)
        self.assertNotIn("UNSUPPORTED_SPIRAL", {f["code"] for f in report["findings"]})
        self.assertIn("ZERO_CROWN_HOLD", {f["code"] for f in report["findings"]})
        import super_dxf

        errors, _ = super_dxf.overlay_export_issues(curves, data)
        self.assertFalse(errors)
        self.assertTrue(super_dxf.overlay_preview_model(curves, data))

    def test_geometry_rejects_unsupported_and_inconsistent_clothoids(self):
        xml, *_ = synthetic_alignment()
        for corrupt in (
            xml.replace('spiType="clothoid"', 'spiType="bloss"', 1),
            xml.replace('length="200"', 'length="190"', 1),
        ):
            with self.assertRaises(ValueError):
                super_landxml.parse_landxml_text(corrupt)

    def test_mixed_circular_and_spiral_groups_and_source_tangent_space(self):
        xml, *_ = synthetic_alignment()
        ns = super_landxml.NS["lx"]
        root = ET.fromstring(xml)
        alignment = root.find(f".//{{{ns}}}Alignment")
        geom = alignment.find(f"{{{ns}}}CoordGeom")
        point = lambda name: tuple(
            reversed([float(v) for v in geom[-1].find(f"{{{ns}}}{name}").text.split()])
        )
        start, end = point("Start"), point("End")
        theta = math.atan2(end[1] - start[1], end[0] - start[0])
        radius, length = 500, 200
        center = (end[0] - radius * math.sin(theta), end[1] + radius * math.cos(theta))
        phi = theta + length / radius
        arc_end = (
            center[0] + radius * math.sin(phi),
            center[1] - radius * math.cos(phi),
        )
        circle = ET.SubElement(
            geom, f"{{{ns}}}Curve", radius=str(radius), length=str(length), rot="ccw"
        )
        for name, xy in (("Start", end), ("Center", center), ("End", arc_end)):
            ET.SubElement(circle, f"{{{ns}}}{name}").text = f"{xy[1]:.12f} {xy[0]:.12f}"
        line = ET.SubElement(geom, f"{{{ns}}}Line", length="500")
        for name, xy in (
            ("Start", arc_end),
            (
                "End",
                (arc_end[0] + 500 * math.cos(phi), arc_end[1] + 500 * math.sin(phi)),
            ),
        ):
            ET.SubElement(line, f"{{{ns}}}{name}").text = f"{xy[1]:.12f} {xy[0]:.12f}"
        alignment.set("length", "2500")
        xml = ET.tostring(root, encoding="unicode")
        data = super_landxml.parse_landxml_text(xml)
        curves = super_service.build_all_landxml_curves(
            xml,
            "mixed.xml",
            inputs(
                speed=30, runoff_tangent_percent=50, acknowledge_spiral_override=True
            ),
        )
        self.assertEqual(
            [c["results"]["inputs"]["alignment_type"] for c in curves],
            ["spiral", "circular"],
        )
        report = super_qa.analyze_corridor(data, curves)
        self.assertFalse([f for f in report["findings"] if f["severity"] == "block"])

        xml, *_ = synthetic_alignment()
        xml = xml.replace(
            'Line length="500"><Start>0 0', 'Line length="20"><Start>0 480', 1
        ).replace('length="1800"', 'length="1320"', 1)
        data = super_landxml.parse_landxml_text(xml)
        manual = self.result(
            speed=30,
            radius=1000,
            pc=220,
            pt=620,
            ts=20,
            st=820,
            alignment_type="spiral",
            acknowledge_spiral_override=True,
        )
        report = super_qa.analyze_corridor(
            data,
            [
                {
                    "results": manual,
                    "meta": {"curve_direction": "left", "alignment_name": "Synthetic"},
                }
            ],
        )
        self.assertIn("INSUFFICIENT_TANGENT", {f["code"] for f in report["findings"]})

    def test_asymmetric_geometry_both_directions_and_imported_equations(self):
        for direction in ("left", "right"):
            xml, sc, cs, st = synthetic_alignment(200, 300, direction)
            data = super_landxml.parse_landxml_text(xml)
            for station, expected in [(700, sc), (1100, cs), (1400, st)]:
                self.assertLess(math.dist(data.xy_at_station(station), expected), 1e-7)
            preset = data.curve_records()[0]
            self.assertEqual(preset["curve_direction"], direction)
            curves = super_service.build_all_landxml_curves(
                xml,
                "asymmetric.xml",
                inputs(speed=30, acknowledge_spiral_override=True),
            )
            r = curves[0]["results"]
            self.assertEqual(r["spiral_lengths"]["entry_actual_ft"], 200)
            self.assertEqual(r["spiral_lengths"]["exit_actual_ft"], 300)
            self.assertEqual((r["full_super_ft"], r["full_super_out_ft"]), (700, 1100))

    def test_repeated_station_labels_require_regions_even_with_full_range(self):
        equations = [{"staInternal": 1500, "staBack": 1500, "staAhead": 1000}]
        with self.assertRaisesRegex(ValueError, "more than one"):
            self.result(
                pc="1200",
                pt="2000",
                station_equations=equations,
                alignment_station_range=[0, 4000],
            )
        r = self.result(
            pc="1200R2",
            pt="2200",
            station_equations=equations,
            alignment_station_range=[0, 4000],
        )
        self.assertEqual(r["pc_ft"], 1700)
        self.assertEqual(
            super_service.lookup(r, "left", "1200R2")["station"]["internal_ft"], 1700
        )

    def test_imported_spiral_station_equations_and_ord_regions(self):
        xml, *_ = synthetic_alignment(200, 300)
        xml = xml.replace(
            "<CoordGeom>",
            '<StaEquation staInternal="900" staBack="900" staAhead="600"/><CoordGeom>',
        )
        curves = super_service.build_all_landxml_curves(
            xml, "equation.xml", inputs(speed=30, acknowledge_spiral_override=True)
        )
        r = curves[0]["results"]
        self.assertEqual((r["pc_ft"], r["pt_ft"]), (700, 1100))
        self.assertEqual(r["inputs"]["pt"], "8+00.000R2")
        out = super_service.export_ord_csv(curves)["content"]
        self.assertIn("R2", out)
        self.assertNotIn("R2R2", out)

    def test_pc_bank_check_and_gradient_overrides(self):
        with self.assertRaisesRegex(aashto.TransitionError, "3-25"):
            self.result(radius=20000)
        for changes in ({"Lr_manual": 100}, {"Lt_manual": 20}):
            with self.assertRaisesRegex(ValueError, "gradient"):
                self.result(**changes)

    def test_tangent_availability_and_strict_station_equations(self):
        with self.assertRaisesRegex(aashto.TransitionError, "Entry tangent"):
            self.result(
                alignment_type="spiral",
                ts=856,
                st=2144,
                linear_unit="USSurveyFoot",
                geometry_provenance={
                    "source": "LandXML",
                    "available_entry_tangent_ft": 47,
                },
            )
        for equations in (
            [{"staBack": "nan", "staAhead": 1000}],
            [{"staInternal": 1000, "staBack": 1500, "staAhead": 2000}],
        ):
            with self.assertRaises(ValueError):
                self.result(station_equations=equations)
        for changes in (
            {"pc": "nan"},
            {"pt": "inf"},
            {"alignment_station_range": [0, float("nan")]},
        ):
            with self.assertRaises(ValueError):
                self.result(**changes)

    def test_actual_lane_lookup_and_saved_result_presentation(self):
        r = self.result(
            roadway="one_way", initial_section="single_slope", lane_widths="12"
        )
        lookup = super_service.lookup(r, "left", str(r["full_super_ft"]), "6%")
        self.assertEqual(set(lookup["station"]["slopes"]), {"Lane 1"})
        self.assertEqual(set(lookup["lanes"]), {"Lane 1"})
        self.assertEqual(len(super_service.present_results(r)["section_lanes"]), 1)
        self.assertEqual(set(lookup["station"]["edge_elevations"]), {"Lane 1"})
        diagram = super_service.curve_diagram(r)
        self.assertEqual(
            [lane["name"] for lane in diagram["section_profiles"]], ["Lane 1"]
        )
        self.assertEqual(
            set(super_qa.diagram_lookup(r, "left", r["full_super_ft"])["lanes"]),
            {"Lane 1"},
        )
        crowned = self.result()
        answer = super_qa.diagram_lookup(
            crowned, "left", crowned["reverse_crown_ft"] + 1
        )
        self.assertEqual(
            {lane["criterion"]["component"] for lane in answer["lanes"].values()},
            {"Runoff length"},
        )

    def test_ord_pivot_and_sign_and_unsupported_fixed_pivot(self):
        for pivot in ("left_edge", "right_edge"):
            r = self.result(
                roadway="one_way",
                initial_section="single_slope",
                lane_widths="12",
                rotation_axis=pivot,
            )
            out = io.StringIO()
            super_exports.write_ord_csv(
                out, [{"results": r, "meta": {"curve_direction": "left"}}]
            )
            rows = list(csv.DictReader(io.StringIO(out.getvalue())))
            self.assertEqual(
                {row["PivotAbout"] for row in rows},
                {"LS" if pivot == "left_edge" else "RS"},
            )
            import Super

            full = next(
                row
                for row in rows
                if row["Station"] == Super.format_result_station(r, r["full_super_ft"])
            )
            self.assertEqual(full["PointType"], "U")
            self.assertAlmostEqual(
                float(full["CrossSlope"]), 0.06 if pivot == "left_edge" else -0.06
            )
        with self.assertRaisesRegex(ValueError, "cannot represent"):
            super_exports.write_ord_csv(
                io.StringIO(),
                [
                    {
                        "results": self.result(rotation_axis="left_edge"),
                        "meta": {"curve_direction": "left"},
                    }
                ],
            )

    def test_exports_reject_stale_results_and_overlapping_transitions(self):
        a = {"results": self.result(), "meta": {"curve_direction": "left"}}
        b = {
            "results": self.result(pc=2250, pt=3250),
            "meta": {"curve_direction": "left"},
        }
        with self.assertRaisesRegex(ValueError, "overlap"):
            super_service.export_ord_csv([a, b])
        edited = copy.deepcopy(a)
        edited["results"]["Lr"] += 1
        with self.assertRaisesRegex(ValueError, "recalculate"):
            super_service.export_detail_dxf([edited])
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "recalculate"):
                super_pdf.export_pdf(str(Path(folder) / "stale.pdf"), [edited])

    def test_diagnostic_only_pdf_and_unsupported_dot_spirals(self):
        from pypdf import PdfReader

        report = {
            "findings": [
                {
                    "code": "INSUFFICIENT_SPIRAL",
                    "severity": "block",
                    "message": "Entry deficiency 44 ft",
                }
            ]
        }
        pdf = super_service.export_pdf([], report)["content"]
        text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("INSUFFICIENT_SPIRAL", text)
        self.assertIn("Entry deficiency 44 ft", text)
        xml, *_ = synthetic_alignment()
        with self.assertRaisesRegex(ValueError, "only by the AASHTO"):
            super_service.build_all_landxml_curves(
                xml, "synthetic.xml", inputs(criteria_profile="mdot")
            )

    def test_uniform_favorable_spiral_hold_is_initial_section(self):
        r = self.result(
            roadway="one_way",
            initial_section="single_slope",
            lane_widths="12",
            initial_slope="-0.02",
            alignment_type="spiral",
            ts=700,
            st=2300,
        )
        self.assertTrue(all(h["section"] == "initial" for h in r["hold_intervals"]))
        self.assertNotIn("ZERO_CROWN_HOLD", {f["code"] for f in r["qa_findings"]})

    def test_project_report_and_entitlement(self):
        r = self.result()
        curve = {
            "results": r,
            "meta": {"curve_direction": "left", "curve_name": "Synthetic"},
        }
        data = super_project.normalize_project(
            {"version": super_project.PROJECT_VERSION, "vars": {}, "curves": [curve]}
        )
        self.assertEqual(data["curves"][0]["results"], r)
        self.assertEqual(super_pdf.select_stamps(r), [])
        self.assertEqual(
            (r["inputs"]["roadway"], r["inputs"]["initial_section"]),
            ("two_way", "crowned"),
        )
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "report.pdf"
            super_pdf.export_pdf(str(target), [curve])
            self.assertGreater(target.stat().st_size, 1000)
            from pypdf import PdfReader

            text = " ".join(page.extract_text() for page in PdfReader(target).pages)
            self.assertIn("LEFT EDGE (ft)", text)
            self.assertIn("two_way / crowned", text)
        reply = super_service.dispatch_safe(
            "calculate",
            json.dumps(
                {
                    "inputs": inputs(),
                    "entitlement": {"plan": "free", "status": "active"},
                }
            ),
        )
        self.assertFalse(reply["ok"])

    def test_dot_placement_override_preserves_rates(self):
        for profile in ("mdot", "tdot"):
            v = inputs(criteria_profile=profile, e_manual="", speed="45", radius="1000")
            a = super_service.calculate_curve(v)["results"]
            b = super_service.calculate_curve(
                {
                    **v,
                    "override_standard_placement": True,
                    "runoff_tangent_percent": "40",
                }
            )["results"]
            self.assertEqual((a["e"], a["Lr"], a["Lt"]), (b["e"], b["Lr"], b["Lt"]))
            self.assertAlmostEqual(b["reverse_crown_ft"], 1000 - 0.4 * b["Lr"])


class TableSelectionTests(unittest.TestCase):
    """Synthetic thresholds test selection policy without distributing AASHTO grids."""

    def setUp(self):
        tables = {
            str(maximum): {
                "speeds": ["Vd = 40 mph"],
                "rows": [
                    ["NC", 6000], ["RC", 5000], [2.2, 4000], [2.4, 3000],
                    [2.6, 3000], [2.8, 2000], [maximum, 1000],
                ],
            }
            for maximum in criteria.MAX_RATES
        }
        runoff = []  # Synthetic sections use the runoff equation, not published lengths.
        digest = hashlib.sha256(
            json.dumps(tables, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        runoff_digest = hashlib.sha256(
            json.dumps(runoff, separators=(",", ":")).encode()
        ).hexdigest()
        self.pack = {"tables": tables, "runoff": runoff, "table_digest": digest}
        for name, value in (("WORKBOOK_TABLE_DIGEST", digest), ("RUNOFF_DIGEST", runoff_digest)):
            patcher = patch.object(criteria, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_exact_between_and_rounded_tie_boundaries_all_maxima(self):
        for maximum in criteria.MAX_RATES:
            for radius, expected in (
                (4500, 2.2), (4000, 2.2), (4000 - 1e-6, 2.4),
                (3500, 2.4), (3000, 2.4), (3000 + 1e-6, 2.4),
                (3000 - 1e-6, 2.8), (2500, 2.8), (2000, 2.8),
                (2000 - 1e-6, maximum), (1000, maximum),
            ):
                with self.subTest(maximum=maximum, radius=radius):
                    e, crown, source = criteria.rate(self.pack, maximum, 40, radius, 0.02)
                    self.assertEqual((e, crown), (expected / 100, "full"))
                    self.assertEqual(source["mode"], "published_table_lookup")
                    self.assertEqual(source["selection_method"], "next_smaller_tabulated_radius")
                    self.assertLessEqual(source["selected_row_radius_ft"], radius)
                    self.assertEqual(source["input_radius_ft"], radius)
                    self.assertIn("§3.3.5", source["reference"])

    def test_crown_thresholds_and_rejected_speed_and_radius(self):
        for maximum in criteria.MAX_RATES:
            for radius, expected in ((6000, (0, "normal")), (5999, (0.02, "reverse")), (5000, (0.02, "reverse"))):
                self.assertEqual(criteria.rate(self.pack, maximum, 40, radius, 0.02)[:2], expected)
            with self.assertRaisesRegex(ValueError, "below"):
                criteria.rate(self.pack, maximum, 40, 999.999, 0.02)
            with self.assertRaisesRegex(ValueError, "does not publish speed"):
                criteria.rate(self.pack, maximum, 37, 3500, 0.02)

    def test_automatic_rate_shared_service_project_and_lane_events(self):
        r = super_service.calculate_curve(inputs(
            aashto_tables=self.pack, e_manual="", speed=40, radius=3500,
            runoff_tangent_percent=50,
        ))["results"]
        self.assertEqual(r["e"], 0.024)
        self.assertFalse(r["calculation_metadata"]["manual_overrides"]["superelevation_rate"])
        source = r["calculation_metadata"]["calculation_sources"][0]
        self.assertEqual(source["selected_row_radius_ft"], 3000)
        self.assertIn("tabulated R=3000 ft", r["e_note"])
        curve = {"results": r, "meta": {"curve_direction": "left"}}
        project = super_project.normalize_project({"version": 5, "curves": [curve]})
        self.assertEqual(project["curves"][0]["results"]["calculation_metadata"], r["calculation_metadata"])
        rows = super_exports.build_normalized_rows([curve])
        self.assertAlmostEqual(max(abs(row["slope_percent"]) for row in rows), 2.4)


class ReviewedTableValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = criteria.built_in_tables()

    def test_embedded_criteria_matches_reviewed_local_workbook(self):
        path = Path(__file__).parent / "docs/AASHTO Super Tables.xlsx"
        if not path.exists():
            self.skipTest("Source workbook absent; embedded boundaries remain covered.")
        source = criteria.import_workbook(base64.b64encode(path.read_bytes()).decode())
        for key in ("tables", "runoff", "table_digest", "file_sha256", "source_version"):
            self.assertEqual(self.pack[key], source[key], key)

    def test_automatic_calculation_without_import_all_maxima(self):
        legacy = {key: value for key, value in self.pack.items() if key != "storage"}
        legacy["distribution_status"] = "User supplied locally; redistribution permission not established"
        with patch.object(criteria, "import_workbook", side_effect=AssertionError("Import is unnecessary")):
            for maximum in criteria.MAX_RATES:
                values = inputs(e_manual="", speed=40, radius=1824.076,
                                max_superelevation=maximum, area="urban_freeway" if maximum == 4 else "rural")
                automatic = super_service.calculate_curve(values)["results"]
                supplied = super_service.calculate_curve({**values, "aashto_tables": legacy})["results"]
                for key in automatic.keys() - {"inputs", "calculation_metadata"}:
                    self.assertEqual(automatic[key], supplied[key], (maximum, key))
                provenance = automatic["calculation_metadata"]["criteria_workbook"]
                self.assertEqual(provenance["storage"], "embedded_python")
                self.assertEqual(provenance["table_digest"], criteria.WORKBOOK_TABLE_DIGEST)
                self.assertEqual(provenance["runoff_digest"], criteria.RUNOFF_DIGEST)
                self.assertIsNone(automatic["inputs"].get("aashto_tables"))
                self.assertFalse(automatic["calculation_metadata"]["manual_overrides"]["superelevation_rate"])
                if maximum == 8:
                    self.assertEqual((automatic["e"], automatic["Lr"], automatic["Lt"]), (0.04, 84, 42))

    def test_embedded_integrity_and_request_isolation(self):
        self.assertEqual(set(self.pack["tables"]), {str(value) for value in criteria.MAX_RATES})
        self.assertEqual(hashlib.sha256(json.dumps(self.pack["runoff"], separators=(",", ":")).encode()).hexdigest(), criteria.RUNOFF_DIGEST)
        edited = criteria.built_in_tables()
        edited["tables"]["8"]["rows"][2][1] += 1
        with self.assertRaisesRegex(ValueError, "changed"):
            criteria.rate(edited, 8, 40, 1824.076, 0.02)
        self.assertEqual(criteria.built_in_tables(), self.pack)

    def test_embedded_project_round_trip_and_exports(self):
        result = super_service.calculate_curve(inputs(e_manual="", speed=40, radius=1824.076))["results"]
        curve = {"results": result, "meta": {"curve_direction": "left"}}
        original = {"version": 5, "curves": [curve]}
        project = super_project.normalize_project(json.loads(json.dumps(original)))
        saved = project["curves"][0]["results"]
        self.assertEqual(saved["calculation_metadata"], result["calculation_metadata"])
        recalculated = super_service.calculate_curve(saved["inputs"])["results"]
        self.assertEqual(super_exports.build_normalized_rows([curve]), super_exports.build_normalized_rows([{"results": recalculated, "meta": curve["meta"]}]))
        self.assertTrue(super_service.export_ord_csv([curve])["content"])
        from pypdf import PdfReader
        report = super_service.export_pdf([curve])
        text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(report["content"])).pages)
        self.assertIn("embedded_python", text)
        self.assertIn(self.pack["file_sha256"], text.replace("\n", ""))

    def test_existing_manual_inputs_and_legacy_data_are_preserved(self):
        result = super_service.calculate_curve(inputs())["results"]
        self.assertEqual((result["e"], result["Lr"], result["Lt"]), (0.06, 144, 48))
        self.assertEqual(result["calculation_metadata"]["criteria_workbook"], {})
        manifest = super_service.application_manifest()["options"]["profiles"][criteria.PROFILE_ID]
        self.assertFalse(manifest["criteria_workbook_required"])
        self.assertEqual(manifest["criteria_data_source"], "embedded_python")

    def test_every_published_radius_boundary_all_maxima(self):
        for maximum in criteria.MAX_RATES:
            table = self.pack["tables"][str(maximum)]
            for col, speed_label in enumerate(table["speeds"], 1):
                speed = int(speed_label.split("=")[1].split()[0])
                self.assertEqual(
                    criteria.rate(
                        self.pack, maximum, speed, table["rows"][0][col], 0.02
                    )[1],
                    "normal",
                )
                self.assertEqual(
                    criteria.rate(
                        self.pack, maximum, speed, table["rows"][1][col], 0.02
                    )[1],
                    "reverse",
                )
                for row in table["rows"][2:]:
                    rate, _, source = criteria.rate(
                        self.pack, maximum, speed, row[col], 0.02
                    )
                    expected = min(other[0] for other in table["rows"][2:] if other[col] <= row[col]) / 100
                    self.assertEqual(rate, expected)
                    self.assertEqual(source["mode"], "published_table_lookup")
                    self.assertEqual(source["selected_row_radius_ft"], row[col])
                distinct = sorted(set(row[col] for row in table["rows"]), reverse=True)
                for larger, smaller in zip(distinct, distinct[1:]):
                    radius = (larger + smaller) / 2
                    rate, crown, source = criteria.rate(self.pack, maximum, speed, radius, 0.02)
                    if radius >= table["rows"][1][col]:
                        self.assertEqual((rate, crown), (0.02, "reverse"))
                    else:
                        expected = min(row[0] for row in table["rows"][2:] if row[col] <= radius) / 100
                        self.assertEqual(rate, expected)
                        self.assertEqual(source["selected_row_radius_ft"], smaller)
                with self.assertRaisesRegex(ValueError, "below"):
                    criteria.rate(
                        self.pack, maximum, speed, table["rows"][-1][col] - 0.001, 0.02
                    )

    def test_all_radius_cells_against_local_source_pdf(self):
        import re
        from pypdf import PdfReader

        path = (
            Path(__file__).parent
            / "docs/AASHTO-a-Policy-on-Geometric-Design_unlocked.pdf"
        )
        if not path.exists():
            self.skipTest("Restricted source PDF is not distributed.")
        reader = PdfReader(path)
        pages = {4: [239], 6: [240], 8: [242], 10: [244, 245], 12: [246, 247]}
        for maximum, numbers in pages.items():
            count = len(self.pack["tables"][str(maximum)]["speeds"])
            source = []
            for page in numbers:
                text = reader.pages[page].extract_text()
                text = text.split("Metric", 1)[0]
                tokens = text.split()
                for i, token in enumerate(tokens):
                    if token not in {"NC", "RC"} and not re.fullmatch(
                        r"(?:[2-9]|1[0-2])\.\d", token
                    ):
                        continue
                    values = tokens[i + 1 : i + 1 + count]
                    if len(values) == count and all(
                        re.fullmatch(r"\d+", v) for v in values
                    ):
                        key = token if token in {"NC", "RC"} else float(token)
                        if isinstance(key, float) and key > maximum:
                            continue
                        row = [key, *map(int, values)]
                        if maximum == 12 and key == 5.8:
                            row[7] = 1620  # October 2019 errata, 45 mph.
                        source.append(row)
            self.assertEqual(
                source,
                self.pack["tables"][str(maximum)]["rows"],
                f"Every source cell in Table 3-{8+criteria.MAX_RATES.index(maximum)}",
            )

    def test_errata_lookup_and_edited_data_rejected(self):
        r = super_service.calculate_curve(
            inputs(e_manual="", aashto_tables=self.pack, radius="1910")
        )["results"]
        self.assertEqual(r["Lr"], 163)
        self.assertEqual(r["e"], 0.068)
        bad = copy.deepcopy(self.pack)
        bad["tables"]["8"]["rows"][2][1] += 1
        with self.assertRaisesRegex(ValueError, "changed"):
            criteria.rate(bad, 8, 60, 2000, 0.02)

    def test_green_book_published_selection_example_and_imported_curve(self):
        # Green Book §3.3.5, p. 3-41: 1870 ft uses the 1830-ft row at 5.4%.
        e, _, source = criteria.rate(self.pack, 8, 50, 1870, 0.02)
        self.assertAlmostEqual(e, 0.054, delta=1e-12)
        self.assertEqual(source["selected_row_radius_ft"], 1830)
        self.assertEqual(criteria.rate(self.pack, 8, 60, 2000, 0.02)[0], 0.068)
        r = super_service.calculate_curve(inputs(
            e_manual="", aashto_tables=self.pack, speed=40, radius=1824.076,
        ))["results"]
        self.assertEqual(r["e"], 0.04)
        self.assertEqual(r["calculation_metadata"]["calculation_sources"][0]["selected_row_radius_ft"], 1770)
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "automatic-rate.pdf"
            super_pdf.export_pdf(str(target), [{"results": r, "meta": {"curve_direction": "left"}}])
            text = " ".join(page.extract_text() for page in PdfReader(target).pages)
            self.assertIn("tabulated R=1770 ft", text)

    def test_normal_crown_needs_no_spiral_override(self):
        r = super_service.calculate_curve(
            inputs(
                e_manual="",
                aashto_tables=self.pack,
                radius=12000,
                alignment_type="spiral",
                ts=700,
                st=2300,
            )
        )["results"]
        self.assertEqual((r["e"], r["Lr"], r["Lt"]), (0, 0, 0))
        self.assertFalse(r["qa_findings"])
        self.assertFalse(r["hold_intervals"])


class LocalORDGeometryValidation(unittest.TestCase):
    def test_actual_ord_clothoid_endpoints_and_station_equation(self):
        path = (
            Path(__file__).parent.parent
            / "Road-Stationing-App/Validation/RealORD/CROSSGATES/CROSSGATES.xml"
        )
        if not path.exists():
            self.skipTest(
                "Private real ORD file is not distributed; native ORD round trip remains separate."
            )
        data = super_landxml.parse_landxml_text(path.read_text())
        self.assertEqual((len(data.spirals), len(data.curves)), (8, 4))
        self.assertEqual(data.linear_unit, "USSurveyFoot")
        station = data.start_station
        for segment in data._segments:
            if isinstance(segment, SpiralSegment):
                self.assertLess(
                    math.dist(segment.xy(segment.length), segment.end), 0.001
                )
                self.assertLess(
                    math.dist(
                        data.xy_at_station(station + segment.length), segment.end
                    ),
                    0.001,
                )
            station += segment.length
        self.assertEqual(len(data.station_equations), 1)


if __name__ == "__main__":
    unittest.main()
