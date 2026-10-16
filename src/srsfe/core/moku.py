"""Moku ADC quantization: LSB, rms noise and its density (SPEC §4.7)."""

from __future__ import annotations

import math


def lsb(v_range: float, n_bits: int) -> float:
    """LSB = V_range / 2^N_bits (V; V_range is peak-to-peak)."""
    if not (isinstance(v_range, (int, float)) and math.isfinite(v_range) and v_range > 0):
        raise ValueError(f"v_range must be a finite number > 0, got {v_range!r}")
    if isinstance(n_bits, bool) or not isinstance(n_bits, int) or n_bits < 1:
        raise ValueError(f"n_bits must be an integer ≥ 1, got {n_bits!r}")
    return v_range / 2**n_bits


def quantization_noise(lsb_v: float) -> float:
    """V_q = LSB/√12: rms of a uniform error over one LSB."""
    if not (isinstance(lsb_v, (int, float)) and math.isfinite(lsb_v) and lsb_v > 0):
        raise ValueError(f"lsb must be a finite number > 0, got {lsb_v!r}")
    return lsb_v / math.sqrt(12)


def quantization_density(v_q: float, f_s: float) -> float:
    """e_q = V_q / √(f_s/2): V_q spread evenly over the Nyquist band 0…f_s/2 (V/√Hz).
    Assumes a white quantization error (signal plus noise spanning many LSBs)."""
    for name, value in (("v_q", v_q), ("f_s", f_s)):
        if not (isinstance(value, (int, float)) and math.isfinite(value) and value > 0):
            raise ValueError(f"{name} must be a finite number > 0, got {value!r}")
    return v_q / math.sqrt(f_s / 2)
