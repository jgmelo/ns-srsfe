"""Analyze existing tank (SPEC §6.2): resonance, Q and settling of given L, C, R."""

from __future__ import annotations

from typing import Any

from srsfe.core import warnings as w
from srsfe.core.params import Params
from srsfe.core.tank import tank_from_lc
from srsfe.tools.base import Calc, Group, Result, Tool, register

TOOL_KEY = "a"
CALC_KEY = "1"
PLOTS = ("bode",)


def _compute(p: Params) -> Result:
    assert p.r_f is not None and p.l_f is not None and p.c_f is not None
    tank = tank_from_lc(p.r_f, p.l_f, p.c_f)
    scalars: dict[str, Any] = {
        "f0_calc": tank.f_res,
        "q": tank.q,
        "tau_tank": tank.tau_tank,
        "bw_3db": tank.bw_3db,
        "b_eq": tank.b_eq,
    }
    warns: list[w.DesignWarning | None] = []
    if p.f_0 is not None:
        warns.append(w.check_w06(tank.f_res, p.f_0))
    if p.t_dwell is not None and p.n_tau is not None:
        scalars["settles"] = tank.settles(p.n_tau, p.t_dwell)
        warns.append(w.check_w07(scalars["settles"]))
    return Result(tool=TOOL_KEY, calc=CALC_KEY, params=p.to_dict(), scalars=scalars,
                  warnings=tuple(x for x in warns if x is not None), plots=PLOTS)


CALC = Calc(
    name="Analyze",
    key=CALC_KEY,
    required=("l_f", "c_f", "r_f"),
    optional=("f_0", "t_dwell", "n_tau"),
    outputs=("f0_calc", "q", "tau_tank", "bw_3db", "b_eq", "settles"),
    plots=PLOTS,
    compute=_compute,
)

TOOL = register(Tool(
    name="Analyze existing tank",
    key=TOOL_KEY,
    description="Resonance, Q, ring-down and settling of a tank built from given L, C and R; "
                "checks it against the signal frequency and the dwell time.",
    calcs=(CALC,),
    groups=(Group("Tank", "t", ("l_f", "c_f", "r_f", "f_0", "t_dwell", "n_tau")),),
))
