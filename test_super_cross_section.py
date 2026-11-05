"""Analytical checks of presentation geometry, independent of pixel coordinates."""
import copy
import unittest

import Super
import aashto_superelevation
import super_cross_section
import super_batch
import super_service
from test_aashto_criteria import inputs


class CrossSectionTests(unittest.TestCase):
    def result(self, **changes):
        return aashto_superelevation.calculate(inputs(**changes))

    def inspect(self, result, station, direction="left"):
        return super_service.diagram_lookup(result, direction, station)["cross_section"]

    def assert_preview_frames(self, curves):
        original = copy.deepcopy(curves)
        for diagram in super_service.corridor_diagram(curves)["curves"]:
            result = curves[diagram["curve_index"]]["results"]
            frames = diagram["cross_section_frames"]
            self.assertEqual(frames[0]["station_ft"], diagram["domain"]["start_ft"])
            self.assertEqual(frames[-1]["station_ft"], diagram["domain"]["end_ft"])
            for frame in frames:
                packet = super_service.diagram_lookup(result, diagram["direction"], frame["station_ft"])
                self.assertEqual(frame["station"], packet["station"])
                self.assertEqual(frame["civil_station_ft"], Super.internal_to_civil_station(frame["station_ft"], result.get("station_equations")))
                for actual, exact in zip(frame["segments"], packet["cross_section"]["segments"]):
                    key = exact["name"] if diagram["cross_section"]["mode"] == "physical" else exact["side"]
                    self.assertEqual(actual, {**exact, "slope_pct": packet["lanes"][key]["slope_pct"]})
            for left, right in zip(frames, frames[1:]):
                self.assertLess(left["station_ft"], right["station_ft"])
                for fraction in (.25, .5, .75):
                    station = left["station_ft"] + fraction * (right["station_ft"] - left["station_ft"])
                    packet = super_service.diagram_lookup(result, diagram["direction"], station)
                    for a, b, exact in zip(left["segments"], right["segments"], packet["cross_section"]["segments"]):
                        key = exact["name"] if diagram["cross_section"]["mode"] == "physical" else exact["side"]
                        self.assertAlmostEqual(a["slope_pct"] + fraction * (b["slope_pct"] - a["slope_pct"]), packet["lanes"][key]["slope_pct"], places=10)
                        for edge in ("left", "right"):
                            for axis in ("x", "y"):
                                self.assertAlmostEqual(a[edge][axis] + fraction * (b[edge][axis] - a[edge][axis]), exact[edge][axis], places=10)
        self.assertEqual(curves, original)

    def test_preview_frames_cover_physical_and_schematic_breakpoints(self):
        for direction in ("left", "right"):
            for changes in ({}, {"roadway": "one_way", "initial_section": "single_slope", "initial_slope": "-0.02", "lane_widths": "11,11,11", "rotation_axis": "right_edge"}):
                self.assert_preview_frames([{"results": self.result(curve_direction=direction, **changes), "meta": {"curve_direction": direction}}])
            case = {"criteria_profile": "aashto-green-book-2018-2019-10", "roadway": "divided_case_ii", "pc": "1000", "pt": "3000", "curve_direction": direction,
                    "case_ii": {side: {"speed": 65, "radius": 3000, "lane_count": 4, "lane_width": 12, "pivot_offset": offset, "initial_slope": slope, "runoff_tangent_percent": 70}
                                for side, offset, slope in (("left", -20, -.02), ("right", 20, .02))}}
            self.assert_preview_frames([{"results": super_service.calculate_curve(case)["results"], "meta": {"curve_direction": direction}}])
        for profile in ("mdot-rdsd-2026-04-22", "tdot-rd11-2026-04-30"):
            result = super_service.calculate_curve({"criteria_profile": profile, "pc": "1000", "pt": "2000", "speed": "45", "radius": "1200", "facility": "undivided" if profile.startswith("tdot") else "centerline"})["results"]
            self.assert_preview_frames([{"results": result}])
        result = self.result()
        result["transition_method"] = "future_model"
        self.assertEqual(super_service.corridor_diagram([{"results": result}])["curves"][0]["cross_section_frames"], [])
        self.assertNotIn("cross_section_frames", super_service.curve_diagram(self.result()))

    def test_crown_bank_and_pivot_geometry_for_both_directions(self):
        for direction in ("left", "right"):
            for pivot in ("centerline", "left_edge", "right_edge"):
                with self.subTest(direction=direction, pivot=pivot):
                    result = self.result(curve_direction=direction, rotation_axis=pivot)
                    original = copy.deepcopy(result)
                    for station in (result["pnc_ft"], result["zero_crown_ft"], result["full_super_ft"], result["pnc_out_ft"]):
                        section = self.inspect(result, station, direction)
                        self.assertEqual(section["mode"], "physical")
                        left, right = section["segments"]
                        self.assertEqual(left["right"], right["left"])
                        pivot_points = [point for segment in section["segments"] for point in (segment["left"], segment["right"]) if point["x"] == section["pivot"]["x"]]
                        self.assertTrue(pivot_points)
                        self.assertTrue(all(abs(point["y"]) < 1e-12 for point in pivot_points))
                        if station == result["full_super_ft"]:
                            expected = -0.06 if direction == "left" else 0.06
                            for segment in section["segments"]:
                                actual = (segment["left"]["y"] - segment["right"]["y"]) / segment["width_ft"]
                                self.assertAlmostEqual(actual, expected, places=12)
                        if station == result["pnc_ft"]:
                            for segment in section["segments"]:
                                expected = -0.02 if segment["side"] == "left" else 0.02
                                actual = (segment["left"]["y"] - segment["right"]["y"]) / segment["width_ft"]
                                self.assertAlmostEqual(actual, expected, places=12)
                    self.assertEqual(result, original)

    def test_every_event_and_midpoint_agrees_with_existing_lane_lookup(self):
        result = self.result(roadway="one_way", initial_section="single_slope", initial_slope="-0.02", lane_widths="11,11,11", rotation_axis="right_edge")
        stations = sorted({event["station_ft"] for lane in result["section_lanes"] for event in lane["events"]})
        stations += [(a + b) / 2 for a, b in zip(stations, stations[1:])]
        bounds = super_service.curve_diagram(result)["cross_section"]["bounds"]
        for station in stations:
            section = self.inspect(result, station)
            existing = super_service.lookup(result, "left", str(station), "")["station"]
            self.assertEqual(section["bounds"], bounds)
            self.assertEqual(len(section["segments"]), 3)
            for segment in section["segments"]:
                edges = existing["edge_elevations"][segment["name"]]
                self.assertAlmostEqual(segment["left"]["y"], edges["left_elevation_ft"], places=12)
                self.assertAlmostEqual(segment["right"]["y"], edges["right_elevation_ft"], places=12)
                self.assertEqual(segment["slope_label"], existing["slopes"][segment["name"]]["label"])
            for left, right in zip(section["segments"], section["segments"][1:]):
                self.assertEqual(left["right"], right["left"])

    def test_retained_initial_slope_and_legacy_centerline_ramp(self):
        result = self.result(roadway="one_way", initial_section="single_slope", initial_slope="-0.02", lane_widths="12", rotation_axis="centerline", radius="100000", e_manual="")
        section = self.inspect(result, result["pc_ft"])
        segment = section["segments"][0]
        self.assertAlmostEqual(segment["left"]["y"], -0.12)
        self.assertAlmostEqual(segment["right"]["y"], 0.12)
        self.assertEqual(section["pivot"]["x"], 0)

    def test_legacy_mdot_and_tdot_are_explicit_schematics(self):
        for profile in ("mdot-rdsd-2026-04-22", "tdot-rd11-2026-04-30"):
            result = super_service.calculate_curve({"criteria_profile": profile, "pc": "1000", "pt": "2000", "speed": "45", "radius": "1200", "facility": "undivided" if profile.startswith("tdot") else "centerline"})["results"]
            section = self.inspect(result, result["full_super_ft"])
            self.assertEqual(section["mode"], "schematic")
            self.assertNotIn("pivot", section)
            self.assertTrue(all("width_ft" not in segment for segment in section["segments"]))
            self.assertIn("not defined", section["message"])
        result.pop("calculation_metadata", None)
        self.assertEqual(self.inspect(result, result["full_super_ft"])["mode"], "schematic")

    def test_invalid_unknown_and_out_of_domain_geometry_is_not_drawn(self):
        result = self.result()
        self.assertEqual(self.inspect(result, -100)["mode"], "unavailable")
        for station in ("-100", "NaN", "Infinity"):
            with self.assertRaises(ValueError):
                super_service.diagram_lookup(result, "left", station)
        for change in ({"transition_method": "future_model"}, {"section_definition": {}}, {"pivot_offset_ft": float("nan")}):
            self.assertEqual(super_cross_section.section_model({**result, **change}, "left")["mode"], "unavailable")
        malformed = copy.deepcopy(result)
        del malformed["section_lanes"][0]["side"]
        self.assertEqual(super_cross_section.section_model(malformed, "left")["mode"], "unavailable")

    def test_station_entry_uses_existing_equation_parser(self):
        result = self.result()
        result["station_equations"] = [{"internal": 1500, "back": 1500, "ahead": 2500}]
        result["alignment_station_range"] = [0, 3000]
        answer = super_service.diagram_lookup(result, "left", "26+00")
        self.assertEqual(answer["station_ft"], 1600)
        self.assertEqual(answer["station"], "26+00.000")
        for ahead in (2500, 1000):
            result["station_equations"][0]["ahead"] = ahead
            self.assert_preview_frames([{"results": result}])
            frames = super_service.corridor_diagram([{"results": result}])["curves"][0]["cross_section_frames"]
            boundary = next(frame for frame in frames if frame["station_ft"] == 1500)
            self.assertEqual(boundary["civil_station_ft"], ahead)
            self.assertEqual(boundary["station_suffix"], "R2")
            for left, right in zip(frames, frames[1:]):
                station = (left["station_ft"] + right["station_ft"]) / 2
                civil = left["civil_station_ft"] + (station - left["station_ft"])
                preview = Super.format_station(civil) + left["station_suffix"]
                self.assertAlmostEqual(Super.parse_station_reference(preview, result["station_equations"], result["alignment_station_range"]), station, places=3)

    def test_coordinated_compound_and_reverse_sections_use_recorded_profiles(self):
        curves = []
        for index, rate in enumerate(("0.03", "0.05")):
            result = aashto_superelevation.calculate(inputs(pc=str(1000 + index * 1000), pt=str(2000 + index * 1000),
                e_manual=rate, Lr_manual="200", Lt_manual="100"), compound_sides=("exit",) if index == 0 else ("entry",))
            curves.append({"results": result, "meta": {"curve_direction": "left"}})
        curves = super_batch.coordinate_compound_curve_transitions(curves)
        self.assert_preview_frames(curves)
        plan = curves[0]["results"]["compound_curve_transitions"]["exit"]
        for curve in curves:
            for station in (plan["start_ft"], (plan["start_ft"] + plan["end_ft"]) / 2, plan["end_ft"]):
                section = self.inspect(curve["results"], station)
                existing = super_service.lookup(curve["results"], "left", str(station), "")["station"]
                for segment in section["segments"]:
                    self.assertAlmostEqual(segment["left"]["y"], existing["edge_elevations"][segment["name"]]["left_elevation_ft"], places=12)
        reverse = []
        for index, direction in enumerate(("left", "right")):
            result = super_service.calculate_curve({"pc": str(1000 + index * 1200), "pt": str(2000 + index * 1200),
                "speed": "45", "radius": "1200", "e_manual": "0.06", "Lr_manual": "100", "Lt_manual": "25", "curve_direction": direction})["results"]
            reverse.append({"results": result, "meta": {"curve_direction": direction}})
        reverse = super_service.coordinate_reverse_curves(reverse, True, [[0, 1]])
        self.assert_preview_frames(reverse)
        for curve in reverse:
            result = curve["results"]
            self.assertIn("reverse_curve_coordination", result)
            for station in (result["full_super_ft"], result["full_super_out_ft"]):
                answer = super_service.diagram_lookup(result, curve["meta"]["curve_direction"], station)
                for segment in answer["cross_section"]["segments"]:
                    edge = segment["left"] if segment["side"] == "left" else segment["right"]
                    self.assertAlmostEqual(edge["y"], answer["lanes"][segment["side"]]["slope_pct"] / 100, places=12)


if __name__ == "__main__":
    unittest.main()
