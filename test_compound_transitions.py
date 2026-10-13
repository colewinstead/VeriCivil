"""Analytical checks for the engineer-requested reduced compound runoff rule."""

import copy
import io
import json
from pathlib import Path
import unittest

import aashto_superelevation
import super_batch
import super_exports
import super_lane
import super_service


FIXTURE = Path(__file__).parent / "tests/fixtures/compound_synthetic.xml"


class CompoundTransitionTests(unittest.TestCase):
    def curves(self, rates=(0.03, 0.05), direction="left", profile="mdot-rdsd-2026-04-22", placement=None, length=1000, **changes):
        curves = []
        for i, rate in enumerate(rates):
            values = {"pc": str(1000 + i * length), "pt": str(1000 + (i + 1) * length),
                      "speed": "45", "radius": "700" if rate == max(rates) else "1000",
                      "criteria_profile": profile, "e_manual": str(rate), "Lr_manual": "200", "Lt_manual": "100",
                      "curve_direction": direction, "facility": "undivided" if profile.startswith("tdot") else "centerline",
                      **changes}
            if placement is not None:
                values.update(runoff_tangent_percent=placement, override_standard_placement=True)
            elif profile.startswith("aashto"):
                values["runoff_tangent_percent"] = 70
            sides = (("entry",) if i else ()) + (("exit",) if i + 1 < len(rates) else ())
            import Super
            result = Super.calculate_superelevation(values["pc"], values["pt"], values["speed"], values["radius"],
                values["facility"], "rural", "12", "2", values["e_manual"], "", "", "0.02", values["Lr_manual"], values["Lt_manual"],
                criteria_profile=profile, profile_options=values, compound_sides=sides)
            curves.append({"results": result, "meta": {"curve_direction": direction, "curve_name": f"Curve {i + 1}"}})
        return curves

    def test_80_foot_transition_uses_existing_bank_and_selected_placement(self):
        for profile in ("mdot-rdsd-2026-04-22", "tdot-rd11-2026-04-30", "aashto-green-book-2018-2019-10"):
            for direction in ("left", "right"):
                for rates in ((0.03, 0.05), (0.05, 0.03)):
                    for placement in (0, 50, 70, 100):
                        with self.subTest(profile=profile, direction=direction, rates=rates, placement=placement):
                            original = self.curves(rates, direction, profile, placement)
                            unchanged = copy.deepcopy(original)
                            curves = super_batch.coordinate_compound_curve_transitions(original)
                            self.assertEqual(original, unchanged)
                            plan = curves[0]["results"]["compound_curve_transitions"]["exit"]
                            before = placement / 100 if rates[1] > rates[0] else 1 - placement / 100
                            self.assertAlmostEqual(plan["length_ft"], 80)
                            self.assertAlmostEqual(plan["start_ft"], 2000 - before * 80)
                            self.assertAlmostEqual(plan["end_ft"], 2000 + (1 - before) * 80)
                            for curve in curves:
                                points = super_lane.lane_profile_points(curve["results"], direction)
                                for lane, sign in (("left", -1 if direction == "left" else 1), ("right", 1 if direction == "left" else -1)):
                                    for fraction in (0, 0.25, before, 0.75, 1):
                                        station = plan["start_ft"] + fraction * 80
                                        expected = sign * (rates[0] + fraction * (rates[1] - rates[0])) * 100
                                        self.assertAlmostEqual(super_lane.slope_at_station(points[lane], station), expected)
                            self.assertEqual(super_batch.coordinate_compound_curve_transitions(curves), curves)
                            aashto_superelevation.validate_export_curves(curves)

    def test_default_placement_and_equal_bank_and_chain(self):
        for profile, before in (("mdot-rdsd-2026-04-22", 0.7), ("tdot-rd11-2026-04-30", 0.25), ("aashto-green-book-2018-2019-10", 0.7)):
            curves = super_batch.coordinate_compound_curve_transitions(self.curves(profile=profile))
            self.assertAlmostEqual(curves[0]["results"]["compound_curve_transitions"]["exit"]["before_fraction"], before)
        curves = super_batch.coordinate_compound_curve_transitions(self.curves((0.03, 0.05, 0.03, 0.03)))
        self.assertEqual(curves[2]["results"]["compound_curve_transitions"]["exit"]["length_ft"], 0)
        self.assertEqual(set(curves[1]["results"]["compound_curve_transitions"]), {"entry", "exit"})
        for curve in curves:
            self.assertLessEqual(curve["results"]["full_super_ft"], curve["results"]["full_super_out_ft"])
        rows = super_exports.build_normalized_rows(curves)
        compound = [r for r in rows if r["event_type"].startswith("Compound")]
        keys = [(r["lane_name"], r["station"], r["event_type"]) for r in compound]
        self.assertEqual(len(keys), len(set(keys)))

    def test_short_chain_and_changed_cross_section_are_rejected(self):
        original = self.curves((0.03, 0.05, 0.03), length=50)
        with self.assertRaisesRegex(ValueError, "overlap"):
            super_batch.coordinate_compound_curve_transitions(original)
        curves = self.curves()
        curves[1]["results"]["inputs"]["lane_width_ft"] = 14
        with self.assertRaisesRegex(ValueError, "cross section"):
            super_batch.coordinate_compound_curve_transitions(curves)

    def test_tangent_reverse_and_spiral_connections_stay_independent(self):
        curves = self.curves()
        curves[1]["results"]["pc_ft"] += 1
        self.assertEqual(super_batch.coordinate_compound_curve_transitions(curves), curves)
        curves = self.curves()
        curves[1]["meta"]["curve_direction"] = "right"
        self.assertEqual(super_batch.coordinate_compound_curve_transitions(curves), curves)
        curves = self.curves()
        curves[1]["results"]["inputs"]["alignment_type"] = "spiral"
        self.assertEqual(super_batch.coordinate_compound_curve_transitions(curves), curves)

    def test_landxml_batch_qa_exports_and_saved_result_validation(self):
        xml = FIXTURE.read_text()
        values = {"criteria_profile": "aashto-green-book-2018-2019-10", "speed": "45", "e_manual": "0.05",
                  "Lr_manual": "200", "Lt_manual": "100", "runoff_tangent_percent": "70"}
        curves = super_service.build_all_landxml_curves(xml, FIXTURE.name, values)
        self.assertEqual(len(curves), 2)
        report = super_service.corridor_qa(xml, FIXTURE.name, curves)
        self.assertFalse([f for f in report["findings"] if f["severity"] == "block"], report["findings"])
        self.assertFalse([f for f in report["findings"] if f["code"] in {"SHORT_TANGENT", "TRANSITION_OVERLAP"}])
        edited = super_service.calculate_curve({**curves[0]["results"]["inputs"], "speed": "45", "radius": "1000", "e_manual": "0.03"}, curves, 0)["results"]
        curves[0]["results"] = edited
        curves = super_service.coordinate_reverse_curves(curves)
        plan = curves[0]["results"]["compound_curve_transitions"]["exit"]
        self.assertAlmostEqual(plan["length_ft"], 80)
        handle = io.StringIO()
        super_exports.write_ord_csv(handle, curves)
        self.assertIn("CrossSlope", handle.getvalue())
        self.assertTrue(super_service.export_pdf(curves)["content"])
        self.assertTrue(super_service.export_detail_dxf(curves)["content"])
        self.assertTrue(super_service.export_overlay_dxf(curves, {"content": xml, "filename": FIXTURE.name})["content"])
        restored = json.loads(json.dumps(curves))
        self.assertEqual(super_service.coordinate_reverse_curves(restored), restored)
        restored[0]["results"]["section_lanes"][0]["events"][-1]["slope_pct"] = 99
        with self.assertRaisesRegex(ValueError, "Saved compound"):
            aashto_superelevation.validate_export_curves(restored)
        with self.assertRaises(ValueError):
            aashto_superelevation.validate_export_curves([curves[0]])

    def test_fixed_pivot_lane_heights_match_reduced_bank_transition(self):
        for direction in ("left", "right"):
            for pivot in ("centerline", "left_edge", "right_edge"):
                curves = super_batch.coordinate_compound_curve_transitions(self.curves(direction=direction,
                    profile="aashto-green-book-2018-2019-10", rotation_axis=pivot, Lr_manual="400", Lt_manual="200"))
                for curve in curves:
                    for lane in curve["results"]["section_lanes"]:
                        for event in lane["events"]:
                            if event.get("compound_pair_id"):
                                signed_bank = event["slope_pct"] / 100 * (1 if lane["side"] == "left" else -1)
                                self.assertAlmostEqual(event["left_elevation_ft"], signed_bank * lane["left_distance_from_pivot_ft"])
                                self.assertAlmostEqual(event["right_elevation_ft"], signed_bank * lane["right_distance_from_pivot_ft"])

    def test_favorable_ramp_preserves_actual_runoff_rate(self):
        curves = super_batch.coordinate_compound_curve_transitions(self.curves(direction="right",
            profile="aashto-green-book-2018-2019-10", roadway="one_way", initial_section="single_slope",
            initial_slope="0.02", lane_widths="12", rotation_axis="left_edge", Lt_manual="0", placement=50))
        plan = curves[0]["results"]["compound_curve_transitions"]["exit"]
        # The sharper ramp's recorded 200-ft runoff develops 2% -> 5%.
        self.assertAlmostEqual(plan["length_ft"], 200 * (0.05 - 0.03) / (0.05 - 0.02))
        self.assertAlmostEqual(plan["rate_pct_per_ft"], 0.015)
        aashto_superelevation.validate_export_curves(curves)

    def test_user_ramp_compound_chain(self):
        path = FIXTURE.parent / "840 choice ramps.xml"
        if not path.exists():
            self.skipTest("User ramp fixture is local-only; public synthetic cases remain available.")
        values = {"criteria_profile": "aashto-green-book-2018-2019-10", "speed": "45", "max_superelevation": "8",
                  "roadway": "one_way", "initial_section": "single_slope", "initial_slope": "0.02",
                  "lane_widths": "12", "rotation_axis": "left_edge", "runoff_tangent_percent": "50"}
        xml = path.read_text()
        excluded = [0, 1, 5, 6, 7]
        curves = super_service.build_all_landxml_curves(xml, path.name, values, excluded)
        self.assertEqual([c["meta"]["landxml_curve_index"] for c in curves], [2, 3, 4])
        plan = curves[1]["results"]["compound_curve_transitions"]["exit"]
        self.assertAlmostEqual(plan["start_e"], 0.02)
        self.assertAlmostEqual(plan["end_e"], 0.048)
        self.assertAlmostEqual(plan["length_ft"], 63)
        self.assertAlmostEqual(plan["boundary_ft"] - plan["start_ft"], 31.5)
        self.assertAlmostEqual(plan["end_ft"] - plan["boundary_ft"], 31.5)
        self.assertEqual(curves[0]["results"]["compound_curve_transitions"]["exit"]["length_ft"], 0)
        report = super_service.corridor_qa(xml, path.name, curves, excluded)
        self.assertFalse([f for f in report["findings"] if f["severity"] == "block"], report["findings"])
        aashto_superelevation.validate_export_curves(curves)
        self.assertTrue(super_service.export_overlay_dxf(curves, {"content": xml, "filename": path.name})["content"])
        # The separate tangent-to-reverse-curve checks are still enforced.
        with self.assertRaises(aashto_superelevation.TransitionError):
            super_service.build_all_landxml_curves(xml, path.name, values)


if __name__ == "__main__":
    unittest.main()
