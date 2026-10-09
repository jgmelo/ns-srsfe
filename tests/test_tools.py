"""M6: tool registry, Design and Analyze tools, Result JSON (SPEC §6)."""

import json
import math
from typing import Any

import pytest

from srsfe.core.params import FIELDS, Params
from srsfe.tools import REGISTRY, CalcInputError, Result
from srsfe.tools import base
from tests import golden

DESIGN = REGISTRY["d"]
ANALYZE = REGISTRY["a"]
POWERS = ["p_min", "p_max"]

SIZING = {"r_f", "f_0", "t_dwell", "n_tau"}
SPECTRUM = SIZING | {"p_min", "p_max", "resp", "f_rep", "f_max"}
NOISE = SIZING | {"p_min", "p_max", "resp", "c_d", "en_opamp", "nep", "temp", "m"}
BUDGET = SPECTRUM | NOISE | {"k_crest", "v_swing", "v_range"}
LOCKIN = NOISE | {"tau_lia", "n_lia"}
# SPEC §6.1 table, with "X +" expanded.
DESIGN_TABLE = {
    "1": ("Sizing", SIZING, {"q_mode"}, ("bode",)),
    "2": ("Spectrum", SPECTRUM, {"q_mode", "tau_p"}, ("spectrum",)),
    "3": ("Budget", BUDGET, {"q_mode", "tau_p", "en_moku", "n_bits"}, ("budget",)),
    "4": ("Noise", NOISE, {"q_mode", "en_moku", "n_bits", "v_range"}, ("noise",)),
    "5": ("Lock-in", LOCKIN, {"q_mode", "en_moku", "n_bits", "v_range"}, ("noise",)),
    "0": ("All", BUDGET | LOCKIN, {"q_mode", "tau_p", "en_moku", "n_bits"},
          ("bode", "spectrum", "budget", "noise")),
}


@pytest.fixture
def gp(golden_params: dict[str, Any]) -> Params:
    return Params.from_dict(golden_params)


def _produced(r: Result) -> set[str]:
    cols = {c for t in r.tables.values() for per in t.values() for c in per if c != "n"}
    return set(r.scalars) | set(r.per_power) | cols


# -- declarations ----------------------------------------------------------------------


@pytest.mark.api
@pytest.mark.spec("§2", "tool-registry")
def test_registry_and_register(monkeypatch: pytest.MonkeyPatch) -> None:
    """Design (d), Buy (b), Analyze (a) are registered in launcher order; a new tool is one
    register() call; keys unique."""
    assert list(REGISTRY) == ["d", "b", "a"]
    monkeypatch.setattr(base, "REGISTRY", dict(base.REGISTRY))
    extra = base.Tool("Extra", "x", "test tool", (), ())
    base.register(extra)
    assert base.REGISTRY["x"] is extra
    with pytest.raises(ValueError):
        base.register(base.Tool("Dup", "d", "", (), ()))


@pytest.mark.schema
@pytest.mark.spec("§6.1", "sizing", "spectrum", "budget", "noise", "lockin", "all")
@pytest.mark.parametrize("key", list(DESIGN_TABLE))
def test_design_calc_declarations(key: str) -> None:
    """Each Design calc declares the SPEC §6.1 name, required, optional and plots."""
    name, required, optional, plots = DESIGN_TABLE[key]
    c = DESIGN.calc(key)
    assert c.name == name and set(c.required) == required and set(c.optional) == optional
    assert c.plots == plots
    assert not set(c.required) & set(c.optional)


@pytest.mark.schema
@pytest.mark.spec("§6.2", "outputs", "optional")
def test_analyze_declaration() -> None:
    """Analyze is a single calc: required l_f, c_f, r_f; optional f_0, t_dwell, n_tau; Bode."""
    (c,) = ANALYZE.calcs
    assert set(c.required) == {"l_f", "c_f", "r_f"}
    assert set(c.optional) == {"f_0", "t_dwell", "n_tau"}
    assert c.outputs == ("f0_calc", "q", "tau_tank", "bw_3db", "b_eq", "settles")
    assert c.plots == ("bode",)


@pytest.mark.schema
def test_groups_follow_field_metadata() -> None:
    """Design groups hold every input except l_f/c_f once, in the group named in field metadata."""
    seen = [f for g in DESIGN.groups for f in g.fields]
    assert sorted(seen) == sorted(set(FIELDS) - {"l_f", "c_f"})
    for g in DESIGN.groups:
        assert all(FIELDS[f].group == g.name for f in g.fields), g.name
    assert [g.key for g in DESIGN.groups] == ["t", "l", "n", "i", "m", "f"]
    (tank,) = ANALYZE.groups
    assert tank.fields == ("l_f", "c_f", "r_f", "f_0", "t_dwell", "n_tau")


@pytest.mark.schema
@pytest.mark.parametrize("key", list(DESIGN_TABLE))
def test_declared_outputs_are_produced(gp: Params, key: str) -> None:
    """With every optional input set, a calc produces exactly its declared outputs."""
    c = DESIGN.calc(key)
    assert _produced(c.run(gp)) == set(c.outputs)


# -- golden through the tools ------------------------------------------------------------


