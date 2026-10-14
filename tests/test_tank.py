"""M2: tank sizing, analysis of existing parts and Z_f (SPEC §4.1)."""

import math
from typing import Any

import numpy as np
import pytest

from srsfe.core.tank import SETTLE_RTOL, TankResult, settles, tank_from_dwell, tank_from_lc, z_f
from tests import golden


@pytest.fixture
def golden_tank(golden_params: dict[str, Any]) -> TankResult:
    g = golden_params
    return tank_from_dwell(g["r_f"], g["f_0"], g["t_dwell"], g["n_tau"], g["q_mode"])


# -- golden ----------------------------------------------------------------------


@pytest.mark.golden
@pytest.mark.spec("§9.1", "q", "l_f", "c_f", "tau_tank", "bw_3db", "b_eq")
@pytest.mark.spec("§4.1", "q-settling", "l-c", "tau", "bw")
def test_golden_sizing(golden_tank: TankResult) -> None:
    """Golden profile (settling mode) gives SPEC §9.1 q, L, C, τ_tank, BW₋₃dB, B_eq."""
    t = golden_tank
    assert t.q == pytest.approx(golden.Q, rel=golden.REL)
    assert t.l_f == pytest.approx(golden.L_F, rel=golden.REL)
    assert t.c_f == pytest.approx(golden.C_F, rel=golden.REL)
    assert t.tau_tank == pytest.approx(golden.TAU_TANK, rel=golden.REL)
    assert t.bw_3db == pytest.approx(golden.BW_3DB, rel=golden.REL)
    assert t.b_eq == pytest.approx(golden.B_EQ, rel=golden.REL)


@pytest.mark.golden
@pytest.mark.spec("§9.1", "z_n")
@pytest.mark.spec("§4.1", "z-f")
def test_golden_z_at_harmonics(golden_tank: TankResult) -> None:
    """|Z_f| at the golden harmonics 40…200 MHz matches SPEC §9.1 z_n."""
    z = np.abs(golden_tank.z(golden.F_N))
    assert z == pytest.approx(golden.Z_N, rel=golden.REL)


@pytest.mark.golden
@pytest.mark.spec("§9.4", "tank")
@pytest.mark.spec("§4.1", "from-lc")
def test_golden_analyze_tank() -> None:
    """tank_from_lc on the SPEC §9.4 parts gives f0_calc = 20 MHz, q, τ_tank = 200 ns."""
    a = golden.ANALYZE_INPUTS
    t = tank_from_lc(a["r_f"], a["l_f"], a["c_f"])
    assert t.f_res == pytest.approx(golden.ANALYZE_F0_CALC, rel=golden.REL)
    assert t.q == pytest.approx(golden.ANALYZE_Q, rel=golden.REL)
    assert t.tau_tank == pytest.approx(golden.ANALYZE_TAU_TANK, rel=golden.REL)


@pytest.mark.golden
@pytest.mark.spec("§9.4", "settles")
def test_golden_analyze_settles() -> None:
    """SPEC §9.4: the analyzed tank settles; N_τ·τ_tank = t_dwell up to rounding counts."""
    a = golden.ANALYZE_INPUTS
    t = tank_from_lc(a["r_f"], a["l_f"], a["c_f"])
    assert t.settles(a["n_tau"], a["t_dwell"]) is True


# -- formulas ----------------------------------------------------------------------


