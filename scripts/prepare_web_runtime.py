"""Stage the shared Python modules for the browser build without duplicating source."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "web" / "public" / "python"
GENERATED = ROOT / "web" / "app" / "generated"
sys.path.insert(0, str(ROOT))

from commercial_entitlements import commercial_manifest  # noqa: E402
from criteria_info import criteria_metadata, criteria_profiles  # noqa: E402
from app_info import APP_VERSION, CALCULATION_ENGINE_VERSION  # noqa: E402
from calculators.catalog import browser_runtime_manifest, calculator_catalog  # noqa: E402
from calculators.guardrail.service import application_manifest as guardrail_manifest  # noqa: E402
from scripts.update_guardrail import verify as verify_guardrail  # noqa: E402


def main() -> None:
    verify_guardrail()
    runtime_manifest = browser_runtime_manifest()
    modules = sorted(
        {
            module
            for bundle in runtime_manifest["calculators"].values()
            for module in bundle["modules"]
        }
    )
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in modules:
        destination = TARGET / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    for bundle in runtime_manifest["calculators"].values():
        for name in bundle.get("assets", []):
            destination = TARGET / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
    (TARGET / "manifest.json").write_text(json.dumps(runtime_manifest, indent=2) + "\n", encoding="utf-8")
    GENERATED.mkdir(parents=True, exist_ok=True)
    (GENERATED / "guardrail.json").write_text(json.dumps(guardrail_manifest(), indent=2) + "\n", encoding="utf-8")
    supported_profiles = []
    for profile in criteria_profiles():
        metadata = criteria_metadata(profile["profile_id"])
        supported_profiles.append(
            {
                **profile,
                "source_status": metadata["source_status"],
                "engineering_change_notice": metadata["engineering_change_notice"],
            }
        )
    (GENERATED / "criteria-profiles.json").write_text(
        json.dumps(supported_profiles, indent=2) + "\n", encoding="utf-8"
    )
    (GENERATED / "commercial-manifest.json").write_text(
        json.dumps(commercial_manifest(), indent=2) + "\n", encoding="utf-8"
    )
    (GENERATED / "release-info.json").write_text(
        json.dumps(
            {
                "application_version": APP_VERSION,
                "calculation_engine_version": CALCULATION_ENGINE_VERSION,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    (GENERATED / "calculators.json").write_text(
        json.dumps(calculator_catalog(), indent=2) + "\n", encoding="utf-8"
    )
    print(f"Staged {len(modules)} shared Python modules across {len(runtime_manifest['calculators'])} calculators.")


if __name__ == "__main__":
    main()
