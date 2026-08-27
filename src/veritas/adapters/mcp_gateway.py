"""MCP execution boundary: client -> VERITAS -> cooperative tool.

Adapters only translate MCP params into ASIR. Authorization remains in the engine.
"""

from __future__ import annotations

from typing import Any

from veritas.adapters.frameworks import MCPToolCallAdapter
from veritas.errors import InvalidCapability, MissingCapability, VeritasError
from veritas.guarded import GuardedTool
from veritas.models import Decision, Principal
from veritas.runtime import LocalRuntime


class MCPExecutionGateway:
    def __init__(self, runtime: LocalRuntime, tool: Any) -> None:
        self.runtime = runtime
        self.adapter = MCPToolCallAdapter()
        self.guarded = GuardedTool(runtime.boundary, tool)

    def handle_tools_call(
        self,
        params: dict[str, Any],
        *,
        agent_id: str,
        principal: Principal,
        delegation: tuple[str, ...],
        resource: str,
        purpose: str,
        session_id: str,
        request_ts: Any,
        current_state: dict[str, Any],
        idempotency_key: str,
        labels: dict[str, Any] | None = None,
        approval_token: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        asir = self.adapter.adapt(
            params,
            agent_id=agent_id,
            principal=principal,
            delegation=delegation,
            resource=resource,
            purpose=purpose,
            session_id=session_id,
            request_ts=request_ts,
            labels=labels,
            request_id=request_id,
        )
        result = self.runtime.engine.authorize(
            asir,
            current_state=current_state,
            idempotency_key=idempotency_key,
            approval_token=approval_token,
        )
        payload: dict[str, Any] = {
            "decision": result.decision.value,
            "reason_code": result.reason_code,
            "explanation": result.explanation,
            "trace_id": result.trace_id,
            "asir_hash": asir.hash,
        }
        if result.decision is Decision.ALLOW:
            try:
                committed = self.guarded.invoke(
                    asir,
                    capability=result.capability,
                    current_state=current_state,
                    trace_id=result.trace_id,
                )
                payload["commit_status"] = committed.commit_status
                payload["tool_output"] = committed.tool_output
            except (MissingCapability, InvalidCapability, VeritasError) as exc:
                payload["decision"] = (
                    Decision.STALE.value if exc.code == "STALE_CAPABILITY" else "DENY"
                )
                payload["reason_code"] = exc.code
                payload["explanation"] = str(exc)
        return payload
