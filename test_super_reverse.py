"""Station-free demand checked against the existing stationed lane profiles."""
import json
import unittest
from unittest.mock import patch

import aashto_superelevation
import super_service
import super_reverse
import super_qa


def inputs(profile="mdot", **changes):
    return {"criteria_profile": profile, "speed": "65", "area": "rural", "lane_width": "12",
            "lanes_rotated": "2", "normal_crown": "0.02", "curve_direction": "left",
            "max_superelevation": 8, "runoff_tangent_percent": 50,
            "circular_placement_basis": "runoff_runout", **changes}


class ReverseTangentTests(unittest.TestCase):
    def check(self, values=None, first=4000, second=3000):
        return super_reverse.required_reverse_tangent(values or inputs(), first, second)

    def compare_stationed(self, values, first=4000, second=3000):
        advice = self.check(values, first, second)
        expected = {}
        for index, curve in enumerate(advice["curves"]):
            request = {**values, "pc": "10000", "pt": "20000", "radius": str(curve["radius_ft"]),
                       "curve_direction": curve["curve_direction"]}
            if request.get("roadway") == "divided_case_ii":
                request["case_ii_geometry_mode"] = "shared_corridor"
                request["case_ii"] = {side: {**definition, "speed": values["speed"]}
                                      for side, definition in values["case_ii"].items()}
            actual = super_service.calculate_curve(request)["results"]
            for side, child in actual.get("carriageways", {"roadway": actual}).items():
                checked = curve.get("carriageways", {"roadway": curve})[side]
                self.assertEqual((child["e"], child["Lr"], child["Lt"]), (checked["e"], checked["Lr"], checked["Lt"]))
                window = super_qa._changing_transition_window({"results": child, "meta": {"curve_direction": curve["curve_direction"]}}, entering=index == 1)
                demand = 0 if window is None else max(0, child["pc_ft"] - window[0] if index else window[1] - child["pt_ft"])
                self.assertAlmostEqual(checked["tangent_demand_ft"], demand, places=7)
                expected[side] = expected.get(side, 0) + demand
        self.assertAlmostEqual(advice["independent_tangent_ft"], max(expected.values()), places=7)
        return advice

    def test_mdot_facilities_and_areas(self):
        for changes in ({}, {"facility": "outside edge"}, {"area": "urban", "speed": "50"},
                        {"area": "urban", "speed": "40"}, {"area": "local", "speed": "30"}):
            with self.subTest(changes=changes):
                self.compare_stationed(inputs(**changes))

    def test_tdot_standard_placement_and_no_linked_rule(self):
        for area, speed in (("urban", "40"), ("rural", "65")):
            advice = self.compare_stationed(inputs("tdot", area=area, speed=speed, facility="undivided"))
            self.assertIsNone(advice["mdot_linked_tangent_ft"])

    def test_aashto_sections_pivots_placement_and_directions(self):
        for direction in ("left", "right"):
            for basis in ("runoff", "runoff_runout"):
                for changes in ({"rotation_axis": "centerline"}, {"rotation_axis": "left_edge"}, {"rotation_axis": "right_edge"},
                                {"roadway": "one_way", "initial_section": "single_slope", "initial_slope": -.02, "rotation_axis": "left_edge", "lane_widths": "12"},
                                {"roadway": "one_way", "initial_section": "single_slope", "initial_slope": .02, "rotation_axis": "right_edge", "lane_widths": "12,12"}):
                    with self.subTest(direction=direction, basis=basis, changes=changes):
                        self.compare_stationed(inputs("aashto", curve_direction=direction, circular_placement_basis=basis, **changes))

    def test_case_ii_both_modes_direction_and_controlling_carriageway(self):
        for mode in ("coordinated", "independent"):
            for direction in ("left", "right"):
                values = inputs("aashto", roadway="divided_case_ii", case_ii_placement_mode=mode, curve_direction=direction,
                    case_ii={side: {"lane_count": count, "lane_width": 12, "pivot_offset": offset,
                                   "initial_slope": slope, "runoff_tangent_percent": 50, "circular_placement_basis": "runoff_runout"}
                             for side, count, offset, slope in (("left", 2, -12, -.02), ("right", 4, 12, .02))})
                advice = self.compare_stationed(values)
                self.assertIn(advice["governing_carriageway"], ("left", "right"))
                for curve in advice["curves"]:
                    self.assertNotEqual(curve["carriageways"]["left"]["radius_provenance"]["design_radius_ft"],
                                        curve["carriageways"]["right"]["radius_provenance"]["design_radius_ft"])
                    self.assertNotIn("pc_ft", curve["carriageways"]["left"])

    def test_normal_crown_and_single_unchanged_curve(self):
        for profile in ("mdot", "tdot", "aashto"):
            advice = self.compare_stationed(inputs(profile), 1000000, 1000000)
            self.assertEqual(advice["independent_tangent_ft"], 0)
            self.assertIsNone(advice["mdot_linked_tangent_ft"])
            self.compare_stationed(inputs(profile), 1000000, 3000)

    def test_unequal_radii_and_mirrored_mdot(self):
        a = self.check()
        b = self.check(inputs(curve_direction="right"))
        self.assertEqual(a["independent_tangent_ft"], b["independent_tangent_ft"])
        self.assertNotEqual(a["curves"][0]["Lr"], a["curves"][1]["Lr"])

    def test_190_140_existing_project_rule(self):
        def lengths(*args, **kwargs):
            return {"e": .06, "Lr": 100, "Lt": 25, "normal_crown_only": False,
                    "segments": {"approx_0p7L": 70}, "calculation_metadata": {}}
        with patch.object(super_reverse.Super, "calculate_superelevation", side_effect=lengths):
            advice = self.check()
        self.assertEqual(advice["independent_tangent_ft"], 190)
        self.assertEqual(advice["mdot_linked_tangent_ft"], 140)

    def test_invalid_inputs_and_overrides(self):
        for radius in (None, "", "nan", "inf", 0, -1):
            with self.subTest(radius=radius), self.assertRaises(ValueError):
                self.check(first=radius)
        for changes in ({"speed": "nan"}, {"lane_width": 0}, {"curve_direction": "straight"},
                        {"e_manual": .06}, {"Lr_manual": 100}, {"rel_grad": .005},
                        {"alignment_type": "spiral"}, {"linear_unit": "meter"}, {"roadway": "divided_case_ii"},
                        {"landxml_source": {"content": "private"}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(inputs(**changes))
        with self.assertRaises(ValueError):
            self.check(inputs("tdot"), first=1)
        with self.assertRaises(ValueError):
            self.check(inputs("aashto", runoff_tangent_percent=""))
        with self.assertRaises(aashto_superelevation.TransitionError):
            self.check(inputs("aashto", runoff_tangent_percent=100), first=3000, second=3000)

    def test_entitlements_and_result_has_no_stationed_curves(self):
        for profile, allowed in (("mdot", True), ("tdot", False), ("aashto", False)):
            response = super_service.dispatch_safe("required_reverse_tangent", json.dumps({"inputs": inputs(profile), "radius_1": 4000, "radius_2": 3000}))
            self.assertEqual(response["ok"], allowed)
        advice = self.check()
        self.assertEqual(advice["result_type"], "reverse_tangent_check")
        self.assertEqual(advice["agency_minimum_status"], "not_evaluated")
        for curve in advice["curves"]:
            self.assertNotIn("pc_ft", curve)
            self.assertNotIn("pt_ft", curve)
        rejected = super_service.dispatch_safe("export_pdf", json.dumps({"entitlement": {"plan": "pro", "status": "active"},
            "curves": [{"results": advice["curves"][0]}]}))
        self.assertFalse(rejected["ok"])
        self.assertIn("no established stations", rejected["error"]["message"])

    def test_case_ii_rejects_nested_overrides_offsets_and_explicit_radii(self):
        values = inputs("aashto", roadway="divided_case_ii", case_ii={
            "left": {"lane_count": 2, "lane_width": 12, "pivot_offset": -12, "initial_slope": -.02},
            "right": {"lane_count": 4, "lane_width": 12, "pivot_offset": 12, "initial_slope": .02}})
        for changes in ({"case_ii_geometry_mode": "explicit_radii"}, {"case_ii": {"left": {}, "right": {}}},
                        {"case_ii": {**values["case_ii"], "left": {**values["case_ii"]["left"], "e_manual": .06}}},
                        {"case_ii": {**values["case_ii"], "left": {**values["case_ii"]["left"], "pivot_offset": 10000}}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check({**values, **changes})


if __name__ == "__main__":
    unittest.main()
