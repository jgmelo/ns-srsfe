"""Engineering-notation input for one Params field (SPEC §8.1)."""

from __future__ import annotations

import math

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.content import Content
from textual.message import Message
from textual.widgets import Input, Label

from srsfe.core.params import FIELDS, FieldValue, coerce, validate_value
from srsfe.core.units import parse_eng
from srsfe.tui import keymap

_EDIT_PREFIX = {-18: "a", -15: "f", -12: "p", -9: "n", -6: "µ", -3: "m", 3: "k", 6: "M", 9: "G",
                12: "T"}


# Display text must parse back to the value within float noise.
_RTOL = 1e-12


def edit_text(value: FieldValue) -> str:
    """Compact text for editing that parses back to `value` ("100k", "2.5n", "0.6").
    Prefix arithmetic (10·1e-6) is not exact in floats, hence the 1e-12 tolerance."""
    if value is None:
        return ""
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return str(value)
    v = float(value)
    if v == 0 or 0.1 <= abs(v) < 1e4:
        for sig in (6, 9, 12, 17):
            t = f"{v:.{sig}g}"
            if math.isclose(float(t), v, rel_tol=_RTOL):
                return t
        return repr(v)
    exp3 = math.floor(math.log10(abs(v)) / 3) * 3
    if exp3 not in _EDIT_PREFIX:
        return repr(v)
    for sig in (6, 9, 12, 17):
        t = f"{v / 10.0**exp3:.{sig}g}{_EDIT_PREFIX[exp3]}"
        if math.isclose(parse_eng(t), v, rel_tol=_RTOL):
            return t
    return repr(v)


def parse_field(name: str, text: str) -> FieldValue:
    """Text → SI value for field `name`; "" → None (unset). ValueError with a reason."""
    meta = FIELDS[name]
    text = text.strip()
    if not text:
        return None
    if meta.kind is str:
        value: FieldValue = text
    else:
        number = parse_eng(text, meta.unit)
        try:
            value = coerce(name, number)
        except TypeError:
            raise ValueError("must be an integer") from None
    reason = validate_value(name, value)
    if reason is not None:
        raise ValueError(reason)
    return value


class FieldRow(Horizontal):
    """`[key] name` · input · unit · reason. Classes set by the screen: required, missing,
    optional, unused, invalid."""

    DEFAULT_CSS = """
    FieldRow { height: 1; }
    FieldRow .key { width: 14; padding: 0 0 0 1; }
    FieldRow Input { width: 16; background: $boost; }
    FieldRow .unit { width: 8; padding: 0 0 0 1; color: $text-muted; }
    FieldRow .reason { width: 1fr; padding: 0 0 0 1; color: $error; }
    FieldRow.required .key { color: $accent; text-style: bold; }
    FieldRow.required Input { background: $accent 15%; }
    FieldRow.missing Input, FieldRow.invalid Input { background: $error 35%; }
    FieldRow.missing .key { color: $error; }
    FieldRow.unused { opacity: 50%; }
    FieldRow Input:focus { background: $accent 40%; }
    """

    class Edited(Message):
        """A field got a new valid value (None = unset)."""

        def __init__(self, name: str, value: FieldValue) -> None:
            super().__init__()
            self.name, self.value = name, value

    def __init__(self, name: str, value: FieldValue) -> None:
        super().__init__(id=f"row-{name}")
        self.field_name = name
        self.shown = edit_text(value)
        self.error: str | None = None

    def compose(self) -> ComposeResult:
        meta = FIELDS[self.field_name]
        yield Label(keymap.hint(meta.key, self.field_name), classes="key")
        yield Input(self.shown, id=f"in-{self.field_name}", tooltip=meta.description, compact=True)
        yield Label(Content("" if meta.unit == "–" else meta.unit), classes="unit")
        yield Label("", classes="reason")

    @property
    def input(self) -> Input:
        return self.query_one(Input)

    def set_value(self, value: FieldValue) -> None:
        """Show a value set from outside (profile load) without reporting an edit."""
        self.shown = edit_text(value)
        self.error = None
        self.input.value = self.shown
        self._show_error()

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        if event.value == self.shown:  # our own set_value / initial text
            return
        self.shown = event.value
        try:
            value = parse_field(self.field_name, event.value)
        except ValueError as exc:
            self.error = str(exc)
        else:
            self.error = None
            self.post_message(self.Edited(self.field_name, value))
        self._show_error()

    def _show_error(self) -> None:
        self.set_class(self.error is not None, "invalid")
        self.query_one(".reason", Label).update(Content(self.error or ""))
