"""Framework adapters that normalize tool calls into ASIR without importing frameworks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from veritas.models import ASIR, Principal, RequestContext


class LangGraphToolCallAdapter:
    """Normalize LangChain/LangGraph's ``{name, args, id}`` tool-call shape."""

    def adapt(
        self,
        tool_call: dict[str, Any],
        *,
        agent_id: str,
        principal: Principal,
        delegation: tuple[str, ...],
        resource: str,
        purpose: str,
        session_id: str,
        request_ts: datetime,
        labels: dict[str, Any] | None = None,
    ) -> ASIR:
        name = tool_call.get("name")
        arguments = tool_call.get("args")
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise ValueError("LangGraph tool call requires string name and object args")
        observation = tool_call.get("id")
        observations = () if observation is None else (f"tool-call:{observation}",)
        return ASIR(
            agent_id=agent_id,
            principal=principal,
            delegation=delegation,
            action=name,
            resource=resource,
            parameters=arguments,
            purpose=purpose,
            labels=labels or {},
            context=RequestContext(
                session_id=session_id,
                request_ts=request_ts,
                source_observations=observations,
            ),
        )


class MCPToolCallAdapter:
    """Normalize an MCP ``tools/call`` params object with ``name`` and ``arguments``."""

    def adapt(self, params: dict[str, Any], **context: Any) -> ASIR:
        normalised = {
            "name": params.get("name"),
            "args": params.get("arguments", {}),
            "id": context.pop("request_id", None),
        }
        return LangGraphToolCallAdapter().adapt(normalised, **context)

