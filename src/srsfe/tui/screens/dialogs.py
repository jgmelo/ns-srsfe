"""Modal dialogs: unsaved changes, delete confirmation, text prompt (SPEC §8.1)."""

from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from srsfe.tui import keymap

UnsavedChoice = Literal["save", "discard", "cancel"]

_CSS = """
{name} {{ align: center middle; }}
{name} > Vertical {{
    width: 60; height: auto; padding: 1 2; border: thick $accent; background: $surface;
}}
{name} Label {{ width: 100%; }}
{name} .hint {{ color: $text-muted; margin-top: 1; }}
"""


class UnsavedDialog(ModalScreen[UnsavedChoice]):
    """`profile <name>` has unsaved changes: [s] save · [d] discard · [c] cancel."""

    DEFAULT_CSS = _CSS.format(name="UnsavedDialog")
    BINDINGS = keymap.bindings(keymap.UNSAVED)

    def __init__(self, profile: str, doing: str) -> None:
        super().__init__()
        self.profile, self.doing = profile, doing

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Content(f"Profile '{self.profile}' has unsaved changes. Save before {self.doing}?"))
            yield Label(keymap.hints(keymap.UNSAVED), classes="hint")

    def action_save(self) -> None:
        self.dismiss("save")

    def action_discard(self) -> None:
        self.dismiss("discard")

    def action_cancel(self) -> None:
        self.dismiss("cancel")


class ConfirmDialog(ModalScreen[bool]):
    """Yes/no question: [y] yes · [n] no (Esc = no)."""

    DEFAULT_CSS = _CSS.format(name="ConfirmDialog")
    BINDINGS = keymap.bindings(keymap.DELETE)

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Content(self.question))
            yield Label(keymap.hints(keymap.DELETE), classes="hint")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class DeleteDialog(ConfirmDialog):
    """Delete profile <name>? [y] yes · [n] no."""

    DEFAULT_CSS = _CSS.format(name="DeleteDialog")

    def __init__(self, profile: str) -> None:
        super().__init__(f"Delete profile '{profile}'? This cannot be undone.")
        self.profile = profile


class PromptDialog(ModalScreen[str | None]):
    """One-line text prompt (profile name, notes). Enter accepts, Esc cancels (None)."""

    DEFAULT_CSS = _CSS.format(name="PromptDialog")
    BINDINGS = keymap.bindings(keymap.PROMPT)

    def __init__(self, title: str, value: str = "") -> None:
        super().__init__()
        self.title_text, self.value = title, value

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Content(self.title_text))
            yield Input(value=self.value)
            yield Label("Enter accept  ·  Esc cancel", classes="hint")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
