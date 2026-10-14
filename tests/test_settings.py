"""M10: user settings file — profiles folder and last-used profile (SPEC §7)."""

import json
from pathlib import Path

import pytest

from srsfe.tui import settings as s


@pytest.mark.round_trip
@pytest.mark.spec("§7", "last-used")
def test_settings_round_trip(tmp_path: Path) -> None:
    """save → load keeps the profiles folder and last-used profile; parent dirs are created."""
    path = tmp_path / "cfg" / "srsfe" / "settings.json"
    s.save(s.Settings(profiles_dir="/data/profiles", last_profile="vendor"), path)
    assert s.load(path) == s.Settings("/data/profiles", "vendor")


@pytest.mark.errors
@pytest.mark.spec("§7", "last-used")
@pytest.mark.parametrize("content", [None, "{nope", "[]", '{"profiles_dir": 5, "last_profile": 1}',
                                     '{"profiles_dir": "  "}'])
def test_bad_or_missing_settings_mean_defaults(tmp_path: Path, content: str | None) -> None:
    """A missing, unparseable or wrongly typed settings file falls back to defaults."""
    path = tmp_path / "settings.json"
    if content is not None:
        path.write_text(content)
    assert s.load(path) == s.Settings()


@pytest.mark.api
def test_default_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """XDG_CONFIG_HOME (or ~/.config) on Linux/macOS, %APPDATA% on Windows."""
    monkeypatch.setattr(s.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert s.default_path() == tmp_path / "srsfe" / "settings.json"
    monkeypatch.setattr(s.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    assert s.default_path() == tmp_path / "AppData" / "srsfe" / "settings.json"
    assert json.dumps({"ok": 1})  # keep json import used
