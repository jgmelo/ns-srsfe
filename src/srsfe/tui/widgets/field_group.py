"""Collapsible input group (SPEC §8.1): title "[t] Tank", one FieldRow per field."""

from __future__ import annotations

from textual.markup import escape
from textual.widgets import Collapsible

from srsfe.core.params import Params
from srsfe.tools.base import Group
from srsfe.tui import keymap
from srsfe.tui.widgets.eng_input import FieldRow


class FieldGroup(Collapsible):
    DEFAULT_CSS = """
    FieldGroup { padding: 0; }
    FieldGroup > Contents { padding: 0 0 0 1; }
    FieldGroup.current > CollapsibleTitle { color: $accent; text-style: bold; }
    """

    def __init__(self, group: Group, params: Params) -> None:
        rows = [FieldRow(f, getattr(params, f)) for f in group.fields]
        title = escape(str(keymap.hint(group.key, group.name)))
        super().__init__(*rows, title=title, collapsed=True, id=f"group-{group.key}")
        self.group = group

    def rows(self) -> list[FieldRow]:
        return list(self.query(FieldRow))
