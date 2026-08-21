"""Reusable deterministic scenario builders for examples, tests, and the benchmark."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from veritas.models import ASIR, Principal, RequestContext


DEFAULT_TIME = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def payment_asir(
    *,
    amount: int,
    destination: str = "acct-987",
    session_id: str = "s-42",
    agent_id: str = "finance-agent-01",
    delegation: tuple[str, ...] | None = None,
    request_ts: datetime = DEFAULT_TIME,
    purpose: str = "benchmark",
) -> ASIR:
    chain = delegation or ("user:alice", "orchestrator-07", agent_id)
    return ASIR(
        agent_id=agent_id,
        principal=Principal(
            sub="user:alice", iss="https://idp.example", act=(agent_id,)
        ),
        delegation=chain,
        action="payment.transfer",
        resource="account-123",
        parameters={"amount": amount, "currency": "BRL", "destination": destination},
        purpose=purpose,
        labels={"data_sensitivity": "financial", "irreversible": True},
        context=RequestContext(
            session_id=session_id,
            request_ts=request_ts,
            source_observations=("obs:sha256:demo",),
        ),
    )


def action_asir(
    action: str,
    *,
    session_id: str,
    parameters: dict[str, Any] | None = None,
) -> ASIR:
    agent_id = "support-agent-01"
    return ASIR(
        agent_id=agent_id,
        principal=Principal(
            sub="user:alice", iss="https://idp.example", act=(agent_id,)
        ),
        delegation=("user:alice", agent_id),
        action=action,
        resource="customer-123",
        parameters=parameters or {},
        purpose="benchmark",
        labels={"data_sensitivity": "restricted"},
        context=RequestContext(session_id=session_id, request_ts=DEFAULT_TIME),
    )


def account_state(balance: int = 50000) -> dict[str, Any]:
    return {"account-123.balance": balance, "currency": "BRL"}


def deterministic_tool(asir: ASIR) -> dict[str, Any]:
    return {
        "status": "accepted",
        "action": asir.action,
        "resource": asir.resource,
        "reference": "tool-result-fixed",
    }