@pytest.mark.golden
@pytest.mark.spec("§6.1", "all")
@pytest.mark.spec("§9.1", "q", "l_f", "c_f", "b_eq", "z_n", "att_n", "i_elec", "lsb", "enbw_lia")
@pytest.mark.spec("§9.2", "v_n_sum", "v_coh", "occ_moku", "snr", "snr_lia", "shot_clear")
def test_golden_design_all(gp: Params) -> None:
    """Design/All on the golden profile reproduces SPEC §9 values end to end."""
    r = DESIGN.calc("0").run(gp)
    assert r.get("q") == pytest.approx(golden.Q, rel=golden.REL)
    assert r.get("l_f") == pytest.approx(golden.L_F, rel=golden.REL)
    assert r.get("c_f") == pytest.approx(golden.C_F, rel=golden.REL)
    assert r.get("b_eq") == pytest.approx(golden.B_EQ, rel=golden.REL)
    assert r.get("i_elec") == pytest.approx(golden.I_ELEC, rel=golden.REL)
    assert r.get("lsb") == pytest.approx(golden.LSB, rel=golden.REL)
    assert r.get("enbw_lia") == pytest.approx(golden.ENBW_LIA[1], rel=golden.REL)
    for power in POWERS:
        h = r.tables["harmonics"][power]
        assert h["z_n"] == pytest.approx(golden.Z_N, rel=golden.REL)
        assert h["att_n"] == pytest.approx(golden.ATT_N, abs=golden.DB_ABS)
        assert h["v_n"] == pytest.approx(golden.V_N[power], rel=golden.REL)
        assert r.get("v_n_sum", power) == pytest.approx(golden.V_N_SUM[power], rel=golden.REL)
        assert r.get("v_coh", power) == pytest.approx(golden.V_COH[power], rel=golden.REL)
        assert r.get("occ_moku", power) == pytest.approx(golden.OCC_MOKU[power], rel=golden.REL)
        assert r.get("snr", power) == pytest.approx(golden.SNR[power], abs=golden.DB_ABS)
        assert r.get("snr_lia", power) == pytest.approx(golden.SNR_LIA[1][power],
                                                        abs=golden.DB_ABS)
        assert r.get("shot_clear", power) == pytest.approx(golden.SHOT_CLEAR[power],
                                                           abs=golden.DB_ABS)


@pytest.mark.golden
@pytest.mark.spec("§9.3", "w02", "w03", "w04", "silent")
def test_golden_design_warnings(gp: Params) -> None:
    """Design/All golden warnings are exactly W02, W03@P_max, W04@P_min, W04@P_max."""
    r = DESIGN.calc("0").run(gp)
    assert [(x.id, x.power) for x in r.warnings] == [
        ("W02", None), ("W03", "p_max"), ("W04", "p_min"), ("W04", "p_max")]


@pytest.mark.golden
@pytest.mark.spec("§6.1", "lockin")
@pytest.mark.spec("§9.2", "snr_lia")
@pytest.mark.spec("§9.3", "w02")
@pytest.mark.parametrize("n_lia", [1, 2, 3, 4])
def test_golden_lockin_calc(gp: Params, n_lia: int) -> None:
    """Lock-in calc: SNR_LIA per n_lia matches SPEC §9.2; W02 only for n_lia 1, 2."""
    r = DESIGN.calc("5").run(gp.replace(n_lia=n_lia))
    for power in POWERS:
        assert r.get("snr_lia", power) == pytest.approx(golden.SNR_LIA[n_lia][power],
                                                        abs=golden.DB_ABS)
    assert ("W02" in {x.id for x in r.warnings}) is golden.W02_FIRES_FOR_N_LIA[n_lia]


@pytest.mark.golden
@pytest.mark.spec("§9.4", "tank", "settles", "no-warnings")
@pytest.mark.spec("§6.2", "outputs")
def test_golden_analyze(gp: Params) -> None:
    """Analyze on the SPEC §9.4 parts: f0_calc, q, τ_tank, settles = True, no warnings."""
    r = ANALYZE.calcs[0].run(gp.replace(**golden.ANALYZE_INPUTS))
    assert r.get("f0_calc") == pytest.approx(golden.ANALYZE_F0_CALC, rel=golden.REL)
    assert r.get("q") == pytest.approx(golden.ANALYZE_Q, rel=golden.REL)
    assert r.get("tau_tank") == pytest.approx(golden.ANALYZE_TAU_TANK, rel=golden.REL)
    assert r.get("settles") is True and r.warnings == ()


# -- validation and optional gating ------------------------------------------------------


@pytest.mark.validation
@pytest.mark.spec("§6.1", "missing-required")
def test_missing_required_nothing_runs() -> None:
    """Missing required inputs raise CalcInputError listing them, in SPEC order."""
    p = Params.from_dict({"r_f": 1e5, "t_dwell": 1e-6})
    with pytest.raises(CalcInputError) as exc:
        DESIGN.calc("1").run(p)
    assert exc.value.missing == ["f_0", "n_tau"] and exc.value.invalid == {}


