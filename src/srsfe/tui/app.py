"""SRS-FE Textual app: active profile, dirty flag, save/quit (SPEC §7, §8)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual.app import App
from textual.reactive import reactive

from srsfe.core.params import Params
from srsfe.core.profiles import DEFAULT_PROFILE, Profile, ProfileError, ProfileStore
from srsfe.tools.designmap import MapSettings
from srsfe.tui import keymap
from srsfe.tui import settings as user_settings
from srsfe.tui.screens.dialogs import UnsavedChoice, UnsavedDialog
from srsfe.tui.screens.help import HelpScreen, Section
from srsfe.tui.screens.launcher import LauncherScreen

TITLE = "SRS-FE"


class SrsfeApp(App[None]):
    TITLE = TITLE
    BINDINGS = keymap.bindings(keymap.GLOBAL)

    header_text: reactive[str] = reactive("")

    def __init__(
        self,
        profiles_dir: str | Path | None = None,
        plots_dir: str | Path = "plots",
        settings_path: Path | None = None,
    ) -> None:
        """profiles_dir overrides the settings file. settings_path None = keep settings in
        memory only (tests); `python -m srsfe` passes the user settings file."""
        super().__init__()
        self.settings_path = settings_path
        self.settings = (user_settings.load(settings_path) if settings_path is not None
                         else user_settings.Settings())
        if profiles_dir is not None:
            self.settings.profiles_dir = str(profiles_dir)
        self.store = ProfileStore(self.settings.profiles_dir)
        self.plots_dir = Path(plots_dir)
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
        self._remember()
        for issue in prof.issues:
            self.notify(f"{prof.name}: {issue}", severity="warning")

    def _remember(self) -> None:
        """Persist the active profile as last-used (SPEC §7)."""
        self.settings.last_profile = self.profile_name
        self._persist_settings()

    def _persist_settings(self) -> None:
        if self.settings_path is not None:
            try:
                user_settings.save(self.settings, self.settings_path)
            except OSError as exc:
                self.notify(f"settings not saved: {exc}", severity="warning")

    @property
    def map_settings(self) -> MapSettings:
        """Map settings from the settings file (defaults for missing or bad values)."""
        return MapSettings.from_dict(self.settings.map)

    def set_map_settings(self, ms: MapSettings) -> None:
        """Store Map settings in the settings file (SPEC §6.5: saved on compute)."""
        self.settings.map = ms.to_dict()
        self._persist_settings()

    def open_start_profile(self) -> None:
        """Last-used profile if it still exists, else default.json (created if missing)."""
        last = self.settings.last_profile
        try:
            if last and self.store.exists(last):
                self._activate(self.store.load(last))
                return
        except ProfileError as exc:
            self.notify(f"last profile '{last}' unreadable: {exc}", severity="warning")
        try:
            self._activate(self.store.ensure_default())
        except ProfileError as exc:
            self.notify(f"default profile unreadable: {exc}", severity="error")
            self._update_header()

    def on_mount(self) -> None:
        self.open_start_profile()
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
            self._remember()
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

    def change_profiles_dir(self, folder: str) -> None:
        """Switch the profiles folder (Settings); asks about unsaved changes first."""

        def go() -> None:
            try:
                Path(folder).mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.notify(f"cannot use '{folder}': {exc}", severity="error")
                return
            self.store = ProfileStore(folder)
            self.settings.profiles_dir = folder
            self.open_start_profile()  # saves settings via _activate
            self.notify(f"Profiles folder: {folder}")

        self.guard_unsaved("switching the profiles folder", go)

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

    def action_calculate(self) -> None:
        """F5: calculate on the tool screen; nothing elsewhere."""
        calculate = getattr(self.screen, "action_calculate", None)
        if calculate is not None:
            calculate()

    def action_help(self) -> None:
        """F1 / ?: toggle the help overlay for the current screen."""
        if isinstance(self.screen, HelpScreen):
            self.screen.dismiss()
            return
        provider = getattr(self.screen, "help_sections", None)
        sections: list[Section] = provider() if callable(provider) else []
        self.push_screen(HelpScreen(type(self.screen).__name__.removesuffix("Screen"), sections))

    async def action_quit(self) -> None:
        self.guard_unsaved("quitting", self.exit)
