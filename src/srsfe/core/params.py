"""Input parameters (SPEC §3.1): the Params dataclass, per-field metadata and validation.

All values are SI. `None` means "unset"; whether a field is required is decided by the
calc that uses it (SPEC §6), not here.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Any

FieldValue = float | int | str | None


@dataclass(frozen=True)
class FieldMeta:
    """Metadata for one input field. `key` is the field's key inside its group (SPEC §8.3)."""

    name: str
    symbol: str
    unit: str
    group: str
    key: str
    description: str
    kind: type = float  # float | int | str
    choices: tuple[float | int | str, ...] | None = None
    nonneg: bool = False  # True: value ≥ 0 allowed; otherwise numeric values must be > 0


def _f(
    default: FieldValue,
    symbol: str,
    unit: str,
    group: str,
    key: str,
    description: str,
    kind: type = float,
    choices: tuple[float | int | str, ...] | None = None,
    nonneg: bool = False,
) -> Any:
    # `name` is filled in by _build_fields() from the dataclass field name.
    meta = FieldMeta("", symbol, unit, group, key, description, kind, choices, nonneg)
    return field(default=default, metadata={"meta": meta})


@dataclass(frozen=True)
class Params:
    """All tool inputs, SI units, identifiers as in SPEC §3.1. Field order = SPEC order."""

    # Tank
    r_f: float | None = _f(100e3, "R", "Ω", "Tank", "r", "Feedback resistor; transimpedance gain at f₀")
    f_0: float | None = _f(20e6, "f₀", "Hz", "Tank", "f", "Tank resonance = signal frequency (f_rep/2)")
    t_dwell: float | None = _f(1e-6, "t_dwell", "s", "Tank", "d", "Pixel dwell time; sets Q")
    n_tau: float | None = _f(5.0, "N_τ", "–", "Tank", "n", "Tank time constants that must fit in one dwell")
    q_mode: str | None = _f(
        "settling", "–", "–", "Tank", "q", 'Q criterion: "settling" or "bandwidth"',
        kind=str, choices=("settling", "bandwidth"),
    )
    l_f: float | None = _f(None, "L", "H", "Tank (Analyze)", "l", "Existing tank inductance")
    c_f: float | None = _f(None, "C", "F", "Tank (Analyze)", "c", "Existing tank capacitance")
    # Light
    p_min: float | None = _f(1e-4, "P_min", "W", "Light", "i", "Minimum average optical power on PD")
    p_max: float | None = _f(1e-3, "P_max", "W", "Light", "x", "Maximum average optical power on PD")
    resp: float | None = _f(0.6, "ℜ", "A/W", "Light", "r", "PD responsivity")
    f_rep: float | None = _f(40e6, "f_rep", "Hz", "Light", "f", "Laser repetition rate")
    tau_p: float | None = _f(2e-12, "τ_p", "s", "Light", "w", "Optical pulse width")
    m: float | None = _f(1e-5, "m", "–", "Light", "m", "SRS modulation depth ΔI/I", nonneg=True)
    # Noise
    c_d: float | None = _f(6e-12, "C_d", "F", "Noise", "c", "PD parasitic capacitance")
    en_opamp: float | None = _f(2.5e-9, "e_n", "V/√Hz", "Noise", "e", "Opamp input voltage noise")
    nep: float | None = _f(7.1e-15, "NEP", "W/√Hz", "Noise", "p", "PD noise-equivalent power")
    temp: float | None = _f(295.0, "Temp", "K", "Noise", "t", "Temperature for Johnson noise of R")
    k_crest: float | None = _f(3.0, "k_crest", "–", "Noise", "k", "Noise crest factor (peak/rms)")
    # Lock-in
    tau_lia: float | None = _f(200e-9, "τ_LIA", "s", "Lock-in", "t", "Lock-in integration time")
    n_lia: int | None = _f(
        1, "n_LIA", "–", "Lock-in", "o", "Lock-in filter order, 1–4", kind=int, choices=(1, 2, 3, 4),
    )
    # Opamp/Moku
    v_swing: float | None = _f(2.0, "V_swing", "V", "Opamp/Moku", "s", "Opamp linear output swing, 0-to-peak")
    en_moku: float | None = _f(30e-9, "e_n,Moku", "V/√Hz", "Opamp/Moku", "e", "Moku input voltage noise")
    n_bits: int | None = _f(12, "N_bits", "bit", "Opamp/Moku", "b", "Moku ADC resolution", kind=int)
    v_range: float | None = _f(
        1.0, "V_range", "Vpp", "Opamp/Moku", "v", "Moku input range (1 or 10 only)", choices=(1.0, 10.0),
    )
    # Spectrum
    f_max: float | None = _f(200e6, "f_max", "Hz", "Spectrum", "f", "Highest harmonic frequency included")

    def replace(self, **changes: FieldValue) -> Params:
        """Copy with some fields changed (values are type-checked, not range-validated)."""
        return dataclasses.replace(self, **{k: coerce(k, v) for k, v in changes.items()})

    def to_dict(self) -> dict[str, FieldValue]:
        """Plain dict in SPEC field order; unset fields map to None."""
        return {name: getattr(self, name) for name in FIELDS}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Params:
        """Build from a dict. Missing keys → None (unset); unknown keys → KeyError;
        wrong types → TypeError."""
        unknown = sorted(set(data) - set(FIELDS))
        if unknown:
            raise KeyError(f"unknown parameter(s): {', '.join(unknown)}")
        return cls(**{name: coerce(name, data.get(name)) for name in FIELDS})

    def missing(self, names: list[str] | tuple[str, ...]) -> list[str]:
        """Those of `names` that are unset."""
        return [n for n in names if getattr(self, n) is None]


