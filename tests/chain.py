"""Golden design chain for tests that need values from several core modules."""

from dataclasses import dataclass
from typing import Any

from srsfe.core.budget import Budget, budget
from srsfe.core.noise import NoiseDensities, densities, v_rms
from srsfe.core.spectrum import Harmonics, Signal, harmonics, photocurrent, signal
from srsfe.core.tank import TankResult, tank_from_dwell


@dataclass(frozen=True)
class PowerChain:
    harmonics: Harmonics
    signal: Signal
    noise: NoiseDensities
    v_rms: float
    budget: Budget


def tank(g: dict[str, Any]) -> TankResult:
    return tank_from_dwell(g["r_f"], g["f_0"], g["t_dwell"], g["n_tau"], g["q_mode"])


def at_power(g: dict[str, Any], power: str) -> PowerChain:
    t = tank(g)
    i_0 = photocurrent(g[power], g["resp"])
    h = harmonics(i_0, g["f_rep"], g["f_max"], t)
    s = signal(i_0, g["m"], g["r_f"])
    d = densities(i_0, g["r_f"], g["f_0"], g["c_d"], g["en_opamp"], g["nep"], g["resp"], g["temp"])
    vr = v_rms(d.v_dens, t.b_eq)
    b = budget(h.v_n_sum, s.v_sig, g["k_crest"], vr, g["v_swing"], g["v_range"])
    return PowerChain(h, s, d, vr, b)
