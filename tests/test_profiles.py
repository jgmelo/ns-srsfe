"""M1: profile store — round trip, load rules and migration (SPEC §7)."""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from srsfe.core import profiles
from srsfe.core.params import Params
from srsfe.core.profiles import (
    SCHEMA_VERSION,
    ProfileError,
    ProfileExistsError,
    ProfileNotFoundError,
    ProfileStore,
    migrate,
)
from tests.conftest import GOLDEN_PATH


@pytest.fixture
def store(tmp_path: Path) -> ProfileStore:
    return ProfileStore(tmp_path / "profiles")


def _write(store: ProfileStore, name: str, doc: Any) -> None:
    store.directory.mkdir(parents=True, exist_ok=True)
    (store.directory / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")


def _doc(params: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"schema_version": 1, "name": "x", "notes": "", "created": "", "modified": "",
            "params": params, **extra}


@pytest.mark.schema
@pytest.mark.spec("§7", "file-format")
@pytest.mark.spec("§9", "profile")
def test_golden_file_loads(golden_params: dict[str, Any], tmp_path: Path) -> None:
    """profiles/golden.json loads through the store with no issues and the golden params."""
    shutil.copy(GOLDEN_PATH, tmp_path / "golden.json")
    prof = ProfileStore(tmp_path).load("golden")
    assert prof.name == "golden" and prof.issues == ()
    assert prof.params.to_dict() == golden_params
    assert prof.notes.startswith("Golden test case")


@pytest.mark.round_trip
@pytest.mark.spec("§7", "load-save")
def test_round_trip(store: ProfileStore) -> None:
    """save → load gives back equal Params, notes and timestamps."""
    p = Params().replace(l_f=63.3257e-6, c_f=None, q_mode="bandwidth", n_lia=3)
    saved = store.save(p, "trip", notes="hello")
    loaded = store.load("trip")
    assert loaded.params == p
    assert loaded.notes == "hello"
    assert loaded.created == saved.created and loaded.modified == saved.modified


@pytest.mark.schema
@pytest.mark.spec("§7", "file-format", "inputs-only", "nulls")
def test_file_contains_inputs_only_with_nulls(store: ProfileStore) -> None:
    """Saved file has exactly the SPEC keys, input params only, unset fields as null."""
    store.save(Params(), "d")
    doc = json.loads(store.path("d").read_text(encoding="utf-8"))
    assert set(doc) == {"schema_version", "name", "notes", "created", "modified", "params"}
    assert doc["schema_version"] == SCHEMA_VERSION
    assert list(doc["params"]) == list(Params().to_dict())
    assert doc["params"]["l_f"] is None and doc["params"]["c_f"] is None


@pytest.mark.errors
@pytest.mark.spec("§7", "unknown-keys")
def test_unknown_keys_dropped_with_issue(store: ProfileStore) -> None:
    """Unknown param keys (e.g. a derived 'q') are dropped and reported in issues."""
    _write(store, "u", _doc({"r_f": 1e3, "q": 12.5, "bogus": 1}))
    prof = store.load("u")
    assert prof.params.r_f == 1e3
    assert len(prof.issues) == 2 and any("'q'" in i for i in prof.issues)


@pytest.mark.errors
@pytest.mark.spec("§7", "missing-keys")
def test_missing_keys_become_null(store: ProfileStore) -> None:
    """Params missing from the file load as None."""
    _write(store, "m", _doc({"r_f": 1e3}))
    prof = store.load("m")
    assert prof.params.r_f == 1e3 and prof.params.f_0 is None and prof.params.q_mode is None


@pytest.mark.errors
@pytest.mark.spec("§7", "wrong-type")
@pytest.mark.parametrize(
    "params", [{"r_f": "100k"}, {"n_bits": 12.5}, {"q_mode": 3}, {"m": True}]
)
def test_wrong_type_is_error(store: ProfileStore, params: dict[str, Any]) -> None:
    """A param of the wrong type makes load raise ProfileError."""
    _write(store, "w", _doc(params))
    with pytest.raises(ProfileError):
        store.load("w")


@pytest.mark.errors
@pytest.mark.spec("§7", "file-format")
@pytest.mark.parametrize(
    "doc", [[], {"schema_version": 1}, {"schema_version": 1, "params": [], "name": "x"},
            _doc({}, notes=5)]
)
def test_malformed_document(store: ProfileStore, doc: Any) -> None:
    """Non-object documents, bad 'params' or non-string metadata raise ProfileError."""
    _write(store, "bad", doc)
    with pytest.raises(ProfileError):
        store.load("bad")


@pytest.mark.errors
@pytest.mark.spec("§7", "file-format")
def test_invalid_json(store: ProfileStore) -> None:
    """Unparseable JSON raises ProfileError."""
    store.directory.mkdir(parents=True)
    (store.directory / "j.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(ProfileError):
        store.load("j")


@pytest.mark.api
def test_file_name_is_authoritative(store: ProfileStore) -> None:
    """The profile name comes from the file name, not the 'name' inside it."""
    _write(store, "real", _doc({}, name="other"))
    assert store.load("real").name == "real"


# -- migration -----------------------------------------------------------------


@pytest.mark.api
@pytest.mark.spec("§7", "migrate")
def test_migrate_current_is_noop() -> None:
    """A current-version document passes through migrate() unchanged."""
    doc = _doc({"r_f": 1.0})
    assert migrate(doc) == doc


@pytest.mark.errors
@pytest.mark.spec("§7", "migrate")
@pytest.mark.parametrize("version", [None, "1", True, SCHEMA_VERSION + 1, 0])
def test_migrate_rejects(version: Any) -> None:
    """Missing, non-integer, future or unmigratable schema_version raises ProfileError."""
    doc = _doc({})
    if version is None:
        del doc["schema_version"]
    else:
        doc["schema_version"] = version
    with pytest.raises(ProfileError):
        migrate(doc)


@pytest.mark.api
@pytest.mark.spec("§7", "migrate")
def test_migration_chain_applied(
    store: ProfileStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registered v0 → v1 step runs on load; saving writes the current schema."""
    # A hypothetical v0 used "rf" instead of "r_f"; check the registry is applied on load.
    def v0_to_v1(doc: dict[str, Any]) -> dict[str, Any]:
        params = dict(doc["params"])
        params["r_f"] = params.pop("rf")
        return {**doc, "params": params}

    monkeypatch.setitem(profiles.MIGRATIONS, 0, v0_to_v1)
    old = _doc({"rf": 47e3})
    old["schema_version"] = 0
    assert migrate(old)["schema_version"] == SCHEMA_VERSION
    _write(store, "old", old)
    prof = store.load("old")
    assert prof.params.r_f == 47e3 and prof.issues == ()
    # Saving writes the current schema.
    store.save(prof.params, "old")
    assert json.loads(store.path("old").read_text())["schema_version"] == SCHEMA_VERSION


# -- store operations ----------------------------------------------------------


@pytest.mark.api
@pytest.mark.spec("§7", "list")
def test_list(store: ProfileStore) -> None:
    """list() returns profiles sorted by name with notes/modified, skipping broken files."""
    assert store.list() == []
    store.save(Params(), "b", notes="nb")
    store.save(Params(), "a")
    store.directory.joinpath("broken.json").write_text("{", encoding="utf-8")
    infos = store.list()
    assert [i.name for i in infos] == ["a", "b"]
    assert infos[1].notes == "nb" and infos[1].modified


@pytest.mark.api
@pytest.mark.spec("§7", "load-save")
def test_save_keeps_created_and_notes(store: ProfileStore) -> None:
    """Overwriting keeps 'created' and notes unless new notes are given."""
    first = store.save(Params(), "p", notes="keep")
    first_doc = json.loads(store.path("p").read_text())
    first_doc["created"] = "2000-01-01T00:00:00"
    store.path("p").write_text(json.dumps(first_doc))
    second = store.save(Params().replace(r_f=1.0), "p")
    assert second.created == "2000-01-01T00:00:00" and second.notes == "keep"
    assert store.save(Params(), "p", notes="new").notes == "new"
    assert first.name == "p"


@pytest.mark.api
@pytest.mark.spec("§7", "save-as")
def test_save_as_refuses_overwrite(store: ProfileStore) -> None:
    """save_as refuses an existing name."""
    store.save_as(Params(), "n")
    with pytest.raises(ProfileExistsError):
        store.save_as(Params(), "n")


@pytest.mark.api
@pytest.mark.spec("§7", "duplicate")
def test_duplicate(store: ProfileStore) -> None:
    """duplicate copies params and notes; refuses existing target or missing source."""
    store.save(Params().replace(r_f=1.0), "src", notes="n")
    dup = store.duplicate("src", "dst")
    assert dup.params.r_f == 1.0 and dup.notes == "n"
    assert store.exists("src") and store.exists("dst")
    with pytest.raises(ProfileExistsError):
        store.duplicate("src", "dst")
    with pytest.raises(ProfileNotFoundError):
        store.duplicate("nope", "x")


@pytest.mark.api
@pytest.mark.spec("§7", "rename")
def test_rename(store: ProfileStore) -> None:
    """rename moves the file, updates the stored name, refuses an existing target."""
    store.save(Params(), "old", notes="n")
    store.save(Params(), "taken")
    with pytest.raises(ProfileExistsError):
        store.rename("old", "taken")
    new = store.rename("old", "new")
    assert not store.exists("old") and store.exists("new")
    assert new.notes == "n"
    assert json.loads(store.path("new").read_text())["name"] == "new"


@pytest.mark.api
@pytest.mark.spec("§7", "delete")
def test_delete(store: ProfileStore) -> None:
    """delete removes the file; deleting or loading a missing profile raises."""
    store.save(Params(), "d")
    store.delete("d")
    assert not store.exists("d")
    with pytest.raises(ProfileNotFoundError):
        store.delete("d")
    with pytest.raises(ProfileNotFoundError):
        store.load("d")


@pytest.mark.api
@pytest.mark.spec("§7", "default-profile")
def test_ensure_default(store: ProfileStore) -> None:
    """ensure_default creates default.json from Params() once, then loads it."""
    prof = store.ensure_default()
    assert prof.name == "default" and prof.params == Params()
    store.save(Params().replace(r_f=1.0), "default")
    assert store.ensure_default().params.r_f == 1.0


@pytest.mark.validation
@pytest.mark.parametrize("name", ["", " a", "a ", "../x", "a/b", ".hidden", "-x", "a\\b"])
def test_invalid_names(store: ProfileStore, name: str) -> None:
    """Names that are empty, padded, hidden or contain path separators are rejected."""
    with pytest.raises(ProfileError):
        store.save(Params(), name)


@pytest.mark.api
def test_no_temp_files_left(store: ProfileStore) -> None:
    """Atomic writes leave no temporary files behind."""
    store.save(Params(), "t")
    assert [p.name for p in store.directory.iterdir()] == ["t.json"]
