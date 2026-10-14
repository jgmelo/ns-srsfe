"""Settings screen (SPEC §8.1): profiles folder. Enter applies, Esc goes back."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.content import Content
from textual.screen import Screen
from textual.widgets import Footer, Input, Label

from srsfe.tui import keymap
from srsfe.tui.screens.help import Section, keys_section
from srsfe.tui.widgets.header import AppHeader

if TYPE_CHECKING:
    from srsfe.tui.app import SrsfeApp


class SettingsScreen(Screen[None]):
    DEFAULT_CSS = """
    SettingsScreen Vertical { padding: 1 2; height: auto; }
    SettingsScreen Input { width: 70; }
    SettingsScreen .hint { color: $text-muted; }
    """
    BINDINGS = keymap.bindings(keymap.SETTINGS)

    @property
    def srsfe(self) -> SrsfeApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Vertical():
            yield Label("Profiles folder")
            yield Input(str(self.srsfe.store.directory), id="profiles-dir")
            yield Label(Content(f"Settings file: {self.srsfe.settings_path or '(not saved)'}"),
                        classes="hint")
            yield Label(keymap.hints(keymap.SETTINGS), classes="hint")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.action_apply()

    def action_apply(self) -> None:
        folder = self.query_one("#profiles-dir", Input).value.strip()
        if not folder:
            self.notify("The profiles folder cannot be empty.", severity="error")
            return
        self.srsfe.change_profiles_dir(folder)

    def action_back(self) -> None:
        self.app.pop_screen()

    def help_sections(self) -> list[Section]:
        return [keys_section("Settings", keymap.SETTINGS)]
