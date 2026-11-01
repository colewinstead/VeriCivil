from copy import deepcopy
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from typicals import exports, model
from typicals.components import template, library
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
        p["left"][0]["params"].update(width_ft=11, slope_pct=3)
        p["left"][1]["params"].update(width_ft=4, slope_pct=-5)
        p["right"][0]["params"].update(width_ft=14, slope_pct=-1)
        result = model.solve(p)["points"]
        self.assertEqual(result["left_lane"], [-11, .33])
        self.assertAlmostEqual(result["left_shoulder"][1], .13)
        self.assertEqual(result["right_lane"], [14, -.14])

    def test_hv_cut_and_fill(self):
        p = model.starter()
        p["left"][2]["params"].update(hv=4, rise_ft=2)
        p["right"][2]["params"].update(hv=3, rise_ft=-2)
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
        p["left"][1]["paved"] = False
        layer = model.solve(p)["layers"][0]
        self.assertEqual(layer["top"][0], [-12, -.24])
        self.assertEqual(layer["top"][-1], [18, -.48])

    def test_edit_propagates_only_downstream_and_annotation_updates(self):
        p = model.starter()
        before = model.solve(p)
        p["left"][0]["params"]["width_ft"] = 11
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
        p["left"][0]["params"]["width_ft"] = 11
        original = deepcopy(p)
        with self.assertRaisesRegex(ValueError, "Constraint conflict: left_shoulder"):
            model.solve(p)
        self.assertEqual(p, original)

    def test_invalid_inputs(self):
        for value in (0, -1, math.inf, math.nan, True, "12"):
            p = model.starter()
            p["left"][0]["params"]["width_ft"] = value
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
        p["version"] = 99
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
        p["left"][0]["params"]["width_ft"] = 11
        result = drawing(p)
        texts = [v["text"] for v in result["primitives"] if v["kind"] == "text"]
        self.assertIn("TRAVEL", texts)
        self.assertIn("SHOULDER", texts)
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
        p["left"][0]["params"]["slope_pct"] = 0
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


