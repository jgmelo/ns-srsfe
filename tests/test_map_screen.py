"""M13: Map screen — settings, compute, boundary table, plot / save, persistence (SPEC §8.1)."""

import shutil
from pathlib import Path

import pytest
from textual.widgets import DataTable, Input

from srsfe.tools.designmap import MapSettings, parse_setting
from srsfe.tui import settings as user_settings
from srsfe.tui.app import SrsfeApp
from srsfe.tui.screens import plot_menu
from srsfe.tui.screens.help import HelpScreen
from srsfe.tui.screens.launcher import LauncherScreen
from srsfe.tui.screens.map_screen import MapScreen, SettingRow, time_cell
from tests.conftest import GOLDEN_PATH

SMALL = MapSettings(n=5).to_dict()  # fast grids in tests


@pytest.fixture
def pdir(tmp_path: Path) -> Path:
    d = tmp_path / "profiles"
    d.mkdir()
    shutil.copy(GOLDEN_PATH, d / "golden.json")
    return d


async def type_text(pilot, text: str) -> None:  # type: ignore[no-untyped-def]
    for ch in text:
        await pilot.press(ch)


async def open_map(app: SrsfeApp, pilot, profile: str = "golden") -> MapScreen:  # type: ignore[no-untyped-def]
    app.load(profile)
    await pilot.press("w")
    await pilot.pause()
    assert isinstance(app.screen, MapScreen)
    return app.screen


async def compute(app: SrsfeApp, pilot) -> None:  # type: ignore[no-untyped-def]
    await pilot.press("c")
    await app.workers.wait_for_complete()
    await pilot.pause()


def small_app(pdir: Path, **kw) -> SrsfeApp:  # type: ignore[no-untyped-def]
    app = SrsfeApp(pdir, pdir / "plots", **kw)
    app.settings.map = dict(SMALL)
    return app


@pytest.mark.round_trip
@pytest.mark.spec("§7", "map-settings")
def test_settings_file_keeps_map(tmp_path: Path) -> None:
    """save → load keeps the map section; a non-dict map falls back to empty (defaults)."""
    path = tmp_path / "settings.json"
    user_settings.save(user_settings.Settings(map=MapSettings(base="b", n=9).to_dict()), path)
    assert MapSettings.from_dict(user_settings.load(path).map) == MapSettings(base="b", n=9)
    path.write_text('{"map": [1, 2]}')
    assert user_settings.load(path).map == {}


