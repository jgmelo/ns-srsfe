"""Parallel R‖L‖C feedback tank (SPEC §4.1).

Both constructors return the same TankResult; everything downstream takes a TankResult
and does not care how it was built (SPEC §2, rule 2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

Q_MODES = ("settling", "bandwidth")


@dataclass(frozen=True)
class TankResult:
    """Tank parameters, SI. `f_res` is the tank's own resonance: equal to the input f_0
    (signal frequency) for tank_from_dwell, f₀_calc for tank_from_lc (SPEC §4.1)."""

    r_f: float  # Ω, |Z_f(f_res)|
    f_res: float  # Hz
    q: float
    l_f: float  # H
    c_f: float  # F
    tau_tank: float  # s, ring-down time constant Q/(π f_res)
    bw_3db: float  # Hz, f_res/Q
    b_eq: float  # Hz, noise-equivalent bandwidth (π/2)·bw_3db

    def z(self, f: ArrayLike) -> NDArray[np.complex128]:
        """Z_f at frequency/frequencies f (Hz)."""
        return z_f(f, self.r_f, self.f_res, self.q)

    def settles(self, n_tau: float, t_dwell: float) -> bool:
        """N_τ·τ_tank ≤ t_dwell, with float-rounding slack (SPEC §3.2)."""
        return settles(self.tau_tank, n_tau, t_dwell)


def _require_positive(**values: float) -> None:
    for name, v in values.items():
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
            raise ValueError(f"{name} must be a finite number > 0, got {v!r}")


def _build(r: float, f0: float, q: float, l: float, c: float) -> TankResult:
    bw = f0 / q
    return TankResult(
        r_f=r, f_res=f0, q=q, l_f=l, c_f=c,
        tau_tank=q / (math.pi * f0),
        bw_3db=bw,
        b_eq=math.pi / 2 * bw,
    )


def tank_from_dwell(
    r: float, f0: float, t_dwell: float, n_tau: float, mode: str = "settling"
) -> TankResult:
    """Size the tank so it fits the pixel dwell.

    settling:  Q = π·f₀·t_dwell / N_τ  (N_τ ring-down time constants fit in one dwell)
    bandwidth: Q = f₀·t_dwell          (BW₋₃dB = 1/t_dwell)
    L = R/(Q·ω₀), C = Q/(R·ω₀).
    """
    _require_positive(r=r, f0=f0, t_dwell=t_dwell, n_tau=n_tau)
    if mode == "settling":
        q = math.pi * f0 * t_dwell / n_tau
    elif mode == "bandwidth":
        q = f0 * t_dwell
    else:
        raise ValueError(f"mode must be one of {Q_MODES}, got {mode!r}")
    w0 = 2 * math.pi * f0
    return _build(r, f0, q, l=r / (q * w0), c=q / (r * w0))


def tank_from_lc(r: float, l: float, c: float) -> TankResult:
    """Analyze existing parts: f₀_calc = 1/(2π√(LC)), Q = R·√(C/L)."""
    _require_positive(r=r, l=l, c=c)
    f0 = 1 / (2 * math.pi * math.sqrt(l * c))
    return _build(r, f0, r * math.sqrt(c / l), l, c)


def z_f(f: ArrayLike, r: float, f0: float, q: float) -> NDArray[np.complex128]:
    """Z_f(f) = R / [1 + jQ(f/f₀ − f₀/f)]. Z_f(0) = 0 (L shorts DC). f must be ≥ 0.
    Returns a complex array with the shape of f (0-d for a scalar)."""
    f = np.asarray(f, dtype=float)
    if np.any(f < 0) or not np.all(np.isfinite(f)):
        raise ValueError("frequencies must be finite and ≥ 0")
    out = np.zeros(f.shape, dtype=np.complex128)
    nz = f > 0
    fn = f[nz]
    out[nz] = r / (1 + 1j * q * (fn / f0 - f0 / fn))
    return out


# Relative slack for float rounding only: τ_tank = 2RC exactly, so a tank sized for
# N_τ·τ_tank = t_dwell must count as settling (SPEC §3.2, §9.4).
SETTLE_RTOL = 1e-9


def settles(tau_tank: float, n_tau: float, t_dwell: float) -> bool:
    """N_τ·τ_tank ≤ t_dwell·(1 + SETTLE_RTOL). W07 fires when this is False."""
    return n_tau * tau_tank <= t_dwell * (1 + SETTLE_RTOL)
