"""Independent edge-rise checks and end-to-end Case II regression coverage."""
import io
import json
from pathlib import Path
import tempfile
import unittest

import aashto_divided
import aashto_superelevation
import super_batch
import super_cross_section
import super_exports
import super_project
import super_service


def inputs(**changes):
    return {"criteria_profile": "aashto-green-book-2018-2019-10", "roadway": "divided_case_ii",
            "pc": "1000", "pt": "3000", "curve_direction": "left", "max_superelevation": 8,
            "case_ii": {side: {"speed": 65, "radius": 3000, "lane_count": 4, "lane_width": 12,
                               "initial_slope": -.02 if side == "left" else .02,
                               "pivot_offset": offset, "runoff_tangent_percent": 70}
                        for side, offset in (("left", -20), ("right", 20))}, **changes}


class CaseIITests(unittest.TestCase):
    def result(self, values=None):
        return super_service.calculate_curve(values or inputs())["results"]

    def test_acceptance_and_mirror(self):
        for direction, favorable in (("left", "left"), ("right", "right")):
            result = self.result(inputs(curve_direction=direction))
            for side, child in result["carriageways"].items():
                self.assertAlmostEqual(child["e"], .056)
                self.assertAlmostEqual(child["lane_adjustment_factor"], .625)
                self.assertAlmostEqual(child["Lr"], 216 if side == favorable else 336)
                self.assertAlmostEqual(child["Lt"], 0 if side == favorable else 120)
            self.assertNotIn("e", result)  # There is no aggregate carriageway rate.

    def test_independent_inputs_and_edge_gradients(self):
        values = inputs()
        values["case_ii"]["left"].update(lane_count=3, lane_width=11, speed=55, radius=2200)
        values["case_ii"]["right"].update(lane_count=5, lane_width=13, speed=70, radius=4000)
        result = self.result(values)
        self.assertNotEqual(result["carriageways"]["left"]["e"], result["carriageways"]["right"]["e"])
        for side, child in result["carriageways"].items():
            count = values["case_ii"][side]["lane_count"]
            effective_width = values["case_ii"][side]["lane_width"] * (1 + .5 * (count - 1))
            change = child["e"] - .02 if side == "left" else child["e"]
            self.assertAlmostEqual(child["Lr"], effective_width * change / .005)
            for lane in child["section_lanes"]:
                for a, b in zip(lane["events"], lane["events"][1:]):
                    distance = b["station_ft"] - a["station_ft"]
                    for edge in ("left_elevation_ft", "right_elevation_ft"):
                        if distance:
                            self.assertLessEqual(abs(b[edge] - a[edge]) / distance, .005 / child["lane_adjustment_factor"] + 1e-10)

    def test_all_supported_lane_counts_use_unrounded_factor(self):
        for count in range(1, 8):
            values = inputs()
            values["case_ii"]["left"].update(lane_count=count, initial_slope=-.015)
            child = self.result(values)["carriageways"]["left"]
            self.assertAlmostEqual(child["lane_adjustment_factor"], (1 + .5 * (count - 1)) / count)
            self.assertAlmostEqual(child["Lr"], 12 * (1 + .5 * (count - 1)) * (.056 - .015) / .005)
            source = next(item for item in child["calculation_metadata"]["calculation_sources"] if item["component"] == "Lane adjustment")
            self.assertEqual(source["mode"], "formula_derived" if count > 3.5 else "calculated")

    def test_geometry_and_level_pivots_at_every_breakpoint(self):
        result = self.result()
        for station in sorted({event["station_ft"] for lane in result["section_lanes"] for event in lane["events"]}):
            packet = super_service.diagram_lookup(result, "left", station)
            self.assertEqual([pivot["y"] for pivot in packet["cross_section"]["pivots"]], [0, 0])
            for side, offset in (("left", 20), ("right", -20)):
                segments = [item for item in packet["cross_section"]["segments"] if item["side"] == side]
                near = min((item[edge] for item in segments for edge in ("left", "right")), key=lambda edge: abs(edge["x"] - offset))
                self.assertEqual(near["x"], offset)
                self.assertAlmostEqual(near["y"], 0)
            segments = packet["cross_section"]["segments"]
            for a, b in zip(segments, segments[1:]):
                if a["side"] == b["side"]:
                    self.assertEqual(a["right"], b["left"])
        model = super_cross_section.section_model(result, "left")
        self.assertEqual(model["bounds"]["x_min"], -68)
        self.assertEqual(model["bounds"]["x_max"], 68)
        self.assertEqual(model["median_gap_ft"], 40)

    def test_invalid_sides_are_atomic(self):
        for side, key, value in (("left", "pivot_offset", ""), ("right", "lane_count", 8),
                                 ("left", "lane_width", -1), ("right", "initial_slope", .025),
                                 ("right", "speed", "nan"), ("left", "radius", 0)):
            values = inputs()
            values["case_ii"][side][key] = value
            with self.subTest(side=side, key=key), self.assertRaisesRegex(ValueError, f"{side.title()} carriageway"):
                self.result(values)
        values = inputs()
        values["case_ii"]["left"]["pivot_offset"] = 30
        with self.assertRaisesRegex(ValueError, "left carriageway pivot"):
            self.result(values)

    def test_nc_rc_and_retained_sections(self):
        values = inputs()
        for side in ("left", "right"):
            values["case_ii"][side]["radius"] = 20000
        result = self.result(values)
        self.assertTrue(result["no_transition_required"])
        for child in result["carriageways"].values():
            self.assertEqual(child["Lr"], 0)
            self.assertEqual(child["Lt"], 0)
        for side in ("left", "right"):
            values["case_ii"][side]["radius"] = 10000
        result = self.result(values)
        self.assertEqual(result["carriageways"]["left"]["Lr"], 0)
        self.assertGreater(result["carriageways"]["right"]["Lt"], 0)

    def test_length_check_and_spiral_anchors(self):
        values = inputs()
        check = super_service.required_spiral_lengths(values)
        self.assertEqual(check["result_type"], "spiral_length_check")
        self.assertAlmostEqual(check["carriageways"]["right"]["minimum_spiral_in_spiral_ft"], 456)
        values.update(alignment_type="spiral", ts="500", st="3500")
        for side in ("left", "right"):
            values["case_ii"][side]["runout_placement"] = "in_spiral"
        result = self.result(values)
        for child in result["carriageways"].values():
            self.assertEqual(child["full_super_ft"], 1000)
            self.assertEqual(child["full_super_out_ft"], 3000)
        values["ts"] = "900"
        with self.assertRaisesRegex(ValueError, "spiral"):
            self.result(values)

    def test_offsets_position_geometry_without_changing_lengths(self):
        first = self.result()
        values = inputs()
        values["case_ii"]["left"]["pivot_offset"] = -35
        values["case_ii"]["right"]["pivot_offset"] = 5
        shifted = self.result(values)
        self.assertEqual(shifted["pivot_offset_convention"], "right_positive")
        self.assertEqual(shifted["pivots"]["left"]["x"], 35)
        self.assertEqual(shifted["pivots"]["right"]["x"], -5)
        for side in ("left", "right"):
            for key in ("e", "Lr", "Lt"):
                self.assertEqual(first["carriageways"][side][key], shifted["carriageways"][side][key])
            values["case_ii"][side]["pivot_offset"] = ""
        check = super_service.required_spiral_lengths(values)
        self.assertEqual(check["pivots"], {})
        self.assertIsNone(check["median_gap_ft"])
        with self.assertRaisesRegex(ValueError, "Pivot offset"):
            self.result(values)

    def test_users_spiral_example_uses_each_speed_and_reports_actual_shortfall(self):
        values = inputs(pc="12+00", pt="14+00", ts="10+00", st="20+00", alignment_type="spiral")
        for side, radius in (("left", 4000), ("right", 2978)):
            values["case_ii"][side].update(lane_count=2, radius=radius, pivot_offset=-12 if side == "left" else 12,
                                          runout_placement="in_spiral", acknowledge_spiral_override=True)
        with self.assertRaisesRegex(ValueError, "Right carriageway: Entry spiral: 200.000 ft available; 273.600 ft required"):
            self.result(values)

    def test_project_roundtrip_stale_results_and_ord_block(self):
        result = self.result()
        project = super_project.normalize_project(json.loads(super_service.project_save({"version": 6, "vars": inputs(), "curves": [{"results": result}]})))
        self.assertEqual(project["version"], 6)
        aashto_divided.validate_curves(project["curves"])
        with self.assertRaisesRegex(ValueError, "Case II ORD CSV"):
            super_exports.write_ord_csv(io.StringIO(), project["curves"])
        project["curves"][0]["results"]["carriageways"]["left"]["Lr"] += 1
        with self.assertRaisesRegex(ValueError, "recalculate"):
            aashto_divided.validate_curves(project["curves"])
        old = super_project.normalize_project({"version": 5, "vars": {"roadway": "one_way"}, "curves": []})
        self.assertEqual(old["vars"]["roadway"], "one_way")
        self.assertNotIn("case_ii", old["vars"])
        import super_app
        legacy_project = {**project, "vars": {"roadway": "two_way"}, "curves": [{"results": None}, *project["curves"]]}
        with self.assertRaisesRegex(ValueError, "Legacy Tkinter cannot edit or export"):
            super_app.ModernSuperElevationUI._apply_project(object(), legacy_project)

    def test_same_side_conflicts_and_compound_exclusion(self):
        a = {"results": self.result(), "meta": {"curve_direction": "left"}}
        b = {"results": self.result(inputs(pc="3000", pt="5000")), "meta": {"curve_direction": "left"}}
        self.assertEqual(super_batch.compound_pairs([a, b]), [])
        with self.assertRaisesRegex(ValueError, "carriageway transition intervals overlap"):
            aashto_divided.validate_curves([a, b])
        aashto_divided.validate_curves([a])  # Opposing sides may overlap in station.

    def test_station_equations_and_tangent_boundary(self):
        values = inputs(station_equations="1500=2500")
        result = self.result(values)
        self.assertTrue(super_service.diagram_lookup(result, "left", "2600")["station"])
        with self.assertRaisesRegex(ValueError, "alignment"):
            self.result(inputs(alignment_station_range=[900, 4000]))

    def test_reports_and_dxf_consume_pair(self):
        result = self.result()
        curves = [{"results": result, "meta": {"curve_name": "Synthetic Case II", "curve_direction": "left"}}]
        with tempfile.TemporaryDirectory() as directory:
            import super_dxf
            import super_pdf
            pdf, dxf = Path(directory) / "case.pdf", Path(directory) / "case.dxf"
            super_pdf.export_pdf(str(pdf), curves)
            super_dxf.export_detail_dxf(dxf, curves)
            self.assertGreater(pdf.stat().st_size, 1000)
            text = dxf.read_text(encoding="cp1252")
            self.assertIn("Case II left carriageway", text)
            self.assertIn("Case II right carriageway", text)

    def test_landxml_batch_qa_and_overlay_keep_design_radii_separate(self):
        source = (Path("tests/fixtures/reverse_spacing_synthetic.xml").read_text()
                  .replace('length="20"', 'length="500"').replace("520 1000", "1000 1000")
                  .replace("520 1500", "1000 1500").replace("1020", "1500")
                  .replace("2590.796326794897", "3070.796326794897"))
        values = inputs()
        for side, rate in (("left", .024), ("right", .022)):
            values["case_ii"][side].update(lane_count=1, initial_slope=-.02, e_manual=rate)
        following = {"case_ii": {side: {**definition, "radius": 3500} for side, definition in values["case_ii"].items()}}
        curves = super_service.build_all_landxml_curves(source, "synthetic.xml", values, curve_inputs={"1": following})
        self.assertEqual(len(curves), 2)
        self.assertEqual(float(curves[0]["results"]["inputs"]["radius"]), 500)
        self.assertEqual(curves[0]["results"]["carriageways"]["right"]["inputs"]["radius_ft"], 3000)
        report = super_service.corridor_qa(source, "synthetic.xml", curves)
        self.assertFalse([finding for finding in report["findings"] if finding["severity"] == "block"], report["findings"])
        aashto_divided.validate_curves(curves)
        response = super_service.export_overlay_dxf(curves, super_project.make_landxml_source("synthetic.xml", source))
        self.assertTrue(response)
        tampered = json.loads(json.dumps(curves))
        tampered[0]["results"]["inputs"]["radius"] = 501
        with self.assertRaisesRegex(ValueError, "recalculate"):
            aashto_divided.validate_curves(tampered)


if __name__ == "__main__":
    unittest.main()
