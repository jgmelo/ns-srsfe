"""M5: warnings W01–W09 (SPEC §5): each fires once and stays silent once, plus golden §9.3."""

from typing import Any

import pytest

from srsfe.core import warnings as w
from srsfe.core.noise import enbw_lia
from srsfe.core.tank import tank_from_lc
from tests import chain, golden

POWERS = ["p_min", "p_max"]


# -- W01–W09 fire / silent -----------------------------------------------------------


@pytest.mark.warning
@pytest.mark.spec("§5", "W01:fires", "W01:silent")
def test_w01() -> None:
    """W01 fires when τ_LIA exceeds the dwell; equal is fine."""
    assert w.check_w01(1.1e-6, 1e-6) == w.make("W01")
    assert w.check_w01(1e-6, 1e-6) is None


@pytest.mark.warning
@pytest.mark.spec("§5", "W02:fires", "W02:silent")
def test_w02() -> None:
    """W02 fires when ENBW > B_eq/5; exactly B_eq/5 is silent."""
    assert w.check_w02(0.51e6, 2.5e6) == w.make("W02")
    assert w.check_w02(0.5e6, 2.5e6) is None


@pytest.mark.warning
@pytest.mark.spec("§5", "W03:fires", "W03:silent")
def test_w03() -> None:
    """W03 fires above 100 % opamp swing and carries the power it was checked at."""
    fired = w.check_w03(100.01, "p_max")
    assert fired is not None and fired.power == "p_max" and fired.id == "W03"
    assert w.check_w03(100.0, "p_min") is None


@pytest.mark.warning
@pytest.mark.spec("§5", "W04:fires", "W04:silent")
def test_w04() -> None:
    """W04 fires above 100 % Moku range and carries the power."""
    fired = w.check_w04(254.8, "p_min")
    assert fired is not None and fired.power == "p_min"
    assert w.check_w04(99.9, "p_max") is None


@pytest.mark.warning
@pytest.mark.spec("§5", "W05:fires", "W05:silent")
def test_w05() -> None:
    """W05 fires when the TIA output density is below 3·e_n,Moku."""
    fired = w.check_w05(80e-9, 30e-9, "p_min")
    assert fired is not None and fired.power == "p_min"
    assert w.check_w05(90e-9, 30e-9, "p_min") is None


@pytest.mark.warning
@pytest.mark.spec("§5", "W06:fires", "W06:silent")
def test_w06() -> None:
    """W06 fires when the tank resonance is more than 1 % off f_0, either side."""
    assert w.check_w06(20.21e6, 20e6) == w.make("W06")
    assert w.check_w06(19.79e6, 20e6) == w.make("W06")
    assert w.check_w06(20.19e6, 20e6) is None


@pytest.mark.warning
@pytest.mark.spec("§5", "W07:fires", "W07:silent")
def test_w07() -> None:
    """W07 fires when the tank does not settle (driven by tank.settles)."""
    slow = tank_from_lc(100e3, 63.3257e-6, 1.1e-12)  # τ = 2RC = 220 ns
    assert w.check_w07(slow.settles(5, 1e-6)) == w.make("W07")
    assert w.check_w07(True) is None


@pytest.mark.warning
@pytest.mark.spec("§5", "W08:fires", "W08:silent")
def test_w08() -> None:
    """W08 fires when the pulse is longer than 1/(10·f_max)."""
    assert w.check_w08(0.6e-9, 200e6) == w.make("W08")
    assert w.check_w08(2e-12, 200e6) is None


@pytest.mark.warning
@pytest.mark.spec("§5", "W09:fires", "W09:silent")
def test_w09() -> None:
    """W09 fires when f_0 is more than 1 % away from f_rep/2."""
    assert w.check_w09(20e6, 38e6) == w.make("W09")
    assert w.check_w09(20e6, 40.2e6) is None


@pytest.mark.schema
@pytest.mark.spec("§5", "fields")
def test_warning_contents() -> None:
    """Every warning carries id, SPEC message, severity (W02/W08 info), power and fields."""
    assert sorted(w.SPECS) == [f"W0{i}" for i in range(1, 10)]
    for wid in w.SPECS:
        x = w.make(wid)
        assert x.id == wid and x.message and x.power is None and x.fields
        assert x.severity == ("info" if wid in {"W02", "W08"} else "warn")
    assert w.make("W03", "p_max").power == "p_max"
    assert w.make("W01").message == "Lock-in smears adjacent pixels"
    with pytest.raises(AttributeError):
        w.make("W01").id = "W02"  # type: ignore[misc]


# -- golden §9.3 / §9.4 ----------------------------------------------------------------


@pytest.mark.golden
@pytest.mark.spec("§9.3", "w02")
@pytest.mark.parametrize("n_lia", [1, 2, 3, 4])
def test_golden_w02(golden_params: dict[str, Any], n_lia: int) -> None:
    """Golden: W02 fires for n_lia = 1, 2 and not for 3, 4."""
    g = golden_params
    fired = w.check_w02(enbw_lia(g["tau_lia"], n_lia), chain.tank(g).b_eq) is not None
    assert fired is golden.W02_FIRES_FOR_N_LIA[n_lia]


@pytest.mark.golden
@pytest.mark.spec("§9.3", "w03", "w04")
def test_golden_w03_w04(golden_params: dict[str, Any]) -> None:
    """Golden: W03 fires at P_max only; W04 fires at both powers."""
    w03, w04 = set(), set()
    for power in POWERS:
        b = chain.at_power(golden_params, power).budget
        if w.check_w03(b.occ_swing, power):
            w03.add(power)
        if w.check_w04(b.occ_moku, power):
            w04.add(power)
    assert w03 == golden.W03_POWERS and w04 == golden.W04_POWERS


@pytest.mark.golden
@pytest.mark.spec("§9.3", "silent")
def test_golden_silent(golden_params: dict[str, Any]) -> None:
    """Golden: W01, W05 (both powers), W08 and W09 do not fire."""
    g = golden_params
    fired = {x.id for x in (
        w.check_w01(g["tau_lia"], g["t_dwell"]),
        w.check_w08(g["tau_p"], g["f_max"]),
        w.check_w09(g["f_0"], g["f_rep"]),
        *(w.check_w05(chain.at_power(g, p).noise.v_dens, g["en_moku"], p) for p in POWERS),
    ) if x is not None}
    assert {"W01", "W05", "W08", "W09"} == golden.SILENT and fired == set()


@pytest.mark.golden
@pytest.mark.spec("§9.4", "no-warnings")
def test_golden_analyze_no_warnings() -> None:
    """SPEC §9.4 analyzed tank: neither W06 nor W07 fires."""
    a = golden.ANALYZE_INPUTS
    t = tank_from_lc(a["r_f"], a["l_f"], a["c_f"])
    assert w.check_w06(t.f_res, a["f_0"]) is None
    assert w.check_w07(t.settles(a["n_tau"], a["t_dwell"])) is None
