from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import Super
from app_info import APP_VERSION, CALCULATION_ENGINE_VERSION
import super_batch
import super_pdf
import tdot_criteria


class PdfReportTests(unittest.TestCase):
    def mdot_curve(self, name: str = "Curve 1", *, notes: str = "Synthetic test data only", e_manual: str = "") -> dict:
        results = Super.calculate_superelevation(
            "120+00", "140+00", "45", "1200", "centerline", "rural", "12", "2", e_manual, "", "", "0.02", "", ""
        )
        return {
            "results": results,
            "meta": {
                "project_name": "Synthetic Pilot Check",
                "route_name": "SR 82",
                "alignment_name": "SR 82",
                "curve_name": name,
                "curve_direction": "right",
            },
            "notes": notes,
        }

    def tdot_curve(self, *, normal_crown: bool = False) -> dict:
        results = Super.calculate_superelevation(
            "10+00",
            "20+00",
            "50",
            "8150" if normal_crown else "2280",
            "undivided",
            "rural",
            "12",
            "2",
            "",
            "",
            "",
            "0.02",
            "",
            "",
            criteria_profile="tdot",
        )
        return {
            "results": results,
            "meta": {
                "project_name": "TDOT Review",
                "route_name": "SR 1",
                "alignment_name": "Mainline",
                "curve_name": "Curve T1",
                "curve_direction": "left",
            },
            "notes": "TDOT regression fixture",
        }

    def export(self, curves: list[dict]) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.pdf"
            result = super_pdf.export_pdf(str(path), curves)
            self.assertIsNone(result)
            return path.read_bytes()

    @staticmethod
    def page_count(content: bytes) -> int:
        return len(re.findall(rb"/Type\s*/Page\b", content))

    def test_single_curve_has_summary_detail_metadata_and_numbered_pages(self):
        content = self.export([self.mdot_curve()])
        self.assertGreaterEqual(self.page_count(content), 2)
        for expected in (
            f"Application {APP_VERSION}",
            CALCULATION_ENGINE_VERSION,
            "Superelevation Calculation Report",
            "Report summary",
            "Governing standard",
            "Mississippi Department of Transportation",
            "MDOT superelevation criteria",
            "Synthetic Pilot Check",
            "Curve 01 / Curve 1",
            f"Page 1 of {self.page_count(content)}",
            f"Page {self.page_count(content)} of {self.page_count(content)}",
        ):
            self.assertIn(expected.encode(), content)

    def test_multi_curve_cover_identifies_mixed_metadata_and_all_profiles(self):
        mdot = self.mdot_curve("Curve M1")
        tdot = self.tdot_curve()
        content = self.export([mdot, tdot])
        self.assertGreaterEqual(self.page_count(content), 3)
        self.assertIn(b"Mixed - see curve index", content)
        self.assertIn(b"Curve M1", content)
        self.assertIn(b"Curve T1", content)
        self.assertIn(b"mdot-rdsd-2026-04-22", content)
        self.assertIn(tdot_criteria.TDOT_PROFILE_ID.encode(), content)
        self.assertIn(b"Mississippi Department of Transportation", content)
        self.assertIn(b"Tennessee Department of Transportation", content)
        self.assertIn(b"MULTI", content)
        self.assertIn(f"Page {self.page_count(content)} of {self.page_count(content)}".encode(), content)

    def test_tdot_report_shows_warning_without_mdot_reference_labels(self):
        content = self.export([self.tdot_curve()])
        self.assertIn(b"REVIEW NOTICE", content)
        self.assertIn(b"spiral", content.lower())
        self.assertIn(b"TDOT criteria pages intentionally omit MDOT reference artwork", content)
        self.assertNotIn(b"Reference sheet SE-", content)

    def test_reverse_curve_report_identifies_prescribed_runoff_and_minimum_tangent(self):
        prior = self.mdot_curve("Curve R1")
        following = self.mdot_curve("Curve R2")
        following["meta"]["curve_direction"] = "left"
        following["results"] = Super.calculate_superelevation(
            "143+00", "163+00", "45", "1200", "centerline", "rural", "12", "2", "", "", "", "0.02", "", ""
        )
        curves = super_batch.coordinate_reverse_curve_transitions([prior, following], pairs=[[0, 1]])

        content = self.export(curves)
        self.assertGreaterEqual(self.page_count(content), 4)
        self.assertIn(b"Reverse Curve Pair 1-2", content)
        self.assertIn(b"Lane-specific standard-rate transition record", content)
        self.assertIn(b"Lane transition controls", content)
        self.assertIn(b"ZERO CROSSINGS", content)
        self.assertNotIn(b"HANDOFF", content)
        self.assertIn(b"NC HOLD", content)
        self.assertIn(b"START", content)
        self.assertIn(b"END", content)
        self.assertNotIn(b"slower than standard", content)
        self.assertIn(b"Tmin = 0.7Lr", content)

    def test_reverse_curve_report_records_real_handoff_after_pc(self):
        common = {
            "speed": "55", "facility": "centerline", "area": "rural",
            "lane_width": "12", "lanes_rotated": "2", "normal_crown": "0.02",
        }

        def build(incoming_pc: float) -> list[dict]:
            return super_batch.build_curves_from_presets(
                [
                    {
                        "pc_station_label": "1000",
                        "pt_station_label": "2000",
                        "radius_ft": 3000.0,
                        "curve_direction": "left",
                        "curve_name": "Outgoing",
                        "alignment_name": "ML",
                    },
                    {
                        "pc_station_label": str(incoming_pc),
                        "pt_station_label": str(incoming_pc + 1000.0),
                        "radius_ft": 6000.0,
                        "curve_direction": "right",
                        "curve_name": "Incoming",
                        "alignment_name": "ML",
                    },
                ],
                common,
            )

        provisional = build(2100.0)
        minimum = 0.7 * provisional[0]["results"]["Lr"] + 0.7 * provisional[1]["results"]["Lr"]
        curves = super_batch.coordinate_reverse_curve_transitions(
            build(2000.0 + minimum + 0.1),
            pairs=[[0, 1]],
        )
        check = curves[0]["results"]["reverse_curve_coordination"]["checks"][0]
        intersection_lane = next(
            lane for lane in check["lanes"].values()
            if lane["mode"] == "standard_rate_intersection"
        )

        content = self.export(curves)
        handoff_label = Super.format_station(intersection_lane["handoff_station_ft"], True).encode()
        self.assertIn(b"HANDOFF", content)
        self.assertIn(handoff_label, content)
        self.assertIn(b"Lane transition controls", content)

    def test_normal_crown_manual_override_and_long_notes_are_reported(self):
        normal = self.tdot_curve(normal_crown=True)
        override = self.mdot_curve("Override Curve", e_manual="0.05", notes="Long review note " * 180)
        content = self.export([normal, override])
        self.assertGreaterEqual(self.page_count(content), 4)
        self.assertIn(b"Normal crown", content)
        self.assertIn(b"Override", content)
        self.assertIn(b"Long review note", content)


if __name__ == "__main__":
    unittest.main()
