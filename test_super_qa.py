from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest import mock

import super_service
import super_batch
import super_exports
import super_qa
import super_transition


FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "sr82_synthetic.xml"
CW_FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "cw_reverse_curve.xml"


class CorridorQATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = FIXTURE.read_text(encoding="utf-8")

    def curves(self) -> list[dict]:
        return super_service.build_all_landxml_curves(
            self.content,
            FIXTURE.name,
            {
                "speed": "45",
                "facility": "centerline",
                "area": "rural",
                "lane_width": "12",
                "lanes_rotated": "2",
                "normal_crown": "0.02",
            },
        )

    def reverse_preset_pair(
        self,
        *,
        speed: int,
        outgoing_radius: float,
        incoming_radius: float,
        tangent_extra_ft: float,
    ) -> list[dict]:
        common = {
            "speed": str(speed),
            "facility": "centerline",
            "area": "rural",
            "lane_width": "12",
            "lanes_rotated": "2",
            "normal_crown": "0.02",
        }

        def build(incoming_pc: float) -> list[dict]:
            return super_batch.build_curves_from_presets(
                [
                    {
                        "pc_station_label": "1000",
                        "pt_station_label": "2000",
                        "radius_ft": outgoing_radius,
                        "curve_direction": "left",
                        "curve_name": "Outgoing",
                        "alignment_name": "ML",
                    },
                    {
                        "pc_station_label": str(incoming_pc),
                        "pt_station_label": str(incoming_pc + 1000.0),
                        "radius_ft": incoming_radius,
                        "curve_direction": "right",
                        "curve_name": "Incoming",
                        "alignment_name": "ML",
                    },
                ],
                common,
            )

        provisional = build(2100.0)
        minimum = 0.7 * provisional[0]["results"]["Lr"] + 0.7 * provisional[1]["results"]["Lr"]
        return super_batch.coordinate_reverse_curve_transitions(
            build(2000.0 + minimum + tangent_extra_ft),
            pairs=[[0, 1]],
        )

    def test_curve_diagram_contains_profiles_markers_and_criteria(self):
        curve = self.curves()[0]
        diagram = super_service.curve_diagram(curve["results"], curve["meta"]["curve_direction"])
        self.assertTrue(diagram["profiles"]["left"])
        self.assertTrue(diagram["profiles"]["right"])
        self.assertIn("PC", {marker["kind"] for marker in diagram["markers"]})
        self.assertIn("PC", {label for point in diagram["snap_points"] for label in point["labels"]})
        self.assertIn("Runoff length", {item["component"] for item in diagram["intervals"]["left"]})

        station = diagram["profiles"]["left"][2]["station_ft"]
        lookup = super_service.diagram_lookup(curve["results"], curve["meta"]["curve_direction"], station)
        self.assertEqual(lookup["station_ft"], station)
        self.assertIn("reference", lookup["lanes"]["left"]["criterion"])

    def test_diagram_includes_station_equations(self):
        curve = copy.deepcopy(self.curves()[0])
        curve["results"]["station_equations"] = [{"staInternal": "18000", "staBack": "18000", "staAhead": "18100"}]
        diagram = super_service.curve_diagram(curve["results"], curve["meta"]["curve_direction"])
        equation = next(marker for marker in diagram["markers"] if marker["kind"] == "STATION EQUATION")
        self.assertEqual(equation["station_ft"], 18000.0)
        self.assertIn("180+00.000", equation["label"])

    def test_corridor_diagram_contains_every_curve_and_global_domain(self):
        curves = self.curves()
        diagram = super_service.corridor_diagram(curves)
        self.assertEqual(diagram["curve_count"], len(curves))
        self.assertEqual([item["curve_name"] for item in diagram["curves"]], [
            curve["meta"]["curve_name"] for curve in curves
        ])
        self.assertEqual(diagram["domain"]["start_ft"], min(
            item["domain"]["start_ft"] for item in diagram["curves"]
        ))
        self.assertEqual(diagram["domain"]["end_ft"], max(
            item["domain"]["end_ft"] for item in diagram["curves"]
        ))

    def test_plan_view_uses_overlay_dxf_entities(self):
        preview = super_service.plan_view(self.content, FIXTURE.name, self.curves())
        self.assertEqual(preview["background"], "#101010")
        self.assertEqual(preview["layers"]["ALI_DESIGN_ML_CURVES"]["color"], 8)
        self.assertIn("LINE", {entity["type"] for entity in preview["entities"]})
        self.assertIn("TEXT", {entity["type"] for entity in preview["entities"]})
        self.assertTrue(any(
            entity["type"] == "TEXT" and entity["text"].startswith("R=")
            for entity in preview["entities"]
        ))
        self.assertNotIn("curve_paths", preview)
        self.assertNotIn("events", preview)
        self.assertLess(preview["bounds"]["min_x"], preview["bounds"]["max_x"])
        self.assertLess(preview["bounds"]["min_y"], preview["bounds"]["max_y"])
        callout = next(entity for entity in preview["entities"] if (entity.get("preview") or {}).get("event_type"))
        self.assertRegex(callout["preview"]["group_id"], r"^curve-\d+-row-\d+$")
        self.assertIn("curve_index", callout["preview"])
        self.assertIn("curve_name", callout["preview"])
        self.assertIn("station", callout["preview"])
        self.assertIn("station_ft", callout["preview"])
        self.assertIn(callout["preview"]["side"], {"left", "right"})
        self.assertIn("slope", callout["preview"])

    def test_normal_crown_only_curve_has_stable_profiles(self):
        inputs = {
            "pc": "10+00", "pt": "12+00", "speed": "30", "radius": "100000",
            "facility": "centerline", "area": "rural", "lane_width": "12",
            "lanes_rotated": "2", "normal_crown": "0.02", "curve_direction": "left",
        }
        response = super_service.calculate_curve(inputs)
        self.assertTrue(response["results"]["normal_crown_only"])
        diagram = super_service.curve_diagram(response["results"], "left")
        self.assertGreaterEqual(len(diagram["profiles"]["left"]), 2)

    def test_complete_synthetic_corridor_passes(self):
        report = super_service.corridor_qa(self.content, FIXTURE.name, self.curves())
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["counts"], {"pass": 2, "review": 0, "block": 0})

    def test_missing_calculation_blocks_corridor(self):
        report = super_service.corridor_qa(self.content, FIXTURE.name, self.curves()[:1])
        self.assertEqual(report["status"], "block")
        self.assertIn("UNCALCULATED_CURVE", {finding["code"] for finding in report["findings"]})

    def test_intentionally_excluded_curve_is_not_reported_as_uncalculated(self):
        curves = self.curves()
        report = super_service.corridor_qa(self.content, FIXTURE.name, curves[:1], [1])
        self.assertNotIn("UNCALCULATED_CURVE", {finding["code"] for finding in report["findings"]})
        self.assertEqual(report["curve_count"], 1)
        self.assertEqual(report["source_curve_count"], 2)
        self.assertEqual(report["excluded_count"], 1)
        self.assertEqual(report["curve_statuses"][1]["status"], "excluded")

    def test_inconsistent_speed_and_overrides_require_review(self):
        curves = copy.deepcopy(self.curves())
        curves[1]["results"]["inputs"]["speed_mph"] = 50.0
        curves[1]["results"]["calculation_metadata"]["manual_overrides"]["runoff_length"] = True
        report = super_service.corridor_qa(self.content, FIXTURE.name, curves)
        codes = {finding["code"] for finding in report["findings"]}
        self.assertIn("INCONSISTENT_SPEED", codes)
        self.assertIn("MIXED_OVERRIDES", codes)
        self.assertEqual(report["status"], "review")

    def test_reverse_curve_uses_zero_to_zero_demand(self):
        curves = copy.deepcopy(self.curves())
        next_entry_zero = curves[1]["results"]["reverse_crown_ft"]
        curves[0]["results"]["reverse_crown_out_ft"] = next_entry_zero + 25.0
        report = super_service.corridor_qa(self.content, FIXTURE.name, curves)
        finding = next(item for item in report["findings"] if item["code"] == "SHORT_TANGENT")
        self.assertIn("zero-slope reverse-curve recovery", finding["message"])

    def test_build_all_keeps_curves_independent_until_explicitly_paired(self):
        curves = self.curves()
        self.assertNotIn("reverse_curve_coordination", curves[0]["results"])
        coordinated = super_batch.coordinate_reverse_curve_transitions(curves, pairs=[[0, 1]])
        self.assertEqual(
            coordinated[0]["results"]["reverse_curve_coordination"]["checks"][0]["paired_curve_indexes"],
            [0, 1],
        )

    def test_reverse_curve_pair_uses_standard_rate_and_preserves_independent_results(self):
        independent = self.curves()
        curves = super_batch.coordinate_reverse_curve_transitions(independent, pairs=[[0, 1]])
        prior, following = curves[:2]
        prior_results = prior["results"]
        following_results = following["results"]
        check = prior_results["reverse_curve_coordination"]["checks"][0]
        self.assertAlmostEqual(prior_results["full_super_out_ft"], prior_results["pt_ft"] - 0.3 * prior_results["Lr"])
        self.assertAlmostEqual(following_results["full_super_ft"], following_results["pc_ft"] + 0.3 * following_results["Lr"])
        self.assertEqual(check["status"], "coordinated")
        self.assertEqual(check["transition_rate_status"], "standard")
        self.assertAlmostEqual(
            check["minimum_tangent_ft"],
            0.7 * prior_results["Lr"] + 0.7 * following_results["Lr"],
        )
        for side in ("left", "right"):
            lane = check["lanes"][side]
            points = sorted({
                (float(event["station_ft"]), float(event["slope_pct"]))
                for event in lane["profile_events"]
            })
            self.assertGreaterEqual(len(points), 4)
            allowed_rates = {
                round(float(lane["outgoing_rate_pct_per_ft"]), 10),
                round(float(lane["incoming_rate_pct_per_ft"]), 10),
            }
            for start, end in zip(points, points[1:]):
                distance = end[0] - start[0]
                self.assertGreater(distance, 0.0)
                segment_rate = abs(end[1] - start[1]) / distance
                self.assertTrue(
                    segment_rate <= 1e-9 or round(segment_rate, 10) in allowed_rates,
                    (side, start, end, segment_rate, allowed_rates),
                )

        report = super_service.corridor_qa(self.content, FIXTURE.name, curves)
        codes = {finding["code"] for finding in report["findings"]}
        self.assertNotIn("SHORT_TANGENT", codes)
        self.assertNotIn("SHORT_REVERSE_TANGENT", codes)
        self.assertNotIn("NONSTANDARD_REVERSE_TRANSITION_RATE", codes)

        restored = super_batch.coordinate_reverse_curve_transitions(curves, enabled=False)
        self.assertNotIn("reverse_curve_coordination", restored[0]["results"])
        self.assertEqual(restored, independent)

    def test_latest_cw_reverse_curve_uses_standard_rate_and_normal_crown_holds(self):
        content = CW_FIXTURE.read_text(encoding="utf-8")
        independent = super_service.build_all_landxml_curves(
            content,
            CW_FIXTURE.name,
            {
                "speed": "65", "facility": "centerline", "area": "rural",
                "lane_width": "12", "lanes_rotated": "2", "normal_crown": "0.02",
            },
        )
        curves = super_batch.coordinate_reverse_curve_transitions(independent, pairs=[[0, 1]])
        self.assertEqual(len(curves), 2)
        check = curves[0]["results"]["reverse_curve_coordination"]["checks"][0]
        self.assertEqual(check["status"], "coordinated")
        self.assertAlmostEqual(check["available_tangent_ft"], 123.0, places=3)
        self.assertAlmostEqual(check["minimum_tangent_ft"], 86.1, places=3)
        self.assertEqual(check["transition_rate_status"], "standard")
        for side in ("left", "right"):
            lane = check["lanes"][side]
            self.assertEqual(lane["mode"], "normal_crown_hold")
            self.assertGreater(lane["normal_crown_hold"]["length_ft"], 0.0)
            self.assertIsNone(lane["handoff_station_ft"])
            self.assertIsNone(lane["handoff_slope_pct"])
            self.assertNotIn(
                "Reverse handoff",
                {event["event_type"] for event in lane["profile_events"]},
            )
            self.assertGreaterEqual(len(lane["zero_stations_ft"]), 1)

        report = super_service.corridor_qa(content, CW_FIXTURE.name, curves)
        self.assertNotIn(
            "NONSTANDARD_REVERSE_TRANSITION_RATE",
            {finding["code"] for finding in report["findings"]},
        )

    def test_90_foot_reverse_tangent_above_minimum_has_no_handoff_dead_zone(self):
        # Regression geometry from ALI_ALT_90'_Tangent.xml.  The source file is
        # intentionally not retained; these are the two curve records needed
        # to reproduce the reverse-transition defect without project data.
        independent = super_batch.build_curves_from_presets(
            [
                {
                    "pc_station_label": "149220.000000",
                    "pt_station_label": "150305.043003",
                    "radius_ft": 8800.0,
                    "curve_direction": "left",
                    "curve_name": "Curve 1",
                    "alignment_name": "ML",
                },
                {
                    "pc_station_label": "150395.043003",
                    "pt_station_label": "151566.396245",
                    "radius_ft": 9500.0,
                    "curve_direction": "right",
                    "curve_name": "Curve 2",
                    "alignment_name": "ML",
                },
            ],
            {
                "speed": "65",
                "facility": "centerline",
                "area": "rural",
                "lane_width": "12",
                "lanes_rotated": "2",
                "normal_crown": "0.02",
            },
        )
        curves = super_batch.coordinate_reverse_curve_transitions(
            independent, pairs=[[0, 1]],
        )
        check = curves[0]["results"]["reverse_curve_coordination"]["checks"][0]

        self.assertEqual(check["status"], "coordinated")
        self.assertAlmostEqual(check["available_tangent_ft"], 90.0, places=6)
        self.assertAlmostEqual(check["minimum_tangent_ft"], 85.4, places=6)
        self.assertEqual(check["transition_rate_status"], "standard")

        for side in ("left", "right"):
            lane = check["lanes"][side]
            self.assertEqual(lane["mode"], "normal_crown_hold")
            self.assertIsNone(lane["handoff_station_ft"])
            self.assertIsNone(lane["handoff_slope_pct"])
            self.assertNotIn(
                "Reverse handoff",
                {event["event_type"] for event in lane["profile_events"]},
            )
            self.assertIsNone(
                super_qa._reverse_lane_issue(
                    lane,
                    curves[0]["results"]["pt_ft"],
                    curves[1]["results"]["pc_ft"],
                )
            )
            points = sorted({
                (float(event["station_ft"]), float(event["slope_pct"]))
                for event in lane["profile_events"]
            })
            allowed_rates = {
                round(float(lane["outgoing_rate_pct_per_ft"]), 10),
                round(float(lane["incoming_rate_pct_per_ft"]), 10),
            }
            for start, end in zip(points, points[1:]):
                distance = end[0] - start[0]
                self.assertGreater(distance, 0.0)
                segment_rate = abs(end[1] - start[1]) / distance
                self.assertTrue(
                    segment_rate <= 1e-9 or round(segment_rate, 10) in allowed_rates,
                    (side, start, end, segment_rate, allowed_rates),
                )

        self.assertLess(
            check["lanes"]["left"]["normal_crown_hold"]["end_ft"],
            curves[0]["results"]["pt_ft"],
        )
        self.assertGreater(
            check["lanes"]["right"]["normal_crown_hold"]["start_ft"],
            curves[1]["results"]["pc_ft"],
        )

        corridor = super_service.corridor_diagram(curves)
        prior_diagram, following_diagram = corridor["curves"]
        for side in ("left", "right"):
            split = float(check["lanes"][side]["normal_crown_hold"]["end_ft"])
            prior_profile = prior_diagram["profiles"][side]
            following_profile = following_diagram["profiles"][side]
            self.assertAlmostEqual(prior_profile[-1]["station_ft"], split, places=7)
            self.assertAlmostEqual(following_profile[0]["station_ft"], split, places=7)
            self.assertAlmostEqual(
                prior_profile[-1]["slope_pct"],
                following_profile[0]["slope_pct"],
                places=9,
            )
            self.assertLessEqual(
                prior_profile[-1]["station_ft"],
                following_profile[0]["station_ft"],
            )

        for curve in curves:
            lookup = super_service.diagram_lookup(
                curve["results"],
                curve["meta"]["curve_direction"],
                150405.0,
            )
            self.assertAlmostEqual(lookup["lanes"]["right"]["slope_pct"], -2.0, places=9)
            self.assertEqual(lookup["lanes"]["right"]["phase"], "Normal crown hold")

    def test_minimum_plus_point_one_allows_standard_rate_handoff_after_pc(self):
        curves = self.reverse_preset_pair(
            speed=55,
            outgoing_radius=3000.0,
            incoming_radius=6000.0,
            tangent_extra_ft=0.1,
        )
        check = curves[0]["results"]["reverse_curve_coordination"]["checks"][0]
        self.assertEqual(check["status"], "coordinated")
        self.assertAlmostEqual(
            check["available_tangent_ft"] - check["minimum_tangent_ft"],
            0.1,
            places=7,
        )

        intersection_lane = next(
            lane for lane in check["lanes"].values()
            if lane["mode"] == "standard_rate_intersection"
        )
        self.assertGreater(
            intersection_lane["handoff_station_ft"],
            curves[1]["results"]["pc_ft"],
        )
        self.assertLess(
            intersection_lane["handoff_station_ft"],
            curves[1]["results"]["full_super_ft"],
        )
        self.assertEqual(
            sum(
                event["event_type"] == "Reverse handoff"
                for event in intersection_lane["profile_events"]
            ),
            2,
        )
        self.assertIsNone(
            super_qa._reverse_lane_issue(
                intersection_lane,
                curves[0]["results"]["pt_ft"],
                curves[1]["results"]["pc_ft"],
            )
        )
        side = next(
            side
            for side, lane in check["lanes"].items()
            if lane is intersection_lane
        )
        corridor = super_service.corridor_diagram(curves)
        prior_profile = corridor["curves"][0]["profiles"][side]
        following_profile = corridor["curves"][1]["profiles"][side]
        self.assertAlmostEqual(
            prior_profile[-1]["station_ft"],
            intersection_lane["handoff_station_ft"],
            places=7,
        )
        self.assertAlmostEqual(
            following_profile[0]["station_ft"],
            intersection_lane["handoff_station_ft"],
            places=7,
        )
        self.assertAlmostEqual(
            prior_profile[-1]["slope_pct"],
            following_profile[0]["slope_pct"],
            places=9,
        )

    def test_full_precision_rate_validation_does_not_false_block_short_segments(self):
        curves = self.reverse_preset_pair(
            speed=25,
            outgoing_radius=800.0,
            incoming_radius=1500.0,
            tangent_extra_ft=5.0,
        )
        check = curves[0]["results"]["reverse_curve_coordination"]["checks"][0]
        self.assertEqual(check["status"], "coordinated")
        for lane in check["lanes"].values():
            self.assertIsNone(
                super_qa._reverse_lane_issue(
                    lane,
                    curves[0]["results"]["pt_ft"],
                    curves[1]["results"]["pc_ft"],
                )
            )

    def test_minimum_plus_point_one_allows_mirrored_handoff_before_pt(self):
        curves = self.reverse_preset_pair(
            speed=55,
            outgoing_radius=6000.0,
            incoming_radius=3000.0,
            tangent_extra_ft=0.1,
        )
        check = curves[0]["results"]["reverse_curve_coordination"]["checks"][0]
        self.assertEqual(check["status"], "coordinated")
        intersection_lane = next(
            lane for lane in check["lanes"].values()
            if lane["mode"] == "standard_rate_intersection"
        )
        self.assertGreater(
            intersection_lane["handoff_station_ft"],
            curves[0]["results"]["full_super_out_ft"],
        )
        self.assertLess(
            intersection_lane["handoff_station_ft"],
            curves[0]["results"]["pt_ft"],
        )
        self.assertIsNone(
            super_qa._reverse_lane_issue(
                intersection_lane,
                curves[0]["results"]["pt_ft"],
                curves[1]["results"]["pc_ft"],
            )
        )

    def test_exact_minimum_reverse_tangent_keeps_standard_rate(self):
        curves = self.curves()
        prior, following = curves[:2]
        required = 0.7 * prior["results"]["Lr"] + 0.7 * following["results"]["Lr"]
        following["results"]["pc_ft"] = prior["results"]["pt_ft"] + required
        following["results"]["full_super_ft"] = following["results"]["pc_ft"] + 0.3 * following["results"]["Lr"]

        coordinated = super_batch.coordinate_reverse_curve_transitions(curves, pairs=[[0, 1]])
        check = coordinated[0]["results"]["reverse_curve_coordination"]["checks"][0]
        self.assertEqual(check["status"], "coordinated")
        self.assertEqual(check["transition_rate_status"], "standard")
        self.assertEqual({check["lanes"][side]["mode"] for side in ("left", "right")}, {"single_zero"})
        meeting_stations = {
            round(check["lanes"][side]["handoff_station_ft"], 7)
            for side in ("left", "right")
        }
        self.assertEqual(len(meeting_stations), 1)
        self.assertTrue(all(abs(check["lanes"][side]["handoff_slope_pct"]) < 1e-9 for side in ("left", "right")))
        prior_rows = super_exports.build_lane_rows(
            coordinated[0]["results"], coordinated[0]["meta"]["curve_direction"], station_format=False,
        )
        following_rows = super_exports.build_lane_rows(
            coordinated[1]["results"], coordinated[1]["meta"]["curve_direction"], station_format=False,
        )
        expected_prior_pt = abs(coordinated[0]["results"]["e"] * 100.0 * 0.7)
        expected_following_pc = abs(coordinated[1]["results"]["e"] * 100.0 * 0.7)
        self.assertTrue(all(
            abs(abs(next(row for row in rows if row["label"] == "PT")["slope_pct"]) - expected_prior_pt) < 1e-9
            for rows in prior_rows
        ))
        self.assertTrue(all(
            abs(abs(next(row for row in rows if row["label"] == "PC")["slope_pct"]) - expected_following_pc) < 1e-9
            for rows in following_rows
        ))

    def test_unequal_rates_produce_continuous_partial_slope_handoff(self):
        prior = {
            "full_super_out_ft": 0.0,
            "pt_ft": 30.0,
            "Lr": 100.0,
            "e": 0.06,
            "crown_state": "SUPERELEVATION",
            "inputs": {"normal_crown": 0.02},
        }
        following = {
            "full_super_ft": 205.0,
            "pc_ft": 175.0,
            "Lr": 100.0,
            "e": 0.04,
            "crown_state": "SUPERELEVATION",
            "inputs": {"normal_crown": 0.02},
        }
        plan = super_transition.build_reverse_pair_plan(
            prior, "left", following, "right",
            pair_id="reverse-pair-test", exact_minimum=False,
        )
        intersection_lane = next(
            lane for lane in plan["lanes"].values()
            if lane["mode"] == "standard_rate_intersection"
        )
        self.assertAlmostEqual(intersection_lane["handoff_station_ft"], 90.0)
        self.assertAlmostEqual(intersection_lane["handoff_slope_pct"], -0.6)
        self.assertIsNone(intersection_lane["normal_crown_hold"])
        plateau_lane = next(
            lane for lane in plan["lanes"].values()
            if lane["mode"] == "normal_crown_hold"
        )
        self.assertGreater(plateau_lane["normal_crown_hold"]["length_ft"], 0.0)

        mirrored = super_transition.build_reverse_pair_plan(
            prior, "right", following, "left",
            pair_id="reverse-pair-mirrored", exact_minimum=False,
        )
        mirrored_intersection = next(
            lane for lane in mirrored["lanes"].values()
            if lane["mode"] == "standard_rate_intersection"
        )
        self.assertAlmostEqual(mirrored_intersection["handoff_station_ft"], 90.0)
        self.assertAlmostEqual(mirrored_intersection["handoff_slope_pct"], -0.6)

    def test_pair_indexes_must_be_adjacent_and_disjoint(self):
        curves = self.curves()
        duplicated = curves + copy.deepcopy(curves)
        with self.assertRaisesRegex(ValueError, "adjacent"):
            super_batch.coordinate_reverse_curve_transitions(duplicated, pairs=[[0, 2]])
        with self.assertRaisesRegex(ValueError, "more than one"):
            super_batch.coordinate_reverse_curve_transitions(duplicated, pairs=[[0, 1], [1, 2]])

    def test_independent_pairs_are_coordinated_without_linking_the_gap_between_them(self):
        base = self.curves()
        curves = base + copy.deepcopy(base)
        offset = curves[1]["results"]["pt_ft"] + 500.0 - curves[2]["results"]["pc_ft"]
        for key in (
            "pc_ft", "pt_ft", "pnc_ft", "reverse_crown_ft", "full_super_ft",
            "full_super_out_ft", "reverse_crown_out_ft", "pnc_out_ft",
        ):
            if curves[2]["results"].get(key) is not None:
                curves[2]["results"][key] += offset
            if curves[3]["results"].get(key) is not None:
                curves[3]["results"][key] += offset
        coordinated = super_batch.coordinate_reverse_curve_transitions(
            curves, pairs=[[0, 1], [2, 3]],
        )
        self.assertEqual(
            coordinated[0]["results"]["reverse_curve_coordination"]["checks"][0]["paired_curve_indexes"],
            [0, 1],
        )
        self.assertEqual(
            {
                tuple(check["paired_curve_indexes"])
                for check in coordinated[1]["results"]["reverse_curve_coordination"]["checks"]
            },
            {(0, 1)},
        )
        self.assertEqual(
            coordinated[2]["results"]["reverse_curve_coordination"]["checks"][0]["paired_curve_indexes"],
            [2, 3],
        )

    def test_short_reverse_tangent_blocks_without_moving_runoff(self):
        curves = self.curves()
        prior, following = curves[:2]
        following["results"]["pc_ft"] = prior["results"]["pt_ft"] + 10.0
        following["results"]["full_super_ft"] = following["results"]["pc_ft"] + 0.3 * following["results"]["Lr"]
        coordinated = super_batch.coordinate_reverse_curve_transitions(curves, pairs=[[0, 1]])
        self.assertNotIn("exit", coordinated[0]["results"]["reverse_curve_coordination"])
        self.assertNotIn("entry", coordinated[1]["results"]["reverse_curve_coordination"])
        self.assertNotIn("reverse_curve_exit_zero_ft", coordinated[0]["results"])
        self.assertNotIn("reverse_curve_entry_zero_ft", coordinated[1]["results"])
        report = super_service.corridor_qa(self.content, FIXTURE.name, coordinated)
        finding = next(item for item in report["findings"] if item["code"] == "SHORT_REVERSE_TANGENT")
        self.assertEqual(finding["severity"], "block")
        self.assertIn("0.7Lr(exit) + 0.7Lr(entry)", finding["details"])

    def test_zero_percent_curve_is_rejected_as_an_ineligible_pair(self):
        curves = super_batch.build_curves_from_presets(
            [
                {
                    "pc_station_label": "1000", "pt_station_label": "2000",
                    "radius_ft": 1500.0, "curve_direction": "left",
                    "curve_name": "Zero percent", "alignment_name": "ML",
                },
                {
                    "pc_station_label": "2200", "pt_station_label": "3200",
                    "radius_ft": 1200.0, "curve_direction": "right",
                    "curve_name": "Incoming", "alignment_name": "ML",
                },
            ],
            {
                "speed": "20", "facility": "centerline", "area": "rural",
                "lane_width": "12", "lanes_rotated": "2", "normal_crown": "0.02",
            },
        )
        self.assertEqual(curves[0]["results"]["e"], 0.0)
        coordinated = super_batch.coordinate_reverse_curve_transitions(curves, pairs=[[0, 1]])
        check = coordinated[0]["results"]["reverse_curve_coordination"]["checks"][0]
        self.assertEqual(check["status"], "invalid_pair")
        self.assertIn("0% superelevation curve", check["failure_reason"])

    def test_corridor_qa_blocks_nonstandard_or_discontinuous_pair_metadata(self):
        curves = super_batch.coordinate_reverse_curve_transitions(self.curves(), pairs=[[0, 1]])
        check = curves[0]["results"]["reverse_curve_coordination"]["checks"][0]
        original_full_super = curves[0]["results"]["full_super_out_ft"]
        check["lanes"]["left"]["profile_events"][1]["slope_pct"] += 0.5
        curves[1]["results"]["reverse_curve_coordination"]["checks"][0] = copy.deepcopy(check)

        report = super_service.corridor_qa(self.content, FIXTURE.name, curves)
        finding = next(
            item for item in report["findings"]
            if item["code"] == "NONSTANDARD_REVERSE_TRANSITION"
        )
        self.assertEqual(finding["severity"], "block")
        self.assertEqual(curves[0]["results"]["full_super_out_ft"], original_full_super)

    def test_normal_crown_curve_does_not_require_transition_recovery_events(self):
        curves = copy.deepcopy(self.curves())
        curves[0]["results"]["normal_crown_only"] = True
        with mock.patch("super_qa._zero_event", return_value=None) as zero_event:
            report = super_service.corridor_qa(self.content, FIXTURE.name, curves)
        self.assertNotIn("MISSING_TRANSITION_DEMAND", {finding["code"] for finding in report["findings"]})
        zero_event.assert_not_called()

    def test_spiral_geometry_blocks_corridor(self):
        spiral = '<Spiral length="100"><Start>1453411.9250950934 993735.04373338632 0</Start><End>1453411.9250950934 993835.04373338632 0</End></Spiral>'
        content = self.content.replace("<Curve crvType=", f"{spiral}<Curve crvType=", 1)
        with self.assertRaisesRegex(ValueError,"explicitly defined LandXML clothoids"):
            super_service.corridor_qa(content, "spiral.xml", [])

    def test_out_of_alignment_transition_blocks_corridor(self):
        curves = copy.deepcopy(self.curves())
        curves[0]["results"]["reverse_crown_ft"] = 9000.0
        report = super_service.corridor_qa(self.content, FIXTURE.name, curves)
        self.assertIn("OUT_OF_ALIGNMENT", {finding["code"] for finding in report["findings"]})

    def test_zero_length_geometry_blocks_corridor(self):
        content = self.content.replace('length="7407.4478297109072"', 'length="0"', 1)
        report = super_service.corridor_qa(content, "invalid.xml", [])
        self.assertIn("INVALID_GEOMETRY", {finding["code"] for finding in report["findings"]})


if __name__ == "__main__":
    unittest.main()
