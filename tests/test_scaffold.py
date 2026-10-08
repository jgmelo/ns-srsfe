"""M0: package imports and the golden profile loads."""

from typing import Any

import srsfe
from srsfe.core import constants


def test_package_imports() -> None:
    assert srsfe.__version__ == "0.1.0"
    assert constants.E_CHARGE == 1.602176634e-19
    assert constants.K_B == 1.380649e-23


def test_golden_profile_loads(golden_profile: dict[str, Any]) -> None:
    assert golden_profile["schema_version"] == 1
    assert golden_profile["name"] == "golden"
    assert golden_profile["params"]["r_f"] == 100e3
