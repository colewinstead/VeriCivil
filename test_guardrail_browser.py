"""Adapter parity with the upstream corrected baseline, not engineering approval."""

import hashlib
from io import BytesIO
import itertools
import json
from pathlib import Path
import unittest

from calculators.guardrail import service
from guardrail_design import DEFAULT_L1_FT, ReportStyle
from guardrail_models import ReportModel
from guardrail_report import report_payload
from guardrail_pdf import generate_pdf_calc_sheet
from pypdf import PdfReader
import vericivil_service

FIXTURE = json.loads((service.UPSTREAM / "test_fixtures/phase3_baseline.json").read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def request(operation, values=None, **payload):
    return service.dispatch(operation, json.dumps({"values": values or service.DEFAULTS.copy(), **payload}))


class GuardrailBrowserTests(unittest.TestCase):
    def test_full_2592_case_boundary_matches_upstream_digest(self):
        outputs = []
        for speed, adt, (LA, L2, L2_opp), L1, terminal, flare in itertools.product(
            (30, 35, 40, 45, 50, 55, 60, 65, 70), (0, 749, 750, 1000, 1500, 5000, 6000, 10000),
            ((30, 10, 22), (28, 10, 22), (5, 10, 22)), (0, DEFAULT_L1_FT), (0, 25), (0, 13, 30),
        ):
            values = {**service.DEFAULTS, "offset_source": "direct", "LA": str(LA), "L2": str(L2),
                      "lane_width": str(L2_opp - L2), "L1_mode": "custom", "L1": str(L1),
                      "terminal_mode": "custom", "terminal": str(terminal), "flare_rate": str(flare),
                      "speed": str(speed), "adt": str(adt)}
            outputs.append(request("calculate", values)["results"])
        self.assertEqual(len(outputs), 2592)
        self.assertEqual(digest(outputs), FIXTURE["engineering"])

    def test_report_payload_and_page_fingerprints(self):
        for facility, style, flare in itertools.product(("two_lane_two_way", "divided_highway"), (1, 2, 3), (0, 30)):
            with self.subTest(facility=facility, style=style, flare=flare):
                values = {**service.DEFAULTS, "facility": facility, "added_distance": "12", "speed": "65",
                          "offset_source": "direct", "LA": "30", "flare_rate": str(flare),
                          "project": "A <b>B</b> & C", "route_location": "SR 8", "job_number": "123",
                          "prepared_by": "Author", "checked_by": "Reviewer", "calculation_date": "2026-10-01"}
                report = ReportModel(service.snapshot(values), ReportStyle(style), "2026-10-01 12:00")
                payload = report_payload(report)
                payload["__app_version"] = "V8.5"
                expected = FIXTURE["reports"][f"{facility}-{style}-{flare}"]
                self.assertEqual(digest(payload), expected["payload"])
                buffer = BytesIO()
                generate_pdf_calc_sheet(buffer, payload)
                pages = [{"box": list(page.mediabox),
                          "stream": hashlib.sha256(page.get_contents().get_data()).hexdigest(),
                          "text": hashlib.sha256(page.extract_text().encode()).hexdigest()}
                         for page in PdfReader(buffer).pages]
                self.assertEqual(pages, expected["pages"])

    def test_clearzone_and_divided_linked_manual_modes(self):
        from guardrail_engine import resolve_clear_zone
        for slope, selection, adt in itertools.product(("6:1_or_flatter", "5:1_to_4:1"),
                ("min", "mid", "max", "custom"), (749, 750, 1500, 1501, 6000, 6001)):
            values = {**service.DEFAULTS, "slope": slope, "clear_zone_selection": selection,
                      "custom_clear_zone": "90", "adt": str(adt)}
            self.assertEqual(request("calculate", values)["LA"], resolve_clear_zone(60, adt, slope, selection, 90))
        divided = {**service.DEFAULTS, "facility": "divided_highway", "opposing_distance_mode": "calculated"}
        self.assertEqual(request("calculate", divided)["roadway"]["L2_opp"], 98)
        divided["lane_width"] = "11.12345678"
        self.assertEqual(request("calculate", divided)["roadway"]["L2_opp"], 10 + 4 * 11.12345678 + 40)
        divided.update(opposing_distance_mode="manual", added_distance="17.25")
        self.assertEqual(request("calculate", divided)["roadway"]["L2_opp"], 27.25)

    def test_strict_numeric_and_selection_validation(self):
        for field, value in (("adt", "6,00"), ("adt", "NaN"), ("adt", "1e999"), ("adt", ""),
                             ("L2", "10 ft"), ("speed", "60.5"), ("flare_rate", "99"),
                             ("facility", "unknown"), ("pdf_style", "4"), ("calculation_date", "2026-02-30"),
                             ("calculation_date", "20261108"), ("calculation_date", "2026-W45-7")):
            response = service.dispatch_safe("calculate", json.dumps({"values": {**service.DEFAULTS, field: value}}))
            self.assertFalse(response["ok"], (field, value))
        self.assertEqual(request("calculate", {**service.DEFAULTS, "adt": "6,000"}), request("calculate"))
        with self.assertRaisesRegex(ValueError, "whole number"):
            request("calculate", {**service.DEFAULTS, "facility": "divided_highway", "lanes_this": "1.5"})

    def test_project_round_trip_recalculates_and_preserves_modes(self):
        values = {**service.DEFAULTS, "facility": "divided_highway", "added_distance": "13",
                  "L1_mode": "custom", "L1": "0", "terminal_mode": "custom", "terminal": "0",
                  "offset_source": "clearzone", "clear_zone_selection": "custom", "custom_clear_zone": "9",
                  "project": "A <b>B</b> & C", "include_appendices": "no", "pdf_style": "2"}
        saved = request("project_save", values)
        document = json.loads(saved["content"])
        self.assertNotIn("results", document)
        document["results"] = {"A": 9999999}
        loaded = request("project_load", content=json.dumps(document))
        self.assertEqual(loaded["values"], values)
        self.assertEqual(loaded["calculation"], request("calculate", values))
        self.assertFalse(loaded["engine_changed"])
        document["source_commit"] = "older-revision"
        self.assertTrue(request("project_load", content=json.dumps(document))["engine_changed"])

    def test_project_rejects_invalid_or_future_content(self):
        good = json.loads(request("project_save")["content"])
        invalid = ["", "[]", "null", "{", "x" * (service.MAX_PROJECT_BYTES + 1)]
        for changes in ({"version": 2}, {"version": True}, {"format": "other"}, {"values": {}},
                        {"values": {**service.DEFAULTS, "adt": "bad"}},
                        {"values": {**service.DEFAULTS, "project": "x" * 1001}},
                        {"values": {**service.DEFAULTS, "L2": True}}):
            invalid.append(json.dumps({**good, **changes}))
        for content in invalid:
            self.assertFalse(service.dispatch_safe("project_load", json.dumps({"content": content}))["ok"])

    def test_pdf_styles_and_both_facility_appendices(self):
        for facility in ("two_lane_two_way", "divided_highway"):
            for style in ("1", "2", "3"):
                values = {**service.DEFAULTS, "facility": facility, "opposing_distance_mode": "calculated",
                          "pdf_style": style, "project": "Synthetic browser parity case", "include_appendices": "no"}
                sheet = PdfReader(BytesIO(request("export_pdf", values)["content"]))
                self.assertEqual(len(sheet.pages), 2 if style == "3" else 1)
                self.assertIn("Synthetic browser parity case", sheet.pages[0].extract_text())
            values["include_appendices"] = "yes"
            package = PdfReader(BytesIO(request("export_pdf", values)["content"]))
            self.assertEqual(len(package.pages), 7)
            self.assertIn("Divided Highways" if facility == "divided_highway" else "Two-Lane, Two-Way", str(package.outline))

    def test_dispatch_is_free_and_unknown_operations_fail(self):
        response = vericivil_service.dispatch_safe("guardrail", "calculate", json.dumps({"values": service.DEFAULTS}))
        self.assertTrue(response["ok"])
        self.assertFalse(service.dispatch_safe("export_dxf", json.dumps({"values": service.DEFAULTS}))["ok"])


if __name__ == "__main__":
    unittest.main()
