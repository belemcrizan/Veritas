"""Versioned experimental action-trace records. No real personal data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from veritas.models import ASIR, FrozenModel, Principal, RequestContext
from veritas.scenarios import DEFAULT_TIME

TRACE_SCHEMA_VERSION = 1
GroundTruth = Literal["legitimate", "policy_violating", "ambiguous"]


class ActionTrace(FrozenModel):
    schema_version: int = TRACE_SCHEMA_VERSION
    trace_id: str
    session_id: str
    principal: str
    agent: str
    action: str
    resource: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    sensitivity: list[str] = Field(default_factory=list)
    timestamp: str
    policy_version: str
    decision: str | None = None
    execution_result: str | None = None
    ground_truth: GroundTruth | None = None


def asir_from_trace(trace: ActionTrace) -> ASIR:
    agent_id = trace.agent
    return ASIR(
        agent_id=agent_id,
        principal=Principal(sub=trace.principal, iss="https://idp.example", act=(agent_id,)),
        delegation=(trace.principal, agent_id),
        action=trace.action,
        resource=trace.resource,
        parameters=trace.parameters,
        purpose="benchmark",
        labels={"data_sensitivity": trace.sensitivity[0] if trace.sensitivity else "restricted"},
        context=RequestContext(session_id=trace.session_id, request_ts=DEFAULT_TIME),
        sensitivity=trace.sensitivity[0] if trace.sensitivity else None,
    )


def load_jsonl(path: Path) -> list[ActionTrace]:
    rows: list[ActionTrace] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(ActionTrace.model_validate(json.loads(stripped)))
    return rows


def replay_traces(traces: list[ActionTrace], evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare candidate decisions to experimental labels, not to VERITAS itself."""

    newly_denied = 0
    newly_allowed = 0
    true_intervention = 0
    false_intervention = 0
    missed_violation = 0
    for trace, evaluation in zip(traces, evaluations, strict=False):
        allowed = bool(evaluation.get("allowed"))
        historical = trace.decision
        if historical == "ALLOW" and not allowed:
            newly_denied += 1
        if historical in {"DENY", "REQUIRE_APPROVAL"} and allowed:
            newly_allowed += 1
        label = trace.ground_truth
        intervened = not allowed
        if label == "policy_violating" and intervened:
            true_intervention += 1
        elif label == "legitimate" and intervened:
            false_intervention += 1
        elif label == "policy_violating" and not intervened:
            missed_violation += 1
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "actions": len(traces),
        "newly_denied": newly_denied,
        "newly_allowed": newly_allowed,
        "true_intervention": true_intervention,
        "false_intervention": false_intervention,
        "missed_violation": missed_violation,
        "interpretation": "newly_denied is a policy behavior change, not 'attacks prevented'",
    }
