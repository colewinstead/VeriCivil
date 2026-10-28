"""Stage only unsigned installer binaries and checksums for the preview release."""
import argparse
import hashlib
import shutil
from pathlib import Path


def stage_installers(root: Path, platform: str, arch: str, version: str) -> list[Path]:
    os_name = {"win32": "win", "darwin": "mac"}[platform]
    source = root / "desktop/installers" / f"{platform}-{arch}"
    output = root / "desktop/release-assets"
    extensions = ["exe"] if platform == "win32" else ["dmg", "zip"]
    artifacts = [source / f"VeriCivil-Superelevation-{version}-{os_name}-{arch}-unsigned.{extension}" for extension in extensions]
    if not all(artifact.is_file() for artifact in artifacts):
        raise ValueError("Unsigned installer artifacts are missing; rebuild before staging.")
    output.mkdir(parents=True, exist_ok=True)
    staged = []
    lines = []
    for artifact in artifacts:
        destination = output / artifact.name
        shutil.copyfile(artifact, destination)
        with destination.open("rb") as data:
            lines.append(f"{hashlib.file_digest(data, 'sha256').hexdigest()}  {destination.name}\n")
        staged.append(destination)
    (output / f"SHA256SUMS-installers-{platform}-{arch}.txt").write_text("".join(lines), encoding="utf-8")
    return staged


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from app_info import APP_VERSION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["darwin", "win32"], required=True)
    parser.add_argument("--arch", choices=["arm64", "x64"], required=True)
    args = parser.parse_args()
    for artifact in stage_installers(root, args.platform, args.arch, APP_VERSION):
        print(artifact)