@pytest.mark.formula
@pytest.mark.spec("§4.1", "q-settling", "tau")
@pytest.mark.parametrize("n_tau", [1, 3, 4.6, 5, 10])
def test_settling_fits_n_tau_in_dwell(n_tau: float) -> None:
    """Settling mode: N_τ·τ_tank = t_dwell exactly, for any N_τ (incl. non-integer)."""
    t = tank_from_dwell(47e3, 15e6, 2e-6, n_tau, "settling")
    assert n_tau * t.tau_tank == pytest.approx(2e-6, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.1", "q-bandwidth", "bw")
def test_bandwidth_mode() -> None:
    """Bandwidth mode: Q = f₀·t_dwell, so BW₋₃dB = 1/t_dwell; n_tau is not used."""
    t = tank_from_dwell(100e3, 20e6, 1e-6, 5, "bandwidth")
    assert t.q == pytest.approx(20.0, rel=1e-12)
    assert t.bw_3db == pytest.approx(1e6, rel=1e-12)
    assert t == tank_from_dwell(100e3, 20e6, 1e-6, 99, "bandwidth")


@pytest.mark.formula
@pytest.mark.spec("§4.1", "l-c")
@pytest.mark.parametrize("mode", ["settling", "bandwidth"])
def test_lc_resonate_at_f0_with_q(mode: str) -> None:
    """The derived L, C resonate at f₀ and give back Q = R·√(C/L)."""
    t = tank_from_dwell(33e3, 7.5e6, 3e-6, 4, mode)
    assert 1 / (2 * math.pi * math.sqrt(t.l_f * t.c_f)) == pytest.approx(7.5e6, rel=1e-12)
    assert 33e3 * math.sqrt(t.c_f / t.l_f) == pytest.approx(t.q, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.1", "from-lc", "tau")
def test_from_lc_tau_is_2rc() -> None:
    """For a parallel RLC, τ_tank = Q/(π f₀) reduces to 2RC, independent of L."""
    for l in (1e-6, 10e-6, 100e-6):
        assert tank_from_lc(10e3, l, 5e-12).tau_tank == pytest.approx(2 * 10e3 * 5e-12, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.1", "z-f")
def test_z_at_resonance_is_r() -> None:
    """Z_f(f₀) = R, purely real: R is the transimpedance gain at f₀."""
    z = z_f(20e6, 100e3, 20e6, 12.566)
    assert z.real == pytest.approx(100e3, rel=1e-12) and z.imag == pytest.approx(0, abs=1e-6)


@pytest.mark.formula
@pytest.mark.spec("§4.1", "z-f", "bw")
@pytest.mark.parametrize("q", [0.7, 5, 12.566, 100])
def test_minus_3db_points(q: float) -> None:
    """At the exact −3 dB edges |Z_f| = R/√2 with phase ±45°, and their spacing is f₀/Q."""
    r, f0 = 1e3, 10e6
    a = 1 / (2 * q)
    f_lo, f_hi = f0 * (math.sqrt(1 + a * a) - a), f0 * (math.sqrt(1 + a * a) + a)
    z = z_f([f_lo, f_hi], r, f0, q)
    assert np.abs(z) == pytest.approx([r / math.sqrt(2)] * 2, rel=1e-12)
    assert np.degrees(np.angle(z)) == pytest.approx([45, -45], abs=1e-9)
    assert f_hi - f_lo == pytest.approx(tank_from_lc(r, *_lc(r, f0, q)).bw_3db, rel=1e-12)


def _lc(r: float, f0: float, q: float) -> tuple[float, float]:
    w0 = 2 * math.pi * f0
    return r / (q * w0), q / (r * w0)


@pytest.mark.formula
@pytest.mark.spec("§4.1", "z-f")
def test_z_dc_shorted_and_geometric_symmetry() -> None:
    """Z_f(0) = 0 (L shorts DC); Z_f(f₀²/f) = conj Z_f(f); shape follows the input."""
    r, f0, q = 1e3, 10e6, 8
    assert z_f(0.0, r, f0, q) == 0
    f = np.array([[1e6, 4e6], [9e6, 30e6]])
    z = z_f(f, r, f0, q)
    assert z.shape == (2, 2)
    assert z_f(f0**2 / f, r, f0, q) == pytest.approx(np.conj(z), rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.1", "bw")
@pytest.mark.parametrize("q", [2, 12.566, 50])
def test_b_eq_is_noise_bandwidth(q: float) -> None:
    """B_eq = (π/2)·f₀/Q equals ∫₀^∞ |Z_f/R|² df (numerical check)."""
    r, f0 = 1e3, 20e6
    f = np.geomspace(f0 * 1e-6, f0 * 1e6, 400_001)
    g = np.abs(z_f(f, r, f0, q) / r) ** 2
    integral = float(np.sum((g[1:] + g[:-1]) / 2 * np.diff(f)))
    assert integral == pytest.approx(tank_from_lc(r, *_lc(r, f0, q)).b_eq, rel=1e-4)


@pytest.mark.formula
@pytest.mark.spec("§3.2", "settles")
def test_settles_boundary() -> None:
    """settles: ≤ holds with only float-rounding slack (rtol 1e-9); clearly longer fails."""
    assert settles(200e-9, 5, 1e-6)
    assert settles(200e-9 * (1 + SETTLE_RTOL / 2), 5, 1e-6)
    assert not settles(200e-9 * (1 + 1e-6), 5, 1e-6)
    assert not settles(201e-9, 5, 1e-6)
    assert settles(100e-9, 5, 1e-6)


@pytest.mark.formula
@pytest.mark.spec("§3.2", "settles")
@pytest.mark.parametrize("mode", ["settling", "bandwidth"])
def test_designed_tank_settles_in_settling_mode_only(mode: str) -> None:
    """A settling-mode design settles exactly at the limit; bandwidth mode (Q = f₀·t_dwell,
    N_τ·τ = N_τ·t_dwell/π) does not for N_τ = 5."""
    t = tank_from_dwell(100e3, 20e6, 1e-6, 5, mode)
    assert t.settles(5, 1e-6) is (mode == "settling")


# -- round trip / API ----------------------------------------------------------------


@pytest.mark.round_trip
@pytest.mark.spec("§4.1", "l-c", "from-lc")
@pytest.mark.parametrize("mode", ["settling", "bandwidth"])
def test_dwell_then_lc_round_trip(mode: str) -> None:
    """tank_from_lc on the L, C from tank_from_dwell reproduces the same tank."""
    a = tank_from_dwell(82e3, 25e6, 0.8e-6, 6, mode)
    b = tank_from_lc(a.r_f, a.l_f, a.c_f)
    for name in ("f_res", "q", "l_f", "c_f", "tau_tank", "bw_3db", "b_eq"):
        assert getattr(b, name) == pytest.approx(getattr(a, name), rel=1e-12), name


@pytest.mark.api
@pytest.mark.spec("§2", "tank-result")
def test_both_constructors_return_tank_result() -> None:
    """tank_from_dwell and tank_from_lc return the same frozen TankResult type."""
    a = tank_from_dwell(1e3, 1e6, 1e-5, 5)
    b = tank_from_lc(1e3, a.l_f, a.c_f)
    assert type(a) is TankResult and type(b) is TankResult
    with pytest.raises(AttributeError):
        a.q = 1.0  # type: ignore[misc]
    assert np.abs(a.z(1e6)) == pytest.approx(1e3)


# -- validation ----------------------------------------------------------------------


@pytest.mark.validation
@pytest.mark.parametrize(
    "args",
    [
        (0, 20e6, 1e-6, 5, "settling"), (100e3, -1, 1e-6, 5, "settling"),
        (100e3, 20e6, 0, 5, "settling"), (100e3, 20e6, 1e-6, 0, "settling"),
        (100e3, 20e6, 1e-6, float("nan"), "settling"), (100e3, 20e6, 1e-6, 5, "other"),
    ],
)
def test_dwell_rejects_bad_input(args: tuple[Any, ...]) -> None:
    """tank_from_dwell raises ValueError for non-positive/non-finite inputs or unknown mode."""
    with pytest.raises(ValueError):
        tank_from_dwell(*args)


@pytest.mark.validation
@pytest.mark.parametrize("args", [(0, 1e-6, 1e-12), (1e3, 0, 1e-12), (1e3, 1e-6, -1e-12)])
def test_lc_rejects_bad_input(args: tuple[float, float, float]) -> None:
    """tank_from_lc raises ValueError for non-positive R, L or C."""
    with pytest.raises(ValueError):
        tank_from_lc(*args)


@pytest.mark.validation
@pytest.mark.parametrize("f", [-1.0, [1e6, -1e6], float("inf"), float("nan")])
def test_z_rejects_bad_frequency(f: Any) -> None:
    """z_f raises ValueError for negative or non-finite frequencies."""
    with pytest.raises(ValueError):
        z_f(f, 1e3, 1e6, 5)
