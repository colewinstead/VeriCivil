"""Authoritative product and calculation-engine release identifiers."""

APP_NAME = "Superelevation Calculator"
APP_VERSION = "1.5.8"
CALCULATION_ENGINE_VERSION = "1.2.4"


def version_label() -> str:
    return f"{APP_NAME} {APP_VERSION}"