def _build_fields() -> dict[str, FieldMeta]:
    out: dict[str, FieldMeta] = {}
    for f in dataclasses.fields(Params):
        out[f.name] = dataclasses.replace(f.metadata["meta"], name=f.name)
    return out


FIELDS: dict[str, FieldMeta] = _build_fields()


def coerce(name: str, value: Any) -> FieldValue:
    """Check `value` has the right type for field `name` and normalise it
    (int → float for float fields, integral float → int for int fields).
    None passes through. Raises KeyError for an unknown field, TypeError for a wrong type."""
    meta = FIELDS[name]
    if value is None:
        return None
    if meta.kind is str:
        if not isinstance(value, str):
            raise TypeError(f"{name}: expected text, got {type(value).__name__}")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name}: expected a number, got {type(value).__name__}")
    if meta.kind is int:
        if isinstance(value, float):
            if not value.is_integer():
                raise TypeError(f"{name}: expected an integer, got {value!r}")
            return int(value)
        return value
    return float(value)


def validate_value(name: str, value: FieldValue) -> str | None:
    """Range/choice check for a single field (SPEC §3.1). Returns a reason, or None if valid.
    Unset (None) is valid here; required-ness is checked by the calc."""
    meta = FIELDS[name]
    if value is None:
        return None
    try:
        value = coerce(name, value)
    except TypeError as exc:
        return str(exc)
    if meta.kind is not str:
        assert isinstance(value, (int, float))
        if not math.isfinite(value):
            return "must be finite"
        if meta.nonneg and value < 0:
            return "must be ≥ 0"
        if not meta.nonneg and value <= 0:
            return "must be > 0"
    if meta.choices is not None and value not in meta.choices:
        opts = ", ".join(f"{c:g}" if isinstance(c, float) else str(c) for c in meta.choices)
        return f"must be one of {opts}"
    return None


def validate(params: Params) -> dict[str, str]:
    """All validation errors, keyed by field name. Empty dict = valid."""
    errors: dict[str, str] = {}
    for name in FIELDS:
        reason = validate_value(name, getattr(params, name))
        if reason is not None:
            errors[name] = reason
    p_min, p_max = params.p_min, params.p_max
    if "p_min" not in errors and "p_max" not in errors and p_min is not None and p_max is not None:
        if p_min > p_max:
            errors["p_min"] = "must be ≤ p_max"
            errors["p_max"] = "must be ≥ p_min"
    return errors
