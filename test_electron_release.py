import hashlib
import json
import plistlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.package_electron_release import package_release


class ElectronReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        staged = self.root / "desktop/app"
        staged.mkdir(parents=True)
        (staged / "package.json").write_text(json.dumps({"version": "1.2.3"}))

    def test_windows_archive_contains_executable_and_runtime_with_matching_checksum(self):
        folder = self.root / "desktop/releases/VeriCivil Desktop Preview-win32-x64"
        (folder / "resources").mkdir(parents=True)
        (folder / "VeriCivil Desktop Preview.exe").write_bytes(b"synthetic executable")
        (folder / "resources/app.asar").write_bytes(b"synthetic runtime")
        archive, checksum = package_release(self.root, "win32", "x64", "1.2.3")
        with zipfile.ZipFile(archive) as contents:
            prefix = folder.name + "/"
            self.assertEqual(contents.read(prefix + "VeriCivil Desktop Preview.exe"), b"synthetic executable")
            self.assertEqual(contents.read(prefix + "resources/app.asar"), b"synthetic runtime")
        self.assertEqual(checksum.read_text(), f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")

    def test_missing_windows_runtime_and_stale_staged_version_are_refused(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            package_release(self.root, "win32", "x64", "1.2.3")
        with self.assertRaisesRegex(ValueError, "staged version"):
            package_release(self.root, "win32", "x64", "1.2.4")

    def test_mac_version_is_checked_before_disk_image_creation(self):
        app = self.root / "desktop/releases/VeriCivil Desktop Preview-darwin-arm64/VeriCivil Desktop Preview.app/Contents"
        (app / "MacOS").mkdir(parents=True)
        (app / "MacOS/VeriCivil Desktop Preview").write_bytes(b"synthetic executable")
        info = {"CFBundleShortVersionString": "1.2.2", "CFBundleExecutable": "VeriCivil Desktop Preview"}
        (app / "Info.plist").write_bytes(plistlib.dumps(info))
        with patch("scripts.package_electron_release.subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "Mac app version"):
                package_release(self.root, "darwin", "arm64", "1.2.3")
            run.assert_not_called()
            info["CFBundleShortVersionString"] = "1.2.3"
            (app / "Info.plist").write_bytes(plistlib.dumps(info))
            run.side_effect = lambda command, **_kwargs: Path(command[-1]).write_bytes(b"synthetic disk image")
            archive, checksum = package_release(self.root, "darwin", "arm64", "1.2.3")
            self.assertEqual(archive.suffix, ".dmg")
            self.assertTrue(checksum.is_file())
            self.assertEqual(run.call_args.args[0][:2], ["hdiutil", "create"])


if __name__ == "__main__":
    unittest.main()
