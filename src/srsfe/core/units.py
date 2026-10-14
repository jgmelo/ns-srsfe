"""Engineering-notation parse/format. Used only at the UI boundary; everything else is SI."""

from __future__ import annotations

import math
import re

# Prefix → exponent. Case-sensitive: "m" is milli, "M" is mega. "u", "µ" (U+00B5) and
# "μ" (U+03BC) all mean micro.
PREFIXES: dict[str, int] = {
    "a": -18, "f": -15, "p": -12, "n": -9, "u": -6, "µ": -6, "μ": -6, "m": -3,
    "k": 3, "M": 6, "G": 9, "T": 12,
}
# Exponent → prefix used when formatting.
_FORMAT_PREFIX: dict[int, str] = {
    -18: "a", -15: "f", -12: "p", -9: "n", -6: "µ", -3: "m", 0: "", 3: "k", 6: "M", 9: "G", 12: "T",
}
# Units that carry no physical dimension; never stripped from input.
_DIMENSIONLESS = {"", "–", "-"}

_NUMBER_RE = re.compile(
    r"^(?P<num>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(?P<prefix>[^\d\s.+-]?)$"
)


def parse_eng(text: str, unit: str = "") -> float:
    """Parse engineering notation to an SI float.

    Accepts plain numbers (`1e-6`, `0.5`), an optional SI prefix (`100k`, `2p`, `20M`,
    `1u`, `1µ`), and optionally the field's own unit after it (`100kΩ`, `2 pF`).
    Raises ValueError with a human-readable reason on bad input.
    """
    s = text.strip()
    if not s:
        raise ValueError("empty input")
    if unit not in _DIMENSIONLESS and s.endswith(unit):
        s = s[: -len(unit)].rstrip()
    m = _NUMBER_RE.match(s)
    if m is None:
        raise ValueError(f"not a number: {text.strip()!r}")
    prefix = m.group("prefix")
    if prefix and prefix not in PREFIXES:
        raise ValueError(f"unknown prefix {prefix!r}")
    value = float(m.group("num")) * 10.0 ** PREFIXES.get(prefix, 0)
    if not math.isfinite(value):
        raise ValueError("number out of range")
    return value


def format_eng(value: float | int | None, unit: str = "", sig: int = 5) -> str:
    """Format an SI value with `sig` significant digits and an SI prefix, e.g.
    format_eng(63.326e-6, "H") → "63.326 µH". None → "—". Outside the prefix range
    (1e-18 … 1e15) falls back to exponent notation."""
    if value is None:
        return "—"
    unit = "" if unit in _DIMENSIONLESS else unit
    v = float(value)
    if not math.isfinite(v):
        return f"{v} {unit}".strip()
    if v == 0:
        return f"0 {unit}".strip()
    exp3 = math.floor(math.log10(abs(v)) / 3) * 3
    mant = round(v / 10.0**exp3, sig - 1 - _mag(v / 10.0**exp3))
    if abs(mant) >= 1000:  # rounding pushed it to the next prefix (e.g. 999.996 → 1000.0)
        exp3 += 3
        mant = round(v / 10.0**exp3, sig - 1 - _mag(v / 10.0**exp3))
    if exp3 not in _FORMAT_PREFIX:
        return f"{v:.{sig - 1}e} {unit}".strip()
    decimals = max(sig - 1 - _mag(mant), 0)
    return f"{mant:.{decimals}f} {_FORMAT_PREFIX[exp3]}{unit}".strip()


def _mag(x: float) -> int:
    """floor(log10(|x|)) for x ≠ 0."""
    return math.floor(math.log10(abs(x)))