@pytest.mark.validation
@pytest.mark.spec("§8.1", "map-screen")
def test_parse_setting_and_time_cell() -> None:
    """Settings take engineering notation; n must be an integer; edge crossings show ≤ t_lo."""
    assert parse_setting("t_lo", "100n") == pytest.approx(100e-9)
    assert parse_setting("p_hi", "10 mW") == pytest.approx(10e-3)
    assert parse_setting("target", "-3") == -3.0
    assert parse_setting("n", "21") == 21 and isinstance(parse_setting("n", "21.0"), int)
    with pytest.raises(ValueError):
        parse_setting("n", "20.5")
    with pytest.raises(ValueError):
        parse_setting("t_hi", "abc")
    assert time_cell(None, 1e-7) == "—"
    assert time_cell(1e-7, 1e-7).startswith("≤ 100")
    assert time_cell(2.5e-6, 1e-7) == "2.50 µs"


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "launcher", "map-screen")
async def test_launcher_w_opens_map_with_stored_settings(pdir: Path) -> None:
    """w opens the Map screen with one row per setting, filled from the settings file."""
    app = SrsfeApp(pdir)
    app.settings.map = MapSettings(base="b", t_lo=1e-6, n=11, target=-3.0).to_dict()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await open_map(app, pilot)
        assert [r.setting for r in screen.query(SettingRow)] == [
            "base", "t_lo", "t_hi", "p_lo", "p_hi", "n", "target", "quantity", "k_lia"]
        assert screen.query_one("#in-t_lo", Input).value == "1µ"
        assert screen.query_one("#in-n", Input).value == "11"
        assert screen.query_one("#in-target", Input).value == "-3"
        assert "Buy" in str(screen.row("base").query(".value").first().render())
        await pilot.press("escape")
        assert isinstance(app.screen, LauncherScreen)


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "map-screen")
@pytest.mark.spec("§7", "map-settings")
async def test_compute_fills_boundary_table_and_saves_settings(pdir: Path, tmp_path: Path) -> None:
    """c computes in the background, fills one row per power and saves the settings file."""
    cfg = tmp_path / "settings.json"
    user_settings.save(user_settings.Settings(str(pdir), "golden", map=SMALL), cfg)
    app = SrsfeApp(plots_dir=pdir / "plots", settings_path=cfg)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await open_map(app, pilot)
        await pilot.press("g")
        await type_text(pilot, "0")
        await pilot.press("enter")
        await compute(app, pilot)
        assert screen.result is not None and screen.result.scalars["target"] == 0.0
        table = screen.query_one(DataTable)
        # golden: P_min 100 µW, P_max 1 mW, then decades 1 µW, 10 µW, 10 mW
        assert table.row_count == 5
        first = [str(c) for c in table.get_row_at(0)]
        assert first[0].startswith("P_min 100") and first[4].endswith("dB")
        assert "5×5 map of snr on Design" in str(screen.query_one("#status").render())
    assert user_settings.load(cfg).map == {**SMALL, "target": 0.0}


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "map-screen", "eng-invalid")
async def test_invalid_settings_show_reason_and_block_compute(pdir: Path) -> None:
    """A bad or out-of-order setting shows its reason in red; c refuses to compute."""
    app = small_app(pdir)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await open_map(app, pilot)
        await pilot.press("x")  # t_hi
        await type_text(pilot, "\b" * 10)
        await type_text(pilot, "10n")
        await pilot.press("escape")
        assert screen.row("t_hi").has_class("invalid")
        assert "must be > t_lo" in str(screen.row("t_hi").query(".reason").first().render())
        await pilot.press("n")
        await type_text(pilot, "abc")
        await pilot.press("enter")
        assert screen.row("n").has_class("invalid")
        await compute(app, pilot)
        assert screen.result is None


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "map-screen", "stale")
async def test_editing_a_setting_greys_the_table(pdir: Path) -> None:
    """After compute, editing a setting or toggling the base greys the table until recomputed."""
    app = small_app(pdir)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await open_map(app, pilot)
        await compute(app, pilot)
        table = screen.query_one(DataTable)
        assert not table.has_class("stale")
        await pilot.press("m")  # base d → b
        assert screen.values["base"] == "b" and table.has_class("stale")
        await compute(app, pilot)
        assert not table.has_class("stale") and screen.result.scalars["base"] == "b"  # type: ignore[union-attr]
        await pilot.press("h")
        await type_text(pilot, "\b" * 10)
        await type_text(pilot, "1m")
        await pilot.press("enter")
        assert table.has_class("stale")
        assert "press c to recompute" in str(screen.query_one("#status").render())


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "map-screen")
@pytest.mark.spec("§6.5", "inputs")
async def test_missing_profile_input_is_reported(pdir: Path) -> None:
    """A profile without an input the Budget calc needs → error toast, nothing computed."""
    app = small_app(pdir)
    async with app.run_test(size=(120, 40)) as pilot:
        app.load("golden")
        app.set_params(app.params.replace(r_f=None))
        await pilot.press("w")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, MapScreen)
        await compute(app, pilot)
        assert screen.result is None and not screen.computing
        assert any("r_f" in str(n.message) for n in app._notifications)


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "map-screen", "plot-menu")
async def test_plot_and_save_png(pdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """p and v need a computed map; p shows the map plot, v saves plots/<profile>_map.png."""
    shown: list[list[str]] = []
    monkeypatch.setattr(plot_menu, "launch", lambda result, plots: shown.append(plots))
    app = small_app(pdir)
    async with app.run_test(size=(120, 40)) as pilot:
        await open_map(app, pilot)
        await pilot.press("p", "v")
        assert shown == [] and not (pdir / "plots").exists()
        await compute(app, pilot)
        await pilot.press("p")
        assert shown == [["map"]]
        await pilot.press("v")
        await pilot.pause()
        assert (pdir / "plots" / "golden_map.png").is_file()


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "help", "map-screen")
async def test_map_help(pdir: Path) -> None:
    """? and F1 on the Map screen list its actions and setting keys."""
    app = small_app(pdir)
    async with app.run_test(size=(120, 40)) as pilot:
        await open_map(app, pilot)
        await pilot.press("question_mark")
        assert isinstance(app.screen, HelpScreen)
        text = app.screen.text
        assert "Compute" in text and "Save PNG" in text and "t_lo — Shortest dwell" in text
        await pilot.press("escape")
        assert isinstance(app.screen, MapScreen)


@pytest.mark.smoke
@pytest.mark.spec("§8.1", "map-screen")
@pytest.mark.spec("§6.5", "lockin")
async def test_quantity_toggle_and_k_lia(pdir: Path) -> None:
    """s toggles snr ↔ snr_lia, k edits k_lia (> 1 is refused); a snr_lia map says so."""
    app = small_app(pdir)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await open_map(app, pilot)
        await pilot.press("s")
        assert screen.values["quantity"] == "snr_lia"
        assert "lock-in" in str(screen.row("quantity").query(".value").first().render())
        await pilot.press("k")
        await type_text(pilot, "\b" * 10)
        await type_text(pilot, "2")
        await pilot.press("enter")
        assert screen.row("k_lia").has_class("invalid")
        await compute(app, pilot)
        assert screen.result is None
        await pilot.press("k")
        await type_text(pilot, "\b" * 10)
        await type_text(pilot, "0.5")
        await pilot.press("enter")
        await compute(app, pilot)
        assert screen.result is not None and screen.result.scalars["k_lia"] == 0.5
        assert "map of snr_lia (τ_LIA = 0.5·t_dwell)" in str(screen.query_one("#status").render())
        await pilot.press("s")
        assert screen.values["quantity"] == "snr" and screen.query_one(DataTable).has_class("stale")
