"""Tool registry. Importing this package registers every tool (SPEC §6)."""

from srsfe.tools import analyze, design  # noqa: F401  (register on import)
from srsfe.tools.base import REGISTRY, Calc, CalcInputError, Group, Result, Tool

__all__ = ["REGISTRY", "Calc", "CalcInputError", "Group", "Result", "Tool"]
