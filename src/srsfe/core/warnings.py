"""Design warnings W01–W09 (SPEC §5).

One check per warning, each taking explicit values and returning a Warning or None.
Per-power checks (W03, W04, W05) take the power label they were evaluated at.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["warn", "info"]
Power = Literal["p_min", "p_max"]


@dataclass(frozen=True)
class WarningSpec:
    message: str
    severity: Severity
    fields: tuple[str, ...]  # inputs/outputs involved; the UI puts ⚠ next to them


# SPEC §5 table.
SPECS: dict[str, WarningSpec] = {
    "W01": WarningSpec("Lock-in smears adjacent pixels", "warn", ("tau_lia", "t_dwell")),
    "W02": WarningSpec("Tank, not lock-in, limits noise bandwidth", "info", ("enbw_lia", "b_eq")),
    "W03": WarningSpec("Output exceeds opamp swing", "warn", ("v_coh", "occ_swing", "v_swing")),
    "W04": WarningSpec("Output exceeds Moku input range", "warn", ("v_coh", "occ_moku", "v_range")),
    "W05": WarningSpec("Moku noise not negligible vs TIA output noise", "warn",
                       ("v_dens", "en_moku")),
    "W06": WarningSpec("Tank resonance off signal frequency", "warn", ("f0_calc", "f_0")),
    "W07": WarningSpec("Tank does not settle within dwell", "warn",
                       ("settles", "tau_tank", "n_tau", "t_dwell")),
    "W08": WarningSpec("Impulse approximation questionable", "info", ("tau_p", "f_max")),
    "W09": WarningSpec("Signal frequency is not f_rep/2", "warn", ("f_0", "f_rep")),
}

# Relative frequency mismatch above which W06 / W09 fire.
FREQ_RTOL = 0.01


@dataclass(frozen=True)
class Warning:  # noqa: A001 — name fixed by SPEC §2/§5
    id: str
    message: str
    severity: Severity
    power: Power | None
    fields: tuple[str, ...]


def make(wid: str, power: Power | None = None) -> Warning:
    s = SPECS[wid]
    return Warning(wid, s.message, s.severity, power, s.fields)


def _if(cond: bool, wid: str, power: Power | None = None) -> Warning | None:
    return make(wid, power) if cond else None


def check_w01(tau_lia: float, t_dwell: float) -> Warning | None:
    """τ_LIA > t_dwell."""
    return _if(tau_lia > t_dwell, "W01")


def check_w02(enbw_lia: float, b_eq: float) -> Warning | None:
    """ENBW > B_eq/5."""
    return _if(enbw_lia > b_eq / 5, "W02")


def check_w03(occ_swing: float, power: Power) -> Warning | None:
    """occ_swing > 100 %."""
    return _if(occ_swing > 100, "W03", power)


def check_w04(occ_moku: float, power: Power) -> Warning | None:
    """occ_moku > 100 %."""
    return _if(occ_moku > 100, "W04", power)


def check_w05(v_dens: float, en_moku: float, power: Power) -> Warning | None:
    """v_dens < 3·e_n,Moku."""
    return _if(v_dens < 3 * en_moku, "W05", power)


def check_w06(f0_calc: float, f_0: float) -> Warning | None:
    """|f₀_calc − f_0|/f_0 > 0.01."""
    return _if(abs(f0_calc - f_0) / f_0 > FREQ_RTOL, "W06")


def check_w07(settles: bool) -> Warning | None:
    """Not settles (N_τ·τ_tank > t_dwell, with rounding slack; see tank.settles)."""
    return _if(not settles, "W07")


def check_w08(tau_p: float, f_max: float) -> Warning | None:
    """τ_p > 1/(10·f_max)."""
    return _if(tau_p > 1 / (10 * f_max), "W08")


def check_w09(f_0: float, f_rep: float) -> Warning | None:
    """|f_0 − f_rep/2|/f_0 > 0.01."""
    return _if(abs(f_0 - f_rep / 2) / f_0 > FREQ_RTOL, "W09")
