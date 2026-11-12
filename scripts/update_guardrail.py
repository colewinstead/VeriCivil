"""Import an unchanged Guardrail revision, or verify the checked-in snapshot."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "calculators" / "guardrail" / "upstream"
FILES = (
    "LICENSE", "guardrail_design.py", "guardrail_models.py", "guardrail_parsing.py",
    "guardrail_validation.py", "guardrail_engine.py", "guardrail_presentation.py",
    "guardrail_report.py", "guardrail_pdf.py", "guardrail_pdf_math.py", "guardrail_pdf_files.py", "guardrail_resources.py",
    "gr manual.pdf", "GR-4.pdf", "GR-4a.pdf", "test_fixtures/phase3_baseline.json",
)


def verify():
    pin = json.loads((TARGET / "source.json").read_text())
    if set(pin["sha256"]) != set(FILES):
        raise ValueError("Guardrail snapshot file list does not match the importer.")
    for name, expected in pin["sha256"].items():
        if hashlib.sha256((TARGET / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Guardrail snapshot changed: {name}. Update upstream instead.")
    return pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Local Guardrail Git checkout")
    parser.add_argument("--revision", help="Reviewed full upstream commit SHA")
    args = parser.parse_args()
    if args.source is None and args.revision is None:
        pin = verify()
    else:
        if args.source is None or not re.fullmatch(r"[0-9a-f]{40}", args.revision or ""):
            parser.error("Supply --source and a full 40-character --revision together.")
        # Read the committed objects, never uncommitted files from a developer's checkout.
        contents = {name: subprocess.check_output(
            ["git", "-C", str(args.source), "show", f"{args.revision}:{name}"],
        ) for name in FILES}
        version = re.search(rb'APP_VERSION = "([^"]+)"', contents["guardrail_design.py"])[1].decode()
        pin = {"repository": "https://github.com/colewinstead/Guardrail-Calculator",
               "commit": args.revision, "version": version,
               "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}}
        for name, data in contents.items():
            path = TARGET / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (TARGET / "source.json").write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8", newline="\n")
        verify()
    print(f"Verified Guardrail {pin['version']} at {pin['commit']} ({len(FILES)} unchanged files).")


if __name__ == "__main__":
    main()
