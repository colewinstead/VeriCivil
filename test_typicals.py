from copy import deepcopy
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from typicals import exports, model
from typicals.drawing import drawing
from typicals.workspace import import_report, mapping_issues, validate_catalog
import vericivil_service

FIXTURE = Path(__file__).parent / "tests/fixtures/typicals_synthetic_levels.csv"


def mapped_project():
    p = model.starter()
    p["catalog"] = import_report(FIXTURE.read_text(), "Synthetic test fixture; NOT MDOT", "test-v1")
    p["level_mappings"] = {r: "TS_TEST_GEOMETRY" for r in model.ROLES}
    p["level_mappings"].update(ground="TS_TEST_GROUND", dimension_text="TS_TEST_ANNOTATION")
    return p


class GeometryTests(unittest.TestCase):
    def test_rural_starter_analytical_coordinates(self):
        result = model.solve(model.starter())
        self.assertEqual(result["points"]["left_lane"], [-12, -.24])
        self.assertEqual(result["points"]["right_shoulder"], [18, -.48])
        self.assertEqual(result["points"]["left_toe"], [-27, -3.48])
        self.assertEqual(result["points"]["right_toe"], [30, -3.48])

    def test_signed_outward_slopes_and_asymmetric_sections(self):
        p = model.starter()
        p["left"].update(lane_width_ft=11, lane_slope_pct=3, shoulder_width_ft=4, shoulder_slope_pct=-5)
        p["right"].update(lane_width_ft=14, lane_slope_pct=-1)
        result = model.solve(p)["points"]
        self.assertEqual(result["left_lane"], [-11, .33])
        self.assertAlmostEqual(result["left_shoulder"][1], .13)
        self.assertEqual(result["right_lane"], [14, -.14])

    def test_hv_cut_and_fill(self):
        p = model.starter()
        p["left"].update(roadside_hv=4, roadside_height_ft=2)
        p["right"].update(roadside_hv=3, roadside_height_ft=-2)
        pts = model.solve(p)["points"]
        self.assertEqual(pts["left_toe"], [-26, 1.52])
        self.assertEqual(pts["right_toe"], [24, -2.48])

    def test_layers_are_continuous_and_increments_not_cumulative(self):
        layers = model.solve(model.starter())["layers"]
        self.assertEqual(layers[0]["bottom"], layers[1]["top"])
        for a, b in zip(layers[1]["top"], layers[1]["bottom"]):
            self.assertEqual(a[0], b[0])
            self.assertAlmostEqual(a[1] - b[1], 8 / 12)
        self.assertAlmostEqual(layers[-1]["bottom"][2][1], -11 / 12)

    def test_survey_foot_uses_exact_international_inch_conversion(self):
        p = model.starter()
        p["units"] = "us_survey_foot"
        result = model.solve(p)
        self.assertAlmostEqual(result["layers"][0]["depth_ft"], .0762 / (1200 / 3937), places=14)
        self.assertNotEqual(result["layers"][0]["depth_ft"], .25)

    def test_unpaved_shoulders_excluded_from_pavement_structure(self):
        p = model.starter()
        p["left"]["shoulder_paved"] = False
        layer = model.solve(p)["layers"][0]
        self.assertEqual(layer["top"][0], [-12, -.24])
        self.assertEqual(layer["top"][-1], [18, -.48])

    def test_edit_propagates_only_downstream_and_annotation_updates(self):
        p = model.starter()
        before = model.solve(p)
        p["left"]["lane_width_ft"] = 11
        after = model.solve(p)
        self.assertEqual(after["points"]["left_shoulder"][0], -17)
        self.assertAlmostEqual(after["points"]["left_shoulder"][1], -.46, places=12)
        self.assertEqual(after["points"]["right_toe"], before["points"]["right_toe"])
        texts = [v["text"] for v in drawing(p)["primitives"] if v["kind"] == "text"]
        self.assertIn("11'", texts)
        p["layers"][0]["thickness_in"] = 6
        self.assertAlmostEqual(model.solve(p)["layers"][-1]["depth_ft"], 14 / 12)

    def test_locked_point_conflict_is_rejected_without_mutation(self):
        p = model.starter()
        p["constraints"]["locked_points"]["left_shoulder"] = [-18, -.48]
        model.solve(p)
        p["left"]["lane_width_ft"] = 11
        original = deepcopy(p)
        with self.assertRaisesRegex(ValueError, "Constraint conflict: left_shoulder"):
            model.solve(p)
        self.assertEqual(p, original)

    def test_invalid_inputs(self):
        for value in (0, -1, math.inf, math.nan, True, "12"):
            p = model.starter()
            p["left"]["lane_width_ft"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                model.solve(p)
        p = model.starter()
        p["ground"].reverse()
        with self.assertRaisesRegex(ValueError, "increasing"):
            model.solve(p)
        p = model.starter()
        p["constraints"]["connections"] = []
        with self.assertRaisesRegex(ValueError, "Only named-point"):
            model.solve(p)

    def test_project_fidelity_and_schema_rejection(self):
        p = mapped_project()
        p["origin"] = [300, 150]
        p["annotations"]["slope_left_lane"] = [1.5, 2.3]
        p["constraints"]["locked_points"]["CL"] = p["origin"][:]
        p["presentation"] = {"future_user_metadata": "preserved"}
        self.assertEqual(model.loads(model.dumps(p)), p)
        p["version"] = 2
        with self.assertRaisesRegex(ValueError, "version 1"):
            model.loads(json.dumps(p))

    def test_print_settings_do_not_change_geometry_or_cad_styles(self):
        p = mapped_project()
        before = drawing(p)
        p["print"].update(monochrome=False, width_in=24, lineweights_mm={"surface": .7})
        after = drawing(p)
        self.assertEqual(before["geometry"], after["geometry"])
        self.assertEqual(before["styles"], after["styles"])
        self.assertEqual(before["primitives"], after["primitives"])

    def test_dot_drawing_hierarchy_uses_computed_dimensions_and_layer_anchors(self):
        p = model.starter()
        p["left"]["lane_width_ft"] = 11
        result = drawing(p)
        texts = [v["text"] for v in result["primitives"] if v["kind"] == "text"]
        self.assertIn("TRAVEL", texts)
        self.assertIn("SHLDR", texts)
        self.assertIn("17' PAVED", texts)
        self.assertIn("23'", texts)
        self.assertIn("35'", texts)
        self.assertIn("STRUCTURE", texts)
        self.assertIn('11"', texts)
        dimensions = {v["id"]: v for v in result["dimensions"]}
        self.assertLess(dimensions["dim_left_lane"]["y"], dimensions["dim_paved_left"]["y"])
        self.assertLess(dimensions["dim_paved_left"]["y"], dimensions["dim_carriageway"]["y"])
        self.assertLess(dimensions["dim_carriageway"]["y"], dimensions["dim_total"]["y"])
        self.assertGreater(sum(v["kind"] == "polygon" for v in result["primitives"]), 10)
        p["left"]["lane_slope_pct"] = 0
        self.assertIn("0%", [v.get("text") for v in drawing(p)["primitives"]])


class WorkspaceTests(unittest.TestCase):
    def test_import_retains_real_report_columns_without_guessing(self):
        p = mapped_project()
        level = p["catalog"]["levels"][0]
        self.assertEqual(level["bylevel_color"], "3")
        self.assertEqual(level["rgb"], "#00aa66")
        self.assertEqual(level["lineweight_mm"], .35)
        self.assertEqual(mapping_issues(p), [])
        self.assertEqual(import_report(json.dumps(p["catalog"]), "unused", "unused"), p["catalog"])

    def test_missing_levels_or_unresolved_symbology_block_export(self):
        p = model.starter()
        self.assertGreater(len(mapping_issues(p)), 0)
        with self.assertRaisesRegex(ValueError, "DXF blocked"):
            exports.dxf(p)
        p = mapped_project()
        p["level_mappings"]["ground"] = "TS_MISSING"
        self.assertTrue(any("TS_MISSING" in v for v in mapping_issues(p)))
        p = mapped_project()
        p["catalog"]["levels"][0]["rgb"] = None
        self.assertTrue(any("unresolved" in v for v in mapping_issues(p)))

    def test_bentley_raw_indexed_values_remain_unresolved(self):
        report = "Name,Description,ByLevelColor,ByLevelWeight,ByLevelStyle\nTS_TEST_ONLY,Fixture,200,2,0\n"
        catalog = import_report(report, "Synthetic", "1")
        self.assertIsNone(catalog["levels"][0]["rgb"])
        self.assertIsNone(catalog["levels"][0]["lineweight_mm"])
        self.assertIsNone(catalog["levels"][0]["dash_ft"])

    def test_duplicate_non_ts_bad_style_and_unsupported_weight_rejected(self):
        for change in (lambda c: c["levels"].append(c["levels"][0].copy()),
                       lambda c: c["levels"][0].update(name="NOT_TS"),
                       lambda c: c["levels"][0].update(lineweight_mm=.34),
                       lambda c: c["levels"][0].update(dash_ft=[1, 2])):
            catalog = mapped_project()["catalog"]
            change(catalog)
            with self.assertRaises(ValueError):
                validate_catalog(catalog)

    def test_read_only_inventory_distinguishes_references_and_binary(self):
        from scripts.inventory_typicals_workspace import inventory
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "x.tbl").write_text("IN_LEVEL = TS_TEST_REFERENCE")
            (root / "x.dgnlib").write_bytes(b"Binary TS_NOT_A_LEVEL")
            before = (root / "x.dgnlib").read_bytes()
            result = inventory(root)
            self.assertEqual(result["file_count"], 2)
            self.assertEqual([v["name"] for v in result["catalog"]["levels"]], ["TS_TEST_REFERENCE"])
            self.assertEqual(result["catalog"]["extraction_status"], "name-references-only")
            self.assertEqual((root / "x.dgnlib").read_bytes(), before)


