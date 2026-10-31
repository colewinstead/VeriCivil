"""Inventory any supplied workspace read-only; never parse binary DGN as level data."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def inventory(root):
    root = Path(root).resolve()
    files, references, config = [], {}, []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        files.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        if path.suffix.lower() == ".tbl":
            for name in set(re.findall(r"IN_LEVEL\s*=\s*(TS_[A-Za-z0-9_$-]+)", data.decode("utf-8", errors="replace"))):
                references.setdefault(name, []).append(relative)
        if path.suffix.lower() == ".cfg":
            for i, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
                if not line.lstrip().startswith("#") and re.search(r"MS_(DGNLIBLIST|LEVEL|FONT|SYMBRSRC|PENTABLE|PLTCFG|COLOR)", line):
                    config.append({"path": relative, "line": i, "setting": line.strip()})
    return {"format": "vericivil.typicals.workspace-inventory", "version": 1, "root": str(root),
            "file_count": len(files), "total_bytes": sum(v["bytes"] for v in files),
            "extensions": dict(sorted(Counter(Path(v["path"]).suffix.lower() for v in files).items())),
            "files": files, "configuration_references": config,
            "catalog": {"format": "vericivil.typicals.levels", "version": 1, "source": str(root),
                        "revision": "Local workspace inventory", "extraction_status": "name-references-only",
                        "levels": [{"name": name, "description": "", "rgb": None, "lineweight_mm": None,
                                    "dash_ft": None, "bylevel_color": None, "bylevel_weight": None,
                                    "bylevel_style": None, "name_sources": sources} for name, sources in sorted(references.items())]},
            "limitations": ["Pen-table IN_LEVEL references establish names only; not an exhaustive DGNLIB level list.",
                            "Binary DGN/DGNLIB/RSC, color tables and fonts were inventoried, not decoded.",
                            "Use Bentley Level Manager reports to resolve levels and ByLevel properties."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.workspace.resolve() in args.output.resolve().parents:
        parser.error("Output must be outside the read-only workspace.")
    result = inventory(args.workspace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Inventoried {result['file_count']} files; {len(result['catalog']['levels'])} TS_ name references, no binary symbology extraction.")
