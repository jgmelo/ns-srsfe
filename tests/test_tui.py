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
        assert prompts[:3] == ["[d] Design from t_dwell", "[b] Buy (vendor detector)",
                               "[a] Analyze existing tank"]
        assert {"[o] Profiles", "[t] Settings", "[q] Quit"} <= set(prompts)


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "launcher")
async def test_launcher_keys_open_screens(pdir: Path) -> None:
    """d / a open the tool screen, o opens Profiles, Esc returns to the launcher."""
    app = SrsfeApp(pdir)
    async with app.run_test() as pilot:
        for key, kind in (("d", ToolScreen), ("b", ToolScreen), ("a", ToolScreen),
                          ("o", ProfilesScreen)):
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


# -- tool screen (M9) ------------------------------------------------------------------------

from textual.widgets import Tabs  # noqa: E402

from srsfe.tools.base import Result  # noqa: E402
from srsfe.tui.screens import plot_menu  # noqa: E402
from srsfe.tui.screens.plot_menu import PlotMenu  # noqa: E402
from srsfe.tui.widgets.eng_input import FieldRow  # noqa: E402
from srsfe.tui.widgets.field_group import FieldGroup  # noqa: E402
from srsfe.tui.widgets.results_table import ResultsTable  # noqa: E402
from srsfe.tui.widgets.warnings_panel import WarningsPanel  # noqa: E402


def row(app: SrsfeApp, name: str) -> FieldRow:
    return app.screen.query_one(f"#row-{name}", FieldRow)


def results(app: SrsfeApp) -> list[str]:
    table = app.screen.query_one(ResultsTable)
    return [str(r.value) for r in table.rows]


async def open_golden(app: SrsfeApp, pilot, tool: str = "d") -> None:  # type: ignore[no-untyped-def]
    app.load("golden")
    await pilot.press(tool)
    await pilot.pause()


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "tool-screen")
async def test_tool_screen_built_from_declaration(pdir: Path) -> None:
    """Calc tabs, groups and field rows come from the Tool; calc keys switch the highlighting."""
    app = SrsfeApp(pdir, pdir / "plots")
    async with app.run_test(size=(150, 50)) as pilot:
        await open_golden(app, pilot)
        tabs = app.screen.query_one(Tabs)
        assert tabs.active == "calc-1"
        assert [g.group.key for g in app.screen.query(FieldGroup)] == ["t", "l", "n", "i", "m", "f"]
        assert row(app, "r_f").has_class("required") and row(app, "q_mode").has_class("optional")
        assert row(app, "p_min").has_class("unused")
        groups = {g.group.key: g for g in app.screen.query(FieldGroup)}
        assert not groups["t"].collapsed and groups["l"].collapsed
        await pilot.press("4")
        assert tabs.active == "calc-4" and row(app, "m").has_class("required")
        assert row(app, "en_moku").has_class("optional") and not groups["n"].collapsed


@pytest.mark.smoke
@pytest.mark.spec("§8.3", "navigation")
@pytest.mark.spec("§8.1", "eng-input")
async def test_group_field_navigation_and_editing(pdir: Path) -> None:
    """t enters Tank, r edits r_f; '47k' is stored as 47e3 SI; Esc climbs back to the launcher."""
    app = SrsfeApp(pdir, pdir / "plots")
    async with app.run_test(size=(150, 50)) as pilot:
        await open_golden(app, pilot)
        screen = app.screen
        await pilot.press("t")
        assert screen.level == "group:t"  # type: ignore[attr-defined]
        await pilot.press("r")
        assert app.focused is row(app, "r_f").input
        await type_text(pilot, "47k")
        await pilot.pause()
        assert app.params.r_f == 47e3 and header(app).endswith("golden*")
        await pilot.press("q")  # typed into the input, not "quit"
        assert row(app, "r_f").has_class("invalid") and app.is_running
        await pilot.press("backspace", "escape")
        assert app.focused is None and screen.level == "group:t"  # type: ignore[attr-defined]
        await pilot.press("escape")
        assert screen.level == "top"  # type: ignore[attr-defined]
        await pilot.press("escape")
        assert isinstance(app.screen, LauncherScreen)


