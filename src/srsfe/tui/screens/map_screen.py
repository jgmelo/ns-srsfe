"""Map screen (SPEC §8.1, §6.5): map settings, compute, boundary table, plot / save PNG.

Letters act only when no text input has focus; setting keys come from
tools.designmap.SETTING_META, action keys from keymap.MAP (both via keymap.map_level()).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from textual import events, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.markup import escape
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Input, Label, Static

from srsfe.core.params import Params
from srsfe.core.units import format_eng
from srsfe.tools import REGISTRY
from srsfe.tools.base import CalcInputError, Result
from srsfe.tools.designmap import (
    CHOICES,
    PLOTS,
    SETTING_META,
    MapSettings,
    MapSettingsError,
    compute,
    parse_setting,
    validate,
)
from srsfe.tui import keymap
from srsfe.tui.screens.help import Section, keys_section
from srsfe.tui.widgets.eng_input import edit_text
from srsfe.tui.widgets.header import AppHeader
from srsfe.tui.widgets.results_table import fmt

if TYPE_CHECKING:
    from srsfe.tui.app import SrsfeApp

COLUMNS = (("P", 18), ("t_snr", 12), ("t_ovl", 12), ("t_safe", 12), ("snr_design", 12))


def time_cell(t: float | None, t_lo: float) -> str:
    """A boundary-table crossing: "—" never reached, "≤ t_lo" already met at the edge."""
    if t is None:
        return "—"
    if math.isclose(t, t_lo, rel_tol=1e-9):
        return f"≤ {format_eng(t_lo, 's', sig=3)}"
    return format_eng(t, "s", sig=3)


def table_rows(result: Result) -> list[tuple[str, str, str, str, str]]:
    """Formatted boundary-table rows of a Map result."""
    rows = result.tables["boundaries"]["rows"]
    t_lo = float(result.scalars["t_lo"])
    out = []
    for k, label in enumerate(rows["label"]):
        name = "" if label == "decade" else f"{label} "
        out.append((f"{name}{format_eng(rows['power'][k], 'W', sig=3)}",
                    time_cell(rows["t_snr"][k], t_lo), time_cell(rows["t_ovl"][k], t_lo),
                    time_cell(rows["t_safe"][k], t_lo), fmt(rows["snr_design"][k], "dB")))
    return out


QUANTITY_TEXT = {"snr": "TIA output over B_eq", "snr_lia": "lock-in, over ENBW"}


def choice_text(name: str, value: str) -> str:
    """How a toggled setting is shown: "d  Design from t_dwell", "snr_lia  lock-in, …"."""
    if name == "base" and value in REGISTRY:
        return f"{value}  {REGISTRY[value].name}"
    return f"{value}  {QUANTITY_TEXT[value]}" if value in QUANTITY_TEXT else value


class SettingRow(Horizontal):
    """`[key] name` · input (or the text of a toggled setting) · unit · reason."""

    DEFAULT_CSS = """
    SettingRow { height: 1; }
    SettingRow .key { width: 14; padding: 0 0 0 1; }
    SettingRow Input { width: 16; background: $boost; }
    SettingRow .value { width: 30; padding: 0 1; }
    SettingRow .unit { width: 6; padding: 0 0 0 1; color: $text-muted; }
    SettingRow .reason { width: 1fr; padding: 0 0 0 1; color: $error; }
    SettingRow.invalid Input { background: $error 35%; }
    SettingRow Input:focus { background: $accent 40%; }
    """

    class Edited(Message):
        """The text of a numeric setting changed (value None = unparseable)."""

        def __init__(self, name: str, value: float | None, error: str | None) -> None:
            super().__init__()
            self.name, self.value, self.error = name, value, error

    def __init__(self, name: str, value: Any) -> None:
        super().__init__(id=f"row-{name}")
        self.setting = name
        self.shown = value if name in CHOICES else edit_text(value)

    def compose(self) -> ComposeResult:
        meta = SETTING_META[self.setting]
        yield Label(keymap.hint(meta.key, self.setting), classes="key")
        if self.setting in CHOICES:
            yield Label(Content(choice_text(self.setting, self.shown)), classes="value")
        else:
            yield Input(self.shown, id=f"in-{self.setting}", tooltip=meta.description,
                        compact=True)
        yield Label(Content("" if meta.unit == "–" else meta.unit), classes="unit")
        yield Label("", classes="reason")

    @property
    def input(self) -> Input:
        return self.query_one(Input)

    def show_choice(self, value: str) -> None:
        self.query_one(".value", Label).update(Content(choice_text(self.setting, value)))

    def show_error(self, reason: str | None) -> None:
        self.set_class(reason is not None, "invalid")
        self.query_one(".reason", Label).update(Content(reason or ""))

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        if event.value == self.shown:
            return
        self.shown = event.value
        try:
            value = parse_setting(self.setting, event.value)
        except ValueError as exc:
            self.post_message(self.Edited(self.setting, None, str(exc)))
        else:
            self.post_message(self.Edited(self.setting, value, None))


class MapScreen(Screen[None]):
    DEFAULT_CSS = """
    MapScreen #settings { height: auto; padding: 1 0; border-bottom: solid $panel; }
    MapScreen #status { height: auto; padding: 0 1; }
    MapScreen DataTable { height: 1fr; }
    MapScreen DataTable.stale { opacity: 50%; }
    MapScreen #hints { height: auto; padding: 0 1; background: $panel; color: $text-muted; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.keys = dict(keymap.map_level())
        self.values: dict[str, Any] = {}
        self.parse_errors: dict[str, str] = {}
        self.result: Result | None = None
        self.computing = False

    @property
    def srsfe(self) -> SrsfeApp:
        return self.app  # type: ignore[return-value]

    # -- layout ------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        self.values = self.srsfe.map_settings.to_dict()
        yield AppHeader()
        with Vertical(id="settings"):
            for name in SETTING_META:
                yield SettingRow(name, self.values[name])
        yield Static(id="status")
        yield DataTable(id="boundaries", cursor_type="row")
        yield Static(id="hints")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.can_focus = False
        for label, width in COLUMNS:
            table.add_column(label, width=width)
        self.update_status()
        self.update_hints()
        self.call_after_refresh(self.set_focus, None)

    def on_screen_resume(self) -> None:
        self.refresh_stale()

    # -- state -----------------------------------------------------------------------------

    def row(self, name: str) -> SettingRow:
        return self.query_one(f"#row-{name}", SettingRow)

    def errors(self) -> dict[str, str]:
        """Parse errors, else range/order errors of the current values."""
        if self.parse_errors:
            return dict(self.parse_errors)
        return validate(MapSettings(**self.values))

    def show_errors(self) -> None:
        errors = self.errors()
        for name in SETTING_META:
            self.row(name).show_error(errors.get(name))

    def is_stale(self) -> bool:
        """The table was computed from other settings or other profile inputs."""
        if self.result is None:
            return False
        shown = MapSettings.from_dict(self.result.scalars).to_dict()
        return (bool(self.parse_errors) or shown != self.values
                or self.result.params != self.srsfe.params.to_dict())

    def refresh_stale(self) -> None:
        self.query_one(DataTable).set_class(self.is_stale(), "stale")
        self.update_status()

    def update_status(self) -> None:
        if self.computing:
            text = "Computing …"
        elif self.result is None:
            text = "Not computed — press c."
        else:
            s = self.result.scalars
            q = str(s.get("quantity", "snr"))
            what = f"snr_lia (τ_LIA = {s['k_lia']:g}·t_dwell)" if q == "snr_lia" else "snr"
            text = (f"{s['n']}×{s['n']} map of {what} on {REGISTRY[str(s['base'])].name}, "
                    f"target {s['target']:g} dB, profile inputs of '{self.srsfe.profile_name}'.")
            if self.is_stale():
                text += "  Settings or inputs changed — press c to recompute."
        self.query_one("#status", Static).update(Content(text))

    def update_hints(self) -> None:
        focused = self.focused
        if isinstance(focused, Input) and isinstance(focused.parent, SettingRow):
            name = focused.parent.setting
            text = f"Editing {name} ({SETTING_META[name].description}) — Enter or Esc to finish"
        else:
            settings = " ".join(str(keymap.hint(m.key, n)) for n, m in SETTING_META.items())
            text = f"{settings}\n{keymap.hints(keymap.MAP)}"
        self.query_one("#hints", Static).update(Content(text))

    def show_result(self, result: Result) -> None:
        self.computing = False
        self.result = result
        table = self.query_one(DataTable)
        table.clear()
        for k, cells in enumerate(table_rows(result)):
            table.add_row(*(Content(c) for c in cells), key=str(k))
        self.refresh_stale()
        self.notify("Map computed.")

    def compute_failed(self, message: str, title: str) -> None:
        self.computing = False
        self.update_status()
        self.notify(message, title=title, severity="error")

    # -- keys ------------------------------------------------------------------------------

    async def on_key(self, event: events.Key) -> None:
        if isinstance(self.focused, Input):
            if event.key == "escape":
                event.stop()
                self.finish_edit()
            return
        if event.key == "escape":
            event.stop()
            self.app.pop_screen()
            return
        target = self.keys.get(event.key)
        if target is None:
            return
        event.stop()
        kind, _, arg = target.partition(":")
        if kind == "setting":
            self.edit_setting(arg)
        else:
            await self.run_action(arg)

    def edit_setting(self, name: str) -> None:
        if name in CHOICES:  # toggle to the next choice
            choices = CHOICES[name]
            current = self.values[name]
            nxt = choices[(choices.index(current) + 1) % len(choices)] if current in choices \
                else choices[0]
            self.values[name] = nxt
            self.row(name).show_choice(nxt)
            self.show_errors()
            self.refresh_stale()
            return
        row = self.row(name)
        row.input.focus()
        row.input.select_all()
        self.call_after_refresh(self.update_hints)

    def finish_edit(self) -> None:
        self.set_focus(None)
        self.update_hints()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.finish_edit()

    def on_setting_row_edited(self, event: SettingRow.Edited) -> None:
        if event.error is None:
            self.parse_errors.pop(event.name, None)
            self.values[event.name] = event.value
        else:
            self.parse_errors[event.name] = event.error
        self.show_errors()
        self.refresh_stale()

    # -- actions ---------------------------------------------------------------------------

    def action_calculate(self) -> None:
        """F5 computes too."""
        self.action_compute()

    def action_compute(self) -> None:
        if self.computing:
            return
        errors = self.errors()
        if errors:
            self.notify("Invalid: " + ", ".join(f"{k} ({v})" for k, v in errors.items()),
                        severity="error")
            return
        settings = MapSettings(**self.values)
        self.srsfe.set_map_settings(settings)
        self.computing = True
        self.update_status()
        self.run_map(settings, self.srsfe.params)

    @work(thread=True, exclusive=True)
    def run_map(self, settings: MapSettings, params: Params) -> None:
        try:
            result = compute(REGISTRY[settings.base], params, settings)
        except CalcInputError as exc:
            self.app.call_from_thread(self.compute_failed, str(exc).capitalize(),
                                      "Map not computed")
        except MapSettingsError as exc:
            self.app.call_from_thread(self.compute_failed, str(exc), "Map not computed")
        else:
            self.app.call_from_thread(self.show_result, result)

    def action_plot(self) -> None:
        from srsfe.tui.screens import plot_menu

        if self.result is None:
            self.notify("Compute first (c).", severity="warning")
            return
        plot_menu.launch(self.result, list(PLOTS))

    def action_save_png(self) -> None:
        from srsfe.tui.screens import plot_menu

        if self.result is None:
            self.notify("Compute first (c).", severity="warning")
            return
        paths = plot_menu.save(self.result, list(PLOTS), self.srsfe.plots_dir,
                               self.srsfe.profile_name)
        self.notify(escape("Saved " + ", ".join(str(p) for p in paths)))

    def help_sections(self) -> list[Section]:
        return [
            keys_section("Actions", keymap.MAP),
            ("Settings (key edits; saved to the settings file on compute)",
             [(m.key, f"{n} — {m.description}") for n, m in SETTING_META.items()]),
            ("Editing", [("Enter", "Finish editing"), ("Esc", "Finish editing; else back")]),
        ]

    async def action_help(self) -> None:
        await self.app.run_action("help")
