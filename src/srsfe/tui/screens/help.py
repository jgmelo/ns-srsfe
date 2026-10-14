"""F1 help overlay (SPEC §8.1): the keys of the current screen, from the key tables."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from srsfe.tui import keymap

Section = tuple[str, list[tuple[str, str]]]

NOTATION = (
    "Inputs take engineering notation: 100k, 2p, 20M, 1e-6, 1µ or 1u; the unit may be typed "
    "(2 pF, 20MHz). Stored in SI. Empty = unset."
)


def keys_section(title: str, keys: tuple[keymap.Key, ...]) -> Section:
    return title, [(keymap.display(k.key), k.label) for k in keys if k.show]


def global_section() -> Section:
    rows = [(keymap.display(k.key).upper() if k.key.startswith("f") else k.key, k.label)
            for k in keymap.GLOBAL]
    return "Always (even while typing)", [("Esc", "Up / back"), *rows, ("ctrl+p", "Command palette")]


def render(sections: list[Section]) -> str:
    lines: list[str] = []
    for title, rows in sections:
        lines.append(title)
        lines += [f"  {key:<8} {label}" for key, label in rows]
        lines.append("")
    lines.append(NOTATION)
    return "\n".join(lines)


class HelpScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    HelpScreen { align: center middle; }
    HelpScreen > VerticalScroll { width: 76; height: 80%; padding: 1 2; border: thick $accent;
                                  background: $surface; }
    HelpScreen .title { text-style: bold; margin-bottom: 1; }
    HelpScreen .hint { color: $text-muted; margin-top: 1; }
    """
    BINDINGS = keymap.bindings(keymap.HELP)

    def __init__(self, title: str, sections: list[Section]) -> None:
        super().__init__()
        self.title_text = title
        self.sections = [*sections, global_section()]

    @property
    def text(self) -> str:
        return render(self.sections)

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(Content(f"Help — {self.title_text}"), classes="title")
            yield Static(Content(self.text))
            yield Label(Content("Esc or F1 close"), classes="hint")

    def action_close(self) -> None:
        self.dismiss()
