"""Tool, Calc, Group, Result and the tool registry (SPEC §6).

Tools are the only place where Params is unpacked into core calls (SPEC §2, rule 3).
Adding a tool = one new module in tools/ that calls register() (rule 4).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from srsfe.core.params import FIELDS, Params, validate, validate_value
from srsfe.core.warnings import DesignWarning

POWERS = ("p_min", "p_max")
PLOTS = ("bode", "spectrum", "budget", "noise")
# Plot-menu toggle keys (SPEC §8.3), declared next to the plot names.
PLOT_KEYS = {"bode": "b", "spectrum": "s", "budget": "u", "noise": "n"}

# Output metadata (SPEC §3.2): name → (unit, description). "bool" marks a yes/no output.
OUTPUTS: dict[str, tuple[str, str]] = {
    "q": ("–", "Tank quality factor"),
    "l_f": ("H", "Tank inductance"),
    "c_f": ("F", "Tank capacitance"),
    "f0_calc": ("Hz", "Resonance from L, C"),
    "tau_tank": ("s", "Tank ring-down time constant"),
    "bw_3db": ("Hz", "Tank −3 dB bandwidth"),
    "b_eq": ("Hz", "Tank noise-equivalent bandwidth"),
    "settles": ("bool", "N_τ·τ_tank ≤ t_dwell"),
    "i_0": ("A", "Average photocurrent"),
    "q_p": ("C", "Charge per pulse"),
    "i_pk": ("A", "Peak pulse current"),
    "f_n": ("Hz", "Harmonic frequency"),
    "i_n": ("A", "Harmonic line current 2·I₀"),
    "z_n": ("Ω", "|Z_f| at the harmonic"),
    "att_n": ("dB", "Attenuation re R"),
    "v_n": ("V", "Harmonic output amplitude"),
    "v_n_sum": ("V", "Coherent sum ΣV_n"),
    "v_n_rss": ("V", "RSS of V_n"),
    "i_sig": ("A", "Signal current m·I₀"),
    "v_sig": ("V", "Signal output amplitude"),
    "i_sh": ("A/√Hz", "Shot noise"),
    "i_r": ("A/√Hz", "Johnson noise of R"),
    "i_en": ("A/√Hz", "Opamp voltage noise, input-referred"),
    "i_nep": ("A/√Hz", "PD NEP noise"),
    "i_elec": ("A/√Hz", "Electronic noise √(i_R² + i_en² + i_NEP²)"),
    "i_tot": ("A/√Hz", "Total input noise"),
    "v_dens": ("V/√Hz", "Output noise density R·i_tot"),
    "v_rms": ("V", "Output rms noise over B_eq"),
    "enbw_lia": ("Hz", "Lock-in ENBW"),
    "v_rms_lia": ("V", "Output rms noise over ENBW"),
    "v_coh": ("V", "Worst-case coherent output peak"),
    "occ_swing": ("%", "Occupancy of opamp swing"),
    "occ_moku": ("%", "Occupancy of Moku range"),
    "snr": ("dB", "SNR over B_eq"),
    "snr_lia": ("dB", "Lock-in SNR"),
    "shot_clear": ("dB", "Shot-noise clearance over electronic noise"),
    "lsb": ("V", "ADC LSB"),
    "v_q": ("V", "Quantization noise rms"),
}
# Outputs that live in the per-power "harmonics" table rather than scalars/per_power.
HARMONIC_COLUMNS = ("f_n", "i_n", "z_n", "att_n", "v_n")


# -- Result --------------------------------------------------------------------------


@dataclass(frozen=True)
class Result:
    """Output of one Calc run. JSON-serializable via to_json()/from_json().

    scalars:   name → value (float, bool or None)
    per_power: name → {"p_min": value, "p_max": value}
    tables:    name → {"p_min": {column: [values]}, "p_max": {...}} (e.g. "harmonics")
    params:    the inputs the result was computed from (Params.to_dict())
    """

    tool: str
    calc: str
    params: dict[str, Any]
    scalars: dict[str, Any] = field(default_factory=dict)
    per_power: dict[str, dict[str, float]] = field(default_factory=dict)
    tables: dict[str, dict[str, dict[str, list[Any]]]] = field(default_factory=dict)
    warnings: tuple[DesignWarning, ...] = ()
    plots: tuple[str, ...] = ()

    def get(self, name: str, power: str | None = None) -> Any:
        """A scalar, or a per-power value when `power` is given. KeyError if absent."""
        if power is None:
            return self.scalars[name]
        return self.per_power[name][power]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "calc": self.calc,
            "params": self.params,
            "scalars": self.scalars,
            "per_power": self.per_power,
            "tables": self.tables,
            "warnings": [
                {"id": w.id, "message": w.message, "severity": w.severity, "power": w.power,
                 "fields": list(w.fields)}
                for w in self.warnings
            ],
            "plots": list(self.plots),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Result:
        return cls(
            tool=d["tool"],
            calc=d["calc"],
            params=d["params"],
            scalars=d["scalars"],
            per_power=d["per_power"],
            tables=d["tables"],
            warnings=tuple(
                DesignWarning(w["id"], w["message"], w["severity"], w["power"],
                              tuple(w["fields"]))
                for w in d["warnings"]
            ),
            plots=tuple(d["plots"]),
        )

    def to_json(self) -> str:
        """Strict JSON; non-finite floats (e.g. SNR = −inf when m = 0) are tagged
        as {"$float": "-inf" | "inf" | "nan"}."""
        return json.dumps(_encode(self.to_dict()), allow_nan=False, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> Result:
        return cls.from_dict(_decode(json.loads(text)))


def _encode(x: Any) -> Any:
    if isinstance(x, float) and not math.isfinite(x):
        return {"$float": "nan" if math.isnan(x) else ("inf" if x > 0 else "-inf")}
    if isinstance(x, dict):
        return {k: _encode(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_encode(v) for v in x]
    return x


def _decode(x: Any) -> Any:
    if isinstance(x, dict):
        if set(x) == {"$float"}:
            return float(x["$float"])
        return {k: _decode(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_decode(v) for v in x]
    return x


# -- Calc / Group / Tool -------------------------------------------------------------


class CalcInputError(ValueError):
    """Raised by Calc.run when required inputs are missing or used inputs are invalid."""

    def __init__(self, missing: list[str], invalid: dict[str, str]) -> None:
        self.missing = missing
        self.invalid = invalid
        parts = []
        if missing:
            parts.append("missing: " + ", ".join(missing))
        if invalid:
            parts.append("invalid: " + ", ".join(f"{k} ({v})" for k, v in invalid.items()))
        super().__init__("; ".join(parts))


@dataclass(frozen=True)
class Calc:
    name: str
    key: str  # one digit
    required: tuple[str, ...]
    optional: tuple[str, ...]
    outputs: tuple[str, ...]
    plots: tuple[str, ...]
    compute: Callable[[Params], Result] = field(repr=False, compare=False)

    def missing(self, params: Params) -> list[str]:
        return params.missing(self.required)

    def invalid(self, params: Params) -> dict[str, str]:
        """Validation errors among the inputs this calc uses (unused fields are ignored)."""
        used = set(self.required) | set(self.optional)
        errors = {n: r for n in used if (r := validate_value(n, getattr(params, n))) is not None}
        cross = validate(params)
        for n in ("p_min", "p_max"):
            if n in used and n in cross and n not in errors:
                errors[n] = cross[n]
        return dict(sorted(errors.items(), key=lambda kv: list(FIELDS).index(kv[0])))

    def run(self, params: Params) -> Result:
        """Validate first; raise CalcInputError and compute nothing if anything is wrong."""
        missing, invalid = self.missing(params), self.invalid(params)
        if missing or invalid:
            raise CalcInputError(missing, invalid)
        return self.compute(params)


@dataclass(frozen=True)
class Group:
    name: str
    key: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class Tool:
    name: str
    key: str
    description: str
    calcs: tuple[Calc, ...]
    groups: tuple[Group, ...]

    def calc(self, key: str) -> Calc:
        for c in self.calcs:
            if c.key == key:
                return c
        raise KeyError(f"tool {self.key!r} has no calc {key!r}")


# -- registry ------------------------------------------------------------------------

REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> Tool:
    if tool.key in REGISTRY:
        raise ValueError(f"tool key {tool.key!r} already registered")
    REGISTRY[tool.key] = tool
    return tool


def unique_ordered(*seqs: tuple[str, ...]) -> tuple[str, ...]:
    """Concatenate name tuples keeping first occurrence order."""
    return tuple(dict.fromkeys(x for s in seqs for x in s))
