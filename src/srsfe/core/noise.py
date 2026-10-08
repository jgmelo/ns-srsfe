"""Noise densities, rms noise, SNR and lock-in bandwidth (SPEC §4.4–§4.6).

Densities are input-referred current noise in A/√Hz, evaluated at the signal frequency
f₀ for one optical power; tools evaluate them at both P_min and P_max.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from srsfe.core.constants import E_CHARGE, K_B

# ENBW of an n-th order lock-in low-pass, as a multiple of 1/τ (SPEC §4.5).
ENBW_FACTOR: dict[int, float] = {1: 1 / 4, 2: 1 / 8, 3: 3 / 32, 4: 5 / 64}


@dataclass(frozen=True)
class NoiseDensities:
    """Input-referred noise densities (A/√Hz) and the output density v_dens (V/√Hz)."""

    i_sh: float
    i_r: float
    i_en: float
    i_nep: float
    i_elec: float  # √(i_r² + i_en² + i_nep²): everything but shot noise
    i_tot: float  # √(i_sh² + i_elec²)
    v_dens: float  # R·i_tot


def _require(name: str, value: float, allow_zero: bool = False) -> None:
    ok = isinstance(value, (int, float)) and math.isfinite(value)
    ok = ok and (value >= 0 if allow_zero else value > 0)
    if not ok:
        raise ValueError(f"{name} must be a finite number {'≥' if allow_zero else '>'} 0, "
                         f"got {value!r}")


def shot_density(i_0: float) -> float:
    """i_sh = √(2·e·I₀)."""
    _require("i_0", i_0, allow_zero=True)
    return math.sqrt(2 * E_CHARGE * i_0)


def johnson_density(r: float, temp: float) -> float:
    """i_R = √(4·k_B·Temp/R)."""
    _require("r", r)
    _require("temp", temp)
    return math.sqrt(4 * K_B * temp / r)


def opamp_density(en_opamp: float, r: float, f0: float, c_d: float) -> float:
    """i_en = e_n·√(1/R² + (ω₀·C_d)²): opamp voltage noise through R and the PD capacitance."""
    _require("en_opamp", en_opamp)
    _require("r", r)
    _require("f0", f0)
    _require("c_d", c_d, allow_zero=True)
    w0 = 2 * math.pi * f0
    return en_opamp * math.sqrt(1 / r**2 + (w0 * c_d) ** 2)


def nep_density(nep: float, resp: float) -> float:
    """i_NEP = NEP·ℜ."""
    _require("nep", nep)
    _require("resp", resp)
    return nep * resp


def densities(
    i_0: float, r: float, f0: float, c_d: float, en_opamp: float, nep: float, resp: float,
    temp: float,
) -> NoiseDensities:
    """All noise densities for one photocurrent I₀."""
    i_sh = shot_density(i_0)
    i_r = johnson_density(r, temp)
    i_en = opamp_density(en_opamp, r, f0, c_d)
    i_nep = nep_density(nep, resp)
    i_elec = math.sqrt(i_r**2 + i_en**2 + i_nep**2)
    i_tot = math.sqrt(i_sh**2 + i_elec**2)
    return NoiseDensities(i_sh, i_r, i_en, i_nep, i_elec, i_tot, v_dens=r * i_tot)


def v_rms(v_dens: float, bandwidth: float) -> float:
    """Output rms noise v_dens·√B (B = B_eq for the tank, ENBW for the lock-in)."""
    _require("v_dens", v_dens, allow_zero=True)
    _require("bandwidth", bandwidth)
    return v_dens * math.sqrt(bandwidth)


def enbw_lia(tau_lia: float, n_lia: int) -> float:
    """Lock-in noise-equivalent bandwidth for filter order 1–4 (SPEC §4.5)."""
    _require("tau_lia", tau_lia)
    if isinstance(n_lia, bool) or n_lia not in ENBW_FACTOR:
        raise ValueError(f"n_lia must be one of {sorted(ENBW_FACTOR)}, got {n_lia!r}")
    return ENBW_FACTOR[n_lia] / tau_lia


def _db20(ratio: float) -> float:
    return -math.inf if ratio == 0 else 20 * math.log10(ratio)


def snr_db(v_sig: float, v_rms_noise: float) -> float:
    """SNR = 20·log₁₀(V_sig / (√2·V_rms)); V_sig is an amplitude. −inf when V_sig = 0."""
    _require("v_sig", v_sig, allow_zero=True)
    _require("v_rms_noise", v_rms_noise)
    return _db20(v_sig / (math.sqrt(2) * v_rms_noise))


def shot_clear_db(i_sh: float, i_elec: float) -> float:
    """shot_clear = 20·log₁₀(i_sh / i_elec): how far shot noise sits above electronic noise."""
    _require("i_sh", i_sh, allow_zero=True)
    _require("i_elec", i_elec)
    return _db20(i_sh / i_elec)
