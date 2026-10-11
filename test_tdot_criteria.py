from __future__ import annotations

import unittest

import Super
from criteria_info import criteria_metadata, criteria_profiles
import super_exports
import super_service
import tdot_criteria


class TDOTCriteriaTests(unittest.TestCase):
    def calculate(
        self,
        *,
        speed: str = "50",
        radius: str = "2280",
        area: str = "rural",
        lanes: str = "2",
        facility: str = "undivided",
    ) -> dict:
        return Super.calculate_superelevation(
            "10+00",
            "20+00",
            speed,
            radius,
            facility,
            area,
            "12",
            lanes,
            "",
            "",
            "",
            "0.02",
            "",
            "",
            criteria_profile="tdot",
        )

    def test_profile_registry_keeps_mdot_default_and_adds_tdot(self):
        self.assertEqual(criteria_metadata()["profile_id"], "mdot-rdsd-2026-04-22")
        self.assertEqual(criteria_metadata("tdot")["profile_id"], tdot_criteria.TDOT_PROFILE_ID)
        self.assertEqual(
            [profile["profile_id"] for profile in criteria_profiles()],
            ["mdot-rdsd-2026-04-22", tdot_criteria.TDOT_PROFILE_ID, "aashto-green-book-2018-2019-10"],
        )

    def test_transcribed_radius_tables_are_structurally_monotonic(self):
        for speeds, rows in (
            (tdot_criteria.URBAN_SPEEDS, tdot_criteria.URBAN_EMAX_4_ROWS),
            (tdot_criteria.RURAL_SPEEDS, tdot_criteria.RURAL_EMAX_8_ROWS),
        ):
            self.assertTrue(all(len(radii) == len(speeds) for _, radii in rows))
            rates = [rate for rate, _ in rows[1:]]
            self.assertEqual(rates, sorted(rates))
            for column in range(len(speeds)):
                radii = [row_radii[column] for _, row_radii in rows]
                self.assertTrue(all(left >= right for left, right in zip(radii, radii[1:])))

    def test_tdot_metadata_records_both_requested_standard_sections(self):
        metadata = criteria_metadata("tdot")
        documents = metadata["source_documents"]
        self.assertIn("RD11TYP05", documents[0]["applicable_anchors"])
        self.assertIn("RD11SLP06", documents[0]["applicable_anchors"])
        typical = next(document for document in documents if "typical sections" in document["title"].lower())
        self.assertIn("RD11-TS-1", typical["applicable_sheets"])
        self.assertIn("RD11-TS-7B", typical["applicable_sheets"])
        self.assertIn("never selected automatically", metadata["active_table_policy"]["allowable_6_percent"])

    def test_rural_design_guide_example_matches_tdot_values(self):
        result = self.calculate()
        self.assertAlmostEqual(result["e"], 0.046)
        self.assertEqual(result["Lr"], 110.0)
        self.assertAlmostEqual(result["Lt"], 47.8260869565)
        self.assertAlmostEqual(result["segments"]["total_transition"], 157.8260869565)
        self.assertEqual(round(result["Lt"], 2), 47.83)
        self.assertEqual(round(result["segments"]["total_transition"], 2), 157.83)
        self.assertEqual(round(result["segments"]["total_transition"]), 158)
        self.assertAlmostEqual(result["pnc_ft"], 921.0869565217)
        self.assertAlmostEqual(result["full_super_ft"], 1078.9130434783)
        self.assertTrue(any("spiral" in warning.lower() for warning in result["warnings"]))

    def test_four_lane_design_guide_example_matches_tdot_values(self):
        result = self.calculate(speed="30", radius="261", area="urban", lanes="4")
        self.assertAlmostEqual(result["e"], 0.03)
        self.assertEqual(result["Lr"], 82.0)
        self.assertEqual(round(result["Lt"], 2), 54.67)
        self.assertEqual(round(result["segments"]["total_transition"], 2), 136.67)
        self.assertEqual(round(result["segments"]["total_transition"]), 137)

    def test_rural_table_minimum_and_six_lane_runoff_cross_check(self):
        two_lane = self.calculate(speed="70", radius="1810", lanes="2")
        six_lane = self.calculate(speed="70", radius="1810", lanes="6")
        self.assertAlmostEqual(two_lane["e"], 0.08)
        self.assertEqual(two_lane["Lr"], 240.0)
        self.assertEqual(six_lane["Lr"], 482.0)

    def test_urban_table_uses_conservative_next_rate(self):
        exact = self.calculate(speed="50", radius="4280", area="urban")
        between = self.calculate(speed="50", radius="4279", area="urban")
        self.assertAlmostEqual(exact["e"], 0.022)
        self.assertAlmostEqual(between["e"], 0.024)
        self.assertAlmostEqual(exact["e_max"], 0.04)

    def test_normal_crown_row_has_no_transition(self):
        result = self.calculate(speed="50", radius="8150")
        self.assertTrue(result["normal_crown_only"])
        self.assertEqual(result["e"], 0.0)
        self.assertEqual(result["Lr"], 0.0)
        self.assertEqual(result["Lt"], 0.0)

    def test_below_minimum_radius_requires_review(self):
        result = self.calculate(speed="70", radius="1809")
        self.assertAlmostEqual(result["e"], 0.08)
        self.assertTrue(any("below" in warning.lower() for warning in result["warnings"]))

    def test_tdot_rejects_non_tabulated_speed_and_lane_count(self):
        with self.assertRaisesRegex(ValueError, "supports these design speeds"):
            self.calculate(speed="47")
        with self.assertRaisesRegex(ValueError, "lane count from 2 through 6"):
            self.calculate(lanes="7")

    def test_divided_lane_geometry_is_blocked_instead_of_using_undivided_events(self):
        with self.assertRaisesRegex(ValueError, "carriageway-specific lane/pivot model"):
            self.calculate(facility="divided")

    def test_lane_events_are_chronological_and_use_tdot_stations(self):
        result = self.calculate()
        left, right = super_exports.build_lane_rows(result, "left")
        for rows in (left, right):
            stations = [row["station_ft"] for row in rows]
            self.assertEqual(stations, sorted(stations))
        zero = next(row for row in right if row["label"] == "0%")
        self.assertAlmostEqual(zero["station_ft"], result["zero_crown_ft"])

    def test_service_routes_selected_profile_to_shared_engine(self):
        response = super_service.calculate_curve(
            {
                "criteria_profile": tdot_criteria.TDOT_PROFILE_ID,
                "pc": "10+00",
                "pt": "20+00",
                "speed": "50",
                "radius": "2280",
                "facility": "undivided",
                "area": "rural",
            }
        )
        self.assertEqual(
            response["results"]["calculation_metadata"]["criteria"]["profile_id"],
            tdot_criteria.TDOT_PROFILE_ID,
        )
        self.assertAlmostEqual(response["baseline"]["e"], 0.046)

    def test_export_surfaces_tdot_engineering_warning(self):
        result = self.calculate()
        curve = {"results": result, "meta": {"curve_direction": "left"}, "notes": ""}
        pdf = super_service.export_pdf([curve])
        self.assertTrue(pdf["content"].startswith(b"%PDF"))
        self.assertTrue(any("spiral" in warning.lower() for warning in pdf["warnings"]))

    def test_default_mdot_outputs_match_explicit_mdot_profile(self):
        arguments = (
            "10+00",
            "20+00",
            "50",
            "2000",
            "centerline",
            "rural",
            "12",
            "2",
            "",
            "",
            "",
            "0.02",
            "",
            "",
        )
        default = Super.calculate_superelevation(*arguments)
        explicit = Super.calculate_superelevation(*arguments, criteria_profile="mdot")
        keys = ["e", "Lr", "Lt", "pnc_ft", "reverse_crown_ft", "full_super_ft"]
        self.assertEqual({key: default[key] for key in keys}, {key: explicit[key] for key in keys})


if __name__ == "__main__":
    unittest.main()
