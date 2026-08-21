"""The twelve-transfer hero scenario from the design document."""

from __future__ import annotations

import json
import tempfile
from datetime import timezone
from pathlib import Path
from typing import Any

from veritas.adapters.local import MutableClock
from veritas.models import Decision
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import DEFAULT_TIME, account_state, deterministic_tool, payment_asir


def run_demo(database_path: str | None = None) -> dict[str, Any]:
    if database_path is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="veritas-demo-")
        db_path = Path(temp_dir.name) / "veritas.db"
    else:
        temp_dir = None
        db_path = Path(database_path)
    clock = MutableClock(DEFAULT_TIME.astimezone(timezone.utc))
    runtime = create_local_runtime(
        database_path=db_path,
        policy_path=bundled_policy_path(),
        clock=clock,
    )

    decisions: list[dict[str, Any]] = []
    last_trace = ""
    try:
        for index in range(1, 13):
            asir = payment_asir(amount=900, session_id=f"hero-{index}")
            result = runtime.engine.authorize(
                asir,
                current_state=account_state(),
                idempotency_key=f"hero-transfer-{index}",
                trace_id=f"trace:hero:{index}",
            )
            last_trace = result.trace_id
            if result.decision == Decision.ALLOW:
                assert result.capability is not None
                runtime.boundary.execute(
                    result.capability,
                    asir=asir,
                    current_state=account_state(),
                    tool=deterministic_tool,
                    trace_id=result.trace_id,
                )
            decisions.append(
                {
                    "transfer": index,
                    "decision": result.decision.value,
                    "reason": result.reason_code,
                    "residual": next(iter(result.residual.values()), None),
                }
            )

        resource_key = "money:acct-987:86400s"
        summary = {
            "scenario": "twelve transfers of 900 against a 10,000/24h invariant",
            "allowed": sum(item["decision"] == "ALLOW" for item in decisions),
            "denied": sum(item["decision"] == "DENY" for item in decisions),
            "used": runtime.store.used(resource_key, 86400, clock.now()),
            "twelfth_decision": decisions[-1]["decision"],
            "ledger_integrity": runtime.store.verify_integrity(),
            "last_trace_nodes": len(runtime.store.trace(last_trace)),
            "decisions": decisions,
        }
        return summary
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def print_demo(database_path: str | None = None) -> None:
    print(json.dumps(run_demo(database_path), indent=2, sort_keys=True))
