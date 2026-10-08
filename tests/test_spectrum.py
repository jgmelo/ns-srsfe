"""M3: photocurrent, harmonics table and signal (SPEC §4.2, §4.3)."""

import math
from typing import Any

import numpy as np
import pytest

from srsfe.core.spectrum import (
    Harmonics,
    harmonics,
    n_harmonics,
    peak_current,
    photocurrent,
    pulse_charge,
    signal,
)
from srsfe.core.tank import TankResult, tank_from_dwell, tank_from_lc
from tests import golden

POWERS = ["p_min", "p_max"]


@pytest.fixture
def golden_tank(golden_params: dict[str, Any]) -> TankResult:
    g = golden_params
    return tank_from_dwell(g["r_f"], g["f_0"], g["t_dwell"], g["n_tau"], g["q_mode"])


def _i0(g: dict[str, Any], power: str) -> float:
    return photocurrent(g[power], g["resp"])


# -- golden ----------------------------------------------------------------------


@pytest.mark.golden
@pytest.mark.spec("§9.2", "i_0", "q_p", "i_pk")
@pytest.mark.spec("§4.2", "i0")
@pytest.mark.parametrize("power", POWERS)
def test_golden_photocurrent(golden_params: dict[str, Any], power: str) -> None:
    """I₀, q_p, I_pk at both powers match SPEC §9.2."""
    g = golden_params
    i_0 = _i0(g, power)
    q_p = pulse_charge(i_0, g["f_rep"])
    assert i_0 == pytest.approx(golden.I_0[power], rel=golden.REL)
    assert q_p == pytest.approx(golden.Q_P[power], rel=golden.REL)
    assert peak_current(q_p, g["tau_p"]) == pytest.approx(golden.I_PK[power], rel=golden.REL)


@pytest.mark.golden
@pytest.mark.spec("§9.1", "f_n", "z_n", "att_n")
@pytest.mark.spec("§4.2", "harmonics-range", "v-n")
def test_golden_harmonics_table(golden_params: dict[str, Any], golden_tank: TankResult) -> None:
    """Golden table has n = 1…5 at 40…200 MHz with SPEC §9.1 |Z_f| and attenuation."""
    g = golden_params
    h = harmonics(_i0(g, "p_min"), g["f_rep"], g["f_max"], golden_tank)
    assert h.n == (1, 2, 3, 4, 5)
    assert h.f_n == pytest.approx(golden.F_N, rel=golden.REL)
    assert h.z_n == pytest.approx(golden.Z_N, rel=golden.REL)
    assert h.att_n == pytest.approx(golden.ATT_N, abs=golden.DB_ABS)


@pytest.mark.golden
@pytest.mark.spec("§9.2", "v_n", "v_n_sum", "v_n_rss")
@pytest.mark.spec("§4.2", "v-n")
@pytest.mark.parametrize("power", POWERS)
def test_golden_harmonic_voltages(
    golden_params: dict[str, Any], golden_tank: TankResult, power: str
) -> None:
    """V_n, ΣV_n and RSS at both powers match SPEC §9.2."""
    g = golden_params
    h = harmonics(_i0(g, power), g["f_rep"], g["f_max"], golden_tank)
    assert h.v_n == pytest.approx(golden.V_N[power], rel=golden.REL)
    assert h.v_n_sum == pytest.approx(golden.V_N_SUM[power], rel=golden.REL)
    assert h.v_n_rss == pytest.approx(golden.V_N_RSS[power], rel=golden.REL)


@pytest.mark.golden
@pytest.mark.spec("§9.2", "i_sig", "v_sig")
@pytest.mark.spec("§4.3", "signal")
@pytest.mark.parametrize("power", POWERS)
def test_golden_signal(golden_params: dict[str, Any], power: str) -> None:
    """I_sig = m·I₀ and V_sig = I_sig·R at both powers match SPEC §9.2."""
    g = golden_params
    s = signal(_i0(g, power), g["m"], g["r_f"])
    assert s.i_sig == pytest.approx(golden.I_SIG[power], rel=golden.REL)
    assert s.v_sig == pytest.approx(golden.V_SIG[power], rel=golden.REL)


# -- formulas ----------------------------------------------------------------------


@pytest.mark.formula
@pytest.mark.spec("§4.2", "harmonics-range")
@pytest.mark.parametrize(
    ("f_rep", "f_max", "expected"),
    [(40e6, 200e6, 5), (40e6, 199.9e6, 4), (40e6, 39e6, 0), (40e6, 40e6, 1),
     (0.1e6, 0.3e6, 3), (76e6, 1e9, 13), (1e6, 1e6 * 49, 49)],
)
def test_harmonic_count(f_rep: float, f_max: float, expected: int) -> None:
    """n runs to ⌊f_max/f_rep⌋; exact multiples are included despite float rounding."""
    assert n_harmonics(f_rep, f_max) == expected


