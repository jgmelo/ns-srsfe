"""Results table (SPEC §8.1): one row per output; P_min / P_max columns where applicable;
engineering formatting; ⚠ / ℹ on rows tied to a warning."""

from __future__ import annotations

import math
from typing import Any

from textual.content import Content
from textual.widgets import DataTable

from srsfe.core.units import format_eng
from srsfe.tools.base import HARMONIC_COLUMNS, OUTPUTS, POWERS, Calc, Result


def fmt(value: Any, unit: str) -> str:
    """Format one output value for display."""
    if value is None:
        return "—"
    if unit == "bool" or isinstance(value, bool):
        return "yes" if value else "no"
    v = float(value)
    if math.isinf(v):
        return f"{'−' if v < 0 else ''}∞ {unit}".strip()
    if unit == "dB":
        return f"{v:+.2f} dB"
    if unit == "%":
        return f"{v:.1f} %"
    if unit == "–":
        return f"{v:.5g}"
    return format_eng(v, unit)


def marks(result: Result) -> dict[str, str]:
    """output name → "⚠" (any warn) or "ℹ" (info only) from the result's warnings."""
    out: dict[str, str] = {}
    for w in result.warnings:
        for f in w.fields:
            if w.severity == "warn" or f not in out:
                out[f] = "⚠" if w.severity == "warn" else "ℹ"
    return out


def rows(calc: Calc, result: Result) -> list[tuple[str, str, str, str, str]]:
    """(mark, label, value or P_min, P_max, note) per displayed row, in calc output order."""
    m = marks(result)
    out: list[tuple[str, str, str, str, str]] = []
    harmonics_done = False
    for name in calc.outputs:
        unit = OUTPUTS[name][0]
        if name in result.scalars:
            out.append((m.get(name, ""), name, fmt(result.scalars[name], unit), "", ""))
        elif name in result.per_power:
            pp = result.per_power[name]
            out.append((m.get(name, ""), name, *(fmt(pp[p], unit) for p in POWERS), ""))
        elif name in HARMONIC_COLUMNS and "harmonics" in result.tables and not harmonics_done:
            harmonics_done = True
            out.extend(_harmonic_rows(result))
    return out


def _harmonic_rows(result: Result) -> list[tuple[str, str, str, str, str]]:
    t = result.tables["harmonics"]
    lo, hi = t["p_min"], t["p_max"]
    out = [("", "i_n (each line)", fmt(lo["i_n"][0], "A") if lo["i_n"] else "—",
            fmt(hi["i_n"][0], "A") if hi["i_n"] else "—", "2·I₀ at n·f_rep")]
    for k, n in enumerate(lo["n"]):
        note = f"|Z| {fmt(lo['z_n'][k], 'Ω')}, att {fmt(lo['att_n'][k], 'dB')}"
        out.append(("", f"v_n  n={n} @ {fmt(lo['f_n'][k], 'Hz')}", fmt(lo["v_n"][k], "V"),
                    fmt(hi["v_n"][k], "V"), note))
    return out


COLUMNS = ((" ", 1), ("output", 26), ("value / P_min", 14), ("P_max", 14), ("note", 36))


class ResultsTable(DataTable):
    DEFAULT_CSS = """
    ResultsTable { height: 1fr; }
    ResultsTable.stale { opacity: 50%; }
    """

    def on_mount(self) -> None:
        self.cursor_type = "row"
        for label, width in COLUMNS:
            self.add_column(label, width=width)

    def show(self, calc: Calc, result: Result | None) -> None:
        self.clear()
        if result is None:
            return
        for mark, label, a, b, note in rows(calc, result):
            self.add_row(Content(mark), Content(label), Content(a), Content(b), Content(note),
                         key=label)
