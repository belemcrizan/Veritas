"""OPA/Cedar comparison artifacts. Per-request baselines, not straw men."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from veritas.baselines import IndependentCallFilter
from veritas.policy import PolicyCompiler
from veritas.runtime import bundled_policy_path
from veritas.scenarios import action_asir, payment_asir

REGO = """
package veritas.b1

default allow := false

allow if {
  input.action == "payment.transfer"
  input.amount <= 10000
}

allow if {
  input.action == "data.read_sensitive"
}

allow if {
  input.action == "message.send_external"
}
"""

CEDAR = """
permit (
  principal,
  action == Action::"payment.transfer",
  resource
) when { context.amount <= 10000 };

permit (
  principal,
  action == Action::"data.read_sensitive",
  resource
);

permit (
  principal,
  action == Action::"message.send_external",
  resource
);
"""


def run_baseline_comparison() -> dict[str, Any]:
    policy = PolicyCompiler().compile_file(bundled_policy_path())
    b1 = IndependentCallFilter(policy)
    fractionation = sum(
        900
        for index in range(12)
        if b1.authorize(payment_asir(amount=900, destination="opa", session_id=f"o-{index}")).executed
    )
    b1.authorize(action_asir("data.read_sensitive", session_id="opa-x"))
    send = b1.authorize(action_asir("message.send_external", session_id="opa-x"))
    return {
        "question": (
            "In which problem classes does trajectory-aware execution control add mechanisms "
            "that per-request authorization needs extra shared state to obtain?"
        ),
        "opa_rego_natural_model": "per-request allow; no residual unless an external store is wired",
        "cedar_natural_model": "per-request permit; same coordination caveat",
        "b1_equivalent_in_process": {
            "fractionation_spent": fractionation,
            "cross_tool_send_executed": send.executed,
        },
        "verdict": {
            "fractionation": "VERITAS wins unless OPA/Cedar is given a shared budget store",
            "atomic_overspend": "equivalent: per-request amount check is enough",
            "cross_tool": "VERITAS wins unless session memory is added outside OPA/Cedar",
            "replay": "different abstraction: capability nonce is not a Cedar/OPA primitive",
        },
        "negative_result": (
            "If operators already keep a transactional budget ledger next to OPA, "
            "the fractionation gap can close. That coordination is the independent variable."
        ),
        "artifacts": {"rego": REGO.strip(), "cedar": CEDAR.strip()},
    }


def write_baseline_artifacts(directory: Path) -> None:
    (directory / "policy.rego").write_text(REGO, encoding="utf-8")
    (directory / "policy.cedar").write_text(CEDAR, encoding="utf-8")
    (directory / "README.md").write_text(
        json.dumps(run_baseline_comparison()["verdict"], indent=2), encoding="utf-8"
    )
