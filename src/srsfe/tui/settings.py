"""Small user settings file (SPEC §7): profiles folder and last-used profile.

Lives in the user config folder: %APPDATA%\\srsfe\\settings.json on Windows,
$XDG_CONFIG_HOME/srsfe/settings.json (default ~/.config/srsfe) elsewhere.
A missing or unreadable file means defaults.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Settings:
    profiles_dir: str = "profiles"  # relative paths resolve against the working directory
    last_profile: str | None = None


def default_path() -> Path:
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "srsfe" / "settings.json"


def load(path: Path) -> Settings:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    out = Settings()
    if isinstance(data.get("profiles_dir"), str) and data["profiles_dir"].strip():
        out.profiles_dir = data["profiles_dir"]
    if isinstance(data.get("last_profile"), str):
        out.last_profile = data["last_profile"]
    return out


def save(settings: Settings, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