@pytest.mark.formula
@pytest.mark.spec("§4.2", "harmonics-range")
def test_no_harmonics_below_f_rep(golden_tank: TankResult) -> None:
    """f_max < f_rep gives an empty table with zero sum and RSS (DC is never listed)."""
    h = harmonics(60e-6, 40e6, 30e6, golden_tank)
    assert h.n == () and h.v_n == () and h.v_n_sum == 0 and h.v_n_rss == 0


@pytest.mark.formula
@pytest.mark.spec("§4.2", "i0")
def test_pulse_charge_and_peak() -> None:
    """q_p·f_rep = I₀ and I_pk·τ_p = q_p (charge conservation)."""
    i_0 = photocurrent(2.5e-3, 0.8)
    q_p = pulse_charge(i_0, 80e6)
    assert i_0 == pytest.approx(2e-3, rel=1e-12)
    assert q_p * 80e6 == pytest.approx(i_0, rel=1e-12)
    assert peak_current(q_p, 100e-15) * 100e-15 == pytest.approx(q_p, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.2", "v-n")
def test_v_n_relations(golden_tank: TankResult) -> None:
    """Each line is 2·I₀; V_n = 2·I₀·R·10^(att/20); RSS ≤ ΣV_n; V_n linear in I₀."""
    a = harmonics(1e-4, 40e6, 400e6, golden_tank)
    b = harmonics(3e-4, 40e6, 400e6, golden_tank)
    assert len(a.n) == 10 and set(a.i_n) == {2e-4}
    expected = [2e-4 * golden_tank.r_f * 10 ** (att / 20) for att in a.att_n]
    assert a.v_n == pytest.approx(expected, rel=1e-12)
    assert a.v_n_rss <= a.v_n_sum
    assert np.array(b.v_n) == pytest.approx(3 * np.array(a.v_n), rel=1e-12)
    assert all(att < 0 for att in a.att_n)  # all harmonics are off resonance


@pytest.mark.formula
@pytest.mark.spec("§4.2", "v-n")
def test_harmonics_use_tank_resonance() -> None:
    """|Z_f(f_n)| uses the tank's own f_res: a tank resonating on a harmonic passes it at R."""
    l, c = 1e-6, 1 / ((2 * math.pi * 40e6) ** 2 * 1e-6)  # resonates at 40 MHz
    t = tank_from_lc(10e3, l, c)
    h = harmonics(1e-4, 40e6, 80e6, t)
    assert h.z_n[0] == pytest.approx(10e3, rel=1e-9) and h.att_n[0] == pytest.approx(0, abs=1e-9)
    assert h.z_n[1] < 10e3


@pytest.mark.formula
@pytest.mark.spec("§4.3", "signal")
def test_signal_zero_modulation() -> None:
    """m = 0 gives no signal; V_sig scales with R."""
    assert signal(1e-3, 0.0, 100e3).v_sig == 0
    assert signal(1e-3, 1e-5, 200e3).v_sig == pytest.approx(2 * signal(1e-3, 1e-5, 100e3).v_sig)


# -- API -----------------------------------------------------------------------------


@pytest.mark.api
def test_harmonics_is_frozen_tuples(golden_tank: TankResult) -> None:
    """Harmonics is a frozen dataclass of plain tuples/floats (ready for JSON in M6)."""
    h = harmonics(1e-4, 40e6, 200e6, golden_tank)
    assert isinstance(h, Harmonics)
    with pytest.raises(AttributeError):
        h.v_n_sum = 0.0  # type: ignore[misc]
    for name in ("n", "f_n", "i_n", "z_n", "att_n", "v_n"):
        seq = getattr(h, name)
        assert isinstance(seq, tuple) and len(seq) == 5
        assert all(type(x) in (int, float) for x in seq)


# -- validation ----------------------------------------------------------------------


@pytest.mark.validation
@pytest.mark.parametrize(
    ("func", "args"),
    [
        (photocurrent, (0, 0.6)), (photocurrent, (1e-3, -0.6)),
        (pulse_charge, (-1e-3, 40e6)), (pulse_charge, (1e-3, 0)),
        (peak_current, (1e-12, 0)), (peak_current, (1e-12, float("nan"))),
        (n_harmonics, (0, 200e6)), (n_harmonics, (40e6, -1)),
        (signal, (1e-3, -1e-5, 100e3)), (signal, (1e-3, 1e-5, 0)),
    ],
)
def test_rejects_bad_input(func: Any, args: tuple[Any, ...]) -> None:
    """Non-positive/non-finite inputs raise ValueError (I₀ and m may be 0)."""
    with pytest.raises(ValueError):
        func(*args)
