"""Plot figures (SPEC §8.2): pure functions Result → matplotlib Figure.

Figures are built on matplotlib.figure.Figure directly (no pyplot, no GUI, never
plt.show()); plots/runner.py decides whether to show or save them.

Colors follow one rule per job: P_min / P_max are the same two categorical hues in every
figure; Budget stacks use categorical slots 1–3 in fixed order; text and reference lines
stay in neutral ink. Different units never share an axis (Bode and Spectrum use two
stacked panels instead of a second y-scale).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import EngFormatter

from srsfe.core.tank import z_f
from srsfe.core.units import format_eng
from srsfe.tools.base import Result

# Validated reference palette (light surface), categorical slots in fixed order.
SLOTS = ("#2a78d6", "#eb6834", "#1baf7a")
POWER_COLOR = {"p_min": SLOTS[0], "p_max": SLOTS[1]}
POWER_LABEL = {"p_min": "P_min", "p_max": "P_max"}
POWER_MARKER = {"p_min": "o", "p_max": "s"}
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
F_MIN_BODE = 1e6  # Hz, SPEC §8.2

POWERS = ("p_min", "p_max")


def _figure(rows: int = 1, height: float = 4.2) -> tuple[Figure, list[Axes]]:
    fig = Figure(figsize=(8, height), facecolor=SURFACE, layout="constrained")
    axes = fig.subplots(rows, 1, sharex=rows > 1, squeeze=False)[:, 0]
    for ax in axes:
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(INK_2)
        ax.tick_params(colors=INK_2, labelcolor=INK)
    return fig, list(axes)


def _title(fig: Figure, text: str, result: Result) -> None:
    fig.suptitle(f"{text}   ({result.tool}/{result.calc})", color=INK, fontsize=12)


def _need(result: Result, plot: str) -> None:
    if plot not in result.plots:
        raise ValueError(f"result of {result.tool}/{result.calc} has no {plot!r} plot")


def _f_res(result: Result) -> float:
    return result.scalars.get("f0_calc", result.params["f_0"])


# -- Bode ------------------------------------------------------------------------------


def bode(result: Result) -> Figure:
    """|Z_f| (dB re 1 Ω) and phase vs log f, 1 MHz … f_max; f₀ and harmonics marked."""
    _need(result, "bode")
    r, q, f_res = result.params["r_f"], result.scalars["q"], _f_res(result)
    f_max = result.params.get("f_max") or 10 * f_res
    f = np.geomspace(min(F_MIN_BODE, f_res / 10), max(f_max, 2 * f_res), 2000)
    z = z_f(f, r, f_res, q)

    fig, (ax_m, ax_p) = _figure(2, 5.6)
    ax_m.semilogx(f, 20 * np.log10(np.abs(z)), color=SLOTS[0], linewidth=2)
    ax_p.semilogx(f, np.degrees(np.angle(z)), color=SLOTS[0], linewidth=2)
    ax_m.set_ylabel("|Z_f|  [dB re 1 Ω]", color=INK)
    ax_p.set_ylabel("phase  [°]", color=INK)
    ax_p.set_yticks([-90, -45, 0, 45, 90])
    ax_p.set_xlabel("frequency", color=INK)
    ax_p.xaxis.set_major_formatter(EngFormatter(unit="Hz"))

    f_n = result.tables.get("harmonics", {}).get("p_min", {}).get("f_n", [])
    for ax in (ax_m, ax_p):
        ax.axvline(f_res, color=INK_2, linewidth=1.2)
        for fn in f_n:
            ax.axvline(fn, color=INK_2, linewidth=0.8, linestyle=":")
    ax_m.annotate(f"f_res = {format_eng(f_res, 'Hz')}", (f_res, 1), xycoords=("data", "axes fraction"),
                  xytext=(4, -12), textcoords="offset points", color=INK, fontsize=9)
    if f_n:
        ax_m.annotate("harmonics f_n (dotted)", (f_n[0], 0), xycoords=("data", "axes fraction"),
                      xytext=(4, 6), textcoords="offset points", color=INK_2, fontsize=9,
                      bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1})
    _title(fig, f"Bode: R = {format_eng(r, 'Ω')}, Q = {q:.4g}", result)
    return fig


# -- Spectrum --------------------------------------------------------------------------


def spectrum(result: Result) -> Figure:
    """Stems of I_n (top) and V_n (bottom) vs f at both powers; signal line at f₀."""
    _need(result, "spectrum")
    table = result.tables["harmonics"]
    f_0 = result.params["f_0"]
    fig, (ax_i, ax_v) = _figure(2, 6.0)
    for k, power in enumerate(POWERS):
        cols = table[power]
        f = np.array(cols["f_n"]) * (1 + (k - 0.5) * 0.012)  # nudge the two powers apart
        color, marker = POWER_COLOR[power], POWER_MARKER[power]
        for ax, key in ((ax_i, "i_n"), (ax_v, "v_n")):
            ax.vlines(f, 0, cols[key], color=color, linewidth=2)
            ax.plot(f, cols[key], marker, color=color, markersize=7,
                    markeredgecolor=SURFACE, markeredgewidth=1.5,
                    label=POWER_LABEL[power] if ax is ax_i else None)
        sig = {"i_n": "i_sig", "v_n": "v_sig"}
        for ax, key in ((ax_i, "i_n"), (ax_v, "v_n")):
            name = sig[key]
            if name in result.per_power:
                fs = f_0 * (1 + (k - 0.5) * 0.024)
                ax.vlines(fs, 0, result.per_power[name][power], color=color, linewidth=2,
                          linestyle="--")
                ax.plot(fs, result.per_power[name][power], "D", color=color, markersize=7,
                        markeredgecolor=SURFACE, markeredgewidth=1.5)
    for ax, unit, label in ((ax_i, "A", "line current"), (ax_v, "V", "output amplitude")):
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(EngFormatter(unit=unit))
        ax.set_ylabel(label, color=INK)
    if "i_sig" in result.per_power:
        ax_i.plot([], [], "D--", color=INK_2, markersize=6, label=f"signal m·I₀ at f₀")
    ax_v.set_xlabel("frequency", color=INK)
    ax_v.xaxis.set_major_formatter(EngFormatter(unit="Hz"))
    fig.legend(loc="outside lower center", ncols=3, frameon=False, labelcolor=INK)
    _title(fig, "Spectrum: harmonics 2·I₀ at n·f_rep", result)
    return fig


# -- Budget ----------------------------------------------------------------------------


def budget(result: Result) -> Figure:
    """Stacked ΣV_n, V_sig, k_crest·V_rms at P_min and P_max; V_swing and V_range/2 lines."""
    _need(result, "budget")
    k = result.params["k_crest"]
    parts = (
        ("ΣV_n", [result.per_power["v_n_sum"][p] for p in POWERS]),
        ("V_sig", [result.per_power["v_sig"][p] for p in POWERS]),
        (f"{k:g}·V_rms", [k * result.per_power["v_rms"][p] for p in POWERS]),
    )
    fig, (ax,) = _figure(1, 4.6)
    x = np.arange(len(POWERS))
    bottom = np.zeros(len(POWERS))
    for (label, values), color in zip(parts, SLOTS):
        ax.bar(x, values, 0.5, bottom=bottom, color=color, edgecolor=SURFACE, linewidth=2,
               label=f"{label}  ({', '.join(format_eng(v, 'V', 4) for v in values)})")
        bottom += np.array(values)
    for xi, total in zip(x, bottom):
        ax.annotate(f"V_coh = {format_eng(total, 'V', 4)}", (xi, total), xytext=(0, 4),
                    textcoords="offset points", ha="center", color=INK, fontsize=9)
    refs = (("V_swing", result.params["v_swing"], "--"),
            ("V_range/2", result.params["v_range"] / 2, ":"))
    for label, value, style in refs:
        ax.axhline(value, color=INK_2, linewidth=1.2, linestyle=style)
        ax.annotate(f"{label} = {format_eng(value, 'V', 4)}", (0.5, value), xytext=(0, 3),
                    textcoords="offset points", ha="center", color=INK_2, fontsize=9)
    ax.set_xticks(x, [POWER_LABEL[p] for p in POWERS])
    ax.yaxis.set_major_formatter(EngFormatter(unit="V"))
    ax.set_ylabel("output, 0-to-peak", color=INK)
    ax.set_ylim(0, max(bottom.max(), *(v for _, v, _ in refs)) * 1.15)
    ax.legend(frameon=False, labelcolor=INK, loc="upper left")
    _title(fig, "Output budget", result)
    return fig


# -- Noise -----------------------------------------------------------------------------


def noise(result: Result) -> Figure:
    """Input-referred noise densities i_sh, i_R, i_en, i_NEP at P_min and P_max
    (only the sources the result models: Buy has i_sh and i_NEP)."""
    _need(result, "noise")
    names = tuple((n, label) for n, label in
                  (("i_sh", "i_sh"), ("i_r", "i_R"), ("i_en", "i_en"), ("i_nep", "i_NEP"))
                  if n in result.per_power or n in result.scalars)  # Buy has no i_R, i_en
    fig, (ax,) = _figure(1, 4.6)
    x = np.arange(len(names))
    width = 0.36
    for k, power in enumerate(POWERS):
        values = [result.per_power[n][power] if n in result.per_power else result.scalars[n]
                  for n, _ in names]
        xs = x + (k - 0.5) * (width + 0.04)
        ax.bar(xs, values, width, color=POWER_COLOR[power], edgecolor=SURFACE, linewidth=2,
               label=POWER_LABEL[power])
        for xi, v in zip(xs, values):
            ax.annotate(format_eng(v, "", 3), (xi, v), xytext=(0, 3), textcoords="offset points",
                        ha="center", color=INK, fontsize=8)
    ax.set_yscale("log")
    ax.set_xticks(x, [label for _, label in names])
    ax.yaxis.set_major_formatter(EngFormatter(unit="A/√Hz"))
    ax.set_ylabel("input-referred density", color=INK)
    ax.legend(frameon=False, labelcolor=INK)
    _title(fig, "Noise contributions", result)
    return fig


FIGURES: dict[str, Callable[[Result], Figure]] = {
    "bode": bode, "spectrum": spectrum, "budget": budget, "noise": noise,
}


def make(result: Result, plot: str) -> Figure:
    """Build the named plot; KeyError for an unknown name, ValueError if not available."""
    return FIGURES[plot](result)