@pytest.mark.validation
@pytest.mark.spec("§6.1", "missing-required")
def test_invalid_used_inputs_block_unused_do_not(gp: Params) -> None:
    """An invalid input the calc uses blocks it; an invalid unused input does not."""
    with pytest.raises(CalcInputError) as exc:
        DESIGN.calc("1").run(gp.replace(r_f=-1.0))
    assert set(exc.value.invalid) == {"r_f"}
    DESIGN.calc("1").run(gp.replace(p_min=-1.0))  # Sizing does not use p_min
    with pytest.raises(CalcInputError) as exc:
        DESIGN.calc("2").run(gp.replace(p_min=2e-3))  # p_min > p_max
    assert set(exc.value.invalid) == {"p_min", "p_max"}


@pytest.mark.formula
@pytest.mark.spec("§6.1", "optional-gating")
def test_tau_p_gates_i_pk_and_w08(gp: Params) -> None:
    """i_pk and W08 only when tau_p is set; a long pulse fires W08."""
    r = DESIGN.calc("2").run(gp.replace(tau_p=None))
    assert "i_pk" not in r.per_power and "W08" not in {x.id for x in r.warnings}
    r = DESIGN.calc("2").run(gp.replace(tau_p=1e-9))
    assert "i_pk" in r.per_power and "W08" in {x.id for x in r.warnings}


@pytest.mark.formula
@pytest.mark.spec("§6.1", "optional-gating")
def test_en_moku_and_bits_gate_w05_and_lsb(gp: Params) -> None:
    """W05 only with en_moku; lsb/v_q only with n_bits and v_range (Noise calc)."""
    r = DESIGN.calc("4").run(gp.replace(en_moku=None, n_bits=None))
    assert "lsb" not in r.scalars and "W05" not in {x.id for x in r.warnings}
    r = DESIGN.calc("4").run(gp.replace(en_moku=1e-6))
    assert "lsb" in r.scalars
    assert {(x.id, x.power) for x in r.warnings if x.id == "W05"} == {("W05", "p_min"),
                                                                       ("W05", "p_max")}


@pytest.mark.formula
@pytest.mark.spec("§6.1", "sizing")
def test_q_mode_defaults_to_settling(gp: Params) -> None:
    """Unset q_mode sizes the tank in settling mode; bandwidth mode gives Q = f₀·t_dwell."""
    unset = DESIGN.calc("1").run(gp.replace(q_mode=None))
    assert unset.get("q") == DESIGN.calc("1").run(gp).get("q")
    assert DESIGN.calc("1").run(gp.replace(q_mode="bandwidth")).get("q") == pytest.approx(20.0)


@pytest.mark.warning
@pytest.mark.spec("§6.1", "spectrum")
@pytest.mark.spec("§5", "W09:fires")
def test_spectrum_calc_checks_f_rep(gp: Params) -> None:
    """The Spectrum calc runs W09 when f_0 is not f_rep/2."""
    r = DESIGN.calc("2").run(gp.replace(f_rep=76e6))
    assert [x.id for x in r.warnings] == ["W09"]


@pytest.mark.formula
@pytest.mark.spec("§6.2", "optional")
@pytest.mark.spec("§5", "W06:fires", "W07:fires")
def test_analyze_optional_inputs(gp: Params) -> None:
    """Without f_0 no W06; without t_dwell/n_tau no settles/W07; an off, slow tank fires both."""
    base_in = {**golden.ANALYZE_INPUTS, "c_f": 1.21e-12}  # f_res ≈ 18.2 MHz, τ = 242 ns
    r = ANALYZE.calcs[0].run(Params.from_dict({k: base_in[k] for k in ("l_f", "c_f", "r_f")}))
    assert r.warnings == () and "settles" not in r.scalars
    r = ANALYZE.calcs[0].run(Params.from_dict(base_in))
    assert r.get("settles") is False
    assert [x.id for x in r.warnings] == ["W06", "W07"]


# -- Result JSON -------------------------------------------------------------------------


@pytest.mark.round_trip
@pytest.mark.spec("§6", "result-json")
@pytest.mark.parametrize("tool_calc", [("d", "0"), ("d", "1"), ("a", "1")])
def test_result_json_round_trip(gp: Params, tool_calc: tuple[str, str]) -> None:
    """Result → JSON → Result is lossless, including warnings, tables and params."""
    tool, calc = tool_calc
    p = gp.replace(**golden.ANALYZE_INPUTS) if tool == "a" else gp
    r = REGISTRY[tool].calc(calc).run(p)
    text = r.to_json()
    assert Result.from_json(text) == r
    assert json.loads(text)["params"]["r_f"] == 100e3


@pytest.mark.round_trip
@pytest.mark.spec("§6", "result-json")
def test_result_json_non_finite(gp: Params) -> None:
    """m = 0 gives SNR = −inf; it is tagged in strict JSON and restored on load."""
    r = DESIGN.calc("5").run(gp.replace(m=0.0))
    assert r.get("snr", "p_min") == -math.inf
    text = r.to_json()
    assert "Infinity" not in text and '{"$float": "-inf"}' in text
    back = Result.from_json(text)
    assert back.get("snr_lia", "p_max") == -math.inf and back == r
