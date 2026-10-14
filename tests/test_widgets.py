"""M9: pure helpers behind the tool-screen widgets (eng input, results, warnings)."""

import math
from typing import Any

import pytest

from srsfe.core.params import FIELDS, Params
from srsfe.tools import REGISTRY
from srsfe.tools.base import OUTPUTS
from srsfe.tui.widgets.eng_input import edit_text, parse_field
from srsfe.tui.widgets.results_table import fmt, marks, rows
from srsfe.tui.widgets.warnings_panel import lines


@pytest.mark.round_trip
@pytest.mark.spec("§8.1", "eng-input")
@pytest.mark.parametrize("name", [n for n in FIELDS if n not in ("l_f", "c_f")])
def test_edit_text_round_trips_defaults(name: str) -> None:
    """Every default value shows as compact text that parses back to the same SI value."""
    value = getattr(Params(), name)
    back = parse_field(name, edit_text(value))
    assert back == value or math.isclose(back, value, rel_tol=1e-12)  # type: ignore[arg-type]


@pytest.mark.validation
@pytest.mark.spec("§8.1", "eng-input")
@pytest.mark.parametrize(
    ("name", "text", "expected"),
    [("r_f", "47k", 47e3), ("c_f", "1.2pF", 1.2e-12), ("tau_lia", "200n", 200e-9),
     ("n_bits", "16", 16), ("q_mode", " bandwidth ", "bandwidth"), ("l_f", "", None),
     ("m", "0", 0.0), ("en_opamp", "2.5nV/√Hz", 2.5e-9)],
)
def test_parse_field(name: str, text: str, expected: Any) -> None:
    """Field text → SI value; empty text unsets the field; the field's unit may be typed."""
    assert parse_field(name, text) == pytest.approx(expected) if expected is not None \
        else parse_field(name, text) is None


@pytest.mark.validation
@pytest.mark.spec("§8.1", "eng-invalid")
@pytest.mark.parametrize(
    ("name", "text", "reason"),
    [("r_f", "-1k", "> 0"), ("r_f", "abc", "not a number"), ("n_bits", "12.5", "integer"),
     ("n_lia", "5", "one of"), ("v_range", "2", "one of"), ("q_mode", "fast", "one of"),
     ("tau_p", "1x", "prefix")],
)
def test_parse_field_reasons(name: str, text: str, reason: str) -> None:
    """Invalid text raises ValueError whose message explains why."""
    with pytest.raises(ValueError, match=reason):
        parse_field(name, text)


@pytest.mark.api
@pytest.mark.spec("§8.1", "eng-format")
@pytest.mark.parametrize(
    ("value", "unit", "text"),
    [(63.326e-6, "H", "63.326 µH"), (-25.033, "dB", "-25.03 dB"), (7.137, "dB", "+7.14 dB"),
     (254.8, "%", "254.8 %"), (True, "bool", "yes"), (12.566370614, "–", "12.566"),
     (-math.inf, "dB", "−∞ dB"), (None, "V", "—")],
)
def test_fmt(value: Any, unit: str, text: str) -> None:
    """Result values: SI prefixes, dB with sign, %, yes/no, plain dimensionless, −∞, unset."""
    assert fmt(value, unit) == text


@pytest.mark.schema
def test_every_output_has_metadata() -> None:
    """Every output any calc declares has a unit and description in OUTPUTS."""
    declared = {o for t in REGISTRY.values() for c in t.calcs for o in c.outputs}
    assert declared <= set(OUTPUTS)


@pytest.mark.api
@pytest.mark.spec("§8.1", "tool-screen")
def test_rows_marks_and_warning_lines(golden_params: dict[str, Any]) -> None:
    """Golden All: harmonic rows, P_min/P_max columns, ⚠ on budget rows, ℹ on W02 rows."""
    calc = REGISTRY["d"].calc("0")
    result = calc.run(Params.from_dict(golden_params))
    table = {label: (mark, a, b) for mark, label, a, b, _ in rows(calc, result)}
    assert table["q"] == ("", "12.566", "")
    assert table["v_coh"] == ("⚠", "1.2740 V", "12.724 V")
    assert table["enbw_lia"][0] == "ℹ" and marks(result)["occ_moku"] == "⚠"
    assert sum(label.startswith("v_n  n=") for label in table) == 5
    assert lines(result) == [
        "ℹ W02 · Tank, not lock-in, limits noise bandwidth",
        "⚠ W03 · P_max · Output exceeds opamp swing",
        "⚠ W04 · P_min · Output exceeds Moku input range",
        "⚠ W04 · P_max · Output exceeds Moku input range",
    ]
    assert lines(None)[0].startswith("Not calculated")