@pytest.mark.smoke
@pytest.mark.spec("§8.3", "navigation")
async def test_single_field_group_edits_directly(pdir: Path) -> None:
    """The Spectrum group (only f_max) jumps straight into editing f_max."""
    app = SrsfeApp(pdir, pdir / "plots")
    async with app.run_test(size=(150, 50)) as pilot:
        await open_golden(app, pilot)
        await pilot.press("f")
        assert app.focused is row(app, "f_max").input


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "tool-screen")
@pytest.mark.spec("§6.1", "all")
async def test_calculate_fills_results_and_warnings(pdir: Path) -> None:
    """0 then c runs Design/All on golden: results table and the four golden warnings."""
    app = SrsfeApp(pdir, pdir / "plots")
    async with app.run_test(size=(150, 50)) as pilot:
        await open_golden(app, pilot)
        await pilot.press("0", "c")
        await pilot.pause()
        labels = results(app)
        assert labels[0] == "q" and "v_coh" in labels and "snr_lia" in labels
        text = str(app.screen.query_one(WarningsPanel).render())
        assert text.count("W04") == 2 and "W03 · P_max" in text


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "calc-validates", "eng-invalid")
async def test_calculate_validates_first(pdir: Path) -> None:
    """Missing required → error toast, nothing runs, field marked; invalid text blocks too."""
    app = SrsfeApp(pdir, pdir / "plots")
    async with app.run_test(size=(150, 50)) as pilot:
        await open_golden(app, pilot)
        await pilot.press("t", "d", "backspace", "escape", "escape", "c")  # entry selects all
        await pilot.pause()
        assert app.params.t_dwell is None and row(app, "t_dwell").has_class("missing")
        assert results(app) == []
        assert any("t_dwell" in n.message for n in app._notifications)
        await pilot.press("t", "d")
        await type_text(pilot, "1x")
        await pilot.press("escape", "escape", "c")
        await pilot.pause()
        assert row(app, "t_dwell").has_class("invalid") and results(app) == []
        assert any("Invalid" in n.message for n in app._notifications)


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "tool-screen")
async def test_f5_calculates_while_typing(pdir: Path) -> None:
    """F5 is always active: it calculates even with focus in an input."""
    app = SrsfeApp(pdir, pdir / "plots")
    async with app.run_test(size=(150, 50)) as pilot:
        await open_golden(app, pilot)
        await pilot.press("t", "n")  # entering selects all
        await type_text(pilot, "4")
        await pilot.press("f5")
        await pilot.pause()
        assert "q" in results(app)
        assert app.screen.results["1"].get("q") == pytest.approx(15.708, rel=1e-4)  # type: ignore[attr-defined]


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "tool-screen")
@pytest.mark.spec("§6.2", "outputs")
async def test_analyze_tool_screen(pdir: Path) -> None:
    """Analyze: enter L and C by key, calculate, read f0_calc."""
    app = SrsfeApp(pdir, pdir / "plots")
    async with app.run_test(size=(150, 50)) as pilot:
        await open_golden(app, pilot, "a")
        await pilot.press("t", "l")
        await type_text(pilot, "63.3257u")
        await pilot.press("escape", "c")
        await type_text(pilot, "1p")
        await pilot.press("escape", "escape", "c")
        await pilot.pause()
        assert "f0_calc" in results(app) and "settles" in results(app)


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "plot-menu")
async def test_plot_menu_show_and_save(pdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """p needs a result; the menu lists available plots, b/s/u/n toggle, Enter shows, v saves."""
    shown: list[list[str]] = []
    monkeypatch.setattr(plot_menu, "launch", lambda result, plots: shown.append(plots))
    app = SrsfeApp(pdir, pdir / "plots")
    async with app.run_test(size=(150, 50)) as pilot:
        await open_golden(app, pilot)
        await pilot.press("0", "p")
        assert not isinstance(app.screen, PlotMenu)  # nothing calculated yet
        await pilot.press("c", "p")
        assert isinstance(app.screen, PlotMenu)
        assert app.screen.selected == ["bode", "spectrum", "budget", "noise"]
        await pilot.press("s", "u", "n", "enter")
        assert shown == [["bode"]] and not isinstance(app.screen, PlotMenu)
        await pilot.press("p", "b", "s", "u", "v")
        await pilot.pause()
        assert (pdir / "plots" / "golden_noise.png").is_file()
        assert not (pdir / "plots" / "golden_bode.png").exists()
        await pilot.press("p", "escape")
        assert not isinstance(app.screen, PlotMenu)


@pytest.mark.smoke
@pytest.mark.spec("§8.3", "navigation")
async def test_top_level_actions(pdir: Path) -> None:
    """v focuses results (Esc back); s saves; w saves as; o opens Profiles and reloads inputs."""
    app = SrsfeApp(pdir, pdir / "plots")
    async with app.run_test(size=(150, 50)) as pilot:
        await open_golden(app, pilot)
        await pilot.press("v")
        assert isinstance(app.focused, ResultsTable)
        await pilot.press("escape")
        assert app.focused is None and app.screen.level == "top"  # type: ignore[attr-defined]
        app.set_params(app.params.replace(r_f=33e3))
        await pilot.press("s")
        await pilot.pause()
        assert ProfileStore(pdir).load("golden").params.r_f == 33e3
        await pilot.press("w")
        await type_text(pilot, "variant")
        await pilot.press("enter")
        await pilot.pause()
        assert app.profile_name == "variant"
        await pilot.press("o")
        assert isinstance(app.screen, ProfilesScreen)
        await pilot.press("up", "up", "l")  # cursor starts on the active "variant"; up twice → "default"
        await pilot.pause()
        assert app.profile_name == "default"
        await pilot.press("escape")  # back to the tool screen: inputs show the loaded profile
        await pilot.pause()
        assert row(app, "r_f").input.value == "100k" and row(app, "en_moku").input.value == "30n"
