"""Minimal, executable integration through the supported public API.

Run from the repository root after installation:

    python examples/library_integration.py
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from veritas import (
    ASIR,
    Decision,
    Principal,
    RequestContext,
    bundled_policy_path,
    create_local_runtime,
)


def payment_tool(asir: ASIR) -> dict[str, str]:
    """Represent a cooperative consequential tool for this local example."""

    return {
        "status": "accepted",
        "action": asir.action,
        "resource": asir.resource,
        "reference": "example-payment-0001",
    }


def build_payment_request() -> ASIR:
    """Build one canonical request accepted by the bundled payment policy."""

    agent_id = "finance-agent-01"
    return ASIR(
        agent_id=agent_id,
        principal=Principal(
            sub="user:alice",
            iss="https://idp.example",
            act=(agent_id,),
        ),
        delegation=("user:alice", "orchestrator-07", agent_id),
        action="payment.transfer",
        resource="account-123",
        parameters={
            "amount": 900,
            "currency": "BRL",
            "destination": "acct-library-example",
        },
        purpose="invoice-payment",
        labels={"data_sensitivity": "financial", "irreversible": True},
        context=RequestContext(
            session_id="library-example-session",
            request_ts=datetime.now(UTC),
            source_observations=("example:invoice-0001",),
        ),
    )


def run_example(database_path: str | Path | None = None) -> dict[str, Any]:
    """Authorize and execute one payment through the local VERITAS boundary."""

    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    if database_path is None:
        temporary_directory = tempfile.TemporaryDirectory(prefix="veritas-library-example-")
        resolved_database = Path(temporary_directory.name) / "veritas.db"
    else:
        resolved_database = Path(database_path)

    try:
        runtime = create_local_runtime(
            database_path=resolved_database,
            policy_path=bundled_policy_path(),
        )
        asir = build_payment_request()
        current_state = {"account-123.balance": 50000, "currency": "BRL"}

        authorization = runtime.engine.authorize(
            asir,
            current_state=current_state,
            idempotency_key="example:invoice-0001",
        )

        output: dict[str, Any] = {
            "decision": authorization.decision.value,
            "reason_code": authorization.reason_code,
            "trace_id": authorization.trace_id,
            "residual": authorization.residual,
        }

        if authorization.decision is Decision.ALLOW:
            if authorization.capability is None:
                raise RuntimeError("ALLOW result did not include a capability")
            committed = runtime.boundary.execute(
                authorization.capability,
                asir=asir,
                current_state=current_state,
                tool=payment_tool,
                trace_id=authorization.trace_id,
            )
            output["commit_status"] = committed.commit_status
            output["tool_output"] = committed.tool_output

        output["ledger_integrity"] = runtime.store.verify_integrity()
        return output
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
