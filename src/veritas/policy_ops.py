"""Policy engineering: lint, diff, simulate, and bounded counterexamples.

`lint` and `diff` are static. They are not proofs. Bounded search is never labeled `prove`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from veritas.models import ASIR
from veritas.policy import CompiledPolicy, PolicyEvaluation, RuntimeVerifier, classification_labels
from veritas.ports import SessionStateStore


@dataclass(frozen=True)
class LintIssue:
    severity: str
    code: str
    message: str
    counterexample: dict[str, Any] | None = None


def lint_policy(policy: CompiledPolicy) -> list[LintIssue]:
    issues: list[LintIssue] = []
    seen_temporal: set[str] = set()
    action_names = set(policy.actions)

    for rule in policy.temporal_rules:
        if rule.rule_id in seen_temporal:
            issues.append(
                LintIssue("error", "DUPLICATE_TEMPORAL_ID", f"duplicate temporal id {rule.rule_id}")
            )
        seen_temporal.add(rule.rule_id)
        if rule.predecessor_action not in action_names:
            issues.append(
                LintIssue(
                    "warning",
                    "UNREACHABLE_TEMPORAL_PREDECESSOR",
                    f"{rule.rule_id}: predecessor {rule.predecessor_action} is not a policy action",
                )
            )
        if rule.forbidden_action not in action_names:
            issues.append(
                LintIssue(
                    "warning",
                    "UNREACHABLE_TEMPORAL_SUCCESSOR",
                    f"{rule.rule_id}: forbidden action {rule.forbidden_action} "
                    "is not a policy action",
                )
            )
        if (
            rule.predecessor_action in action_names
            and rule.forbidden_action in action_names
            and rule.predecessor_action != rule.forbidden_action
        ):
            issues.append(
                LintIssue(
                    "info",
                    "COUNTEREXAMPLE",
                    (
                        f"{rule.predecessor_action} then {rule.forbidden_action}: "
                        "each action may be "
                        f"admissible alone; composition violates {rule.rule_id}"
                    ),
                    counterexample={
                        "sequence": [rule.predecessor_action, rule.forbidden_action],
                        "rule_id": rule.rule_id,
                    },
                )
            )

    for action, action_rule in policy.actions.items():
        if action_rule.budget is not None and action_rule.approval_above is not None:
            if action_rule.approval_above >= action_rule.budget.limit:
                issues.append(
                    LintIssue(
                        "warning",
                        "IMPOSSIBLE_APPROVAL",
                        (
                            f"{action}: approval_above={action_rule.approval_above} "
                            f"is not below budget limit={action_rule.budget.limit}; "
                            "approved amounts cannot reserve"
                        ),
                    )
                )
        if action_rule.allowed_purposes == frozenset():
            issues.append(
                LintIssue(
                    "warning",
                    "EMPTY_PURPOSE_SET",
                    f"{action}: empty allowed_purposes denies every purpose",
                )
            )

    for flow in policy.flow_rules:
        if flow.forbidden_action not in action_names:
            issues.append(
                LintIssue(
                    "warning",
                    "UNREACHABLE_FLOW_ACTION",
                    f"{flow.rule_id}: forbidden action {flow.forbidden_action} "
                    "is not a policy action",
                )
            )
        else:
            issues.append(
                LintIssue(
                    "info",
                    "COUNTEREXAMPLE",
                    (
                        f"label {flow.predecessor_label} then {flow.forbidden_action} violates "
                        f"{flow.rule_id}"
                    ),
                    counterexample={
                        "label": flow.predecessor_label,
                        "action": flow.forbidden_action,
                        "rule_id": flow.rule_id,
                    },
                )
            )
    return issues


def diff_policies(old: CompiledPolicy, new: CompiledPolicy) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    old_actions = set(old.actions)
    new_actions = set(new.actions)
    for added in sorted(new_actions - old_actions):
        changes.append({"kind": "new_tool_exposed", "action": added})
    for removed in sorted(old_actions - new_actions):
        changes.append({"kind": "tool_removed", "action": removed})
    for action in sorted(old_actions & new_actions):
        left = old.actions[action]
        right = new.actions[action]
        if right.max_delegation_depth > left.max_delegation_depth:
            changes.append(
                {
                    "kind": "delegation_widened",
                    "action": action,
                    "from": left.max_delegation_depth,
                    "to": right.max_delegation_depth,
                }
            )
        elif right.max_delegation_depth < left.max_delegation_depth:
            changes.append(
                {
                    "kind": "delegation_narrowed",
                    "label": "AUTHORITY REDUCTION",
                    "action": action,
                    "from": left.max_delegation_depth,
                    "to": right.max_delegation_depth,
                }
            )
        if right.allowed_purposes > left.allowed_purposes:
            changes.append({"kind": "privilege_expanded", "action": action, "field": "purposes"})
        elif right.allowed_purposes < left.allowed_purposes:
            changes.append({"kind": "privilege_reduced", "action": action, "field": "purposes"})
        if left.approval_above != right.approval_above:
            changes.append(
                {
                    "kind": "approval_threshold_changed",
                    "action": action,
                    "from": left.approval_above,
                    "to": right.approval_above,
                }
            )
        if left.budget is not None and right.budget is not None:
            if right.budget.limit > left.budget.limit:
                changes.append(
                    {
                        "kind": "budget_increased",
                        "action": action,
                        "from": left.budget.limit,
                        "to": right.budget.limit,
                    }
                )
            elif right.budget.limit < left.budget.limit:
                changes.append(
                    {
                        "kind": "budget_decreased",
                        "action": action,
                        "from": left.budget.limit,
                        "to": right.budget.limit,
                    }
                )
    return changes


LABELS = {
    "budget_increased": "PRIVILEGE EXPANSION",
    "budget_decreased": "RESOURCE LIMIT CHANGED",
    "approval_threshold_changed": "APPROVAL BURDEN CHANGED",
    "delegation_widened": "AUTHORITY EXPANSION",
    "delegation_narrowed": "AUTHORITY REDUCTION",
    "privilege_expanded": "PRIVILEGE EXPANSION",
    "privilege_reduced": "PRIVILEGE REDUCTION",
    "new_tool_exposed": "PRIVILEGE EXPANSION",
    "tool_removed": "PRIVILEGE REDUCTION",
}


def format_diff(changes: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in changes:
        label = LABELS.get(str(item["kind"]), item["kind"].upper().replace("_", " "))
        action = item.get("action", "")
        if "from" in item and "to" in item:
            lines.append(f"{item['kind']}: {item['from']} → {item['to']}  {label}  {action}")
        else:
            lines.append(f"{item['kind']}: {label}  {action}")
    return "\n".join(lines) if lines else "no semantic differences classified"


class _EphemeralSessions:
    def __init__(self) -> None:
        self._actions: set[tuple[str, str]] = set()
        self._labels: set[tuple[str, str]] = set()

    def has_action(self, session_id: str, action: str) -> bool:
        return (session_id, action) in self._actions

    def record_action(self, session_id: str, action: str, now: datetime) -> None:
        del now
        self._actions.add((session_id, action))

    def has_label(self, session_id: str, label: str) -> bool:
        return (session_id, label) in self._labels

    def record_labels(self, session_id: str, labels: tuple[str, ...], now: datetime) -> None:
        del now
        for label in labels:
            self._labels.add((session_id, label))


def simulate(
    policy: CompiledPolicy,
    actions: list[ASIR],
    *,
    sessions: SessionStateStore | None = None,
) -> list[dict[str, Any]]:
    store: SessionStateStore = sessions if sessions is not None else _EphemeralSessions()
    verifier = RuntimeVerifier(store)
    results: list[dict[str, Any]] = []
    for asir in actions:
        evaluation: PolicyEvaluation = verifier.evaluate(asir, policy)
        results.append(
            {
                "action": asir.action,
                "session_id": asir.context.session_id,
                "allowed": evaluation.allowed,
                "requires_approval": evaluation.requires_approval,
                "reason_code": evaluation.reason_code,
                "explanation": evaluation.explanation,
            }
        )
        if evaluation.allowed:
            store.record_action(asir.context.session_id, asir.action, asir.context.request_ts)
            labels = classification_labels(asir)
            store.record_labels(asir.context.session_id, labels, asir.context.request_ts)
    return results
