"""Shared fixtures: the golden profile from SPEC §9."""

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = ROOT / "profiles" / "golden.json"


@pytest.fixture(scope="session")
def golden_profile() -> dict[str, Any]:
    """Raw golden profile document (schema_version, name, params, …)."""
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def golden_params(golden_profile: dict[str, Any]) -> dict[str, Any]:
    """Golden input parameters, SI units, keyed by SPEC §3 identifiers."""
    return golden_profile["params"]
