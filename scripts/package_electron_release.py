"""Archive an existing Electron preview and record its download checksum."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import shutil
import subprocess
from pathlib import Path


def package_release(root: Path, platform: str, arch: str, version: str) -> tuple[Path, Path]:
    targets = {("darwin", "arm64"): "macOS-Apple-Silicon", ("darwin", "x64"): "macOS-Intel", ("win32", "x64"): "Windows-x64"}
    target = targets[(platform, arch)]
    staged = root / "desktop" / "app" / "package.json"
    if json.loads(staged.read_text())["version"] != version:
        raise ValueError("Rebuild the Electron app before archiving: staged version differs from APP_VERSION.")
    folder = root / "desktop" / "releases" / f"VeriCivil Desktop Preview-{platform}-{arch}"
    if platform == "darwin":
        application = folder / "VeriCivil Desktop Preview.app"
        with (application / "Contents" / "Info.plist").open("rb") as source:
            info = plistlib.load(source)
        if info["CFBundleShortVersionString"] != version:
            raise ValueError("Packaged Mac app version differs from APP_VERSION.")
        if not (application / "Contents" / "MacOS" / info["CFBundleExecutable"]).is_file():
            raise ValueError("Packaged Mac app executable is missing.")
    elif not all((folder / item).is_file() for item in ("VeriCivil Desktop Preview.exe", "resources/app.asar")):
        raise ValueError("Packaged Windows executable or application archive is missing.")
    output = root / "desktop" / "release-assets"
    output.mkdir(parents=True, exist_ok=True)
    basename = f"Superelevation-Desktop-Preview-{version}-{target}"
    if platform == "darwin":
        archive = output / f"{basename}.dmg"
        subprocess.run(["hdiutil", "create", "-volname", "VeriCivil Desktop Preview", "-srcfolder", str(folder), "-ov", "-format", "UDZO", str(archive)], check=True)
    else:
        archive = Path(shutil.make_archive(str(output / basename), "zip", root_dir=folder.parent, base_dir=folder.name))
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    checksum = output / f"SHA256SUMS-electron-{target}.txt"
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, checksum


if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from app_info import APP_VERSION

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["darwin", "win32"], required=True)
    parser.add_argument("--arch", choices=["arm64", "x64"], required=True)
    args = parser.parse_args()
    for artifact in package_release(root, args.platform, args.arch, APP_VERSION):
        print(artifact)
