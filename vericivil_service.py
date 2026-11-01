"""Shared browser dispatcher for all VeriCivil calculators."""

from __future__ import annotations

from typing import Any


def _service(calculator: str):
    if calculator == "typicals":
        from typicals import service

        return service
    if calculator == "superelevation":
        import super_service

        return super_service
    if calculator == "crushed_stone_base":
        from calculators.crushed_stone_base import service

        return service
    raise ValueError(f"Unsupported calculator: {calculator}")


def application_manifest(calculator: str) -> dict[str, Any]:
    return _service(calculator).application_manifest()


def dispatch_safe(calculator: str, operation: str, payload_json: str = "{}") -> dict[str, Any]:
    try:
        return _service(calculator).dispatch_safe(operation, payload_json)
    except Exception as exc:
        return {
            "ok": False,
            "error": {"type": type(exc).__name__, "message": str(exc) or "Operation failed."},
        }
