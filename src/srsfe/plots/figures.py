"""Plot figures (SPEC §8.2): pure functions Result → matplotlib Figure.

Figures are built on matplotlib.figure.Figure directly (no pyplot, no GUI, never
plt.show()); plots/runner.py decides whether to show or save them.

Colors follow one rule per job: P_min / P_max are the same two categorical hues in every
figure; Budget stacks use categorical slots 1–3 in fixed order; text and reference lines
stay in neutral ink; the Map uses one sequential blue ramp for SNR magnitude. Different
units never share an axis (Bode, Spectrum and Map use stacked panels instead of a second
y-scale).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from matplotlib.artist import Artist
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


# -- Map (design-space map, SPEC §6.5) ---------------------------------------------------

# Sequential blue ramp (one hue, light → dark) for SNR magnitude.
MAP_RAMP = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
OVERLOAD = "#e34948"
HATCH = (0.04, 0.04, 0.04, 0.45)  # translucent ink for hatch patterns


def _finite(a: np.ndarray) -> np.ndarray:
    """−inf (m = 0) and nan become nan so contouring ignores them."""
    return np.where(np.isfinite(a), a, np.nan)


def _within(level: float, a: np.ndarray) -> bool:
    finite = a[np.isfinite(a)]
    return finite.size > 0 and float(finite.min()) < level < float(finite.max())


def designmap(result: Result) -> Figure:
    """Top: the mapped SNR (snr or snr_lia) over log t_dwell × log P with target, iso-SNR
    lines, overload and shot/electronic boundaries and the profile's design points. Bottom:
    SNR vs t_dwell slices at the profile's P_min and P_max, overloaded stretches dashed."""
    from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    _need(result, "map")
    m = result.tables["map"]
    t = np.array(m["axes"]["t_dwell"])
    p = np.array(m["axes"]["power"])
    snr = _finite(np.array(m["grid"]["snr"], dtype=float))
    occ = np.array(m["grid"]["occ"], dtype=float)
    clear = _finite(np.array(m["grid"]["shot_clear"], dtype=float))
    target = float(result.scalars["target"])
    lia = result.scalars.get("quantity", "snr") == "snr_lia"
    name_q = "SNR_LIA" if lia else "SNR"
    T, P = np.meshgrid(t, p)

    fig = Figure(figsize=(9, 8.2), facecolor=SURFACE, layout="constrained")
    ax, ax2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1.5]})
    for a in (ax, ax2):
        a.set_facecolor(SURFACE)
        a.tick_params(colors=INK_2, labelcolor=INK)
        for side in ("top", "right"):
            a.spines[side].set_visible(False)

    handles: list[Artist] = []
    if np.isfinite(snr).any():
        lo = np.floor(np.nanmin(snr) / 5) * 5
        hi = np.ceil(np.nanmax(snr) / 5) * 5 + (5 if np.nanmax(snr) % 5 == 0 else 0)
        levels = np.arange(lo, max(hi, lo + 5) + 0.1, 5)
        cmap = LinearSegmentedColormap.from_list("snr", MAP_RAMP)
        cf = ax.contourf(T, P, snr, levels=levels, cmap=cmap,
                         norm=BoundaryNorm(levels, cmap.N))
        fig.colorbar(cf, ax=ax, label=f"{name_q} over {'ENBW' if lia else 'B_eq'} [dB]", pad=0.01)
        iso = [v for v in np.arange(np.ceil(lo / 10) * 10, hi + 0.1, 10) if _within(v, snr)]
        if iso:
            lines = ax.contour(T, P, snr, levels=iso, colors=SURFACE, linewidths=0.6,
                               linestyles="solid")
            ax.clabel(lines, fmt="%d", fontsize=7, colors=SURFACE)
        vmin, vmax = float(np.nanmin(snr)), float(np.nanmax(snr))
        if _within(target, snr):
            ax.contour(T, P, snr, levels=[target], colors=INK, linewidths=2.6)
            handles.append(Line2D([], [], color=INK, lw=2.6,
                                  label=f"{name_q} = {target:g} dB (target)"))
        else:
            where = "everywhere" if target <= vmin else "nowhere"
            handles.append(Line2D([], [], color="none",
                                  label=f"target {target:g} dB met {where} in range"))
        if target > vmin:
            # Below-target side: dots only, colours stay true to the colour bar.
            below = ax.contourf(T, P, snr, levels=[vmin - 1, min(target, vmax + 1)],
                                colors="none", hatches=["."])
            below.set_edgecolor(HATCH)
            handles.append(Patch(facecolor="none", edgecolor=INK_2, hatch=".",
                                 label="below target"))
    if _within(100.0, occ):
        over = ax.contourf(T, P, occ, levels=[100.0, float(np.nanmax(occ)) + 1],
                           colors="none", hatches=["//"])
        over.set_edgecolor(HATCH)
        ax.contour(T, P, occ, levels=[100.0], colors=OVERLOAD, linewidths=2, linestyles="--")
    if (occ > 100).any():
        handles += [Line2D([], [], color=OVERLOAD, lw=2, ls="--",
                           label="overload: opamp swing or Moku range"),
                    Patch(facecolor="none", edgecolor=INK_2, hatch="//", label="overloaded")]
    if _within(0.0, clear):
        ax.contour(T, P, clear, levels=[0.0], colors=INK, linewidths=1.8, linestyles="-.")
        handles.append(Line2D([], [], color=INK, lw=1.8, ls="-.",
                              label="shot noise = electronic noise"))
    t_design = result.params.get("t_dwell")
    for name in POWERS:
        power = result.params.get(name)
        if t_design is not None and power is not None:
            ax.plot([t_design], [power], POWER_MARKER[name], color="#eda100", ms=10,
                    mec=INK, mew=1.2)
            handles.append(Line2D([], [], marker=POWER_MARKER[name], ls="", color="#eda100",
                                  mec=INK, ms=8, label=f"profile {POWER_LABEL[name]}"))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(t[0], t[-1])
    ax.set_ylim(p[0], p[-1])
    ax.yaxis.set_major_formatter(EngFormatter(unit="W"))
    ax.set_ylabel("optical power P on photodiode", color=INK)
    ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=0.92,
              facecolor=SURFACE)

    # Slices at the profile's powers; overloaded stretches dashed.
    sl = result.tables["slices"]
    ts = np.array(sl["t_dwell"]["values"])
    ax2.grid(True, color=GRID, linewidth=0.8)
    for name in POWERS:
        if name not in sl:
            continue
        y = _finite(np.array(sl[name]["snr"], dtype=float))
        over = np.array(sl[name]["occ"], dtype=float) > 100
        ok_y = np.where(over, np.nan, y)
        # Overloaded stretches drawn dashed; extend by one point so the two styles meet.
        over_y = np.where(over | np.roll(over, 1) | np.roll(over, -1), y, np.nan)
        power = sl[name]["power"][0]
        ax2.plot(ts, ok_y, color=POWER_COLOR[name], lw=2,
                 label=f"{POWER_LABEL[name]} = {format_eng(power, 'W', 3)}")
        ax2.plot(ts, over_y, color=POWER_COLOR[name], lw=2, ls="--")
    ax2.axhline(target, color=INK, lw=1.5, ls="--")
    ax2.annotate(f"target {target:g} dB", (1, target), xycoords=("axes fraction", "data"),
                 xytext=(-4, 4), textcoords="offset points", ha="right", color=INK, fontsize=9)
    ax2.set_ylabel(f"{name_q} [dB]", color=INK)
    ax2.set_xlabel("pixel dwell time t_dwell  (dashed: overloaded)", color=INK)
    ax2.xaxis.set_major_formatter(EngFormatter(unit="s"))
    ax2.legend(frameon=False, labelcolor=INK, fontsize=9, loc="lower right")

    base = {"d": "Design", "b": "Buy"}.get(str(result.scalars.get("base")), "?")
    r_f = result.params.get("r_f")
    gain = f", R = {format_eng(r_f, 'Ω', 3)}" if r_f is not None else ""
    k = result.scalars.get("k_lia")
    lockin = f", lock-in τ = {float(k):g}·t_dwell, n = {result.params.get('n_lia')}" if lia else ""
    _title(fig, f"Design-space map — {base}{gain}{lockin}", result)
    return fig


FIGURES: dict[str, Callable[[Result], Figure]] = {
    "bode": bode, "spectrum": spectrum, "budget": budget, "noise": noise, "map": designmap,
}


def make(result: Result, plot: str) -> Figure:
    """Build the named plot; KeyError for an unknown name, ValueError if not available."""
    return FIGURES[plot](result)
