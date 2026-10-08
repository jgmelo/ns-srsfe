"""M0: package imports and the golden profile loads."""

from typing import Any

import pytest

import srsfe
from srsfe.core import constants


@pytest.mark.smoke
@pytest.mark.spec("§0", "constants")
def test_package_imports() -> None:
    """The package imports; physical constants have their SPEC values."""
    assert srsfe.__version__ == "0.1.0"
    assert constants.E_CHARGE == 1.602176634e-19
    assert constants.K_B == 1.380649e-23


@pytest.mark.smoke
@pytest.mark.spec("§9", "profile")
def test_golden_profile_loads(golden_profile: dict[str, Any]) -> None:
    """The conftest fixture reads profiles/golden.json."""
    assert golden_profile["schema_version"] == 1
    assert golden_profile["name"] == "golden"
    assert golden_profile["params"]["r_f"] == 100e3
