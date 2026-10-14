"""M5: output occupancy budget (SPEC §4.6)."""

from typing import Any

import pytest

from srsfe.core.budget import Budget, budget
from tests import chain, golden

POWERS = ["p_min", "p_max"]


@pytest.mark.golden
@pytest.mark.spec("§9.2", "v_coh", "occ_swing", "occ_moku")
@pytest.mark.spec("§4.6", "v-coh", "occupancy")
@pytest.mark.parametrize("power", POWERS)
def test_golden_budget(golden_params: dict[str, Any], power: str) -> None:
    """V_coh, occ_swing and occ_moku at both powers match SPEC §9.2."""
    b = chain.at_power(golden_params, power).budget
    assert b.v_coh == pytest.approx(golden.V_COH[power], rel=golden.REL)
    assert b.occ_swing == pytest.approx(golden.OCC_SWING[power], rel=golden.REL)
    assert b.occ_moku == pytest.approx(golden.OCC_MOKU[power], rel=golden.REL)


@pytest.mark.formula
@pytest.mark.spec("§4.6", "v-coh", "occupancy")
def test_budget_formulas() -> None:
    """V_coh adds the three terms; Moku occupancy counts 2·V_coh against peak-to-peak range."""
    b = budget(v_n_sum=1.0, v_sig=0.25, k_crest=3, v_rms=0.25, v_swing=2.0, v_range=10.0)
    assert b.v_coh == pytest.approx(2.0, rel=1e-12)
    assert b.occ_swing == pytest.approx(100.0, rel=1e-12)
    assert b.occ_moku == pytest.approx(40.0, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.6", "occupancy")
def test_moku_range_ten_times() -> None:
    """Switching the Moku from 1 V to 10 V range cuts occ_moku tenfold; occ_swing unchanged."""
    a = budget(0.5, 0.0, 3, 1e-3, 2.0, 1.0)
    b = budget(0.5, 0.0, 3, 1e-3, 2.0, 10.0)
    assert b.occ_moku == pytest.approx(a.occ_moku / 10, rel=1e-12)
    assert b.occ_swing == a.occ_swing


@pytest.mark.api
def test_budget_frozen() -> None:
    """Budget is an immutable result."""
    b = budget(1.0, 0.0, 3, 0.0, 2.0, 1.0)
    assert isinstance(b, Budget)
    with pytest.raises(AttributeError):
        b.v_coh = 0.0  # type: ignore[misc]


@pytest.mark.validation
@pytest.mark.parametrize(
    "args",
    [(-1.0, 0, 3, 0, 2, 1), (1.0, -1e-6, 3, 0, 2, 1), (1.0, 0, 0, 0, 2, 1),
     (1.0, 0, 3, -1, 2, 1), (1.0, 0, 3, 0, 0, 1), (1.0, 0, 3, 0, 2, 0),
     (float("nan"), 0, 3, 0, 2, 1)],
)
def test_budget_rejects_bad_input(args: tuple[float, ...]) -> None:
    """Negative voltages or non-positive k_crest, V_swing, V_range raise ValueError."""
    with pytest.raises(ValueError):
        budget(*args)
