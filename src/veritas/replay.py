"""Policy digital twin: re-evaluate historical ASIR ledger nodes under a candidate policy.

This reports policy differences and potential violations. It does not invent
"incidents prevented" and cannot confirm historical incidents the ledger did not record.
"""

from __future__ import annotations

from typing import Any

from veritas.models import ASIR
from veritas.policy import CompiledPolicy, RuntimeVerifier, classification_labels
from veritas.policy_ops import _EphemeralSessions
from veritas.ports import LedgerStore


def replay_policy(
    ledger: LedgerStore,
    *,
    trace_id: str,
    candidate: CompiledPolicy,
    historical_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sessions = _EphemeralSessions()
    verifier = RuntimeVerifier(sessions)
    asir_nodes = [node for node in ledger.trace(trace_id) if node["type"] == "ASIR"]
    new_decisions: list[dict[str, Any]] = []
    for node in asir_nodes:
        payload = node["payload"]
        reconstructed = payload.get("asir")
        if not isinstance(reconstructed, dict):
            new_decisions.append(
                {
                    "asir_hash": payload.get("asir_hash"),
                    "action": payload.get("action"),
                    "status": "unreplayable",
                    "reason": "ASIR payload is a summary hash, not a full request",
                }
            )
            continue
        asir = ASIR.model_validate(reconstructed)
        evaluation = verifier.evaluate(asir, candidate)
        if evaluation.allowed:
            sessions.record_action(asir.context.session_id, asir.action, asir.context.request_ts)
            sessions.record_labels(
                asir.context.session_id,
                classification_labels(asir),
                asir.context.request_ts,
            )
        new_decisions.append(
            {
                "asir_hash": asir.hash,
                "action": asir.action,
                "allowed": evaluation.allowed,
                "requires_approval": evaluation.requires_approval,
                "reason_code": evaluation.reason_code,
            }
        )

    old = historical_decisions or [
        node["payload"] for node in ledger.trace(trace_id) if node["type"] == "VERIFIER_DECISION"
    ]
    newly_denied: list[dict[str, Any]] = []
    newly_allowed: list[dict[str, Any]] = []
    approval_changes = 0
    for historical, candidate_row in zip(old, new_decisions, strict=False):
        old_decision = historical.get("decision")
        if candidate_row.get("status") == "unreplayable":
            continue
        new_allow = bool(candidate_row.get("allowed"))
        if old_decision == "ALLOW" and not new_allow:
            newly_denied.append(candidate_row)
        if old_decision in {"DENY", "REQUIRE_APPROVAL"} and new_allow:
            newly_allowed.append(candidate_row)
        if historical.get("reason_code") == "APPROVAL_REQUIRED" and not candidate_row.get(
            "requires_approval"
        ):
            approval_changes += 1
        if (
            candidate_row.get("requires_approval")
            and historical.get("reason_code") != "APPROVAL_REQUIRED"
        ):
            approval_changes += 1

    reason_distribution: dict[str, int] = {}
    for row in new_decisions:
        code = str(row.get("reason_code") or row.get("status") or "unknown")
        reason_distribution[code] = reason_distribution.get(code, 0) + 1

    return {
        "trace_id": trace_id,
        "candidate_policy_version": candidate.version,
        "historical_actions": len(asir_nodes),
        "old_decisions": old,
        "new_decisions": new_decisions,
        "newly_denied": newly_denied,
        "newly_allowed": newly_allowed,
        "approval_changes": approval_changes,
        "reason_distribution": reason_distribution,
        "claim_boundary": {
            "policy_differences": True,
            "potential_violations": True,
            "confirmed_historical_incidents": False,
        },
    }


def replay_trace_file(path: Any, candidate: CompiledPolicy) -> dict[str, Any]:
    from pathlib import Path

    from veritas.policy_ops import simulate
    from veritas.traces import asir_from_trace, load_jsonl, replay_traces

    traces = load_jsonl(Path(path))
    asirs = [asir_from_trace(item) for item in traces]
    evaluations = simulate(candidate, asirs)
    metrics = replay_traces(traces, evaluations)
    return {
        "source": str(path),
        "candidate_policy_version": candidate.version,
        "evaluations": evaluations,
        "metrics": metrics,
        "claim_boundary": {
            "policy_behavior_change": True,
            "attacks_prevented": False,
        },
    }
