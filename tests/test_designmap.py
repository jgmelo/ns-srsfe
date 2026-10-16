"""M11: design-space map computation (SPEC §6.5)."""

import math
from typing import Any

import numpy as np
import pytest

from srsfe.core.params import Params
from srsfe.tools import REGISTRY, CalcInputError, Result
from srsfe.tools.designmap import (
    MapSettings,
    MapSettingsError,
    compute,
    first_crossing,
    table_powers,
    validate,
)

DESIGN, BUY = REGISTRY["d"], REGISTRY["b"]
SMALL = MapSettings(n=9)  # 100 ns … 100 µs, 1 µW … 10 mW: grid points every 10^(3/8) / 10^(4/8)


@pytest.fixture
def gp(golden_params: dict[str, Any]) -> Params:
    return Params.from_dict(golden_params)


@pytest.fixture
def small_map(gp: Params) -> Result:
    return compute(DESIGN, gp, SMALL)


def _point(gp: Params, t: float, p: float, base: str = "d") -> Result:
    return REGISTRY[base].calc("3").run(gp.replace(t_dwell=t, p_min=p, p_max=p))


# -- settings ------------------------------------------------------------------------------


@pytest.mark.schema
@pytest.mark.spec("§6.5", "settings")
def test_settings_defaults() -> None:
    """Defaults: Design base, 100 ns–100 µs, 1 µW–10 mW, 41 points, target 10 dB; valid."""
    s = MapSettings()
    assert (s.base, s.t_lo, s.t_hi, s.p_lo, s.p_hi, s.n, s.target) == (
        "d", 100e-9, 100e-6, 1e-6, 10e-3, 41, 10.0)
    assert validate(s) == {}


@pytest.mark.validation
@pytest.mark.spec("§6.5", "settings")
@pytest.mark.parametrize(
    ("change", "field"),
    [({"base": "a"}, "base"), ({"t_lo": 0.0}, "t_lo"), ({"t_hi": 50e-9}, "t_hi"),
     ({"p_lo": -1.0}, "p_lo"), ({"p_hi": 1e-6}, "p_hi"), ({"n": 4}, "n"), ({"n": 202}, "n"),
     ({"target": math.inf}, "target")],
)
def test_settings_validation(change: dict[str, Any], field: str) -> None:
    """Bad base, non-positive or inverted ranges, n outside 5…201, non-finite target."""
    assert field in validate(MapSettings(**{**MapSettings().to_dict(), **change}))


@pytest.mark.round_trip
@pytest.mark.spec("§6.5", "settings")
def test_settings_dict_round_trip_and_fallback() -> None:
    """to_dict/from_dict round-trips; wrong types or missing keys fall back to defaults."""
    s = MapSettings(base="b", t_lo=1e-7, t_hi=1e-5, p_lo=1e-5, p_hi=1e-2, n=21, target=3.0)
    assert MapSettings.from_dict(s.to_dict()) == s
    bad = MapSettings.from_dict({"base": 3, "n": 12.5, "target": "x", "t_lo": 2e-7, "extra": 1})
    assert bad == MapSettings(t_lo=2e-7)
    assert MapSettings.from_dict({"n": 21, "target": 3}).target == 3.0


@pytest.mark.validation
@pytest.mark.spec("§6.5", "settings", "inputs")
def test_compute_refuses_bad_settings_or_inputs(gp: Params) -> None:
    """Invalid settings raise MapSettingsError; a missing profile input raises CalcInputError."""
    with pytest.raises(MapSettingsError):
        compute(DESIGN, gp, MapSettings(n=3))
    with pytest.raises(CalcInputError) as exc:
        compute(DESIGN, gp.replace(f_rep=None), SMALL)
    assert exc.value.missing == ["f_rep"]


# -- crossings -----------------------------------------------------------------------------


@pytest.mark.formula
@pytest.mark.spec("§6.5", "crossings")
def test_first_crossing() -> None:
    """Log-linear interpolation; t[0] if already met; None if never; falling direction."""
    t = np.array([1e-6, 1e-5, 1e-4])
    y = np.array([0.0, 10.0, 20.0])
    assert first_crossing(t, y, 5.0, rising=True) == pytest.approx(10**-5.5, rel=1e-12)
    assert first_crossing(t, y, -3.0, rising=True) == 1e-6
    assert first_crossing(t, y, 25.0, rising=True) is None
    assert first_crossing(t, -y, -15.0, rising=False) == pytest.approx(10**-4.5, rel=1e-12)


# -- grid ------------------------------------------------------------------------------------


@pytest.mark.schema
@pytest.mark.spec("§6.5", "grid", "result-json")
def test_map_result_layout(small_map: Result, gp: Params) -> None:
    """Tool w, log-spaced axes from the settings, n×n grids, plot 'map', JSON round trip."""
    m = small_map.tables["map"]
    t, p = np.array(m["axes"]["t_dwell"]), np.array(m["axes"]["power"])
    assert small_map.tool == "w" and small_map.plots == ("map",)
    assert t[0] == pytest.approx(100e-9) and t[-1] == pytest.approx(100e-6) and len(t) == 9
    assert np.allclose(np.diff(np.log10(p)), 0.5)
    for key in ("snr", "occ", "shot_clear"):
        assert np.array(m["grid"][key]).shape == (9, 9)
    assert small_map.scalars["target"] == 10.0 and small_map.params == gp.to_dict()
    assert Result.from_json(small_map.to_json()) == small_map


