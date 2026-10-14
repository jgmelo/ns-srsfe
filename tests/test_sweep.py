"""M6: generic sweep engine (SPEC §6.3)."""

from typing import Any

import pytest

from srsfe.core.params import Params
from srsfe.core.sweep import sweep
from srsfe.tools import REGISTRY, CalcInputError


@pytest.fixture
def gp(golden_params: dict[str, Any]) -> Params:
    return Params.from_dict(golden_params)


@pytest.mark.api
@pytest.mark.spec("§6.3", "sweep")
def test_sweep_scalar_output(gp: Params) -> None:
    """One row per value with the field and each requested scalar output."""
    rows = sweep(REGISTRY["d"].calc("1"), gp, "t_dwell", [0.5e-6, 1e-6, 2e-6], ["q", "tau_tank"])
    assert [r["t_dwell"] for r in rows] == [0.5e-6, 1e-6, 2e-6]
    assert [r["q"] for r in rows] == pytest.approx([6.2832, 12.566, 25.133], rel=1e-4)
    assert set(rows[0]) == {"t_dwell", "q", "tau_tank"}


@pytest.mark.api
@pytest.mark.spec("§6.3", "per-power")
def test_sweep_per_power_expands(gp: Params) -> None:
    """Per-power outputs become name@p_min and name@p_max columns."""
    rows = sweep(REGISTRY["d"].calc("4"), gp, "m", [1e-5, 2e-5], ["snr", "i_elec"])
    assert set(rows[0]) == {"m", "snr@p_min", "snr@p_max", "i_elec"}
    assert rows[1]["snr@p_min"] - rows[0]["snr@p_min"] == pytest.approx(6.0206, abs=1e-4)


@pytest.mark.api
@pytest.mark.spec("§6.3", "no-mutate")
def test_sweep_does_not_mutate(gp: Params) -> None:
    """The input Params is unchanged after a sweep."""
    before = gp.to_dict()
    sweep(REGISTRY["d"].calc("0"), gp, "r_f", [10e3, 1e6], ["q"])
    assert gp.to_dict() == before


@pytest.mark.errors
@pytest.mark.spec("§6.3", "sweep")
def test_sweep_errors(gp: Params) -> None:
    """Unknown field or output raises KeyError; an invalid swept value raises CalcInputError."""
    calc = REGISTRY["d"].calc("1")
    with pytest.raises(KeyError):
        sweep(calc, gp, "bogus", [1.0], ["q"])
    with pytest.raises(KeyError):
        sweep(calc, gp, "r_f", [1.0], ["snr"])
    with pytest.raises(CalcInputError):
        sweep(calc, gp, "r_f", [-1.0], ["q"])
