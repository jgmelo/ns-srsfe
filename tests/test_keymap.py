"""M9: key map — no collisions within any focus level, for every registered tool (SPEC §8.3)."""

from collections import Counter

import pytest

from srsfe.core.params import FIELDS
from srsfe.tools import REGISTRY
from srsfe.tools.base import PLOT_KEYS
from srsfe.tui import keymap

STATIC_LEVELS = {
    "launcher": [t.key for t in REGISTRY.values()] + [k.key for k in keymap.LAUNCHER],
    "profiles": [k.key for k in keymap.PROFILES],
    "unsaved dialog": [k.key for k in keymap.UNSAVED],
    "delete dialog": [k.key for k in keymap.DELETE],
    "plot menu": list(PLOT_KEYS.values()) + [k.key for k in keymap.PLOT_MENU],
    "global": [k.key for k in keymap.GLOBAL],
}


def _dups(keys: list[str]) -> list[str]:
    return [k for k, n in Counter(keys).items() if n > 1]


@pytest.mark.schema
@pytest.mark.spec("§8.3", "collisions")
@pytest.mark.parametrize("tool_key", list(REGISTRY))
def test_no_collisions_in_tool_levels(tool_key: str) -> None:
    """Top level (calcs, actions, groups) and each group's field keys are collision-free."""
    for level, keys in keymap.tool_levels(REGISTRY[tool_key]).items():
        assert _dups([k for k, _ in keys]) == [], f"{tool_key} {level}"


@pytest.mark.schema
@pytest.mark.spec("§8.3", "collisions")
@pytest.mark.parametrize("level", list(STATIC_LEVELS))
def test_no_collisions_in_screen_tables(level: str) -> None:
    """Launcher, Profiles, dialogs, plot menu and global keys are each collision-free."""
    assert _dups(STATIC_LEVELS[level]) == []


@pytest.mark.schema
@pytest.mark.spec("§8.3", "collisions")
def test_levels_do_not_take_reserved_keys() -> None:
    """No level reuses an always-active key (F1, F5, Ctrl+S, Ctrl+Q, Ctrl+P)."""
    levels = [k for t in REGISTRY.values() for keys in keymap.tool_levels(t).values()
              for k, _ in keys]
    levels += [k for name, keys in STATIC_LEVELS.items() if name != "global" for k in keys]
    assert set(levels).isdisjoint(keymap.RESERVED)


@pytest.mark.schema
@pytest.mark.spec("§8.3", "collisions")
def test_key_shapes_match_spec() -> None:
    """Calc keys are digits; group and field keys single letters; SPEC §8.3 group keys."""
    for tool in REGISTRY.values():
        assert all(c.key.isdigit() and len(c.key) == 1 for c in tool.calcs)
        assert all(g.key.isalpha() and len(g.key) == 1 for g in tool.groups)
    assert all(m.key.isalpha() and len(m.key) == 1 for m in FIELDS.values())
    levels = keymap.tool_levels(REGISTRY["d"])
    assert dict(levels["group:t"]) == {"r": "field:r_f", "f": "field:f_0", "d": "field:t_dwell",
                                       "n": "field:n_tau", "q": "field:q_mode"}
    assert dict(keymap.tool_levels(REGISTRY["a"])["group:t"]) == {
        "l": "field:l_f", "c": "field:c_f", "r": "field:r_f", "f": "field:f_0",
        "d": "field:t_dwell", "n": "field:n_tau"}
