"""Launcher (SPEC §8.1): tools from the registry + Profiles + Settings; description right."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.content import Content
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from srsfe.tools import REGISTRY
from srsfe.tui import keymap
from srsfe.tui.widgets.header import AppHeader

DESCRIPTIONS = {
    "sweep": "Sweep one input over a list of values and tabulate outputs. "
             "The sweep engine exists; its screen comes in a later version.",
    "profiles": "Load, create, duplicate, rename, annotate or delete profiles "
                "(one JSON file per profile).",
    "settings": "Profiles folder and other preferences.",
    "quit": "Leave SRS-FE (asks first if the profile has unsaved changes).",
}


class LauncherScreen(Screen[None]):
    DEFAULT_CSS = """
    LauncherScreen Horizontal { height: 1fr; }
    LauncherScreen OptionList { width: 40; height: 1fr; }
    LauncherScreen #description { width: 1fr; padding: 1 2; }
    """
    BINDINGS = [
        *(Binding(t.key, f"open_tool('{t.key}')", t.name.split()[0]) for t in REGISTRY.values()),
        *keymap.bindings(keymap.LAUNCHER),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        options = [Option(keymap.hint(t.key, t.name), id=f"tool:{t.key}") for t in REGISTRY.values()]
        options += [
            Option(keymap.hint(k.key, k.label), id=k.action, disabled=k.action == "sweep")
            for k in keymap.LAUNCHER
        ]
        with Horizontal():
            yield OptionList(*options, id="menu")
            yield Static(id="description")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(OptionList).highlighted = 0

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self.query_one("#description", Static).update(Content(self._describe(event.option.id or "")))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id or ""
        if oid.startswith("tool:"):
            self.action_open_tool(oid.removeprefix("tool:"))
        else:
            self.run_action(oid)

    @staticmethod
    def _describe(oid: str) -> str:
        if oid.startswith("tool:"):
            tool = REGISTRY[oid.removeprefix("tool:")]
            calcs = "\n".join(f"  [{c.key}] {c.name}" for c in tool.calcs)
            return f"{tool.name}\n\n{tool.description}\n\nCalculations:\n{calcs}"
        return DESCRIPTIONS.get(oid, "")

    def action_open_tool(self, key: str) -> None:
        from srsfe.tui.screens.tool_screen import ToolScreen

        self.app.push_screen(ToolScreen(REGISTRY[key]))

    def action_profiles(self) -> None:
        from srsfe.tui.screens.profiles import ProfilesScreen

        self.app.push_screen(ProfilesScreen())

    def action_settings(self) -> None:
        self.app.notify("Settings screen arrives in M10.")

    def action_sweep(self) -> None:
        self.app.notify("Sweep has no screen yet (core engine only in v1).")

    async def action_quit(self) -> None:
        await self.app.run_action("quit")
