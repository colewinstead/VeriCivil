import io
import logging
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import Super
from app_info import APP_VERSION, CALCULATION_ENGINE_VERSION
import app_logging
from criteria_info import criteria_metadata
import super_batch
import super_dxf
import super_exports
import super_landxml
import super_pdf
import super_project
from scripts.generate_windows_version_info import generate, version_tuple


LANDXML_FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "sr82_synthetic.xml"


class PilotReadinessTests(unittest.TestCase):
    def sample_results(self):
        return Super.calculate_superelevation(
            "120+00", "140+00", "45", "1200", "centerline", "rural", "12", "2", "", "", "", "0.02", "", ""
        )

    def sample_curve(self):
        return {
            "results": self.sample_results(),
            "meta": {
                "project_name": "Synthetic Pilot Check",
                "route_name": "SR 82",
                "alignment_name": "SR 82",
                "curve_name": "Curve 1",
                "curve_direction": "right",
            },
            "notes": "Synthetic test data only",
        }

    def test_new_calculation_records_engine_criteria_and_overrides(self):
        results = self.sample_results()
        metadata = results["calculation_metadata"]
        self.assertEqual(metadata["engine_version"], CALCULATION_ENGINE_VERSION)
        self.assertEqual(metadata["criteria"]["profile_id"], "mdot-rdsd-2026-04-22")
        self.assertIn("RESPONSIBLE PROJECT PE MUST VERIFY", metadata["criteria"]["source_status"])
        self.assertEqual(metadata["criteria"]["source_documents"][1]["compilation_revision"], "2026-04-22")
        self.assertEqual(metadata["criteria"]["source_documents"][1]["issue_date"], "2017-08-01")
        self.assertFalse(metadata["manual_overrides"]["superelevation_rate"])
        self.assertFalse(metadata["manual_overrides"]["normal_crown"])

    def test_current_project_schema_records_release_metadata_and_round_trips(self):
        payload = {
            "version": super_project.PROJECT_VERSION,
            "application_version": APP_VERSION,
            "calculation_engine_version": CALCULATION_ENGINE_VERSION,
            "criteria": criteria_metadata(),
            "vars": {"pc": "120+00"},
            "curves": [self.sample_curve()],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pilot-project.json"
            super_project.save_project(path, payload)
            loaded = super_project.load_project(path)
            leftovers = list(path.parent.glob(f".{path.name}.*.tmp"))
        self.assertEqual(loaded["version"], super_project.PROJECT_VERSION)
        self.assertEqual(loaded["application_version"], APP_VERSION)
        self.assertEqual(loaded["calculation_engine_version"], CALCULATION_ENGINE_VERSION)
        self.assertEqual(loaded["criteria"]["profile_id"], "mdot-rdsd-2026-04-22")
        self.assertEqual(leftovers, [])

    def test_future_project_schema_is_refused(self):
        with self.assertRaisesRegex(super_project.ProjectFormatError, "newer application release"):
            super_project.normalize_project({"version": super_project.PROJECT_VERSION + 1})

    def test_project_provenance_does_not_relabel_legacy_calculations(self):
        engine, criteria = super_project.calculation_provenance([{"results": {"inputs": {}}}])
        self.assertEqual(engine, "legacy-unversioned")
        self.assertEqual(criteria["profile_id"], "legacy-unversioned")

    def test_invalid_project_json_reports_line_and_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "broken.json"
            path.write_text('{"version": 3,', encoding="utf-8")
            with self.assertRaisesRegex(super_project.ProjectFormatError, r"line 1, column"):
                super_project.load_project(path)

    def test_logging_writes_rotating_user_log(self):
        logger = logging.getLogger(app_logging.LOGGER_NAME)
        old_handlers = list(logger.handlers)
        for handler in old_handlers:
            logger.removeHandler(handler)
            handler.close()
        old_override = os.environ.get("SUPERELEVATION_LOG_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.environ["SUPERELEVATION_LOG_DIR"] = tmpdir
                try:
                    try:
                        raise RuntimeError("synthetic failure")
                    except RuntimeError as exc:
                        path = app_logging.record_exception("test_operation", exc)
                    for handler in logger.handlers:
                        handler.flush()
                    content = path.read_text(encoding="utf-8")
                    self.assertIn("operation=test_operation", content)
                    self.assertIn("RuntimeError", content)
                finally:
                    # Windows will not delete the temporary log while its
                    # RotatingFileHandler still has the file open.
                    for handler in list(logger.handlers):
                        logger.removeHandler(handler)
                        handler.close()
        finally:
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()
            if old_override is None:
                os.environ.pop("SUPERELEVATION_LOG_DIR", None)
            else:
                os.environ["SUPERELEVATION_LOG_DIR"] = old_override

    def test_error_messages_are_operation_specific(self):
        self.assertIn("well-formed XML", app_logging.friendly_error("landxml", ET.ParseError("bad"), "a.xml"))
        self.assertIn("ORD CSV", app_logging.friendly_error("csv_export", RuntimeError("bad"), "a.csv"))
        self.assertIn("newer", app_logging.friendly_error("project_load", super_project.ProjectFormatError("newer"), "a.json"))

    def test_pdf_contains_release_traceability(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.pdf"
            super_pdf.export_pdf(str(path), [self.sample_curve()])
            content = path.read_bytes()
        self.assertIn(f"Application {APP_VERSION}".encode(), content)
        self.assertIn(CALCULATION_ENGINE_VERSION.encode(), content)

    def test_pdf_export_excludes_agency_and_consultant_logos(self):
        source = (Path(__file__).parent / "super_pdf.py").read_text(encoding="utf-8")
        self.assertNotIn("MDOT_PNG_B64", source)
        self.assertNotIn("STANTEC_PNG_B64", source)

    def test_windows_version_resource_uses_authoritative_version(self):
        self.assertEqual(version_tuple(APP_VERSION), (1, 5, 5, 0))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "version.txt"
            generate(path)
            content = path.read_text(encoding="utf-8")
        self.assertIn(f"StringStruct('ProductVersion', '{APP_VERSION}')", content)

    def test_windows_build_signs_before_final_checksums(self):
        root = Path(__file__).parent
        script = (root / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
        exe_sign = script.index('Set-ReleaseSignature -Path "dist/SuperElevation.exe"')
        installer_sign = script.index("Set-ReleaseSignature -Path $InstallerPath")
        checksum = script.index("Get-FileHash -LiteralPath $ReleaseFile.FullName")
        self.assertLess(exe_sign, installer_sign)
        self.assertLess(installer_sign, checksum)
        self.assertIn('Where-Object { $_.Name -ne "SHA256SUMS.txt" }', script)

    def test_desktop_release_builds_remain_available_manually(self):
        root = Path(__file__).parent
        script = (root / "scripts" / "build_macos.sh").read_text(encoding="utf-8")
        spec = (root / "SuperElevationMac.spec").read_text(encoding="utf-8")
        release_workflow = (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        macos_workflow = (root / ".github" / "workflows" / "macos-build.yml").read_text(encoding="utf-8")
        windows_workflow = (root / ".github" / "workflows" / "windows-build.yml").read_text(encoding="utf-8")
        self.assertIn('release_arch="Apple-Silicon"', script)
        self.assertIn('release_arch="Intel"', script)
        self.assertIn("hdiutil create", script)
        self.assertIn('lipo "$executable" -verify_arch', script)
        self.assertIn('"LSMinimumSystemVersion": "15.0"', spec)
        self.assertIn('bundle_identifier="com.colewinstead.superelevationcalculator"', spec)
        self.assertIn("workflow_dispatch:", macos_workflow)
        self.assertIn("macos-15-intel", macos_workflow)
        self.assertNotIn("pull_request:", macos_workflow)
        self.assertIn("workflow_dispatch:", windows_workflow)
        self.assertNotIn("pull_request:", windows_workflow)
        self.assertNotIn("build-windows:", release_workflow)
        self.assertNotIn("build-macos:", release_workflow)
        self.assertIn("needs: [validate-version, build-browser]", release_workflow)

    def test_pilot_certificate_release_contains_no_private_key_export(self):
        root = Path(__file__).parent
        create_script = (root / "scripts" / "new_pilot_signing_certificate.ps1").read_text(encoding="utf-8")
        build_script = (root / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
        trust_script = (root / "scripts" / "install_pilot_public_certificate.ps1").read_text(encoding="utf-8")
        self.assertIn("Export-Certificate", create_script)
        self.assertIn("Export-Certificate", build_script)
        self.assertIn("Pilot-Root.cer", create_script)
        self.assertIn("Pilot-Root.cer", build_script)
        self.assertNotIn("Export-PfxCertificate", create_script)
        self.assertNotIn("Export-PfxCertificate", build_script)
        self.assertIn("AcknowledgePilotTrust", trust_script)
        self.assertIn("Cert:\\CurrentUser\\TrustedPublisher", trust_script)
        self.assertIn("Cert:\\CurrentUser\\Root", trust_script)

    def test_release_verifier_checks_hashes_signatures_and_private_chain(self):
        script = (Path(__file__).parent / "scripts" / "verify_windows_release.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-FileHash", script)
        self.assertIn("Get-AuthenticodeSignature", script)
        self.assertIn("X509Chain", script)
        self.assertIn("Pilot root thumbprint", script)

    def test_end_to_end_file_workflows_with_synthetic_fixture(self):
        landxml = super_landxml.load_landxml(LANDXML_FIXTURE)
        curves = super_batch.build_curves_from_presets(
            landxml.curve_records(),
            {
                "project_name": "Synthetic Pilot Check",
                "route_name": "SR 82",
                "speed": "60",
                "facility": "centerline",
                "area": "rural",
                "lane_width": "12",
                "lanes_rotated": "2",
                "e_manual": "",
                "friction": "",
                "rel_grad": "",
                "normal_crown": "0.02",
                "Lr_manual": "",
                "Lt_manual": "",
                "curve_notes": "Synthetic test data only",
            },
        )
        csv_buffer = io.StringIO()
        super_exports.write_ord_csv(csv_buffer, curves)
        self.assertIn("SuperelevationLane,Station,CrossSlope", csv_buffer.getvalue())

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf_path = root / "report.pdf"
            dxf_path = root / "overlay.dxf"
            project_path = root / "project.json"
            super_pdf.export_pdf(str(pdf_path), curves)
            super_dxf.export_overlay_dxf(dxf_path, curves, landxml)
            super_project.save_project(
                project_path,
                {
                    "version": 3,
                    "application_version": APP_VERSION,
                    "calculation_engine_version": CALCULATION_ENGINE_VERSION,
                    "criteria": criteria_metadata(),
                    "vars": {"landxml_path": str(LANDXML_FIXTURE)},
                    "curves": curves,
                },
            )
            loaded = super_project.load_project(project_path)
            self.assertGreater(pdf_path.stat().st_size, 1_000)
            self.assertGreater(dxf_path.stat().st_size, 1_000)
            self.assertEqual(len(loaded["curves"]), len(curves))


if __name__ == "__main__":
    unittest.main()
