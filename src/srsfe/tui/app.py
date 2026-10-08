"""SRS-FE Textual app: active profile, dirty flag, save/quit (SPEC §7, §8)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual.app import App
from textual.reactive import reactive

from srsfe.core.params import Params
from srsfe.core.profiles import DEFAULT_PROFILE, Profile, ProfileError, ProfileStore
from srsfe.tui import keymap
from srsfe.tui.screens.dialogs import UnsavedChoice, UnsavedDialog
from srsfe.tui.screens.launcher import LauncherScreen

TITLE = "SRS-FE"


class SrsfeApp(App[None]):
    TITLE = TITLE
    BINDINGS = keymap.bindings(keymap.GLOBAL)

    header_text: reactive[str] = reactive("")

    def __init__(self, profiles_dir: str | Path = "profiles") -> None:
        super().__init__()
        self.store = ProfileStore(profiles_dir)
        self.profile_name = DEFAULT_PROFILE
        self.notes = ""
        self.params = Params()
        self.saved_params = Params()

    # -- state -------------------------------------------------------------------------

    @property
    def dirty(self) -> bool:
        return self.params != self.saved_params

    def set_params(self, params: Params) -> None:
        """Replace the working inputs (the tool screen calls this on every edit)."""
        self.params = params
        self._update_header()

    def _update_header(self) -> None:
        self.header_text = f"{TITLE} │ profile: {self.profile_name}{'*' if self.dirty else ''}"

    def _activate(self, prof: Profile) -> None:
        self.profile_name, self.notes = prof.name, prof.notes
        self.params = self.saved_params = prof.params
        self._update_header()
        for issue in prof.issues:
            self.notify(f"{prof.name}: {issue}", severity="warning")

    def on_mount(self) -> None:
        # Last-used profile arrives in M10; until then always the default profile.
        try:
            self._activate(self.store.ensure_default())
        except ProfileError as exc:
            self.notify(f"default profile unreadable: {exc}", severity="error")
            self._update_header()
        self.push_screen(LauncherScreen())

    # -- profile operations ----------------------------------------------------------------

    def save(self) -> bool:
        try:
            self.store.save(self.params, self.profile_name)
        except ProfileError as exc:
            self.notify(str(exc), severity="error")
            return False
        self.saved_params = self.params
        self._update_header()
        self.notify(f"Saved profile '{self.profile_name}'.")
        return True

    def save_as(self, name: str) -> bool:
        try:
            prof = self.store.save_as(self.params, name, self.notes)
        except ProfileError as exc:
            self.notify(str(exc), severity="error")
            return False
        self._activate(prof)
        return True

    def load(self, name: str) -> bool:
        try:
            prof = self.store.load(name)
        except ProfileError as exc:
            self.notify(str(exc), severity="error")
            return False
        self._activate(prof)
        return True

    def rename(self, old: str, new: str) -> bool:
        try:
            prof = self.store.rename(old, new)
        except ProfileError as exc:
            self.notify(str(exc), severity="error")
            return False
        if old == self.profile_name:
            self.profile_name = prof.name
            self._update_header()
        return True

    def set_notes(self, name: str, notes: str) -> bool:
        """Change a profile's notes on disk without touching its params or the working set."""
        try:
            prof = self.store.load(name)
            self.store.save(prof.params, name, notes=notes)
        except ProfileError as exc:
            self.notify(str(exc), severity="error")
            return False
        if name == self.profile_name:
            self.notes = notes
        return True

    def guard_unsaved(self, doing: str, then: Callable[[], None]) -> None:
        """Run `then` now if clean; otherwise ask save / discard / cancel first."""
        if not self.dirty:
            then()
            return

        def done(choice: UnsavedChoice | None) -> None:
            if choice == "save" and self.save():
                then()
            elif choice == "discard":
                then()

        self.push_screen(UnsavedDialog(self.profile_name, doing), done)

    def request_load(self, name: str, on_done: Callable[[], None] | None = None) -> None:
        def go() -> None:
            if self.load(name) and on_done is not None:
                on_done()

        if name == self.profile_name and not self.dirty:
            self.notify(f"'{name}' is already loaded.")
            return
        self.guard_unsaved(f"loading '{name}'", go)

    # -- actions -----------------------------------------------------------------------

    def action_save(self) -> None:
        self.save()

    async def action_quit(self) -> None:
        self.guard_unsaved("quitting", self.exit)
