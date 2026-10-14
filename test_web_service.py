from __future__ import annotations

import json
import copy
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import super_project
import super_service
import super_landxml
from commercial_entitlements import LocalDevelopmentEntitlementProvider, Plan


FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "sr82_synthetic.xml"


class WebServiceTests(unittest.TestCase):
    def test_compound_presets_identify_neighbors_for_browser_preview(self):
        fixture = FIXTURE.parent / "compound_synthetic.xml"
        parsed = super_service.parse_landxml(fixture.read_text(), fixture.name)
        presets = parsed["curve_presets"]
        self.assertIn(1, presets[0]["compound_neighbor_indexes"])
        self.assertIn(0, presets[1]["compound_neighbor_indexes"])

    def test_method_notes_are_not_warnings_but_real_warnings_survive(self):
        response = super_service.present_results({**super_service.calculate_curve(self.inputs())["results"],
            "warnings": ["One-way carriageway uses unadjusted relative gradient; no multilane runoff reduction is assumed for ramps.",
                         "Project compound exit: 2% to 2% over 0.000 ft; existing runoff rate retained.",
                         "Manual rate: published radius/rate applicability must be independently verified."]})
        self.assertEqual(response["results"]["warnings"], ["Manual rate: published radius/rate applicability must be independently verified."])

    def pro_payload(self, payload: dict) -> dict:
        return {
            **payload,
            "entitlement": LocalDevelopmentEntitlementProvider(Plan.PRO).snapshot().as_dict(),
        }

    def inputs(self) -> dict:
        return {
            "pc": "10+00",
            "pt": "12+00",
            "speed": "45",
            "radius": "1000",
            "facility": "centerline",
            "area": "rural",
            "lane_width": "12",
            "lanes_rotated": "2",
            "normal_crown": "0.02",
            "curve_direction": "right",
        }

    def test_browser_calculation_uses_shared_engine_and_lane_rows(self):
        response = super_service.calculate_curve(self.inputs())
        self.assertEqual(response["results"]["inputs"]["speed_mph"], 45.0)
        self.assertTrue(response["lanes"]["left"])
        self.assertTrue(response["lanes"]["right"])
        self.assertEqual(
            response["results"]["calculation_metadata"]["engine_version"],
            super_service.CALCULATION_ENGINE_VERSION,
        )

    def test_landxml_is_embedded_with_integrity_hash(self):
        content = FIXTURE.read_text(encoding="utf-8")
        parsed = super_service.parse_landxml(content, FIXTURE.name)
        self.assertEqual(parsed["source"]["filename"], FIXTURE.name)
        self.assertEqual(len(parsed["source"]["sha256"]), 64)
        self.assertGreater(parsed["summary"]["curve_count"], 0)
        self.assertEqual(parsed["summary"]["coordinate_system"]["status"], "recognized")
        self.assertEqual(parsed["summary"]["coordinate_system"]["code"], "6507")
        self.assertTrue(parsed["summary"]["coordinate_system"]["preserve_xy"])

    def test_schema_v5_project_round_trip_embeds_landxml_and_pairs(self):
        content = FIXTURE.read_text(encoding="utf-8")
        source = super_project.make_landxml_source(FIXTURE.name, content)
        serialized = super_service.project_save({
            "version": 5,
            "vars": self.inputs(),
            "landxml_source": source,
            "excluded_landxml_curve_indexes": [1],
            "curves": [{}, {}],
            "reverse_curve_pairs": [[0, 1]],
        })
        loaded = super_service.project_load(serialized)
        self.assertEqual(loaded["project"]["version"], 5)
        self.assertEqual(loaded["project"]["landxml_source"]["sha256"], source["sha256"])
        self.assertEqual(loaded["landxml"]["source"]["content"], content)
        self.assertEqual(loaded["project"]["excluded_landxml_curve_indexes"], [1])
        self.assertEqual(loaded["project"]["reverse_curve_pairs"], [[0, 1]])

    def test_embedded_landxml_hash_mismatch_is_refused(self):
        with self.assertRaisesRegex(super_project.ProjectFormatError, "integrity"):
            super_project.normalize_project({
                "version": 5,
                "landxml_source": {"filename": "a.xml", "encoding": "utf-8", "sha256": "0" * 64, "content": "<LandXML />"},
            })

    def test_schema_v4_infers_disjoint_pairs_without_recalculating_results(self):
        recorded = {
            "calculation_metadata": {"engine_version": "1.2.1"},
            "reverse_curve_coordination": {
                "checks": [{"paired_curve_indexes": [0, 1], "status": "coordinated"}],
            },
        }
        loaded = super_project.normalize_project({
            "version": 4,
            "vars": {"coordinate_reverse_curves": True},
            "curves": [
                {"results": recorded},
                {"results": {"recorded_value": 123.456}},
            ],
        })
        self.assertEqual(loaded["version"], 5)
        self.assertEqual(loaded["source_version"], 4)
        self.assertEqual(loaded["reverse_curve_pairs"], [[0, 1]])
        self.assertNotIn("coordinate_reverse_curves", loaded["vars"])
        self.assertEqual(loaded["curves"][0]["results"], recorded)
        self.assertEqual(loaded["curves"][1]["results"]["recorded_value"], 123.456)

    def test_schema_v5_rejects_overlapping_pair_chain(self):
        with self.assertRaisesRegex(super_project.ProjectFormatError, "more than one"):
            super_project.normalize_project({
                "version": 5,
                "curves": [{}, {}, {}],
                "reverse_curve_pairs": [[0, 1], [1, 2]],
            })

    def test_safe_dispatch_returns_friendly_project_error_without_traceback(self):
        response = super_service.dispatch_safe("project_load", json.dumps(self.pro_payload({"content": ""})))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["type"], "ProjectFormatError")
        self.assertIn("not valid JSON", response["error"]["message"])
        self.assertNotIn("Traceback", response["error"]["message"])

    def test_browser_exports_are_generated_in_memory(self):
        response = super_service.calculate_curve(self.inputs())
        curve = {"results": response["results"], "meta": {"curve_direction": "right"}, "notes": ""}
        csv_result = super_service.export_ord_csv([curve])
        pdf_result = super_service.export_pdf([curve])
        dxf_result = super_service.export_detail_dxf([curve])
        self.assertIn("SuperelevationLane", csv_result["content"])
        self.assertTrue(pdf_result["content"].startswith(b"%PDF"))
        self.assertIn(b"SECTION", dxf_result["content"])

    def test_lookup_returns_descriptive_display_labels(self):
        results = super_service.calculate_curve(self.inputs())["results"]
        station = super_service.lookup(results, "right", "10+50", "")
        slope = super_service.lookup(results, "right", "", str(results["e"] * 100))
        self.assertIn("decimal", station["station"]["slopes"]["left"])
        self.assertEqual(slope["slope"]["decimal"], "+0.0800")
        self.assertEqual(slope["lanes"]["left"][0]["label"], "Full-super range")

    def test_browser_dispatch_exposes_diagram_and_corridor_qa(self):
        content = FIXTURE.read_text(encoding="utf-8")
        curves = super_service.build_all_landxml_curves(content, FIXTURE.name, self.inputs())
        diagram = super_service.dispatch("curve_diagram", json.dumps({
            "results": curves[0]["results"], "direction": curves[0]["meta"]["curve_direction"],
        }))
        qa = super_service.dispatch(
            "corridor_qa",
            json.dumps(self.pro_payload({"content": content, "filename": FIXTURE.name, "curves": curves})),
        )
        self.assertTrue(diagram["profiles"]["left"])
        self.assertEqual(qa["status"], "pass")

    def test_landxml_selection_skips_blocked_curves_and_keeps_source_identity(self):
        root = ET.fromstring(FIXTURE.read_text(encoding="utf-8"))
        root.find(".//{*}Curve").set("radius", "400")
        content = ET.tostring(root, encoding="unicode")
        inputs = {**self.inputs(), "criteria_profile": "aashto-green-book-2018-2019-10",
                  "lane_widths": "12,12", "runoff_tangent_percent": "50"}
        with self.assertRaisesRegex(ValueError, "below Table"):
            super_service.build_all_landxml_curves(content, FIXTURE.name, inputs)
        curves = super_service.dispatch("build_all_landxml_curves", json.dumps(self.pro_payload({
            "content": content, "shared_inputs": inputs, "excluded_curve_indexes": [0],
        })))
        self.assertEqual(len(curves), 1)
        self.assertEqual(curves[0]["meta"]["landxml_curve_index"], 1)
        self.assertEqual(curves[0]["meta"]["landxml_curve_id"], "curve-2")
        report = super_service.corridor_qa(content, FIXTURE.name, curves, [0], inputs)
        self.assertEqual(report["status"], "pass")
        with self.assertRaises(ValueError) as blocked:
            super_service.build_all_landxml_curves(content, FIXTURE.name,
                                                 {**inputs, "runoff_tangent_percent": "100"}, [0])
        self.assertTrue(blocked.exception.findings)
        self.assertTrue(all(finding["curve_indexes"] == [1] for finding in blocked.exception.findings))
        with self.assertRaisesRegex(ValueError, "below Table"):
            super_service.build_all_landxml_curves(content, FIXTURE.name, inputs, [1])
        for excluded in ([0, 1], [-1], [2], [True], "0"):
            with self.subTest(excluded=excluded), self.assertRaises(ValueError):
                super_service.build_all_landxml_curves(content, FIXTURE.name, inputs, excluded)

    def test_multiple_landxml_alignments_keep_geometry_qa_exports_and_saved_selection(self):
        root = ET.fromstring(FIXTURE.read_text(encoding="utf-8"))
        alignment = root.find(".//{*}Alignment")
        second = copy.deepcopy(alignment)
        second.set("name", "Ramp B")
        second.set("staStart", "50000")
        for point in second.iter():
            if point.tag.rsplit("}", 1)[-1] in {"Start", "End", "Center"}:
                north, east, z = map(float, point.text.split())
                point.text = f"{north + 10000} {east + 20000} {z}"
        ET.SubElement(alignment, "{http://www.landxml.org/schema/LandXML-1.2}Superelevation", {"name": "First only"})
        root.find(".//{*}Alignments").append(second)
        content = ET.tostring(root, encoding="unicode")
        payload = self.pro_payload({"content": content, "alignment_index": 1})
        parsed = super_service.dispatch("parse_landxml", json.dumps(payload))
        self.assertEqual([a["alignment_name"] for a in parsed["alignments"]], ["SR 82", "Ramp B"])
        self.assertEqual(parsed["summary"]["start_station"], 50000)
        data = super_landxml.parse_landxml_text(content, alignment_index=1)
        self.assertEqual(data.superelevation_nodes, [])
        curves = super_service.dispatch("build_all_landxml_curves", json.dumps({**payload, "shared_inputs": self.inputs()}))
        self.assertTrue(all(c["meta"]["alignment_name"] == "Ramp B" for c in curves))
        report = super_service.dispatch("corridor_qa", json.dumps({**payload, "curves": curves}))
        self.assertEqual(report["status"], "pass")
        preview = super_service.dispatch("plan_view", json.dumps({**payload, "curves": curves}))
        self.assertEqual(preview["alignment_name"], "Ramp B")
        self.assertFalse(preview["errors"])
        self.assertIn(b"SECTION", super_service.export_overlay_dxf(curves, parsed["source"])["content"])
        saved = super_service.project_save({"version": 5, "vars": self.inputs(), "curves": curves, "landxml_source": parsed["source"]})
        restored = super_service.project_load(saved)["landxml"]
        self.assertEqual(restored["source"]["alignment_index"], 1)
        self.assertEqual(restored["summary"]["alignment_name"], "Ramp B")
        self.assertEqual(restored["source"]["content"], content)
        for index in (-1, 2, True, "1"):
            with self.subTest(index=index), self.assertRaises(ValueError):
                super_service.parse_landxml(content, alignment_index=index)

    def test_present_results_accepts_pyodide_omitted_optional_values(self):
        results = self.calculate_results_without_none_values()
        presented = super_service.present_results(results, "right")
        self.assertTrue(presented["lanes"]["left"])

    def calculate_results_without_none_values(self) -> dict:
        results = super_service.calculate_curve(self.inputs())["results"]
        return {key: value for key, value in results.items() if value is not None}


if __name__ == "__main__":
    unittest.main()
