"""Profiles screen (SPEC §8.1): table of name, modified, notes; load/new/duplicate/rename/
notes/delete."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.content import Content
from textual.screen import Screen
from textual.widgets import DataTable, Footer

from srsfe.core.profiles import ProfileError
from srsfe.tui import keymap
from srsfe.tui.screens.dialogs import DeleteDialog, PromptDialog
from srsfe.tui.widgets.header import AppHeader

if TYPE_CHECKING:
    from srsfe.tui.app import SrsfeApp


class ProfilesScreen(Screen[None]):
    BINDINGS = keymap.bindings(keymap.PROFILES)

    @property
    def srsfe(self) -> SrsfeApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("name", "modified", "notes")
        self.refresh_table(select=self.srsfe.profile_name)

    def refresh_table(self, select: str | None = None) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for info in self.srsfe.store.list():
            mark = " ◂ active" if info.name == self.srsfe.profile_name else ""
            table.add_row(Content(info.name + mark), info.modified.replace("T", " "),
                          Content(info.notes), key=info.name)
        if select is not None and select in table.rows:
            table.move_cursor(row=table.get_row_index(select))

    def selected(self) -> str | None:
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        return table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value

    # -- actions -----------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_load()

    def action_load(self) -> None:
        name = self.selected()
        if name is not None:
            self.srsfe.request_load(name, on_done=lambda: self.refresh_table(select=name))

    def action_new(self) -> None:
        def done(name: str | None) -> None:
            if name and self.srsfe.save_as(name.strip()):
                self.refresh_table(select=name.strip())

        self.app.push_screen(PromptDialog("Save current inputs as new profile:"), done)

    def action_duplicate(self) -> None:
        src = self.selected()
        if src is None:
            return

        def done(name: str | None) -> None:
            if name and self._try(lambda: self.srsfe.store.duplicate(src, name.strip())):
                self.refresh_table(select=name.strip())

        self.app.push_screen(PromptDialog(f"Duplicate '{src}' as:", f"{src}_copy"), done)

    def action_rename(self) -> None:
        old = self.selected()
        if old is None:
            return

        def done(name: str | None) -> None:
            if name and self.srsfe.rename(old, name.strip()):
                self.refresh_table(select=name.strip())

        self.app.push_screen(PromptDialog(f"Rename '{old}' to:", old), done)

    def action_edit_notes(self) -> None:
        name = self.selected()
        if name is None:
            return
        try:
            notes = self.srsfe.store.load(name).notes
        except ProfileError as exc:
            self.app.notify(str(exc), severity="error")
            return

        def done(text: str | None) -> None:
            if text is not None and self.srsfe.set_notes(name, text):
                self.refresh_table(select=name)

        self.app.push_screen(PromptDialog(f"Notes for '{name}':", notes), done)

    def action_delete(self) -> None:
        name = self.selected()
        if name is None:
            return
        if name == self.srsfe.profile_name:
            self.app.notify("Cannot delete the active profile; load another one first.",
                            severity="warning")
            return

        def done(yes: bool | None) -> None:
            if yes and self._try(lambda: self.srsfe.store.delete(name)):
                self.refresh_table()

        self.app.push_screen(DeleteDialog(name), done)

    def action_back(self) -> None:
        self.app.pop_screen()

    def _try(self, op: object) -> bool:
        try:
            op()  # type: ignore[operator]
        except ProfileError as exc:
            self.app.notify(str(exc), severity="error")
            return False
        return True
