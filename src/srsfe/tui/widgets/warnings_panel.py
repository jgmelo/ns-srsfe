"""Warnings panel (SPEC §8.1) under the results table."""

from __future__ import annotations

from textual.content import Content
from textual.widgets import Static

from srsfe.tools.base import Result

POWER_LABEL = {"p_min": "P_min", "p_max": "P_max"}


def lines(result: Result | None) -> list[str]:
    if result is None:
        return ["Not calculated yet — press c or F5."]
    if not result.warnings:
        return ["No warnings."]
    out = []
    for w in result.warnings:
        icon = "⚠" if w.severity == "warn" else "ℹ"
        where = f" · {POWER_LABEL[w.power]}" if w.power else ""
        out.append(f"{icon} {w.id}{where} · {w.message}")
    return out


class WarningsPanel(Static):
    DEFAULT_CSS = """
    WarningsPanel { height: auto; max-height: 12; padding: 0 1; border-top: solid $panel; }
    """

    def show(self, result: Result | None) -> None:
        self.update(Content("\n".join(lines(result))))