class ComponentTests(unittest.TestCase):
    def test_v1_migration_preserves_geometry_locks_metadata_and_source(self):
        content = (FIXTURE.parent / "typicals_v1.json").read_text()
        legacy = json.loads(content)
        legacy["constraints"]["locked_points"]["left_shoulder"] = [-18, -.48]
        before = deepcopy(legacy)
        p = model.loads(json.dumps(legacy))
        self.assertEqual(legacy, before)
        self.assertEqual(p["version"], 2)
        self.assertEqual(p["metadata"], before["metadata"])
        self.assertEqual(p["drafting"], before["drafting"])
        self.assertEqual(p["constraints"], before["constraints"])
        pts = model.solve(p)["points"]
        for name, expected in {"CL": [0, 0], "left_lane": [-12, -.24], "right_lane": [12, -.24],
                               "left_shoulder": [-18, -.48], "right_shoulder": [18, -.48],
                               "left_toe": [-27, -3.48], "right_toe": [30, -3.48]}.items():
            self.assertEqual(pts[name], expected)
        self.assertEqual(model.loads(model.dumps(p)), p)

    def test_additional_lanes_propagate_downstream_without_changing_other_side(self):
        p = model.starter()
        before = model.solve(p)
        p["right"].insert(1, template("auxiliary_lane", "right_aux"))
        result = model.solve(p)
        self.assertEqual(result["points"]["right_aux"], [24, -.48])
        self.assertEqual(result["points"]["right_shoulder"], [30, -.72])
        self.assertEqual(result["points"]["right_toe"][0], 42)
        self.assertAlmostEqual(result["points"]["right_toe"][1], -3.72, places=12)
        self.assertEqual(result["points"]["left_toe"], before["points"]["left_toe"])
        self.assertIn("30' PAVED", [v.get("text") for v in drawing(p)["primitives"]])

    def test_ditch_fore_bottom_and_back_are_analytical_and_connected(self):
        p = model.starter()
        ditch = template("ditch", "drain")
        ditch["params"].update(depth_ft=3, foreslope_hv=2, bottom_width_ft=4, backslope_hv=4, back_rise_ft=1)
        p["right"] = [ditch, template("slope", "beyond_ditch")]
        result = model.solve(p)
        self.assertEqual(result["components"][-2]["paths"][0], [[0, 0], [6, -3], [10, -3], [14, -2]])
        self.assertEqual(result["components"][-1]["a"], [14, -2])
        p["left"] = [deepcopy(ditch)]
        p["left"][0]["id"] = p["left"][0]["end_point"] = "left_drain"
        self.assertEqual(model.solve(p)["points"]["left_drain"], [-14, -2])

    def test_wall_grade_step_and_barrier_footprint_have_distinct_connections(self):
        p = model.starter()
        p["right"] = [template("retaining_wall", "wall"), template("lane", "upper_lane")]
        points = model.solve(p)["points"]
        self.assertEqual(points["wall"], [1, 4])
        self.assertEqual(points["upper_lane"], [13, 3.76])
        p["right"][0]["params"]["height_ft"] = -4
        self.assertEqual(model.solve(p)["points"]["wall"], [1, -4])
        p["right"] = [template("barrier", "rail"), template("lane", "beside_barrier")]
        result = model.solve(p)
        self.assertEqual(result["points"]["rail"], [2, 0])
        self.assertEqual(result["points"]["beside_barrier"], [14, -.24])
        self.assertEqual(max(pt[1] for pt in result["components"][-2]["paths"][0]), 3.5)

    def test_curb_inch_conversion_and_sidewalk_connection(self):
        p = model.starter()
        p["right"] = [template("curb_gutter", "curb"), template("sidewalk", "walk")]
        pts = model.solve(p)["points"]
        self.assertEqual(pts["curb"], [2.5, .46])
        self.assertAlmostEqual(pts["walk"][1], .36, places=12)
        self.assertEqual(pts["walk"][0], 7.5)
        p["units"] = "us_survey_foot"
        self.assertAlmostEqual(model.solve(p)["points"]["curb"][1], -.04 + .1524 / (1200 / 3937), places=12)

    def test_custom_profile_is_relative_outward_geometry(self):
        p = model.starter()
        custom = template("custom", "profile")
        custom["points"] = [[0, 0], [2, -1], [5, 1]]
        p["left"] = [custom, template("lane", "outside_profile")]
        pts = model.solve(p)["points"]
        self.assertEqual(pts["profile"], [-5, 1])
        self.assertEqual(pts["outside_profile"], [-17, .76])
        custom["points"] = [[0, 0], [2, -1], [1, 0]]
        custom["paved"] = True
        with self.assertRaisesRegex(ValueError, "increasing offsets"):
            model.solve(p)
        custom["paved"] = False
        custom["points"] = [[0, 0], [-1, -1], [3, -1], [3, 1], [0, 0]]
        self.assertEqual(model.solve(p)["points"]["profile"], [0, 0])

    def test_pavement_runs_stop_at_median_barrier_and_wall_instead_of_bridging_gaps(self):
        for kind in ("median", "barrier", "retaining_wall"):
            p = model.starter()
            p["right"].insert(1, template(kind, "separator"))
            result = model.solve(p)
            self.assertEqual(len(result["paved_runs"]), 2)
            first, second = result["paved_runs"]
            self.assertEqual(first[-1], [12, -.24])
            self.assertGreater(second[0][0], 12)
            for a, b in zip(result["layers"][0]["runs"], result["layers"][1]["runs"]):
                self.assertEqual(a["bottom"], b["top"])
            self.assertNotIn("18' PAVED", [v["text"] for v in drawing(p)["dimensions"] if v["a"][0] >= 0])

    def test_reorder_remove_and_locked_endpoint_conflict(self):
        p = model.starter()
        p["right"][0], p["right"][1] = p["right"][1], p["right"][0]
        pts = model.solve(p)["points"]
        self.assertEqual(pts["right_shoulder"], [6, -.24])
        self.assertEqual(pts["right_lane"], [18, -.48])
        p["constraints"]["locked_points"]["right_lane"] = pts["right_lane"]
        p["right"] = p["right"][:1]
        with self.assertRaisesRegex(ValueError, "no longer exists"):
            model.solve(p)

    def test_invalid_ids_dimensions_and_version_do_not_produce_geometry(self):
        for change in (lambda p: p["right"].append(deepcopy(p["left"][0])),
                       lambda p: p["right"][0].update(end_point="CL"),
                       lambda p: p.update(version=True),
                       lambda p: p["right"].append({**template("barrier", "bad"), "params": {"width_ft": 1, "height_ft": 3, "top_width_ft": 2}})):
            p = model.starter(); change(p)
            with self.assertRaises(ValueError):
                model.solve(p)

    def test_all_library_components_draw_and_empty_section_has_no_fictitious_structure(self):
        for item in library():
            p = mapped_project()
            p["right"] = [item["template"]]
            with self.subTest(kind=item["kind"]):
                scene = drawing(p)
                self.assertTrue(scene["geometry"]["components"][-1]["paths"])
                self.assertTrue(exports.svg(p).startswith(b"<svg"))
        p = model.starter(); p["left"] = []; p["right"] = []
        self.assertEqual(model.solve(p)["paved_runs"], [])
        self.assertNotIn("STRUCTURE", [v.get("text") for v in drawing(p)["primitives"]])

    def test_component_specific_level_is_exported_and_missing_used_mapping_blocks(self):
        import ezdxf
        p = mapped_project()
        p["right"].insert(1, template("barrier", "concrete"))
        new_level = {**p["catalog"]["levels"][0], "name": "TS_TEST_BARRIER", "rgb": "#cc8833"}
        p["catalog"]["levels"].append(new_level)
        p["level_mappings"]["component:concrete"] = "TS_TEST_BARRIER"
        content, _ = exports.dxf(p)
        doc = ezdxf.read(io.StringIO(content.decode()))
        self.assertGreater(len(doc.modelspace().query('LINE[layer=="TS_TEST_BARRIER"]')), 0)
        p["level_mappings"]["component:concrete"] = "TS_MISSING"
        with self.assertRaisesRegex(ValueError, "TS_MISSING"):
            exports.dxf(p)

    def test_component_preset_roundtrip_and_malformed_presets_are_rejected(self):
        from typicals.service import dispatch
        c = template("ditch", "reusable_drain")
        c["name"] = "North roadside ditch"
        c["params"]["bottom_width_ft"] = 4.5
        saved = dispatch("component_save", json.dumps({"component": c}))
        self.assertEqual(dispatch("component_load", json.dumps(saved)), c)
        for preset in ({"format": "vericivil.typicals.component", "version": 99, "component": c},
                       {"format": "vericivil.typicals.component", "version": True, "component": c},
                       {"format": "vericivil.typicals.component", "version": 1, "component": {**c, "params": {}}}):
            with self.assertRaises(ValueError):
                dispatch("component_load", json.dumps({"content": json.dumps(preset)}))


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
