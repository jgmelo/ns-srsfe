"""JSON profile store (SPEC §7). The only module in core/ that does file I/O.

A profile file stores inputs only:
    {"schema_version": 1, "name": ..., "notes": ..., "created": ISO-8601,
     "modified": ISO-8601, "params": {...}}
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from srsfe.core.params import FIELDS, Params

SCHEMA_VERSION = 1
DEFAULT_PROFILE = "default"

# MIGRATIONS[n] upgrades a document from schema_version n to n + 1.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}

_NAME_RE = re.compile(r"^[\w][\w .-]*$")


class ProfileError(Exception):
    """Malformed profile file or invalid profile operation."""


class ProfileNotFoundError(ProfileError):
    pass


class ProfileExistsError(ProfileError):
    pass


@dataclass(frozen=True)
class Profile:
    name: str
    params: Params
    notes: str = ""
    created: str = ""
    modified: str = ""
    # Non-fatal problems found while loading (e.g. dropped unknown keys). Never saved.
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileInfo:
    """One row of the Profiles screen."""

    name: str
    modified: str
    notes: str


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a profile document to SCHEMA_VERSION. Returns a new dict."""
    version = data.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ProfileError(f"missing or invalid schema_version: {version!r}")
    if version > SCHEMA_VERSION:
        raise ProfileError(
            f"schema_version {version} is newer than supported ({SCHEMA_VERSION})"
        )
    out = dict(data)
    while version < SCHEMA_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:
            raise ProfileError(f"no migration from schema_version {version}")
        out = step(out)
        version += 1
        out["schema_version"] = version
    return out


def from_document(data: Any) -> Profile:
    """Parse a profile document (already JSON-decoded).
    Unknown param keys → dropped with an issue; missing → None; wrong type → ProfileError."""
    if not isinstance(data, dict):
        raise ProfileError("profile must be a JSON object")
    data = migrate(data)
    raw = data.get("params")
    if not isinstance(raw, dict):
        raise ProfileError("'params' must be a JSON object")
    issues: list[str] = []
    unknown = [k for k in raw if k not in FIELDS]
    for key in unknown:
        issues.append(f"unknown parameter {key!r} dropped")
    known = {k: v for k, v in raw.items() if k in FIELDS}
    try:
        params = Params.from_dict(known)
    except TypeError as exc:
        raise ProfileError(str(exc)) from exc
    for key in ("name", "notes", "created", "modified"):
        if key in data and not isinstance(data[key], str):
            raise ProfileError(f"{key!r} must be a string")
    return Profile(
        name=data.get("name", ""),
        params=params,
        notes=data.get("notes", ""),
        created=data.get("created", ""),
        modified=data.get("modified", ""),
        issues=tuple(issues),
    )


def to_document(profile: Profile) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": profile.name,
        "notes": profile.notes,
        "created": profile.created,
        "modified": profile.modified,
        "params": profile.params.to_dict(),
    }


class ProfileStore:
    """One JSON file per profile in `directory`, named `<name>.json`."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self.directory = Path(directory)

    # -- paths ---------------------------------------------------------------

    def path(self, name: str) -> Path:
        check_name(name)
        return self.directory / f"{name}.json"

    def exists(self, name: str) -> bool:
        return self.path(name).is_file()

    # -- API (SPEC §7) -------------------------------------------------------

    def list(self) -> list[ProfileInfo]:
        """All profiles sorted by name. Unreadable files are skipped."""
        out: list[ProfileInfo] = []
        if not self.directory.is_dir():
            return out
        for p in sorted(self.directory.glob("*.json")):
            try:
                prof = self.load(p.stem)
            except (ProfileError, OSError, ValueError):
                continue
            out.append(ProfileInfo(p.stem, prof.modified, prof.notes))
        return out

    def load(self, name: str) -> Profile:
        path = self.path(name)
        if not path.is_file():
            raise ProfileNotFoundError(f"profile {name!r} not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProfileError(f"{path.name}: invalid JSON: {exc}") from exc
        prof = from_document(data)
        # The file name is authoritative.
        if prof.name != name:
            prof = Profile(name, prof.params, prof.notes, prof.created, prof.modified, prof.issues)
        return prof

    def save(self, params: Params, name: str, notes: str | None = None) -> Profile:
        """Create or overwrite. Keeps `created` (and `notes`, unless given) of an existing file."""
        created, old_notes = _now(), ""
        if self.exists(name):
            try:
                old = self.load(name)
                created, old_notes = old.created or created, old.notes
            except ProfileError:
                pass
        prof = Profile(name, params, old_notes if notes is None else notes, created, _now())
        self._write(prof)
        return prof

    def save_as(self, params: Params, name: str, notes: str = "") -> Profile:
        """Save under a new name; refuses to overwrite."""
        if self.exists(name):
            raise ProfileExistsError(f"profile {name!r} already exists")
        return self.save(params, name, notes)

    def duplicate(self, src: str, dst: str) -> Profile:
        prof = self.load(src)
        return self.save_as(prof.params, dst, prof.notes)

    def rename(self, old: str, new: str) -> Profile:
        if old == new:
            return self.load(old)
        if self.exists(new):
            raise ProfileExistsError(f"profile {new!r} already exists")
        prof = self.load(old)
        renamed = Profile(new, prof.params, prof.notes, prof.created, _now())
        self._write(renamed)
        self.path(old).unlink()
        return renamed

    def delete(self, name: str) -> None:
        path = self.path(name)
        if not path.is_file():
            raise ProfileNotFoundError(f"profile {name!r} not found")
        path.unlink()

    def ensure_default(self) -> Profile:
        """Load `default`, creating it from Params() defaults if missing (SPEC §7)."""
        if not self.exists(DEFAULT_PROFILE):
            return self.save(Params(), DEFAULT_PROFILE)
        return self.load(DEFAULT_PROFILE)

    # -- internals -----------------------------------------------------------

    def _write(self, prof: Profile) -> None:
        """Atomic write: temp file in the same directory, then replace."""
        self.directory.mkdir(parents=True, exist_ok=True)
        text = json.dumps(to_document(prof), indent=2, ensure_ascii=False) + "\n"
        fd, tmp = tempfile.mkstemp(dir=self.directory, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, self.path(prof.name))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def check_name(name: str) -> None:
    """Profile names become file names: letters, digits, `_`, space, `.`, `-`;
    must start with a letter, digit or `_`."""
    if not isinstance(name, str) or not _NAME_RE.match(name) or name != name.strip():
        raise ProfileError(f"invalid profile name: {name!r}")
