"""Output occupancy budget (SPEC §4.6)."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Budget:
    """Worst-case coherent output peak and how much of the opamp / Moku range it uses."""

    v_coh: float  # V, ΣV_n + V_sig + k_crest·V_rms
    occ_swing: float  # %, of the opamp 0-to-peak swing
    occ_moku: float  # %, of the Moku peak-to-peak range


def _require(name: str, value: float, allow_zero: bool = False) -> None:
    ok = isinstance(value, (int, float)) and math.isfinite(value)
    ok = ok and (value >= 0 if allow_zero else value > 0)
    if not ok:
        raise ValueError(f"{name} must be a finite number {'≥' if allow_zero else '>'} 0, "
                         f"got {value!r}")


def budget(
    v_n_sum: float, v_sig: float, k_crest: float, v_rms: float, v_swing: float, v_range: float
) -> Budget:
    """V_coh = ΣV_n + V_sig + k_crest·V_rms; occ_swing = 100·V_coh/V_swing;
    occ_moku = 100·2·V_coh/V_range (V_coh is 0-to-peak, V_range is peak-to-peak)."""
    for name, v in (("v_n_sum", v_n_sum), ("v_sig", v_sig), ("v_rms", v_rms)):
        _require(name, v, allow_zero=True)
    for name, v in (("k_crest", k_crest), ("v_swing", v_swing), ("v_range", v_range)):
        _require(name, v)
    v_coh = v_n_sum + v_sig + k_crest * v_rms
    return Budget(v_coh=v_coh, occ_swing=100 * v_coh / v_swing, occ_moku=100 * 2 * v_coh / v_range)
