"""Policy compilation and constant-time runtime checks.

The hot path consumes an immutable table. Optional Cedar and SMT artifacts are kept outside
the runtime path, matching design rule R7.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from veritas.canonical import digest
from veritas.errors import PolicyError
from veritas.models import ASIR
from veritas.ports import SessionStateStore


@dataclass(frozen=True)
class BudgetRule:
    name: str
    amount_parameter: str
    key_parameter: str
    limit: int
    window_seconds: int

    def resource_key(self, asir: ASIR) -> str:
        key = asir.parameters.get(self.key_parameter)
        if not isinstance(key, str) or not key:
            raise PolicyError(f"missing string parameter: {self.key_parameter}")
        return f"{self.name}:{key}:{self.window_seconds}s"

    def amount(self, asir: ASIR) -> int:
        amount = asir.parameters.get(self.amount_parameter)
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise PolicyError(f"{self.amount_parameter} must be a positive integer in minor units")
        return amount


@dataclass(frozen=True)
class ActionRule:
    action: str
    max_delegation_depth: int
    allowed_purposes: frozenset[str]
    approval_above: int | None
    budget: BudgetRule | None


@dataclass(frozen=True)
class TemporalRule:
    rule_id: str
    predecessor_action: str
    forbidden_action: str


@dataclass(frozen=True)
class CompiledPolicy:
    version: str
    digest: str
    actions: dict[str, ActionRule]
    temporal_rules: tuple[TemporalRule, ...]
    source: dict[str, Any]


@dataclass(frozen=True)
class PolicyEvaluation:
    allowed: bool
    reason_code: str
    explanation: str
    requires_approval: bool = False
    budget: BudgetRule | None = None
    amount: int | None = None
    resource_key: str | None = None


class PolicyCompiler:
    """Compile a reviewed JSON policy into immutable runtime lookup tables."""

    compiler_version = "veritas-table-v1"

    def compile_file(self, path: str | Path) -> CompiledPolicy:
        resolved = Path(path)
        if not resolved.is_file():
            raise PolicyError(f"policy file not found: {resolved}")
        try:
            with resolved.open("r", encoding="utf-8") as stream:
                raw = json.load(stream)
        except json.JSONDecodeError as exc:
            raise PolicyError(f"policy is not valid JSON: {exc.msg}") from exc
        except OSError as exc:
            raise PolicyError(f"policy file could not be read: {exc}") from exc
        if not isinstance(raw, dict):
            raise PolicyError("policy must be an object")
        return self.compile(raw)

    def compile(self, raw: dict[str, Any]) -> CompiledPolicy:
        if not isinstance(raw, dict):
            raise PolicyError("policy must be an object")
        version = raw.get("version")
        if not isinstance(version, str) or not version:
            raise PolicyError("policy.version is required")
        raw_actions = raw.get("actions")
        if not isinstance(raw_actions, dict) or not raw_actions:
            raise PolicyError("policy.actions must be a non-empty object")

        actions: dict[str, ActionRule] = {}
        for action, config in raw_actions.items():
            if not isinstance(action, str) or not isinstance(config, dict):
                raise PolicyError("each action rule must be an object")
            max_depth = config.get("max_delegation_depth", 3)
            if not isinstance(max_depth, int) or max_depth < 1:
                raise PolicyError(f"{action}: invalid max_delegation_depth")
            purposes_raw = config.get("allowed_purposes", [])
            if not isinstance(purposes_raw, list) or not all(
                isinstance(item, str) and item for item in purposes_raw
            ):
                raise PolicyError(f"{action}: allowed_purposes must be strings")
            approval = config.get("approval_above")
            if approval is not None and (
                isinstance(approval, bool) or not isinstance(approval, int) or approval < 0
            ):
                raise PolicyError(f"{action}: approval_above must be a non-negative integer")

            budget: BudgetRule | None = None
            budget_raw = config.get("budget")
            if budget_raw is not None:
                if not isinstance(budget_raw, dict):
                    raise PolicyError(f"{action}: budget must be an object")
                try:
                    budget = BudgetRule(
                        name=str(budget_raw["name"]),
                        amount_parameter=str(budget_raw["amount_parameter"]),
                        key_parameter=str(budget_raw["key_parameter"]),
                        limit=int(budget_raw["limit"]),
                        window_seconds=int(budget_raw["window_seconds"]),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise PolicyError(f"{action}: invalid budget rule") from exc
                if budget.limit <= 0 or budget.window_seconds <= 0:
                    raise PolicyError(f"{action}: budget values must be positive")

            actions[action] = ActionRule(
                action=action,
                max_delegation_depth=max_depth,
                allowed_purposes=frozenset(purposes_raw),
                approval_above=approval,
                budget=budget,
            )

        temporal_rules: list[TemporalRule] = []
        for item in raw.get("temporal_rules", []):
            if not isinstance(item, dict):
                raise PolicyError("temporal rules must be objects")
            try:
                temporal_rules.append(
                    TemporalRule(
                        rule_id=str(item["id"]),
                        predecessor_action=str(item["predecessor_action"]),
                        forbidden_action=str(item["forbidden_action"]),
                    )
                )
            except KeyError as exc:
                raise PolicyError("incomplete temporal rule") from exc

        policy_digest = digest(
            {"compiler": self.compiler_version, "policy": raw},
            prefix="policy:sha256:",
        )
        return CompiledPolicy(
            version=version,
            digest=policy_digest,
            actions=actions,
            temporal_rules=tuple(temporal_rules),
            source=raw,
        )


class InMemoryPolicyStore:
    def __init__(self, policy: CompiledPolicy) -> None:
        self._policy = policy

    def current(self) -> CompiledPolicy:
        return self._policy

    def publish(self, policy: CompiledPolicy) -> None:
        self._policy = policy


class RuntimeVerifier:
    def __init__(self, sessions: SessionStateStore) -> None:
        self._sessions = sessions

    def evaluate(self, asir: ASIR, policy: CompiledPolicy) -> PolicyEvaluation:
        rule = policy.actions.get(asir.action)
        if rule is None:
            return PolicyEvaluation(False, "ACTION_NOT_ALLOWED", "Action is absent from policy")
        if len(asir.delegation) > rule.max_delegation_depth:
            return PolicyEvaluation(
                False,
                "DELEGATION_DEPTH_EXCEEDED",
                f"Delegation depth {len(asir.delegation)} exceeds {rule.max_delegation_depth}",
            )
        if rule.allowed_purposes and asir.purpose not in rule.allowed_purposes:
            return PolicyEvaluation(False, "PURPOSE_NOT_ALLOWED", "Purpose is not allowed")

        for temporal in policy.temporal_rules:
            if temporal.forbidden_action == asir.action and self._sessions.has_action(
                asir.context.session_id, temporal.predecessor_action
            ):
                return PolicyEvaluation(
                    False,
                    "TEMPORAL_INVARIANT_VIOLATION",
                    f"{temporal.rule_id}: {asir.action} is forbidden after "
                    f"{temporal.predecessor_action}",
                )

        amount: int | None = None
        resource_key: str | None = None
        if rule.budget is not None:
            try:
                amount = rule.budget.amount(asir)
                resource_key = rule.budget.resource_key(asir)
            except PolicyError as exc:
                return PolicyEvaluation(False, "INVALID_ACTION_ARGUMENTS", str(exc))

        requires_approval = (
            rule.approval_above is not None and amount is not None and amount > rule.approval_above
        )
        return PolicyEvaluation(
            True,
            "POLICY_ALLOW",
            "Compiled policy table allows the action",
            requires_approval=requires_approval,
            budget=rule.budget,
            amount=amount,
            resource_key=resource_key,
        )


def bounded_fractionation_counterexample(
    *, limit: int, atomic_limit: int, amount: int, depth: int
) -> list[int] | None:
    """Return a simple counterexample against a unit-call-only baseline.

    This dependency-free check is intentionally small. The repository also includes an SMT-LIB
    model for CI with Z3.
    """

    if amount <= 0 or depth <= 0:
        return None
    trajectory: list[int] = []
    total = 0
    for _ in range(depth):
        if amount > atomic_limit:
            return None
        trajectory.append(amount)
        total += amount
        if total > limit:
            return trajectory
    return None
