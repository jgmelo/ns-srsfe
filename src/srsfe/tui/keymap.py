"""Screen-level key tables (SPEC §8.3). Field keys live in field metadata (core/params.py),
group keys in Group, tool keys in Tool; screens build their bindings from these tables
and never hard-code a key."""

from __future__ import annotations

from dataclasses import dataclass

from textual.binding import Binding
from textual.content import Content

from srsfe.tools.base import Tool


@dataclass(frozen=True)
class Key:
    key: str
    action: str
    label: str
    show: bool = True
    priority: bool = False  # True: active even while typing in an input


# Always active (even while typing). Esc (up/back) is handled per screen; Ctrl+P is
# Textual's command palette.
GLOBAL = (
    Key("f1", "help", "Help", priority=True),
    Key("f5", "calculate", "Calculate", priority=True),
    Key("ctrl+s", "save", "Save", priority=True),
    Key("ctrl+q", "quit", "Quit", priority=True),
)
RESERVED = ("f1", "f5", "ctrl+s", "ctrl+q", "ctrl+p")

# Tool screen, top level (calc keys come from Calc.key, group keys from Group.key).
TOOL_TOP = (
    Key("c", "calculate", "Calculate"),
    Key("p", "plots", "Plots"),
    Key("v", "results", "Results"),
    Key("s", "save", "Save"),
    Key("w", "save_as", "Save as"),
    Key("o", "profiles", "Profiles"),
    Key("question_mark", "help", "Help"),
    Key("q", "quit", "Quit"),
)

# Plot menu (plot toggle keys come from tools.base.PLOT_KEYS).
PLOT_MENU = (
    Key("enter", "show", "Show", priority=True),
    Key("v", "save", "Save PNG", priority=True),
    Key("escape", "close", "Close", priority=True),
)

# Launcher (tool keys come from the registry: Tool.key).
LAUNCHER = (
    Key("w", "sweep", "Sweep (later)"),
    Key("o", "profiles", "Profiles"),
    Key("t", "settings", "Settings"),
    Key("q", "quit", "Quit"),
)

PROFILES = (
    Key("l", "load", "Load"),
    Key("n", "new", "New"),
    Key("d", "duplicate", "Duplicate"),
    Key("r", "rename", "Rename"),
    Key("e", "edit_notes", "Notes"),
    Key("x", "delete", "Delete"),
    Key("escape", "back", "Back"),
)

UNSAVED = (
    Key("s", "save", "Save"),
    Key("d", "discard", "Discard"),
    Key("c", "cancel", "Cancel"),
    Key("escape", "cancel", "Cancel", show=False),
)

DELETE = (
    Key("y", "yes", "Yes"),
    Key("n", "no", "No"),
    Key("escape", "no", "No", show=False),
)

PROMPT = (Key("escape", "cancel", "Cancel"),)

BACK = (Key("escape", "back", "Back"),)


def bindings(keys: tuple[Key, ...]) -> list[Binding]:
    return [Binding(k.key, k.action, k.label, show=k.show, priority=k.priority) for k in keys]


def hint(key: str, label: str) -> Content:
    """Key hint shown next to an option, e.g. "[r] r_f" (plain text, not markup)."""
    return Content(f"[{key}] {label}")


def hints(keys: tuple[Key, ...]) -> Content:
    """One line of key hints for the shown keys: "[s] Save  ·  [d] Discard  ·  …"."""
    return Content("  ·  ".join(f"[{display(k.key)}] {k.label}" for k in keys if k.show))


def display(key: str) -> str:
    """How a key name is shown in hints."""
    return {"question_mark": "?", "escape": "Esc", "enter": "Enter"}.get(key, key)


def tool_levels(tool: Tool) -> dict[str, list[tuple[str, str]]]:
    """Every key level of a tool screen: "top" and one "group:<key>" per group.
    Each level is an ordered list of (key, target); targets are "calc:<key>",
    "group:<key>", "field:<name>" or "action:<name>". Used by the screen to dispatch
    keys and by test_keymap.py to check collisions."""
    from srsfe.core.params import FIELDS

    top = [(c.key, f"calc:{c.key}") for c in tool.calcs]
    top += [(k.key, f"action:{k.action}") for k in TOOL_TOP]
    top += [(g.key, f"group:{g.key}") for g in tool.groups]
    levels = {"top": top}
    for g in tool.groups:
        levels[f"group:{g.key}"] = [(FIELDS[f].key, f"field:{f}") for f in g.fields]
    return levels
