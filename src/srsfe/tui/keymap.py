"""Screen-level key tables (SPEC §8.3). Field keys live in field metadata (core/params.py),
group keys in Group, tool keys in Tool; screens build their bindings from these tables
and never hard-code a key."""

from __future__ import annotations

from dataclasses import dataclass

from textual.binding import Binding
from textual.content import Content


@dataclass(frozen=True)
class Key:
    key: str
    action: str
    label: str
    show: bool = True
    priority: bool = False  # True: active even while typing in an input


# Always active (even while typing). F1 help and F5 calculate join in M9/M10.
GLOBAL = (
    Key("ctrl+s", "save", "Save", priority=True),
    Key("ctrl+q", "quit", "Quit", priority=True),
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
    return Content("  ·  ".join(f"[{k.key}] {k.label}" for k in keys if k.show))
