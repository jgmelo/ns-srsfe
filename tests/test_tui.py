"""M8: TUI shell smoke tests with App.run_test() (SPEC §7, §8.1)."""

import json
import shutil
from pathlib import Path

import pytest
from textual.widgets import DataTable, Input, OptionList

from srsfe.core.params import Params
from srsfe.core.profiles import ProfileStore
from srsfe.tui.app import SrsfeApp
from srsfe.tui.screens.dialogs import DeleteDialog, PromptDialog, UnsavedDialog
from srsfe.tui.screens.launcher import LauncherScreen
from srsfe.tui.screens.profiles import ProfilesScreen
from srsfe.tui.screens.tool_screen import ToolScreen
from srsfe.tui.widgets.header import AppHeader
from tests.conftest import GOLDEN_PATH


@pytest.fixture
def pdir(tmp_path: Path) -> Path:
    d = tmp_path / "profiles"
    d.mkdir()
    shutil.copy(GOLDEN_PATH, d / "golden.json")
    return d


def header(app: SrsfeApp) -> str:
    return str(app.screen.query_one(AppHeader).render())


async def type_text(pilot, text: str) -> None:  # type: ignore[no-untyped-def]
    for ch in text:
        await pilot.press(ch)


# -- app / header / launcher -------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "launcher")
@pytest.mark.spec("§7", "default-profile")
async def test_starts_on_launcher_with_default_profile(pdir: Path) -> None:
    """The app opens the launcher; default.json is created from defaults; header names it."""
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LauncherScreen)
        assert (pdir / "default.json").is_file() and app.params == Params()
        assert header(app) == "SRS-FE │ profile: default"
        prompts = [str(o.prompt) for o in app.screen.query_one(OptionList).options]
        assert prompts[:2] == ["[d] Design from t_dwell", "[a] Analyze existing tank"]
        assert {"[o] Profiles", "[t] Settings", "[q] Quit"} <= set(prompts)


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "launcher")
async def test_launcher_keys_open_screens(pdir: Path) -> None:
    """d / a open the tool screen, o opens Profiles, Esc returns to the launcher."""
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        for key, kind in (("d", ToolScreen), ("a", ToolScreen), ("o", ProfilesScreen)):
            await pilot.press(key)
            assert isinstance(app.screen, kind)
            await pilot.press("escape")
            assert isinstance(app.screen, LauncherScreen)
        await pilot.press("a")
        assert app.screen.tool.key == "a"  # type: ignore[attr-defined]


@pytest.mark.smoke
@pytest.mark.spec("§7", "dirty-flag")
async def test_dirty_flag_and_save(pdir: Path) -> None:
    """Editing inputs adds * to the header; Ctrl+S saves the profile and clears it."""
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        app.set_params(app.params.replace(r_f=10e3))
        await pilot.pause()
        assert header(app).endswith("default*")
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert header(app).endswith("default") and not app.dirty
        assert ProfileStore(pdir).load("default").params.r_f == 10e3


# -- quit / unsaved dialog -----------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "dialogs")
@pytest.mark.spec("§7", "dirty-flag")
async def test_quit_prompts_when_dirty(pdir: Path) -> None:
    """Quitting with unsaved changes asks: c cancels, d discards and quits."""
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        app.set_params(app.params.replace(r_f=10e3))
        await pilot.press("q")
        assert isinstance(app.screen, UnsavedDialog)
        await pilot.press("c")
        assert isinstance(app.screen, LauncherScreen) and app.is_running
        await pilot.press("ctrl+q")
        assert isinstance(app.screen, UnsavedDialog)
        await pilot.press("d")
        await pilot.pause()
    assert not app.is_running
    assert ProfileStore(pdir).load("default").params.r_f == 100e3  # discarded


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "dialogs")
async def test_quit_save_then_exit(pdir: Path) -> None:
    """In the unsaved dialog, s saves the profile and then quits; a clean app quits at once."""
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        app.set_params(app.params.replace(m=2e-5))
        await pilot.press("ctrl+q")
        await pilot.press("s")
        await pilot.pause()
    assert not app.is_running
    assert ProfileStore(pdir).load("default").params.m == 2e-5

    clean = SrsfeApp(pdir)
    async with clean.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
    assert not clean.is_running


