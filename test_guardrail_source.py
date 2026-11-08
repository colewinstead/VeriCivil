"""The imported Guardrail source must remain an unchanged pinned snapshot."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import update_guardrail


class GuardrailSourceTests(unittest.TestCase):
    def test_pin_matches_every_imported_file(self):
        pin = update_guardrail.verify()
        self.assertEqual(pin["commit"], "c5df84ad9376442e6ba0cac1d37611a3cd34df2b")
        self.assertEqual(pin["version"], "V8.5.2")

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
