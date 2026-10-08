"""Tool screen — placeholder until M9 builds the generic screen from the Tool declaration."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static

from srsfe.tools.base import Tool
from srsfe.tui import keymap
from srsfe.tui.widgets.header import AppHeader


class ToolScreen(Screen[None]):
    BINDINGS = keymap.bindings(keymap.BACK)

    def __init__(self, tool: Tool) -> None:
        super().__init__()
        self.tool = tool

    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield Static(f"{self.tool.name}\n\n{self.tool.description}\n\n"
                     "(The generic tool screen arrives in M9.)", id="body")
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()