class ExportTests(unittest.TestCase):
    def test_dxf_coordinates_units_layers_dimensions_and_bylevel(self):
        import ezdxf
        for unit, code in (("international_foot", 2), ("us_survey_foot", 21)):
            p = mapped_project()
            p["units"] = unit
            content, report = exports.dxf(p)
            doc = ezdxf.read(io.StringIO(content.decode()))
            self.assertEqual(doc.header["$INSUNITS"], code)
            self.assertEqual(doc.audit().errors, [])
            line = list(doc.modelspace().query("LINE"))[0]
            self.assertEqual(tuple(line.dxf.start), (0, 0, 0))
            self.assertEqual(tuple(line.dxf.end), (-12, -.24, 0))
            self.assertEqual(line.dxf.layer, "TS_TEST_GEOMETRY")
            self.assertEqual(line.dxf.color, 256)
            self.assertEqual(line.dxf.lineweight, -1)
            self.assertEqual(doc.layers.get("TS_TEST_GEOMETRY").rgb, (0, 170, 102))
            self.assertEqual(doc.layers.get("TS_TEST_GEOMETRY").dxf.lineweight, 35)
            dims = list(doc.modelspace().query("DIMENSION"))
            self.assertEqual(len(dims), 8)
            self.assertAlmostEqual(dims[0].get_measurement(), 12)
            self.assertEqual(report["entities"]["DIMENSION"], 8)
            self.assertEqual(report["insunits"], code)
            self.assertTrue(all(v.dxf.layer.startswith("TS_") for v in doc.modelspace()))
            self.assertEqual(doc.layers.get("TS_TEST_GROUND").dxf.linetype[:3], "VC_")

    def test_svg_pdf_physical_dimensions_and_vector_content(self):
        from pypdf import PdfReader
        p = model.starter()
        raw = exports.svg(p)
        svg = ET.fromstring(raw)
        self.assertEqual(svg.attrib["width"], "17in")
        self.assertEqual(svg.attrib["height"], "11in")
        self.assertEqual(svg.attrib["viewBox"], "0 0 1224 792")
        self.assertGreater(len(svg.findall("{http://www.w3.org/2000/svg}line")), 50)
        self.assertNotIn(b"<image", raw)
        self.assertNotIn(b"#68dfc2", raw)
        p["print"]["monochrome"] = False
        self.assertIn(b"#68dfc2", exports.svg(p))
        page = PdfReader(io.BytesIO(exports.pdf(p))).pages[0]
        self.assertEqual(float(page.mediabox.width), 1224)
        self.assertEqual(float(page.mediabox.height), 792)
        self.assertEqual(len(page.images), 0)
        self.assertIn("TYPICAL SECTION", page.extract_text())
        self.assertIn("12'", page.extract_text())

    def test_sheet_overflow_and_unicode_are_explicit(self):
        p = model.starter()
        p["drafting"]["scale_ft_per_in"] = 1
        with self.assertRaisesRegex(ValueError, "exceeds"):
            exports.pdf(p)
        p = model.starter()
        p["metadata"]["title"] = "道路"
        with self.assertRaisesRegex(ValueError, "Western text"):
            exports.pdf(p)
        self.assertIn("道路", exports.svg(p).decode())

    def test_shared_dispatch_and_errors(self):
        result = vericivil_service.dispatch_safe("typicals", "starter")
        self.assertTrue(result["ok"])
        drawn = vericivil_service.dispatch_safe("typicals", "draw", json.dumps({"project": result["result"]}))
        self.assertEqual(drawn["result"]["geometry"]["points"]["left_lane"], [-12, -.24])
        self.assertFalse(vericivil_service.dispatch_safe("typicals", "dxf", json.dumps({"project": result["result"]}))["ok"])


if __name__ == "__main__":
    unittest.main()
