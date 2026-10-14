"""Shared fixtures: the golden profile from SPEC §9."""

import json
from pathlib import Path
from typing import Any

import pytest

from tests.spec_items import KINDS

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = ROOT / "profiles" / "golden.json"


def pytest_configure(config: pytest.Config) -> None:
    """Register the catalog markers (tests/spec_items.py); --strict-markers rejects typos."""
    for name, description in KINDS.items():
        config.addinivalue_line("markers", f"{name}: {description}")
    config.addinivalue_line("markers", "spec(section, *items): SPEC items this test covers")


@pytest.fixture(scope="session")
def golden_profile() -> dict[str, Any]:
    """Raw golden profile document (schema_version, name, params, …)."""
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def golden_params(golden_profile: dict[str, Any]) -> dict[str, Any]:
    """Golden input parameters, SI units, keyed by SPEC §3 identifiers."""
    return golden_profile["params"]
