"""The imported Guardrail source must remain an unchanged pinned snapshot."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import update_guardrail


class GuardrailSourceTests(unittest.TestCase):
    def test_windows_checkout_preserves_pinned_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            checkout = Path(folder)
            target = checkout / "calculators/guardrail/upstream"
            shutil.copytree(update_guardrail.TARGET, target)
            attributes = update_guardrail.ROOT / ".gitattributes"
            if attributes.exists():
                shutil.copy2(attributes, checkout / ".gitattributes")

            def git(*args):
                subprocess.run(["git", "-C", str(checkout), *args], check=True, capture_output=True)

            git("init", "--quiet")
            git("config", "core.autocrlf", "true")
            git("add", ".")
            shutil.rmtree(target)
            git("checkout-index", "--all", "--force")
            with patch.object(update_guardrail, "TARGET", target):
                update_guardrail.verify()

    def test_pin_matches_every_imported_file(self):
        pin = update_guardrail.verify()
        self.assertEqual(pin["commit"], "4fe8b323b35644ce1cf32888607effbe6ffec999")
        self.assertEqual(pin["version"], "V9.0.2")

    def test_report_runtime_includes_vector_math(self):
        from calculators.catalog import browser_runtime_manifest

        runtime = browser_runtime_manifest()["calculators"]["guardrail"]
        self.assertIn("guardrail_pdf_math.py", update_guardrail.FILES)
        self.assertIn("calculators/guardrail/upstream/guardrail_pdf_math.py", runtime["modules"])
        self.assertIn("matplotlib", runtime["pyodide_packages"])

    def test_modified_source_or_incomplete_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "upstream"
            shutil.copytree(update_guardrail.TARGET, target)
            with patch.object(update_guardrail, "TARGET", target):
                source = target / "guardrail_engine.py"
                original = source.read_bytes()
                source.write_bytes(original + b"\n")
                with self.assertRaisesRegex(ValueError, "snapshot changed"):
                    update_guardrail.verify()
                source.write_bytes(original)
                manifest = target / "source.json"
                pin = json.loads(manifest.read_text())
                del pin["sha256"]["guardrail_engine.py"]
                manifest.write_text(json.dumps(pin))
                with self.assertRaisesRegex(ValueError, "file list"):
                    update_guardrail.verify()
