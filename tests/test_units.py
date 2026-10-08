"""M1: engineering-notation parse/format."""

import math

import pytest

from srsfe.core.units import format_eng, parse_eng


@pytest.mark.validation
@pytest.mark.spec("§8.1", "eng-input")
@pytest.mark.parametrize(
    ("text", "unit", "expected"),
    [
        ("100k", "", 100e3),
        ("2p", "", 2e-12),
        ("20M", "", 20e6),
        ("1e-6", "", 1e-6),
        ("1µ", "", 1e-6),   # U+00B5 micro sign
        ("1μ", "", 1e-6),   # U+03BC Greek mu
        ("1u", "", 1e-6),
        ("1m", "", 1e-3),
        ("2.5n", "", 2.5e-9),
        ("7.1f", "", 7.1e-15),
        (" 295 ", "", 295.0),
        (".5", "", 0.5),
        ("-3k", "", -3e3),
        ("1.5e3k", "", 1.5e6),
        ("100kΩ", "Ω", 100e3),
        ("2 pF", "F", 2e-12),
        ("20MHz", "Hz", 20e6),
        ("1ms", "s", 1e-3),
        ("295K", "K", 295.0),
        ("2.5nV/√Hz", "V/√Hz", 2.5e-9),
        ("1 Vpp", "Vpp", 1.0),
    ],
)
def test_parse(text: str, unit: str, expected: float) -> None:
    """parse_eng accepts SPEC examples, every prefix spelling and an optional unit suffix."""
    assert parse_eng(text, unit) == pytest.approx(expected, rel=1e-12)


@pytest.mark.validation
@pytest.mark.spec("§8.1", "eng-invalid")
@pytest.mark.parametrize(
    ("text", "unit"),
    [("", ""), ("   ", ""), ("abc", ""), ("1x", ""), ("1K", ""), ("1..2", ""),
     ("k", ""), ("1kΩ", ""), ("1e999", ""), ("1 2", "")],
)
def test_parse_rejects(text: str, unit: str) -> None:
    """parse_eng raises ValueError (with a reason) for empty, garbage, bad prefix, overflow."""
    with pytest.raises(ValueError):
        parse_eng(text, unit)


@pytest.mark.api
@pytest.mark.spec("§8.1", "eng-format")
@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (100e3, "Ω", "100.00 kΩ"),
        (63.326e-6, "H", "63.326 µH"),
        (1e-12, "F", "1.0000 pF"),
        (20e6, "Hz", "20.000 MHz"),
        (0.6, "A/W", "600.00 mA/W"),
        (295, "K", "295.00 K"),
        (-25.033e-3, "V", "-25.033 mV"),
        (999.9999, "Ω", "1.0000 kΩ"),
        (0, "V", "0 V"),
        (None, "V", "—"),
        (1e-5, "–", "10.000 µ"),
        (1e-21, "A", "1.0000e-21 A"),
        (float("inf"), "", "inf"),
    ],
)
def test_format(value: float | None, unit: str, expected: str) -> None:
    """format_eng: 5 significant digits, SI prefix, rounding carry, None/0/inf, out of range."""
    assert format_eng(value, unit) == expected


@pytest.mark.api
@pytest.mark.spec("§8.1", "eng-format")
def test_format_sig() -> None:
    """format_eng honours a custom number of significant digits."""
    assert format_eng(1.2345678e-9, "s", sig=3) == "1.23 ns"


@pytest.mark.round_trip
@pytest.mark.spec("§8.1", "eng-input", "eng-format")
@pytest.mark.parametrize("value", [1e-15, 4.0363e-13, 1.25e6, 7.2095, 12.717, 2545.0, 3e-8])
def test_round_trip(value: float) -> None:
    """format_eng → parse_eng returns the value within the 5-digit display precision."""
    for unit in ("", "V"):
        back = parse_eng(format_eng(value, unit), unit)
        assert math.isclose(back, value, rel_tol=1e-4)
