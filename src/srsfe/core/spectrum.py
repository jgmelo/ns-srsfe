"""Photocurrent, pulse-train harmonics and SRS signal (SPEC §4.2, §4.3).

All functions take one optical power at a time; tools evaluate them at both P_min and
P_max. Pulses are treated as impulses: the current spectrum is I₀ at DC (shorted by the
tank's L, no output) plus lines of amplitude 2·I₀ at every n·f_rep.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from srsfe.core.tank import TankResult

# Slack for ⌊f_max/f_rep⌋ so that e.g. f_max = 3·f_rep is not lost to float rounding.
_FLOOR_RTOL = 1e-9


@dataclass(frozen=True)
class Harmonics:
    """Harmonics table n = 1 … ⌊f_max/f_rep⌋ for one optical power. Tuples, one entry per n."""

    n: tuple[int, ...]
    f_n: tuple[float, ...]  # Hz, n·f_rep
    i_n: tuple[float, ...]  # A, line amplitude 2·I₀
    z_n: tuple[float, ...]  # Ω, |Z_f(f_n)|
    att_n: tuple[float, ...]  # dB, 20·log₁₀(|Z_f(f_n)|/R)
    v_n: tuple[float, ...]  # V, output amplitude 2·I₀·|Z_f(f_n)|
    v_n_sum: float  # V, coherent sum ΣV_n
    v_n_rss: float  # V, √(ΣV_n²)


@dataclass(frozen=True)
class Signal:
    i_sig: float  # A, m·I₀
    v_sig: float  # V, amplitude I_sig·R


def _require(name: str, value: float, allow_zero: bool = False) -> None:
    ok = isinstance(value, (int, float)) and math.isfinite(value)
    ok = ok and (value >= 0 if allow_zero else value > 0)
    if not ok:
        raise ValueError(f"{name} must be a finite number {'≥' if allow_zero else '>'} 0, "
                         f"got {value!r}")


def photocurrent(p: float, resp: float) -> float:
    """I₀ = P·ℜ (average photocurrent, A)."""
    _require("p", p)
    _require("resp", resp)
    return p * resp


def pulse_charge(i_0: float, f_rep: float) -> float:
    """q_p = I₀/f_rep (charge per pulse, C)."""
    _require("i_0", i_0, allow_zero=True)
    _require("f_rep", f_rep)
    return i_0 / f_rep


def peak_current(q_p: float, tau_p: float) -> float:
    """I_pk = q_p/τ_p (peak pulse current, A)."""
    _require("q_p", q_p, allow_zero=True)
    _require("tau_p", tau_p)
    return q_p / tau_p


def n_harmonics(f_rep: float, f_max: float) -> int:
    """⌊f_max/f_rep⌋, tolerant of float rounding; 0 if f_max < f_rep."""
    _require("f_rep", f_rep)
    _require("f_max", f_max)
    return math.floor(f_max / f_rep * (1 + _FLOOR_RTOL))


def harmonics(i_0: float, f_rep: float, f_max: float, tank: TankResult) -> Harmonics:
    """Harmonics table for one photocurrent I₀ through the given tank."""
    _require("i_0", i_0, allow_zero=True)
    n = np.arange(1, n_harmonics(f_rep, f_max) + 1)
    f_n = n * f_rep
    z_n = np.abs(tank.z(f_n))
    v_n = 2 * i_0 * z_n
    return Harmonics(
        n=tuple(int(k) for k in n),
        f_n=tuple(f_n.tolist()),
        i_n=(2 * i_0,) * len(n),
        z_n=tuple(z_n.tolist()),
        att_n=tuple((20 * np.log10(z_n / tank.r_f)).tolist()),
        v_n=tuple(v_n.tolist()),
        v_n_sum=float(np.sum(v_n)),
        v_n_rss=float(np.sqrt(np.sum(v_n**2))),
    )


def signal(i_0: float, m: float, r: float) -> Signal:
    """I_sig = m·I₀ at f₀; V_sig = I_sig·R (amplitude, R = gain at f₀)."""
    _require("i_0", i_0, allow_zero=True)
    _require("m", m, allow_zero=True)
    _require("r", r)
    i_sig = m * i_0
    return Signal(i_sig=i_sig, v_sig=i_sig * r)
