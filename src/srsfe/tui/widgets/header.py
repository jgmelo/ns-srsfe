"""App header: `SRS-FE │ profile: <name>[*]` (SPEC §8)."""

from __future__ import annotations

from textual.content import Content
from textual.widgets import Static


class AppHeader(Static):
    DEFAULT_CSS = """
    AppHeader { dock: top; height: 1; padding: 0 1; background: $panel; color: $text; }
    """

    def on_mount(self) -> None:
        self.watch(self.app, "header_text", self._update)

    def _update(self, text: str) -> None:
        self.update(Content(text))