# -- profiles screen ---------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "profiles")
async def test_profiles_table_and_load(pdir: Path) -> None:
    """Profiles lists name/modified/notes; l (or Enter) loads the highlighted profile."""
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        await pilot.press("o")
        table = app.screen.query_one(DataTable)
        assert [str(c.label) for c in table.columns.values()] == ["name", "modified", "notes"]
        assert list(r.value for r in table.rows) == ["default", "golden"]
        await pilot.press("down", "l")
        await pilot.pause()
        assert app.profile_name == "golden" and app.params.en_moku == 30e-9
        assert header(app) == "SRS-FE │ profile: golden"
        await pilot.press("up", "enter")
        await pilot.pause()
        assert app.profile_name == "default"


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "profiles", "dialogs")
@pytest.mark.spec("§7", "dirty-flag")
async def test_switching_profile_prompts_when_dirty(pdir: Path) -> None:
    """Loading another profile with unsaved changes asks first; c keeps the current one."""
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        app.set_params(app.params.replace(r_f=1e3))
        await pilot.press("o", "down", "l")
        assert isinstance(app.screen, UnsavedDialog)
        await pilot.press("c")
        assert app.profile_name == "default" and app.dirty
        await pilot.press("l", "d")
        await pilot.pause()
        assert app.profile_name == "golden" and not app.dirty


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "profiles", "dialogs")
async def test_profiles_new_duplicate_rename_notes_delete(pdir: Path) -> None:
    """n, d, r, e and x drive the profile store through prompt and delete dialogs."""
    app = SrsfeApp(pdir)
    store = ProfileStore(pdir)
    async with app.run_test() as pilot:
        await pilot.press("o", "n")
        assert isinstance(app.screen, PromptDialog)
        await type_text(pilot, "mine")
        await pilot.press("enter")
        await pilot.pause()
        assert app.profile_name == "mine" and store.exists("mine")

        await pilot.press("d")  # duplicate the highlighted (active) profile
        app.screen.query_one(Input).value = "mine2"
        await pilot.press("enter")
        await pilot.pause()
        assert store.exists("mine2")

        await pilot.press("r")
        app.screen.query_one(Input).value = "ours"
        await pilot.press("enter")
        await pilot.pause()
        assert store.exists("ours") and not store.exists("mine2")

        await pilot.press("e")
        app.screen.query_one(Input).value = "lab bench"
        await pilot.press("enter")
        await pilot.pause()
        assert store.load("ours").notes == "lab bench"

        await pilot.press("x")
        assert isinstance(app.screen, DeleteDialog)
        await pilot.press("n")
        assert store.exists("ours")
        await pilot.press("x", "y")
        await pilot.pause()
        assert not store.exists("ours")
        assert isinstance(app.screen, ProfilesScreen)


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "profiles")
async def test_cannot_delete_active_and_prompt_escape(pdir: Path) -> None:
    """The active profile cannot be deleted; Esc in a prompt cancels without changes."""
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        await pilot.press("o", "x")
        assert isinstance(app.screen, ProfilesScreen)  # no dialog for the active profile
        assert ProfileStore(pdir).exists("default")
        await pilot.press("n", "escape")
        assert isinstance(app.screen, ProfilesScreen)
        assert sorted(p.name for p in pdir.iterdir()) == ["default.json", "golden.json"]


@pytest.mark.smoke
@pytest.mark.spec("§7", "unknown-keys")
async def test_load_issues_are_notified(pdir: Path) -> None:
    """Loading a profile with unknown keys works and raises a warning notification."""
    doc = json.loads(GOLDEN_PATH.read_text())
    doc["params"]["q"] = 12.5
    (pdir / "odd.json").write_text(json.dumps(doc))
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        assert app.load("odd")
        await pilot.pause()
        assert app.profile_name == "odd"
        assert any("'q'" in n.message for n in app._notifications)
