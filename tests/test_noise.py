"""M4: noise densities, rms noise, SNR, shot clearance and lock-in ENBW (SPEC §4.4–§4.6)."""

import math
from typing import Any

import pytest

from srsfe.core.noise import (
    NoiseDensities,
    densities,
    enbw_lia,
    johnson_density,
    nep_density,
    opamp_density,
    shot_clear_db,
    shot_density,
    snr_db,
    v_rms,
)
from srsfe.core.spectrum import photocurrent, signal
from srsfe.core.tank import TankResult, tank_from_dwell
from tests import golden

POWERS = ["p_min", "p_max"]


@pytest.fixture
def golden_tank(golden_params: dict[str, Any]) -> TankResult:
    g = golden_params
    return tank_from_dwell(g["r_f"], g["f_0"], g["t_dwell"], g["n_tau"], g["q_mode"])


def _dens(g: dict[str, Any], power: str) -> NoiseDensities:
    return densities(photocurrent(g[power], g["resp"]), g["r_f"], g["f_0"], g["c_d"],
                     g["en_opamp"], g["nep"], g["resp"], g["temp"])


def _v_sig(g: dict[str, Any], power: str) -> float:
    return signal(photocurrent(g[power], g["resp"]), g["m"], g["r_f"]).v_sig


# -- golden ----------------------------------------------------------------------


@pytest.mark.golden
@pytest.mark.spec("§9.1", "i_r", "i_en", "i_nep", "i_elec")
@pytest.mark.spec("§4.4", "i-r", "i-en", "i-nep", "i-tot")
def test_golden_power_independent_densities(golden_params: dict[str, Any]) -> None:
    """i_R, i_en, i_NEP and i_elec match SPEC §9.1 (identical at both powers)."""
    for power in POWERS:
        d = _dens(golden_params, power)
        assert d.i_r == pytest.approx(golden.I_R, rel=golden.REL)
        assert d.i_en == pytest.approx(golden.I_EN, rel=golden.REL)
        assert d.i_nep == pytest.approx(golden.I_NEP, rel=golden.REL)
        assert d.i_elec == pytest.approx(golden.I_ELEC, rel=golden.REL)


@pytest.mark.golden
@pytest.mark.spec("§9.2", "i_sh", "i_tot", "v_dens", "v_rms")
@pytest.mark.spec("§4.4", "i-sh", "i-tot", "v-rms")
@pytest.mark.parametrize("power", POWERS)
def test_golden_power_dependent_noise(
    golden_params: dict[str, Any], golden_tank: TankResult, power: str
) -> None:
    """i_sh, i_tot, v_dens and V_rms over B_eq match SPEC §9.2."""
    d = _dens(golden_params, power)
    assert d.i_sh == pytest.approx(golden.I_SH[power], rel=golden.REL)
    assert d.i_tot == pytest.approx(golden.I_TOT[power], rel=golden.REL)
    assert d.v_dens == pytest.approx(golden.V_DENS[power], rel=golden.REL)
    assert v_rms(d.v_dens, golden_tank.b_eq) == pytest.approx(golden.V_RMS[power], rel=golden.REL)


@pytest.mark.golden
@pytest.mark.spec("§9.2", "snr", "shot_clear")
@pytest.mark.spec("§4.6", "snr", "shot-clear")
@pytest.mark.parametrize("power", POWERS)
def test_golden_snr_and_shot_clear(
    golden_params: dict[str, Any], golden_tank: TankResult, power: str
) -> None:
    """SNR over B_eq and shot_clear match SPEC §9.2 (±0.01 dB)."""
    d = _dens(golden_params, power)
    snr = snr_db(_v_sig(golden_params, power), v_rms(d.v_dens, golden_tank.b_eq))
    assert snr == pytest.approx(golden.SNR[power], abs=golden.DB_ABS)
    assert shot_clear_db(d.i_sh, d.i_elec) == pytest.approx(golden.SHOT_CLEAR[power],
                                                            abs=golden.DB_ABS)


