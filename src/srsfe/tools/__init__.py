"""Tool registry. Importing this package registers every tool (SPEC §6)."""

from srsfe.tools import design, analyze  # noqa: F401, I001  (registration order = launcher order)
from srsfe.tools.base import REGISTRY, Calc, CalcInputError, Group, Result, Tool

__all__ = ["REGISTRY", "Calc", "CalcInputError", "Group", "Result", "Tool"]
