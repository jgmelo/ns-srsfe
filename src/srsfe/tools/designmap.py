"""Design-space map (SPEC §6.5): snr over t_dwell × optical power, with the limits that bound
a usable design (SNR target, overload) and a boundary table.

The base tool's Budget calc (key 3) is run on the active profile at every grid point with
t_dwell = t and p_min = p_max = P; tools are the only place Params are unpacked (SPEC §2).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any

import numpy as np

from srsfe.core.params import Params
from srsfe.core.units import parse_eng
from srsfe.tools.base import Calc, CalcInputError, Result, Tool

TOOL_KEY = "w"
CALC_KEY = "1"
BUDGET_CALC = "3"
BASES = ("d", "b")
N_RANGE = (5, 201)
PLOTS = ("map",)


@dataclass(frozen=True)
class MapSettings:
    """Map settings (SPEC §6.5); stored in the settings file, not in profiles."""

    base: str = "d"
    t_lo: float = 100e-9
    t_hi: float = 100e-6
    p_lo: float = 1e-6
    p_hi: float = 10e-3
    n: int = 41
    target: float = 10.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapSettings:
        """Known keys only; wrong types or missing keys fall back to defaults."""
        default = cls()
        values: dict[str, Any] = {}
        for f in fields(cls):
            v = data.get(f.name, getattr(default, f.name))
            ref = getattr(default, f.name)
            if isinstance(ref, str):
                ok = isinstance(v, str)
            elif isinstance(ref, int):
                ok = isinstance(v, int) and not isinstance(v, bool)
            else:
                ok = isinstance(v, (int, float)) and not isinstance(v, bool)
                v = float(v) if ok else v
            values[f.name] = v if ok else ref
        return cls(**values)


@dataclass(frozen=True)
class SettingMeta:
    """Key (Map screen, SPEC §8.3), unit and description of one map setting."""

    key: str
    unit: str
    description: str


SETTING_META: dict[str, SettingMeta] = {
    "base": SettingMeta("m", "–", "Base tool: d Design or b Buy (m toggles)"),
    "t_lo": SettingMeta("i", "s", "Shortest dwell time on the map"),
    "t_hi": SettingMeta("x", "s", "Longest dwell time on the map"),
    "p_lo": SettingMeta("l", "W", "Lowest optical power on the map"),
    "p_hi": SettingMeta("h", "W", "Highest optical power on the map"),
    "n": SettingMeta("n", "–", f"Grid points per axis, {N_RANGE[0]}…{N_RANGE[1]}"),
    "target": SettingMeta("g", "dB", "SNR target (higher is better)"),
}


def parse_setting(name: str, text: str) -> float | int:
    """Text in engineering notation → SI value for a numeric setting. ValueError with a
    reason for unparseable text or a non-integer n (range checks are validate()'s)."""
    v = parse_eng(text.strip(), SETTING_META[name].unit)
    if name == "n":
        if not float(v).is_integer():
            raise ValueError("must be an integer")
        return int(v)
    return v


def validate(s: MapSettings) -> dict[str, str]:
    """Errors keyed by setting name; empty = valid."""
    errors: dict[str, str] = {}
    if s.base not in BASES:
        errors["base"] = f"must be one of {', '.join(BASES)}"
    for name in ("t_lo", "t_hi", "p_lo", "p_hi"):
        v = getattr(s, name)
        if not (math.isfinite(v) and v > 0):
            errors[name] = "must be > 0"
    if "t_lo" not in errors and "t_hi" not in errors and s.t_lo >= s.t_hi:
        errors["t_hi"] = "must be > t_lo"
    if "p_lo" not in errors and "p_hi" not in errors and s.p_lo >= s.p_hi:
        errors["p_hi"] = "must be > p_lo"
    if not (N_RANGE[0] <= s.n <= N_RANGE[1]):
        errors["n"] = f"must be an integer {N_RANGE[0]}…{N_RANGE[1]}"
    if not math.isfinite(s.target):
        errors["target"] = "must be finite"
    return errors


class MapSettingsError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("invalid map settings: " + ", ".join(f"{k} ({v})" for k, v in errors.items()))


# -- crossings ---------------------------------------------------------------------------


def first_crossing(t: np.ndarray, y: np.ndarray, level: float, rising: bool) -> float | None:
    """Smallest t where y ≥ level (rising) or y ≤ level (falling), interpolated linearly in
    (log t, y) between grid points. t[0] if already met at the first point; None if never."""
    ok = y >= level if rising else y <= level
    if not ok.any():
        return None
    k = int(np.argmax(ok))
    if k == 0:
        return float(t[0])
    y0, y1 = y[k - 1], y[k]
    if not (math.isfinite(y0) and math.isfinite(y1)) or y1 == y0:
        return float(t[k])
    frac = (level - y0) / (y1 - y0)
    return float(10 ** (math.log10(t[k - 1]) + frac * (math.log10(t[k]) - math.log10(t[k - 1]))))


# -- computation -------------------------------------------------------------------------


@dataclass(frozen=True)
class _Point:
    snr: float
    occ: float
    shot_clear: float


def _run(calc: Calc, params: Params, t: float, p: float) -> _Point:
    r = calc.compute(params.replace(t_dwell=t, p_min=p, p_max=p))
    occ = max(r.get("occ_swing", "p_min"), r.get("occ_moku", "p_min"))
    return _Point(r.get("snr", "p_min"), occ, r.get("shot_clear", "p_min"))


def _check_inputs(calc: Calc, params: Params, s: MapSettings) -> None:
    """Validate the profile once at a representative point (grid values replace the axes)."""
    probe = params.replace(t_dwell=s.t_lo, p_min=s.p_lo, p_max=s.p_lo)
    missing, invalid = calc.missing(probe), calc.invalid(probe)
    if missing or invalid:
        raise CalcInputError(missing, invalid)


def table_powers(params: Params, s: MapSettings) -> list[tuple[str, float]]:
    """Boundary-table rows: profile P_min, P_max, then every decade inside [p_lo, p_hi]
    that is not already one of them."""
    rows: list[tuple[str, float]] = []
    if params.p_min is not None:
        rows.append(("P_min", params.p_min))
    if params.p_max is not None:
        rows.append(("P_max", params.p_max))
    profile = [v for _, v in rows]
    for k in range(math.ceil(math.log10(s.p_lo) - 1e-12), math.floor(math.log10(s.p_hi) + 1e-12) + 1):
        if not any(math.isclose(10.0**k, v, rel_tol=1e-9) for v in profile):
            rows.append(("decade", 10.0**k))
    return rows


def compute(tool: Tool, params: Params, s: MapSettings) -> Result:
    """Run the map. Raises MapSettingsError or CalcInputError before computing anything."""
    errors = validate(s)
    if errors:
        raise MapSettingsError(errors)
    calc = tool.calc(BUDGET_CALC)
    _check_inputs(calc, params, s)

    t = np.geomspace(s.t_lo, s.t_hi, s.n)
    p = np.geomspace(s.p_lo, s.p_hi, s.n)
    snr = np.empty((s.n, s.n))
    occ = np.empty_like(snr)
    clear = np.empty_like(snr)
    for i, pi in enumerate(p):
        for j, tj in enumerate(t):
            pt = _run(calc, params, float(tj), float(pi))
            snr[i, j], occ[i, j], clear[i, j] = pt.snr, pt.occ, pt.shot_clear

    def along_t(power: float) -> tuple[np.ndarray, np.ndarray]:
        pts = [_run(calc, params, float(tj), power) for tj in t]
        return np.array([x.snr for x in pts]), np.array([x.occ for x in pts])

    slices: dict[str, dict[str, list[float]]] = {}
    for name in ("p_min", "p_max"):
        power = getattr(params, name)
        if power is not None:
            s_snr, s_occ = along_t(power)
            slices[name] = {"power": [power], "snr": s_snr.tolist(), "occ": s_occ.tolist()}

    rows: dict[str, list[Any]] = {k: [] for k in
                                  ("label", "power", "t_snr", "t_ovl", "t_safe", "snr_design")}
    for label, power in table_powers(params, s):
        r_snr, r_occ = along_t(power)
        t_snr = first_crossing(t, r_snr, s.target, rising=True)
        t_ovl = first_crossing(t, np.log10(r_occ), 2.0, rising=False)  # occupancy ≤ 100 %
        rows["label"].append(label)
        rows["power"].append(power)
        rows["t_snr"].append(t_snr)
        rows["t_ovl"].append(t_ovl)
        rows["t_safe"].append(None if t_snr is None or t_ovl is None else max(t_snr, t_ovl))
        rows["snr_design"].append(
            _run(calc, params, params.t_dwell, power).snr if params.t_dwell is not None else None)

    return Result(
        tool=TOOL_KEY,
        calc=CALC_KEY,
        params=params.to_dict(),
        scalars={"base": s.base, **{k: v for k, v in s.to_dict().items() if k != "base"}},
        tables={
            "map": {"axes": {"t_dwell": t.tolist(), "power": p.tolist()},
                    "grid": {"snr": snr.tolist(), "occ": occ.tolist(), "shot_clear": clear.tolist()}},
            "slices": {"t_dwell": {"values": t.tolist()}, **slices},
            "boundaries": {"rows": rows},
        },
        plots=PLOTS,
    )