@pytest.mark.formula
@pytest.mark.spec("§6.5", "grid")
@pytest.mark.parametrize(("i", "j"), [(0, 0), (4, 4), (8, 2), (3, 7)])
def test_grid_matches_direct_runs(small_map: Result, gp: Params, i: int, j: int) -> None:
    """Grid cell (power i, t_dwell j) equals the Budget calc run directly at that point."""
    m = small_map.tables["map"]
    t, p = m["axes"]["t_dwell"][j], m["axes"]["power"][i]
    r = _point(gp, t, p)
    assert m["grid"]["snr"][i][j] == pytest.approx(r.get("snr", "p_min"), rel=1e-12)
    occ = max(r.get("occ_swing", "p_min"), r.get("occ_moku", "p_min"))
    assert m["grid"]["occ"][i][j] == pytest.approx(occ, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§6.5", "grid")
def test_map_physics(gp: Params) -> None:
    """snr rises 10 dB per decade of t_dwell (B_eq ∝ 1/t_dwell); shot_clear is independent of
    t_dwell and rises 10 dB per decade of power."""
    m = compute(DESIGN, gp, MapSettings(n=7, t_lo=1e-7, t_hi=1e-4, p_lo=1e-6, p_hi=1e-3)).tables["map"]
    snr, clear = np.array(m["grid"]["snr"]), np.array(m["grid"]["shot_clear"])
    assert np.allclose(snr[:, 2::2] - snr[:, :-2:2], 10.0, atol=1e-9)  # 2 steps = one decade
    assert np.allclose(clear - clear[:, :1], 0.0, atol=1e-9)
    assert np.allclose(clear[2::2, 0] - clear[:-2:2, 0], 10.0, atol=1e-9)


@pytest.mark.formula
@pytest.mark.spec("§6.5", "grid")
def test_map_buy_base(gp: Params) -> None:
    """The Buy base runs without DIY-only inputs and matches Buy's Budget calc."""
    p = gp.replace(c_d=None, en_opamp=None, temp=None)
    m = compute(BUY, p, MapSettings(base="b", n=5)).tables["map"]
    t, pw = m["axes"]["t_dwell"][2], m["axes"]["power"][1]
    assert m["grid"]["snr"][1][2] == pytest.approx(_point(p, t, pw, "b").get("snr", "p_min"))


# -- slices and boundaries --------------------------------------------------------------------


@pytest.mark.formula
@pytest.mark.spec("§6.5", "slices")
def test_slices_at_profile_powers(small_map: Result, gp: Params) -> None:
    """Slices run along the same t_dwell points at the profile's P_min and P_max."""
    sl = small_map.tables["slices"]
    t = sl["t_dwell"]["values"]
    for name in ("p_min", "p_max"):
        power = getattr(gp, name)
        assert sl[name]["power"] == [power]
        assert sl[name]["snr"][3] == pytest.approx(_point(gp, t[3], power).get("snr", "p_min"))


@pytest.mark.schema
@pytest.mark.spec("§6.5", "boundaries")
def test_table_rows(gp: Params) -> None:
    """Rows: P_min, P_max, then each decade inside [p_lo, p_hi] not equal to either."""
    rows = table_powers(gp, MapSettings(p_lo=2e-6, p_hi=1e-2))
    assert rows == [("P_min", 1e-4), ("P_max", 1e-3), ("decade", 1e-5), ("decade", 1e-2)]
    other = table_powers(gp.replace(p_min=3e-5, p_max=3e-4), MapSettings(p_lo=1e-5, p_hi=1e-4))
    assert other == [("P_min", 3e-5), ("P_max", 3e-4), ("decade", 1e-5), ("decade", 1e-4)]


@pytest.mark.formula
@pytest.mark.spec("§6.5", "boundaries", "crossings")
def test_boundaries_hit_their_limits(gp: Params) -> None:
    """At t_snr the snr equals the target; at t_ovl occupancy is 100 %; t_safe is the larger."""
    p = gp.replace(r_f=10e3)
    res = compute(DESIGN, p, MapSettings(n=31, target=-10.0))
    rows = res.tables["boundaries"]["rows"]
    k = rows["label"].index("P_max")
    t_snr, t_ovl, t_safe = rows["t_snr"][k], rows["t_ovl"][k], rows["t_safe"][k]
    assert t_snr is not None and t_ovl is not None
    at_snr = _point(p, t_snr, 1e-3)
    assert at_snr.get("snr", "p_min") == pytest.approx(-10.0, abs=1e-6)  # snr linear in log t
    at_ovl = _point(p, t_ovl, 1e-3)
    occ = max(at_ovl.get("occ_swing", "p_min"), at_ovl.get("occ_moku", "p_min"))
    assert occ == pytest.approx(100.0, rel=0.02)
    assert t_safe == max(t_snr, t_ovl)
    assert rows["snr_design"][k] == pytest.approx(_point(p, gp.t_dwell, 1e-3).get("snr", "p_min"))


@pytest.mark.formula
@pytest.mark.spec("§6.5", "crossings", "boundaries")
def test_boundaries_edges(gp: Params) -> None:
    """Unreachable target → None (and t_safe None); target met at t_lo → t_lo."""
    never = compute(DESIGN, gp, MapSettings(n=5, target=200.0)).tables["boundaries"]["rows"]
    assert all(v is None for v in never["t_snr"]) and all(v is None for v in never["t_safe"])
    always = compute(DESIGN, gp, MapSettings(n=5, target=-500.0)).tables["boundaries"]["rows"]
    assert all(v == pytest.approx(100e-9) for v in always["t_snr"])
