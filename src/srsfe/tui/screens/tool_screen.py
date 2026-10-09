"""Generic tool screen (SPEC §8.1), built entirely from a Tool declaration.

Focus is a tree: screen (top) → group → field. Letters act only when no text input has
focus; the key tables come from keymap.tool_levels(tool), i.e. from the Calc, Group,
field-metadata and TOOL_TOP declarations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import Screen
from textual.widgets import Footer, Input, Static, Tab, Tabs

from srsfe.core.params import FIELDS
from srsfe.tools.base import Calc, CalcInputError, Result, Tool
from srsfe.tui import keymap
from srsfe.tui.screens.dialogs import ConfirmDialog, PromptDialog
from srsfe.tui.widgets.eng_input import FieldRow
from srsfe.tui.widgets.field_group import FieldGroup
from srsfe.tui.widgets.header import AppHeader
from srsfe.tui.widgets.results_table import ResultsTable
from srsfe.tui.widgets.warnings_panel import WarningsPanel

if TYPE_CHECKING:
    from srsfe.tui.app import SrsfeApp


class ToolScreen(Screen[None]):
    DEFAULT_CSS = """
    ToolScreen Tabs { height: 2; }
    ToolScreen #body { height: 1fr; }
    ToolScreen #inputs { width: 58; border-right: solid $panel; }
    ToolScreen #right { width: 1fr; }
    ToolScreen #hints { height: auto; padding: 0 1; background: $panel; color: $text-muted; }
    """

    def __init__(self, tool: Tool) -> None:
        super().__init__()
        self.tool = tool
        self.calc: Calc = tool.calcs[0]
        self.level = "top"
        self.levels = {name: dict(keys) for name, keys in keymap.tool_levels(tool).items()}
        self.results: dict[str, Result] = {}

    @property
    def srsfe(self) -> SrsfeApp:
        return self.app  # type: ignore[return-value]

    # -- layout ------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield Tabs(*(Tab(keymap.hint(c.key, c.name), id=f"calc-{c.key}") for c in self.tool.calcs))
        with Horizontal(id="body"):
            with VerticalScroll(id="inputs"):
                for g in self.tool.groups:
                    yield FieldGroup(g, self.srsfe.params)
            with Vertical(id="right"):
                yield ResultsTable(id="results")
                yield WarningsPanel(id="warnings")
        yield Static(id="hints")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Tabs).can_focus = False
        self.select_calc(self.calc.key)
        self.call_after_refresh(self.set_focus, None)

    def on_screen_resume(self) -> None:
        # Back from Profiles: the active profile (and so the inputs) may have changed.
        for row in self.query(FieldRow):
            row.set_value(getattr(self.srsfe.params, row.field_name))
        self.apply_field_classes()

    # -- state -----------------------------------------------------------------------------

    def groups(self) -> list[FieldGroup]:
        return list(self.query(FieldGroup))

    def row(self, name: str) -> FieldRow:
        return self.query_one(f"#row-{name}", FieldRow)

    def select_calc(self, key: str) -> None:
        self.calc = self.tool.calc(key)
        self.query_one(Tabs).active = f"calc-{key}"
        self.apply_field_classes()
        required = set(self.calc.required)
        for g in self.groups():
            g.collapsed = not (required & set(g.group.fields))
        self.show_result()
        self.update_hints()

    def apply_field_classes(self) -> None:
        required, optional = set(self.calc.required), set(self.calc.optional)
        params = self.srsfe.params
        for row in self.query(FieldRow):
            n = row.field_name
            row.set_class(n in required, "required")
            row.set_class(n in required and getattr(params, n) is None, "missing")
            row.set_class(n in optional, "optional")
            row.set_class(n not in required and n not in optional, "unused")

    def show_result(self) -> None:
        result = self.results.get(self.calc.key)
        self.query_one(ResultsTable).show(self.calc, result)
        self.query_one(WarningsPanel).show(result)

    def update_hints(self) -> None:
        focused = self.focused
        if isinstance(focused, Input) and isinstance(focused.parent, FieldRow):
            name = focused.parent.field_name
            text = f"Editing {name} ({FIELDS[name].description}) — Enter or Esc to finish"
        elif isinstance(focused, ResultsTable):
            text = "Results — arrows to scroll · Esc back"
        elif self.level == "top":
            calcs = " ".join(str(keymap.hint(c.key, c.name)) for c in self.tool.calcs)
            acts = " ".join(f"[{keymap.display(k.key)}] {k.label}" for k in keymap.TOOL_TOP)
            groups = " ".join(str(keymap.hint(g.key, g.name)) for g in self.tool.groups)
            text = f"{calcs}\n{acts}\nGroups: {groups} · Esc back"
        else:
            g = self.current_group()
            fields = " ".join(str(keymap.hint(FIELDS[f].key, f)) for f in g.group.fields)
            text = f"{g.group.name}: {fields} · Esc up"
        self.query_one("#hints", Static).update(Content(text))

    def current_group(self) -> FieldGroup:
        return self.query_one(f"#group-{self.level.removeprefix('group:')}", FieldGroup)

    def set_level(self, level: str) -> None:
        self.level = level
        for g in self.groups():
            g.set_class(level == f"group:{g.group.key}", "current")
        self.update_hints()

    # -- keys ------------------------------------------------------------------------------

    async def on_key(self, event: events.Key) -> None:
        focused = self.focused
        if isinstance(focused, Input):
            if event.key == "escape":
                event.stop()
                self.finish_edit()
            return
        if event.key == "escape":
            event.stop()
            self.go_up()
            return
        target = self.levels[self.level].get(event.key)
        if target is not None:
            event.stop()
            await self.dispatch(target)

    async def dispatch(self, target: str) -> None:
        kind, _, arg = target.partition(":")
        if kind == "calc":
            self.select_calc(arg)
        elif kind == "group":
            self.enter_group(arg)
        elif kind == "field":
            self.edit_field(arg)
        else:
            await self.run_action(arg)

    def enter_group(self, key: str) -> None:
        group = self.query_one(f"#group-{key}", FieldGroup)
        group.collapsed = False
        if len(group.group.fields) == 1:  # single field → edit it directly
            self.set_level("top")
            self.edit_field(group.group.fields[0])
        else:
            self.set_level(f"group:{key}")
            group.scroll_visible()

    def edit_field(self, name: str) -> None:
        row = self.row(name)
        row.input.focus()
        row.input.select_all()
        self.call_after_refresh(self.update_hints)

    def finish_edit(self) -> None:
        self.set_focus(None)
        self.update_hints()

    def go_up(self) -> None:
        if isinstance(self.focused, ResultsTable):
            self.set_focus(None)
            self.update_hints()
        elif self.level != "top":
            self.set_level("top")
        else:
            self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.finish_edit()

    def on_field_row_edited(self, event: FieldRow.Edited) -> None:
        self.srsfe.set_params(self.srsfe.params.replace(**{event.name: event.value}))
        self.apply_field_classes()

    # -- actions ---------------------------------------------------------------------------

    def action_calculate(self) -> None:
        used = set(self.calc.required) | set(self.calc.optional)
        bad = {r.field_name: r.error for r in self.query(FieldRow)
               if r.error is not None and r.field_name in used}
        if bad:
            self.notify("Invalid: " + ", ".join(f"{k} ({v})" for k, v in bad.items()),
                        severity="error")
            return
        try:
            result = self.calc.run(self.srsfe.params)
        except CalcInputError as exc:
            self.notify(str(exc).capitalize(), title=f"{self.calc.name} not run",
                        severity="error")
            self.apply_field_classes()
            return
        self.results[self.calc.key] = result
        self.show_result()
        fired = sum(w.severity == "warn" for w in result.warnings)
        self.notify(f"{self.calc.name} calculated" + (f" — {fired} warning(s)" if fired else ""))

    def action_plots(self) -> None:
        from srsfe.tui.screens.plot_menu import PlotMenu

        result = self.results.get(self.calc.key)
        if result is None:
            self.notify("Calculate first (c or F5).", severity="warning")
            return
        self.app.push_screen(PlotMenu(result))

    def action_results(self) -> None:
        self.set_level("top")
        self.query_one(ResultsTable).focus()
        self.call_after_refresh(self.update_hints)

    def action_save(self) -> None:
        self.srsfe.save()

    def action_save_as(self) -> None:
        def done(name: str | None) -> None:
            if name:
                self.srsfe.save_as(name.strip())

        self.app.push_screen(PromptDialog("Save current inputs as new profile:"), done)

    def action_clear(self) -> None:
        """Unset every input of this tool (after confirmation); nothing is saved."""
        names = [f for g in self.tool.groups for f in g.fields]

        def done(yes: bool | None) -> None:
            if not yes:
                return
            self.srsfe.set_params(self.srsfe.params.replace(**dict.fromkeys(names)))
            for row in self.query(FieldRow):
                row.set_value(None)
            self.apply_field_classes()
            self.results.clear()
            self.show_result()
            self.notify(f"Cleared {len(names)} inputs (not saved).")

        self.app.push_screen(ConfirmDialog(
            f"Clear all {len(names)} inputs of {self.tool.name}? The profile is not "
            "changed on disk until you save."), done)

    def action_profiles(self) -> None:
        from srsfe.tui.screens.profiles import ProfilesScreen

        self.app.push_screen(ProfilesScreen())

    async def action_help(self) -> None:
        await self.app.run_action("help")

    async def action_quit(self) -> None:
        await self.app.run_action("quit")
