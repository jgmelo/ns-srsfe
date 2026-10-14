"""Generic sweep engine (SPEC §6.3): run a calc once per value of one input field."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from srsfe.core.params import FIELDS, FieldValue, Params

POWERS = ("p_min", "p_max")


class _ResultLike(Protocol):
    scalars: Mapping[str, Any]
    per_power: Mapping[str, Mapping[str, Any]]


class _CalcLike(Protocol):
    def run(self, params: Params) -> _ResultLike: ...


def sweep(
    calc: _CalcLike, params: Params, field: str, values: Iterable[FieldValue],
    outputs: Iterable[str],
) -> list[dict[str, Any]]:
    """One row per value: {field: value, output: v, per_power_output@p_min: v, …@p_max: v}.

    `params` is never mutated (each run uses a copy with `field` replaced). An output the
    calc does not produce raises KeyError. Calc errors (missing/invalid input) propagate.
    """
    if field not in FIELDS:
        raise KeyError(f"unknown field {field!r}")
    outputs = list(outputs)
    rows: list[dict[str, Any]] = []
    for value in values:
        result = calc.run(params.replace(**{field: value}))
        row: dict[str, Any] = {field: value}
        for name in outputs:
            if name in result.scalars:
                row[name] = result.scalars[name]
            elif name in result.per_power:
                for power in POWERS:
                    row[f"{name}@{power}"] = result.per_power[name][power]
            else:
                raise KeyError(f"calc does not produce output {name!r}")
        rows.append(row)
    return rows
