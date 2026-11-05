"""Archive an existing Electron preview and record its download checksum."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import shutil
import subprocess
import time
from pathlib import Path


def package_release(root: Path, platform: str, arch: str, version: str, edition: str = "vericivil") -> tuple[Path, Path]:
    branding = json.loads((Path(__file__).resolve().parents[1] / "desktop/editions.json").read_text(encoding="utf-8"))[edition]
    suffix = "" if edition == "vericivil" else "-neutral"
    targets = {("darwin", "arm64"): "macOS-Apple-Silicon", ("darwin", "x64"): "macOS-Intel", ("win32", "x64"): "Windows-x64"}
    target = targets[(platform, arch)]
    staged = root / "desktop" / branding["appDirectory"] / "package.json"
    if json.loads(staged.read_text())["version"] != version:
        raise ValueError("Rebuild the Electron app before archiving: staged version differs from APP_VERSION.")
    folder = root / "desktop" / branding["previewDirectory"] / f"{branding['previewName']}-{platform}-{arch}"
    if platform == "darwin":
        application = folder / f"{branding['previewName']}.app"
        with (application / "Contents" / "Info.plist").open("rb") as source:
            info = plistlib.load(source)
        if info["CFBundleShortVersionString"] != version:
            raise ValueError("Packaged Mac app version differs from APP_VERSION.")
        if not (application / "Contents" / "MacOS" / info["CFBundleExecutable"]).is_file():
            raise ValueError("Packaged Mac app executable is missing.")
    elif not all((folder / item).is_file() for item in (f"{branding['previewName']}.exe", "resources/app.asar")):
        raise ValueError("Packaged Windows executable or application archive is missing.")
    output = root / "desktop" / "release-assets"
    output.mkdir(parents=True, exist_ok=True)
    basename = f"{branding['previewArtifactPrefix']}-{version}-{target}"
    if platform == "darwin":
        archive = output / f"{basename}.dmg"
        command = ["hdiutil", "create", "-volname", branding["previewName"], "-srcfolder", str(folder), "-ov", "-format", "UDZO", str(archive)]
        for attempt in range(3):
            try:
                subprocess.run(command, check=True, stderr=subprocess.PIPE, text=True)
                break
            except subprocess.CalledProcessError as error:
                print(error.stderr)
                if "Resource busy" not in (error.stderr or "") or attempt == 2:
                    raise
                # Hosted Mac image creation can briefly return Resource busy.
                time.sleep(2 * (attempt + 1))
        subprocess.run(["hdiutil", "verify", str(archive)], check=True)
    else:
        archive = Path(shutil.make_archive(str(output / basename), "zip", root_dir=folder.parent, base_dir=folder.name))
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    checksum = output / f"SHA256SUMS-electron{suffix}-{target}.txt"
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
    parser.add_argument("--edition", choices=["vericivil", "neutral"], default="vericivil")
    args = parser.parse_args()
    for artifact in package_release(root, args.platform, args.arch, APP_VERSION, args.edition):
        print(artifact)
