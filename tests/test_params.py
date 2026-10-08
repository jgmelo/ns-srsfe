"""M1: Params fields, metadata and validation (SPEC §3.1)."""

import dataclasses
from typing import Any

import pytest

from srsfe.core.params import FIELDS, Params, coerce, validate, validate_value

SPEC_ORDER = [
    "r_f", "f_0", "t_dwell", "n_tau", "q_mode", "l_f", "c_f",
    "p_min", "p_max", "resp", "f_rep", "tau_p", "m",
    "c_d", "en_opamp", "nep", "temp", "k_crest",
    "tau_lia", "n_lia",
    "v_swing", "en_moku", "n_bits", "v_range",
    "f_max",
]


@pytest.mark.schema
@pytest.mark.spec("§3.1", "fields")
def test_fields_match_spec_order() -> None:
    """Params has exactly the SPEC §3.1 fields, in table order."""
    assert list(FIELDS) == SPEC_ORDER
    assert [f.name for f in dataclasses.fields(Params)] == SPEC_ORDER


@pytest.mark.schema
@pytest.mark.spec("§3.1", "metadata")
def test_metadata_complete() -> None:
    """Every field has a unit, group, symbol, description and a one-letter key."""
    for name, meta in FIELDS.items():
        assert meta.name == name
        assert meta.unit and meta.group and meta.symbol and meta.description
        assert len(meta.key) == 1


@pytest.mark.schema
@pytest.mark.spec("§3.1", "metadata", "types")
def test_selected_metadata() -> None:
    """Spot-check units, groups, keys and types against the SPEC table."""
    assert FIELDS["r_f"].unit == "Ω" and FIELDS["r_f"].group == "Tank" and FIELDS["r_f"].key == "r"
    assert FIELDS["en_opamp"].unit == "V/√Hz"
    assert FIELDS["v_range"].unit == "Vpp"
    assert FIELDS["l_f"].group == "Tank (Analyze)"
    assert FIELDS["n_lia"].kind is int and FIELDS["n_bits"].kind is int
    assert FIELDS["q_mode"].kind is str


@pytest.mark.schema
@pytest.mark.spec("§3.1", "defaults")
def test_defaults_match_spec() -> None:
    """Params() carries the SPEC defaults (l_f, c_f unset) and is valid."""
    p = Params()
    assert p.r_f == 100e3 and p.f_0 == 20e6 and p.t_dwell == 1e-6 and p.n_tau == 5
    assert p.q_mode == "settling" and p.l_f is None and p.c_f is None
    assert p.en_moku == 30e-9 and p.n_bits == 12 and p.v_range == 1.0 and p.f_max == 200e6
    assert validate(p) == {}


@pytest.mark.round_trip
@pytest.mark.spec("§9", "profile")
def test_golden_params_load_and_are_valid(golden_params: dict[str, Any]) -> None:
    """Golden params survive from_dict → to_dict unchanged and pass validation."""
    p = Params.from_dict(golden_params)
    assert p.to_dict() == golden_params
    assert validate(p) == {}


@pytest.mark.api
def test_params_frozen_and_replace_copies() -> None:
    """Params is immutable; replace() returns a coerced copy and leaves the original alone."""
    p = Params()
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.r_f = 1.0  # type: ignore[misc]
    q = p.replace(r_f=50e3, n_bits=16.0)
    assert q.r_f == 50e3 and q.n_bits == 16 and isinstance(q.n_bits, int)
    assert p.r_f == 100e3


@pytest.mark.api
def test_from_dict_missing_is_none_unknown_raises() -> None:
    """from_dict: missing keys become None (unset); unknown keys raise KeyError."""
    p = Params.from_dict({"r_f": 1e3})
    assert p.r_f == 1e3 and p.f_0 is None and p.q_mode is None
    with pytest.raises(KeyError):
        Params.from_dict({"bogus": 1})


@pytest.mark.api
def test_missing() -> None:
    """missing() lists the unset fields among those asked for."""
    p = Params.from_dict({"r_f": 1e3})
    assert p.missing(["r_f", "f_0", "l_f"]) == ["f_0", "l_f"]


@pytest.mark.validation
@pytest.mark.spec("§3.1", "types")
@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("r_f", 5, 5.0),
        ("n_lia", 2.0, 2),
        ("q_mode", "bandwidth", "bandwidth"),
        ("l_f", None, None),
    ],
)
def test_coerce_ok(name: str, value: Any, expected: Any) -> None:
    """coerce() normalises types: int → float, integral float → int, None passes."""
    out = coerce(name, value)
    assert out == expected and type(out) is type(expected)


@pytest.mark.validation
@pytest.mark.spec("§3.1", "types")
@pytest.mark.parametrize(
    ("name", "value"),
    [("r_f", "100k"), ("r_f", True), ("n_bits", 12.5), ("q_mode", 1), ("n_lia", [1])],
)
def test_coerce_wrong_type(name: str, value: Any) -> None:
    """coerce() raises TypeError for text-in-number, bools, non-integers, numbers-in-text."""
    with pytest.raises(TypeError):
        coerce(name, value)


@pytest.mark.validation
@pytest.mark.spec("§3.1", "positive", "m-nonneg", "n-lia", "v-range", "q-mode", "n-bits")
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("r_f", 0.0), ("r_f", -1.0), ("f_max", float("inf")), ("temp", float("nan")),
        ("m", -1e-6), ("n_lia", 0), ("n_lia", 5), ("v_range", 2.0),
        ("q_mode", "other"), ("n_bits", 0), ("n_bits", 12.5),
    ],
)
def test_validate_value_rejects(name: str, value: Any) -> None:
    """Out-of-range values get a reason: ≤ 0, non-finite, m < 0, bad choices, non-integer."""
    assert validate_value(name, value) is not None


@pytest.mark.validation
@pytest.mark.spec("§3.1", "m-nonneg", "n-lia", "v-range", "q-mode", "n-bits")
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("m", 0.0), ("n_lia", 4), ("v_range", 10), ("v_range", 1.0),
        ("q_mode", "bandwidth"), ("n_bits", 16), ("l_f", None),
    ],
)
def test_validate_value_accepts(name: str, value: Any) -> None:
    """Boundary and allowed values pass: m = 0, n_lia = 4, v_range 1/10, unset."""
    assert validate_value(name, value) is None


@pytest.mark.validation
@pytest.mark.spec("§3.1", "p-order")
def test_p_min_le_p_max() -> None:
    """p_min > p_max flags both fields; equal is fine; one unset skips the check."""
    assert validate(Params(p_min=1e-3, p_max=1e-3)) == {}
    errors = validate(Params(p_min=2e-3, p_max=1e-3))
    assert set(errors) == {"p_min", "p_max"}
    # Only one set → no cross-field error.
    assert validate(Params(p_min=2e-3, p_max=None)) == {}