@pytest.mark.golden
@pytest.mark.spec("§9.1", "enbw_lia")
@pytest.mark.spec("§4.5", "enbw")
@pytest.mark.parametrize("n_lia", [1, 2, 3, 4])
def test_golden_enbw(golden_params: dict[str, Any], n_lia: int) -> None:
    """Lock-in ENBW for τ_LIA = 200 ns, orders 1–4, matches SPEC §9.1."""
    assert enbw_lia(golden_params["tau_lia"], n_lia) == pytest.approx(golden.ENBW_LIA[n_lia],
                                                                      rel=golden.REL)


@pytest.mark.golden
@pytest.mark.spec("§9.2", "snr_lia")
@pytest.mark.spec("§4.5", "v-rms-lia")
@pytest.mark.spec("§4.6", "snr")
@pytest.mark.parametrize("n_lia", [1, 2, 3, 4])
@pytest.mark.parametrize("power", POWERS)
def test_golden_snr_lia(golden_params: dict[str, Any], power: str, n_lia: int) -> None:
    """Lock-in SNR (V_rms over ENBW) for orders 1–4 at both powers matches SPEC §9.2."""
    g = golden_params
    noise = v_rms(_dens(g, power).v_dens, enbw_lia(g["tau_lia"], n_lia))
    assert snr_db(_v_sig(g, power), noise) == pytest.approx(golden.SNR_LIA[n_lia][power],
                                                            abs=golden.DB_ABS)


# -- formulas ----------------------------------------------------------------------


@pytest.mark.formula
@pytest.mark.spec("§4.4", "i-en")
def test_opamp_noise_limits() -> None:
    """i_en → e_n/R with no PD capacitance; → e_n·ω₀·C_d when C_d dominates."""
    assert opamp_density(2e-9, 1e4, 1e6, 0.0) == pytest.approx(2e-9 / 1e4, rel=1e-12)
    w0c = 2 * math.pi * 50e6 * 100e-12
    assert opamp_density(2e-9, 1e9, 50e6, 100e-12) == pytest.approx(2e-9 * w0c, rel=1e-9)


