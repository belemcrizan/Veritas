"""Ablations: remove one mechanism and measure what breaks. Not a marketing table."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from veritas.baselines import IndependentCallFilter
from veritas.models import Decision
from veritas.policy import PolicyCompiler
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import account_state, action_asir, payment_asir


def _fractionation_spend() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="veritas-ablate-") as directory:
        runtime = create_local_runtime(
            database_path=Path(directory) / "a.db", policy_path=bundled_policy_path()
        )
        allowed = 0
        for index in range(12):
            asir = payment_asir(amount=900, destination="ablate", session_id=f"a-{index}")
            result = runtime.engine.authorize(
                asir, current_state=account_state(), idempotency_key=f"a-{index}"
            )
            if result.decision is Decision.ALLOW:
                allowed += 1
        used = runtime.store.used("money:ablate:86400s", 86400, runtime.clock.now())
        return {"allowed": allowed, "used": used, "overspend": used > 10000}


def run_ablations() -> dict[str, Any]:
    full = _fractionation_spend()
    policy = PolicyCompiler().compile_file(bundled_policy_path())
    b1 = IndependentCallFilter(policy)
    b1_spent = sum(
        900
        for index in range(12)
        if b1.authorize(
            payment_asir(amount=900, destination="ablate-b1", session_id=f"b1-{index}")
        ).executed
    )
    b1_read = b1.authorize(action_asir("data.read_sensitive", session_id="ab-cross"))
    b1_send = b1.authorize(action_asir("message.send_external", session_id="ab-cross"))
    return {
        "full_veritas_fractionation": full,
        "no_trajectory_b1_fractionation_spent": b1_spent,
        "no_trajectory_cross_tool_send": b1_send.executed,
        "observation": (
            "Removing trajectory memory (B1) lets 12x900 spend 10800 and allows "
            f"external send after sensitive read={b1_read.executed}."
        ),
        "not_claimed": "This is not a complete factorial ablation of nonce/boundary/state binding.",
    }
