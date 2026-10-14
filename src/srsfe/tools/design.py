"""Design from t_dwell (SPEC §6.1): size the tank from the dwell time, then spectrum,
noise, budget and lock-in. Each calc runs a set of stages; later stages reuse earlier ones.

The same pipeline serves the Buy tool (tools/buy.py, SPEC §6.4) through a Variant that
swaps the noise model and the per-stage input/output tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from srsfe.core import moku, noise, spectrum
from srsfe.core import warnings as w
from srsfe.core.budget import budget
from srsfe.core.params import Params
from srsfe.core.tank import tank_from_dwell
from srsfe.tools.base import POWERS, Calc, Group, Result, Tool, register, unique_ordered

TOOL_KEY = "d"

# Inputs and outputs per stage (SPEC §6.1).
REQ = {
    "sizing": ("r_f", "f_0", "t_dwell", "n_tau"),
    "spectrum": ("p_min", "p_max", "resp", "f_rep", "f_max"),
    "noise": ("p_min", "p_max", "resp", "c_d", "en_opamp", "nep", "temp", "m"),
    "budget": ("k_crest", "v_swing", "v_range"),
    "lockin": ("tau_lia", "n_lia"),
}
OPT = {
    "sizing": ("q_mode",),
    "spectrum": ("tau_p",),
    "noise": ("en_moku", "n_bits", "v_range"),
    "budget": (),
    "lockin": (),
}
OUT = {
    "sizing": ("q", "l_f", "c_f", "tau_tank", "bw_3db", "b_eq"),
    "spectrum": ("i_0", "q_p", "i_pk", "f_n", "i_n", "z_n", "att_n", "v_n", "v_n_sum",
                 "v_n_rss"),
    "noise": ("i_0", "i_sig", "v_sig", "i_sh", "i_r", "i_en", "i_nep", "i_elec", "i_tot",
              "v_dens", "v_rms", "snr", "shot_clear", "lsb", "v_q"),
    "budget": ("v_coh", "occ_swing", "occ_moku"),
    "lockin": ("enbw_lia", "v_rms_lia", "snr_lia"),
}
# Stage → the stages it builds on ("Sizing +", "Spectrum + Noise +", …).
DEPS = {
    "sizing": (),
    "spectrum": ("sizing",),
    "noise": ("sizing",),
    "budget": ("sizing", "spectrum", "noise"),
    "lockin": ("sizing", "noise"),
}
ORDER = ("sizing", "spectrum", "noise", "budget", "lockin")




@dataclass(frozen=True)
class Variant:
    """Per-tool tables for the shared pipeline."""

    tool_key: str
    req: dict[str, tuple[str, ...]]
    opt: dict[str, tuple[str, ...]]
    out: dict[str, tuple[str, ...]]
    detector_noise: bool  # True: shot + NEP only (bought detector); False: full DIY model


DIY = Variant(TOOL_KEY, REQ, OPT, OUT, detector_noise=False)


def _stages(top: tuple[str, ...]) -> tuple[str, ...]:
    need = set(top)
    for s in top:
        need |= set(DEPS[s])
    return tuple(s for s in ORDER if s in need)


def _compute(
    v: Variant, p: Params, stages: tuple[str, ...], calc_key: str, plots: tuple[str, ...]
) -> Result:
    scalars: dict[str, Any] = {}
    per_power: dict[str, dict[str, Any]] = {}
    tables: dict[str, dict[str, dict[str, list[Any]]]] = {}
    warns: list[w.DesignWarning | None] = []

    def put(name: str, power: str, value: Any) -> None:
        per_power.setdefault(name, {})[power] = value

    assert p.r_f is not None and p.f_0 is not None and p.t_dwell is not None and p.n_tau is not None
    tank = tank_from_dwell(p.r_f, p.f_0, p.t_dwell, p.n_tau, p.q_mode or "settling")
    for name in v.out["sizing"]:
        scalars[name] = getattr(tank, name)

    i_0: dict[str, float] = {}
    if "spectrum" in stages or "noise" in stages:
        for power in POWERS:
            i_0[power] = spectrum.photocurrent(getattr(p, power), p.resp)  # type: ignore[arg-type]
            put("i_0", power, i_0[power])

    v_n_sum: dict[str, float] = {}
    if "spectrum" in stages:
        assert p.f_rep is not None and p.f_max is not None and p.f_0 is not None
        table: dict[str, dict[str, list[Any]]] = {}
        for power in POWERS:
            q_p = spectrum.pulse_charge(i_0[power], p.f_rep)
            put("q_p", power, q_p)
            if p.tau_p is not None:
                put("i_pk", power, spectrum.peak_current(q_p, p.tau_p))
            h = spectrum.harmonics(i_0[power], p.f_rep, p.f_max, tank)
            table[power] = {"n": list(h.n), "f_n": list(h.f_n), "i_n": list(h.i_n),
                            "z_n": list(h.z_n), "att_n": list(h.att_n), "v_n": list(h.v_n)}
            put("v_n_sum", power, h.v_n_sum)
            put("v_n_rss", power, h.v_n_rss)
            v_n_sum[power] = h.v_n_sum
        tables["harmonics"] = table
        if p.tau_p is not None:
            warns.append(w.check_w08(p.tau_p, p.f_max))
        warns.append(w.check_w09(p.f_0, p.f_rep))

    v_sig: dict[str, float] = {}
    v_dens: dict[str, float] = {}
    v_rms: dict[str, float] = {}
    if "noise" in stages:
        for power in POWERS:
            s = spectrum.signal(i_0[power], p.m, p.r_f)  # type: ignore[arg-type]
            if v.detector_noise:
                d = noise.detector_densities(i_0[power], p.r_f, p.nep, p.resp)  # type: ignore[arg-type]
            else:
                d = noise.densities(i_0[power], p.r_f, p.f_0, p.c_d,  # type: ignore[arg-type]
                                    p.en_opamp, p.nep, p.resp, p.temp)  # type: ignore[arg-type]
            vr = noise.v_rms(d.v_dens, tank.b_eq)
            v_sig[power], v_dens[power], v_rms[power] = s.v_sig, d.v_dens, vr
            put("i_sig", power, s.i_sig)
            put("v_sig", power, s.v_sig)
            put("i_sh", power, d.i_sh)
            put("i_tot", power, d.i_tot)
            put("v_dens", power, d.v_dens)
            put("v_rms", power, vr)
            put("snr", power, noise.snr_db(s.v_sig, vr))
            put("shot_clear", power, noise.shot_clear_db(d.i_sh, d.i_elec))
            scalars.update({k: getattr(d, k) for k in ("i_r", "i_en", "i_nep", "i_elec")
                            if k in v.out["noise"]})
            if p.en_moku is not None:
                warns.append(w.check_w05(d.v_dens, p.en_moku, power))  # type: ignore[arg-type]
        if p.n_bits is not None and p.v_range is not None:
            scalars["lsb"] = moku.lsb(p.v_range, p.n_bits)
            scalars["v_q"] = moku.quantization_noise(scalars["lsb"])

    if "budget" in stages:
        for power in POWERS:
            b = budget(v_n_sum[power], v_sig[power], p.k_crest, v_rms[power],  # type: ignore[arg-type]
                       p.v_swing, p.v_range)  # type: ignore[arg-type]
            put("v_coh", power, b.v_coh)
            put("occ_swing", power, b.occ_swing)
            put("occ_moku", power, b.occ_moku)
            warns.append(w.check_w03(b.occ_swing, power))  # type: ignore[arg-type]
            warns.append(w.check_w04(b.occ_moku, power))  # type: ignore[arg-type]

    if "lockin" in stages:
        assert p.tau_lia is not None and p.n_lia is not None
        enbw = noise.enbw_lia(p.tau_lia, p.n_lia)
        scalars["enbw_lia"] = enbw
        for power in POWERS:
            vr_lia = noise.v_rms(v_dens[power], enbw)
            put("v_rms_lia", power, vr_lia)
            put("snr_lia", power, noise.snr_db(v_sig[power], vr_lia))
        warns.append(w.check_w01(p.tau_lia, p.t_dwell))
        warns.append(w.check_w02(enbw, tank.b_eq))

    fired = sorted((x for x in warns if x is not None),
                   key=lambda x: (x.id, POWERS.index(x.power) if x.power else -1))
    return Result(tool=v.tool_key, calc=calc_key, params=p.to_dict(), scalars=scalars,
                  per_power=per_power, tables=tables, warnings=tuple(fired), plots=plots)


def _calc(v: Variant, name: str, key: str, top: tuple[str, ...], plots: tuple[str, ...]) -> Calc:
    stages = _stages(top)
    required = unique_ordered(*(v.req[s] for s in stages))
    optional = tuple(x for x in unique_ordered(*(v.opt[s] for s in stages)) if x not in required)
    outputs = unique_ordered(*(v.out[s] for s in stages))
    return Calc(name, key, required, optional, outputs, plots,
                compute=lambda p: _compute(v, p, stages, key, plots))


def make_calcs(v: Variant) -> tuple[Calc, ...]:
    """Calcs 1–5 and 0 (SPEC §6.1 table) for a variant."""
    return (
        _calc(v, "Sizing", "1", ("sizing",), ("bode",)),
        _calc(v, "Spectrum", "2", ("spectrum",), ("spectrum",)),
        _calc(v, "Budget", "3", ("budget",), ("budget",)),
        _calc(v, "Noise", "4", ("noise",), ("noise",)),
        _calc(v, "Lock-in", "5", ("lockin",), ("noise",)),
        _calc(v, "All", "0", ORDER, ("bode", "spectrum", "budget", "noise")),
    )


CALCS = make_calcs(DIY)

GROUPS = (
    Group("Tank", "t", ("r_f", "f_0", "t_dwell", "n_tau", "q_mode")),
    Group("Light", "l", ("p_min", "p_max", "resp", "f_rep", "tau_p", "m")),
    Group("Noise", "n", ("c_d", "en_opamp", "nep", "temp", "k_crest")),
    Group("Lock-in", "i", ("tau_lia", "n_lia")),
    Group("Opamp/Moku", "m", ("v_swing", "en_moku", "n_bits", "v_range")),
    Group("Spectrum", "f", ("f_max",)),
)

TOOL = register(Tool(
    name="Design from t_dwell",
    key=TOOL_KEY,
    description="Size the resonant tank from the pixel dwell time, then compute the "
                "harmonic spectrum, noise, output budget and lock-in SNR at P_min and P_max.",
    calcs=CALCS,
    groups=GROUPS,
))