@pytest.mark.formula
@pytest.mark.spec("§4.4", "i-sh", "i-r", "i-nep")
def test_density_scaling() -> None:
    """i_sh ∝ √I₀, i_R ∝ √(T/R), i_NEP ∝ NEP·ℜ."""
    assert shot_density(4e-3) == pytest.approx(2 * shot_density(1e-3), rel=1e-12)
    assert shot_density(0.0) == 0
    assert johnson_density(1e3, 4 * 300) == pytest.approx(2 * johnson_density(1e3, 300), rel=1e-12)
    assert johnson_density(4e3, 300) == pytest.approx(johnson_density(1e3, 300) / 2, rel=1e-12)
    assert nep_density(1e-14, 0.5) == pytest.approx(5e-15, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.4", "i-tot", "v-rms")
def test_densities_add_in_quadrature() -> None:
    """i_tot² = i_sh² + i_elec², i_elec² = i_R² + i_en² + i_NEP², v_dens = R·i_tot."""
    d = densities(1e-4, 50e3, 10e6, 4e-12, 3e-9, 1e-14, 0.9, 300)
    assert d.i_elec**2 == pytest.approx(d.i_r**2 + d.i_en**2 + d.i_nep**2, rel=1e-12)
    assert d.i_tot**2 == pytest.approx(d.i_sh**2 + d.i_elec**2, rel=1e-12)
    assert d.v_dens == pytest.approx(50e3 * d.i_tot, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.4", "v-rms")
def test_v_rms_scales_with_sqrt_bandwidth() -> None:
    """V_rms = v_dens·√B: 4× the bandwidth doubles the rms noise."""
    assert v_rms(1e-6, 4e6) == pytest.approx(2 * v_rms(1e-6, 1e6), rel=1e-12)
    assert v_rms(1e-6, 1e6) == pytest.approx(1e-3, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.5", "enbw")
@pytest.mark.parametrize("n_lia", [1, 2, 3, 4])
def test_enbw_matches_rc_cascade(n_lia: int) -> None:
    """SPEC ENBW factors equal the n-pole RC result Γ(n−½)/(4√π·Γ(n)·τ)."""
    tau = 1e-6
    expected = math.gamma(n_lia - 0.5) / (4 * math.sqrt(math.pi) * math.gamma(n_lia) * tau)
    assert enbw_lia(tau, n_lia) == pytest.approx(expected, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.6", "snr")
def test_snr_definition() -> None:
    """SNR compares an amplitude with rms: V_sig = √2·V_rms is 0 dB; ×10 is +20 dB; m = 0 → −inf."""
    assert snr_db(math.sqrt(2) * 1e-3, 1e-3) == pytest.approx(0, abs=1e-12)
    assert snr_db(10 * math.sqrt(2) * 1e-3, 1e-3) == pytest.approx(20, abs=1e-12)
    assert snr_db(0.0, 1e-3) == -math.inf


@pytest.mark.formula
@pytest.mark.spec("§4.5", "v-rms-lia")
@pytest.mark.spec("§4.6", "snr")
def test_lock_in_gain_is_bandwidth_ratio(
    golden_params: dict[str, Any], golden_tank: TankResult
) -> None:
    """SNR_LIA − SNR = 10·log₁₀(B_eq/ENBW): the lock-in only narrows the noise bandwidth."""
    g = golden_params
    d = _dens(g, "p_min")
    v_sig = _v_sig(g, "p_min")
    enbw = enbw_lia(g["tau_lia"], 3)
    gain = snr_db(v_sig, v_rms(d.v_dens, enbw)) - snr_db(v_sig, v_rms(d.v_dens, golden_tank.b_eq))
    assert gain == pytest.approx(10 * math.log10(golden_tank.b_eq / enbw), abs=1e-9)


@pytest.mark.formula
@pytest.mark.spec("§4.6", "shot-clear")
def test_shot_clear_rises_10db_per_decade_of_power(golden_params: dict[str, Any]) -> None:
    """i_sh ∝ √P, so 10× the power raises shot_clear by exactly 10 dB."""
    g = golden_params
    d1 = _dens(g, "p_min")
    d10 = _dens({**g, "p_min": 10 * g["p_min"]}, "p_min")
    diff = shot_clear_db(d10.i_sh, d10.i_elec) - shot_clear_db(d1.i_sh, d1.i_elec)
    assert diff == pytest.approx(10, abs=1e-9)


# -- API / validation ------------------------------------------------------------------


@pytest.mark.api
def test_noise_densities_frozen() -> None:
    """NoiseDensities is an immutable result."""
    d = densities(1e-4, 1e5, 20e6, 6e-12, 2.5e-9, 7.1e-15, 0.6, 295)
    with pytest.raises(AttributeError):
        d.i_sh = 0.0  # type: ignore[misc]


@pytest.mark.validation
@pytest.mark.spec("§3.1", "n-lia")
@pytest.mark.parametrize("n_lia", [0, 5, 1.5, True, "1"])
def test_enbw_rejects_bad_order(n_lia: Any) -> None:
    """enbw_lia accepts only orders 1, 2, 3, 4."""
    with pytest.raises(ValueError):
        enbw_lia(1e-6, n_lia)


@pytest.mark.validation
@pytest.mark.parametrize(
    ("func", "args"),
    [
        (shot_density, (-1e-3,)), (johnson_density, (0, 295)), (johnson_density, (1e3, 0)),
        (opamp_density, (0, 1e3, 1e6, 1e-12)), (opamp_density, (1e-9, 1e3, 1e6, -1e-12)),
        (nep_density, (0, 0.6)), (v_rms, (1e-6, 0)), (enbw_lia, (0, 1)),
        (snr_db, (1e-3, 0)), (snr_db, (-1e-3, 1e-3)), (shot_clear_db, (1e-12, 0)),
    ],
)
def test_rejects_bad_input(func: Any, args: tuple[Any, ...]) -> None:
    """Non-positive/non-finite inputs raise ValueError (I₀, C_d, V_sig, i_sh may be 0)."""
    with pytest.raises(ValueError):
        func(*args)
