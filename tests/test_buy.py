"""Buy tool: vendor-built resonant detector, NEP + shot noise only (SPEC §6.4)."""

import math
from typing import Any

import matplotlib

matplotlib.use("Agg")

import pytest  # noqa: E402

from srsfe.core.noise import detector_densities, shot_density  # noqa: E402
from srsfe.core.params import Params  # noqa: E402
from srsfe.plots import figures  # noqa: E402
from srsfe.tools import REGISTRY, Result  # noqa: E402
from tests import golden  # noqa: E402

BUY = REGISTRY["b"]
DESIGN = REGISTRY["d"]
POWERS = ["p_min", "p_max"]
DIY_ONLY = {"c_d": None, "en_opamp": None, "temp": None}


@pytest.fixture
def gp(golden_params: dict[str, Any]) -> Params:
    return Params.from_dict(golden_params)


@pytest.mark.schema
@pytest.mark.spec("§6.4", "calcs", "groups")
def test_buy_declarations() -> None:
    """Same calcs as Design; Noise needs only p_min, p_max, resp, nep, m; Noise group nep, k_crest."""
    assert [c.key for c in BUY.calcs] == [c.key for c in DESIGN.calcs]
    noise = BUY.calc("4")
    assert set(noise.required) == {"r_f", "f_0", "t_dwell", "n_tau", "p_min", "p_max", "resp",
                                   "nep", "m"}
    for c in BUY.calcs:
        assert not set(c.required) & {"c_d", "en_opamp", "temp", "l_f", "c_f"}, c.name
        assert not set(c.outputs) & {"l_f", "c_f", "i_r", "i_en"}, c.name
    groups = {g.key: g.fields for g in BUY.groups}
    assert groups["n"] == ("nep", "k_crest")
    assert [g.key for g in BUY.groups] == [g.key for g in DESIGN.groups]


@pytest.mark.schema
@pytest.mark.spec("§6.4", "calcs")
@pytest.mark.parametrize("key", ["1", "2", "3", "4", "5", "0"])
def test_buy_runs_without_diy_inputs(gp: Params, key: str) -> None:
    """Every Buy calc runs with c_d, en_opamp, temp unset and produces exactly its outputs."""
    c = BUY.calc(key)
    r = c.run(gp.replace(**DIY_ONLY))
    cols = {col for t in r.tables.values() for per in t.values() for col in per if col != "n"}
    assert set(r.scalars) | set(r.per_power) | cols == set(c.outputs)


@pytest.mark.formula
@pytest.mark.spec("§6.4", "tank", "same-as-design")
def test_buy_tank_spectrum_signal_match_design(gp: Params) -> None:
    """Tank shape, harmonics and signal equal Design's for the same r_f, f_0, t_dwell, n_tau."""
    b = BUY.calc("0").run(gp)
    d = DESIGN.calc("0").run(gp)
    for name in ("q", "tau_tank", "bw_3db", "b_eq"):
        assert b.get(name) == d.get(name)
    assert b.tables == d.tables
    for name in ("v_n_sum", "v_sig", "i_sh"):
        assert b.per_power[name] == d.per_power[name]
    assert b.get("q") == pytest.approx(golden.Q, rel=golden.REL)


@pytest.mark.formula
@pytest.mark.spec("§6.4", "noise-model")
@pytest.mark.spec("§4.4", "i-tot")
@pytest.mark.parametrize("power", POWERS)
def test_buy_noise_model(gp: Params, power: str) -> None:
    """i_tot = √(i_sh² + i_NEP²), i_elec = i_NEP, v_dens = R·i_tot, V_rms over B_eq."""
    r = BUY.calc("4").run(gp)
    i_sh = r.get("i_sh", power)
    i_nep = r.get("i_nep")
    assert i_nep == pytest.approx(gp.nep * gp.resp, rel=1e-12)  # type: ignore[operator]
    assert r.get("i_elec") == i_nep
    assert r.get("i_tot", power) == pytest.approx(math.hypot(i_sh, i_nep), rel=1e-12)
    assert r.get("v_dens", power) == pytest.approx(gp.r_f * r.get("i_tot", power), rel=1e-12)  # type: ignore[operator]
    assert r.get("v_rms", power) == pytest.approx(
        r.get("v_dens", power) * math.sqrt(r.get("b_eq")), rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§6.4", "noise-model")
def test_detector_densities() -> None:
    """detector_densities: shot + NEP·ℜ only; i_R and i_en are not modelled (0)."""
    d = detector_densities(1e-4, 5e3, 2e-12, 0.5)
    assert d.i_sh == shot_density(1e-4) and d.i_nep == pytest.approx(1e-12)
    assert d.i_r == 0 and d.i_en == 0 and d.i_elec == d.i_nep
    assert d.v_dens == pytest.approx(5e3 * math.hypot(d.i_sh, 1e-12), rel=1e-12)
    with pytest.raises(ValueError):
        detector_densities(1e-4, 0, 2e-12, 0.5)


@pytest.mark.formula
@pytest.mark.spec("§6.4", "noise-model")
def test_buy_snr_beats_diy_with_same_gain(gp: Params) -> None:
    """Without R's Johnson noise and the opamp noise, Buy SNR ≥ Design SNR at the same gain."""
    b = BUY.calc("5").run(gp)
    d = DESIGN.calc("5").run(gp)
    for power in POWERS:
        assert b.get("snr", power) > d.get("snr", power)
        assert b.get("snr_lia", power) > d.get("snr_lia", power)


@pytest.mark.warning
@pytest.mark.spec("§6.4", "same-as-design")
def test_buy_warnings_as_design(gp: Params) -> None:
    """Golden inputs: Buy fires the same budget/lock-in warnings as Design."""
    b = BUY.calc("0").run(gp)
    assert [(x.id, x.power) for x in b.warnings] == [
        ("W02", None), ("W03", "p_max"), ("W04", "p_min"), ("W04", "p_max")]


@pytest.mark.round_trip
@pytest.mark.spec("§6", "result-json")
def test_buy_result_json(gp: Params) -> None:
    """A Buy result survives JSON and records tool "b"."""
    r = BUY.calc("0").run(gp)
    assert r.tool == "b" and Result.from_json(r.to_json()) == r


@pytest.mark.smoke
@pytest.mark.spec("§8.2", "noise", "bode")
def test_buy_plots_build(gp: Params) -> None:
    """All four plots build for Buy; the noise plot shows only i_sh and i_NEP."""
    r = BUY.calc("0").run(gp)
    for plot in r.plots:
        figures.make(r, plot).canvas.draw()
    ax = figures.make(r, "noise").axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["i_sh", "i_NEP"]
