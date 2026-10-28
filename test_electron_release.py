import hashlib
import json
import plistlib
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.package_electron_release import package_release
from scripts.stage_desktop_installers import stage_installers


class ElectronReleaseTests(unittest.TestCase):
    def test_installer_staging_excludes_update_feeds_and_stale_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "desktop/installers/win32-x64"
            source.mkdir(parents=True)
            installer = source / "VeriCivil-Superelevation-1.7.0-win-x64-unsigned.exe"
            installer.write_bytes(b"synthetic installer")
            (source / "latest-win32-x64.yml").write_text("must not publish unsigned feed")
            staged = stage_installers(root, "win32", "x64", "1.7.0")
            self.assertEqual(staged[0].read_bytes(), installer.read_bytes())
            self.assertFalse((root / "desktop/release-assets/latest-win32-x64.yml").exists())
            self.assertIn(hashlib.sha256(installer.read_bytes()).hexdigest(), (root / "desktop/release-assets/SHA256SUMS-installers-win32-x64.txt").read_text())
            with self.assertRaisesRegex(ValueError, "missing"):
                stage_installers(root, "win32", "x64", "1.7.1")

    def test_native_icons_have_multiple_resolutions_and_transparency(self):
        icons = Path(__file__).resolve().parent / "desktop/icons"
        with Image.open(icons / "vericivil.ico") as icon:
            self.assertEqual(icon.format, "ICO")
            self.assertEqual(icon.ico.sizes(), {(size, size) for size in (16, 24, 32, 48, 64, 128, 256)})
            for size in icon.ico.sizes():
                frame = icon.ico.getimage(size)
                self.assertEqual(frame.mode, "RGBA")
                self.assertEqual(frame.getextrema()[3], (0, 255))
        with Image.open(icons / "vericivil.icns") as icon:
            self.assertEqual(icon.format, "ICNS")
            self.assertTrue({(size, size, 1) for size in (128, 256, 512)}.issubset(icon.info["sizes"]))
            icon.load()
            self.assertEqual(icon.mode, "RGBA")
            self.assertEqual(icon.getextrema()[3], (0, 255))

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
            attempts = []
            def create(command, **_kwargs):
                if command[1] == "verify":
                    return
                attempts.append(command)
                if len(attempts) == 1:
                    raise subprocess.CalledProcessError(1, command, stderr="hdiutil: create failed - Resource busy")
                Path(command[-1]).write_bytes(b"synthetic disk image")
            run.side_effect = create
            with patch("scripts.package_electron_release.time.sleep") as sleep:
                archive, checksum = package_release(self.root, "darwin", "arm64", "1.2.3")
                sleep.assert_called_once_with(2)
            self.assertEqual(archive.suffix, ".dmg")
            self.assertTrue(checksum.is_file())
            self.assertEqual(len(attempts), 2)
            self.assertEqual(run.call_args.args[0][:2], ["hdiutil", "verify"])
            run.reset_mock()
            run.side_effect = subprocess.CalledProcessError(1, ["hdiutil"], stderr="Permission denied")
            with patch("scripts.package_electron_release.time.sleep") as sleep:
                with self.assertRaises(subprocess.CalledProcessError):
                    package_release(self.root, "darwin", "arm64", "1.2.3")
                sleep.assert_not_called()
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
