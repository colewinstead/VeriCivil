import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from app_info import APP_VERSION, CALCULATION_ENGINE_VERSION
from scripts.create_pilot_evidence_bundle import ROOT, create_bundle
from scripts.create_support_diagnostics import create_diagnostics


class PilotOperationsTests(unittest.TestCase):
    def test_private_evidence_bundle_is_created_outside_repository(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "pilot-evidence"
            create_bundle(output)
            identity = json.loads((output / "release-identity.json").read_text(encoding="utf-8"))

            self.assertEqual(identity["application_version"], APP_VERSION)
            self.assertEqual(identity["calculation_engine_version"], CALCULATION_ENGINE_VERSION)
            self.assertEqual(identity["project_schema_version"], 5)
            self.assertEqual(identity["approval_status"], "unapproved")
            self.assertIsInstance(identity["tracked_worktree_clean"], bool)
            self.assertIsInstance(identity["untracked_files_present"], bool)
            self.assertEqual(
                {profile["profile_id"] for profile in identity["criteria_profiles"]},
                {"mdot-rdsd-2026-04-22", "tdot-rd11-2026-04-30", "aashto-green-book-2018-2019-10"},
            )
            self.assertTrue((output / "01-private-pe-validation-record.md").is_file())
            self.assertTrue((output / "02-pilot-acceptance-record.md").is_file())
            self.assertTrue((output / "08-release-and-rollback").is_dir())

    def test_private_evidence_bundle_refuses_repository_destination(self):
        with self.assertRaisesRegex(ValueError, "outside the public repository"):
            create_bundle(ROOT / "private-pilot-evidence")

    def test_support_bundle_contains_metadata_without_engineering_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "support.zip"
            create_diagnostics(output, "grace")
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist(), ["diagnostics.json"])
                manifest = json.loads(archive.read("diagnostics.json"))

            self.assertEqual(manifest["entitlement_status"], "grace")
            self.assertFalse(manifest["engineering_files_included"])
            self.assertFalse(manifest["user_selected_log_included"])

    def test_support_bundle_refuses_repository_and_unstructured_status(self):
        with self.assertRaisesRegex(ValueError, "outside the public repository"):
            create_diagnostics(ROOT / "support.zip", "active")
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "Entitlement status"):
                create_diagnostics(Path(temp_dir) / "support.zip", "user-123-pro")

    def test_explicit_log_is_redacted_and_engineering_attachment_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            log_path = temp / "application.log"
            log_path.write_text(
                "user=engineer@example.com path=C:\\Users\\Engineer\\Projects\\Road token=private-value\n",
                encoding="utf-8",
            )
            output = temp / "support.zip"
            create_diagnostics(output, "active", log_path)
            with zipfile.ZipFile(output) as archive:
                redacted = archive.read("application-redacted.log").decode("utf-8")

            self.assertIn("[EMAIL]", redacted)
            self.assertIn("[LOCAL_PATH]", redacted)
            self.assertNotIn("private-value", redacted)

            project = temp / "project.json"
            project.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "application .log"):
                create_diagnostics(temp / "forbidden.zip", "active", project)

    def test_operating_documents_keep_external_approval_gates_explicit(self):
        commercial = (ROOT / "docs" / "COMMERCIAL_READINESS.md").read_text(encoding="utf-8")
        operations = (ROOT / "docs" / "PILOT_OPERATIONS.md").read_text(encoding="utf-8")
        terms = (ROOT / "web" / "app" / "terms" / "page.tsx").read_text(encoding="utf-8")
        privacy = (ROOT / "web" / "app" / "privacy" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("Payment and automated Pro activation remain disabled", operations)
        self.assertIn("incorrect-result suspicion", operations)
        self.assertIn("licensed professional", terms)
        self.assertIn("Engineering work stays local", privacy)
        self.assertIn("internal PE record", commercial)

        verifier = (ROOT / "scripts" / "verify_windows_release.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$RequireTimestamp", verifier)
        self.assertIn("$Signature.TimeStamperCertificate", verifier)


if __name__ == "__main__":
    unittest.main()
