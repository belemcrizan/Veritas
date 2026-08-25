"""Consequential tools that refuse to run without a verified capability."""

from __future__ import annotations

from typing import Any, Callable

from veritas.boundary import ToolBoundary
from veritas.errors import MissingCapability
from veritas.models import ASIR, BoundaryResult

Tool = Callable[[ASIR], Any]


class GuardedTool:
    """Execution boundary: the tool is unreachable without a capability string.

    This is the difference between an advisor the agent can ignore and a control
    the tool itself enforces.
    """

    def __init__(self, boundary: ToolBoundary, tool: Tool) -> None:
        self.boundary = boundary
        self.tool = tool

    def invoke(
        self,
        asir: ASIR,
        *,
        capability: str | None,
        current_state: dict[str, Any],
        trace_id: str,
    ) -> BoundaryResult:
        if capability is None or capability.strip() == "":
            raise MissingCapability(
                "the protected tool will not execute without a capability verified at the boundary"
            )
        return self.boundary.execute(
            capability,
            asir=asir,
            current_state=current_state,
            tool=self.tool,
            trace_id=trace_id,
        )
