"""Stage unsigned installers, checksums, and the Windows update feed."""
import argparse
import base64
import hashlib
import json
import shutil
from pathlib import Path


def stage_installers(root: Path, platform: str, arch: str, version: str, edition: str = "vericivil") -> list[Path]:
    branding = json.loads((Path(__file__).resolve().parents[1] / "desktop/editions.json").read_text(encoding="utf-8"))[edition]
    suffix = "" if edition == "vericivil" else "-neutral"
    os_name = {"win32": "win", "darwin": "mac"}[platform]
    source = root / "desktop" / branding["installerDirectory"] / f"{platform}-{arch}"
    output = root / "desktop/release-assets"
    extensions = ["exe"] if platform == "win32" else ["dmg", "zip"]
    artifacts = [source / f"{branding['artifactPrefix']}-{version}-{os_name}-{arch}-unsigned.{extension}" for extension in extensions]
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
    (output / f"SHA256SUMS-installers{suffix}-{platform}-{arch}.txt").write_text("".join(lines), encoding="utf-8")
    if platform == "win32":
        installer = staged[0]
        with installer.open("rb") as data:
            checksum = base64.b64encode(hashlib.file_digest(data, "sha512").digest()).decode("ascii")
        feed = output / f"{branding['channelPrefix']}unsigned-{platform}-{arch}.yml"
        # JSON is valid YAML; derive the feed from this exact version's staged installer.
        feed.write_text(json.dumps({
            "version": version,
            "files": [{"url": installer.name, "sha512": checksum, "size": installer.stat().st_size}],
            "path": installer.name,
            "sha512": checksum,
        }), encoding="utf-8")
        staged.append(feed)
    return staged


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
    for artifact in stage_installers(root, args.platform, args.arch, APP_VERSION, args.edition):
        print(artifact)
