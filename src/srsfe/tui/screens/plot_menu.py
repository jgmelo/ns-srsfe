"""Plot menu (SPEC §8.1): pick plots available for the current Result; show or save PNG."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.markup import escape
from textual.screen import ModalScreen
from textual.widgets import Label, SelectionList

from srsfe.tools.base import PLOT_KEYS, Result
from srsfe.tui import keymap

if TYPE_CHECKING:
    from srsfe.tui.app import SrsfeApp

TITLES = {"bode": "Bode", "spectrum": "Spectrum", "budget": "Budget", "noise": "Noise"}


def launch(result: Result, plots: list[str]) -> None:
    """Show plots in a separate process so matplotlib's GUI loop never blocks Textual."""
    tmp = Path(tempfile.mkdtemp(prefix="srsfe-")) / "result.json"
    tmp.write_text(result.to_json(), encoding="utf-8")
    subprocess.Popen([sys.executable, "-m", "srsfe.plots.runner", str(tmp), *plots],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def save(result: Result, plots: list[str], directory: Path, profile: str) -> list[Path]:
    """Write <directory>/<profile>_<plot>.png for each plot (in-process, no GUI)."""
    from srsfe.plots import runner

    return [runner.save(result, p, directory / f"{profile}_{p}.png") for p in plots]


class PlotMenu(ModalScreen[None]):
    DEFAULT_CSS = """
    PlotMenu { align: center middle; }
    PlotMenu > Vertical { width: 56; height: auto; padding: 1 2; border: thick $accent;
                          background: $surface; }
    PlotMenu Label { width: 100%; }
    PlotMenu .hint { color: $text-muted; margin-top: 1; }
    """
    BINDINGS = keymap.bindings(keymap.PLOT_MENU)

    def __init__(self, result: Result) -> None:
        super().__init__()
        self.result = result
        self.available = [p for p in PLOT_KEYS if p in result.plots]

    @property
    def srsfe(self) -> SrsfeApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Plots")
            choices = SelectionList[str](
                *((keymap.hint(PLOT_KEYS[p], TITLES[p]), p, True) for p in self.available)
            )
            choices.can_focus = False  # keys go to the menu, not the list
            yield choices
            yield Label(keymap.hints(keymap.PLOT_MENU), classes="hint")

    @property
    def selected(self) -> list[str]:
        chosen = set(self.query_one(SelectionList).selected)
        return [p for p in self.available if p in chosen]

    def on_key(self, event: events.Key) -> None:
        for plot in self.available:
            if event.key == PLOT_KEYS[plot]:
                event.stop()
                self.query_one(SelectionList).toggle(plot)

    def action_show(self) -> None:
        if not self.selected:
            self.notify("Select at least one plot.", severity="warning")
            return
        launch(self.result, self.selected)
        self.dismiss()

    def action_save(self) -> None:
        if not self.selected:
            self.notify("Select at least one plot.", severity="warning")
            return
        paths = save(self.result, self.selected, self.srsfe.plots_dir, self.srsfe.profile_name)
        self.notify(escape("Saved " + ", ".join(str(p) for p in paths)))
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()
