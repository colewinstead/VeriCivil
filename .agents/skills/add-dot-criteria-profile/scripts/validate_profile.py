#!/usr/bin/env python3
"""Check that a non-default DOT criteria profile is wired through the repository.

This script validates integration and provenance only. It does not approve numeric
criteria, replace golden calculations, or certify engineering correctness.
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import runpy
import sys
from typing import Any


DEFAULT_ROOT = Path(__file__).resolve().parents[4]
REQUIRED_METADATA = (
    "profile_id",
    "profile_name",
    "revision",
    "source_status",
    "governing_authority",
    "source_documents",
    "implementation_modules",
    "engineering_change_notice",
)


class Validation:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if condition:
            self.passes.append(message)
        else:
            self.failures.append(message)


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_id", help="Canonical profile ID or registered alias")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Repository root; defaults to the checkout containing this skill",
    )
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="State criteria module filename; may be repeated and otherwise inferred from metadata",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = args.repo_root.resolve()
    sys.path.insert(0, str(root))

    from criteria_info import criteria_metadata, criteria_profiles, normalize_profile_id
    import super_service

    check = Validation()
    profile_id = normalize_profile_id(args.profile_id)
    metadata = criteria_metadata(profile_id)

    check.require(metadata.get("profile_id") == profile_id, "metadata uses the canonical profile ID")
    for field in REQUIRED_METADATA:
        value = metadata.get(field)
        if field in {"source_documents", "implementation_modules"}:
            check.require(isinstance(value, list) and bool(value), f"metadata field '{field}' is populated")
        else:
            check.require(_nonempty_text(value), f"metadata field '{field}' is populated")

    summaries = [item for item in criteria_profiles() if item.get("profile_id") == profile_id]
    check.require(len(summaries) == 1, "profile appears exactly once in criteria_profiles()")

    source_documents = metadata.get("source_documents", [])
    for index, document in enumerate(source_documents, start=1):
        prefix = f"source document {index}"
        check.require(_nonempty_text(document.get("title")), f"{prefix} has a title")
        url = document.get("url")
        check.require(_nonempty_text(url) and url.startswith("https://"), f"{prefix} has an official HTTPS URL")

    manifest = super_service.application_manifest()
    manifest_profiles = manifest.get("criteria_profiles", [])
    check.require(
        sum(item.get("profile_id") == profile_id for item in manifest_profiles) == 1,
        "service manifest exposes the profile exactly once",
    )
    profile_options = ((manifest.get("options") or {}).get("profiles") or {}).get(profile_id)
    check.require(isinstance(profile_options, dict), "service manifest defines profile-specific input options")
    if isinstance(profile_options, dict):
        for option in ("facility", "area", "speed"):
            check.require(
                isinstance(profile_options.get(option), list) and bool(profile_options[option]),
                f"service manifest defines nonempty '{option}' options",
            )

    try:
        desktop = importlib.import_module("super_app")
        labels = getattr(desktop, "CRITERIA_PROFILE_LABELS", {})
        check.require(_nonempty_text(labels.get(profile_id)), "desktop selector has a friendly profile label")
    except ModuleNotFoundError as exc:
        if exc.name == "tkinter":
            check.failures.append("desktop selector check requires Python tkinter")
        else:
            raise

    module_names = list(args.module)
    if not module_names:
        module_names = [
            name for name in metadata.get("implementation_modules", [])
            if str(name).endswith("_criteria.py")
        ]
    check.require(bool(module_names), "at least one state criteria module is identified")

    runtime = runpy.run_path(str(root / "scripts" / "prepare_web_runtime.py"))
    runtime_modules = {name for bundle in runtime["browser_runtime_manifest"]()["calculators"].values() for name in bundle["modules"]}
    for module_name in module_names:
        filename = module_name if module_name.endswith(".py") else f"{module_name}.py"
        module_path = root / filename
        check.require(module_path.is_file(), f"state criteria module exists: {filename}")
        check.require(filename in runtime_modules, f"browser runtime stages state criteria module: {filename}")
        if module_path.is_file():
            module = importlib.import_module(Path(filename).stem)
            constants = {
                name: value for name, value in vars(module).items()
                if name.endswith("PROFILE_ID")
            }
            check.require(
                profile_id in constants.values(),
                f"state criteria module declares the canonical profile ID: {filename}",
            )

    for message in check.passes:
        print(f"PASS: {message}")
    for message in check.failures:
        print(f"FAIL: {message}", file=sys.stderr)

    if check.failures:
        print(
            f"Profile integration validation failed with {len(check.failures)} issue(s).",
            file=sys.stderr,
        )
        return 1
    print(
        f"Profile integration validation passed for {profile_id}. "
        "Numeric criteria still require source review and golden calculations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
