"""Executable independent-call baselines.

B0 never consults policy. B1 evaluates ``Policy(a_t)`` only: the current action,
with no trajectory ``H``, no reserved residual, and no capability lifecycle.

These baselines exist so VERITAS can lose on families that a per-call filter
already handles. A forced-fail baseline would not be science.
"""

from __future__ import annotations

from dataclasses import dataclass

from veritas.errors import PolicyError
from veritas.models import ASIR, Decision
from veritas.policy import CompiledPolicy


@dataclass(frozen=True)
class BaselineDecision:
    name: str
    decision: Decision
    reason_code: str
    explanation: str
    executed: bool


class AlwaysAllowBaseline:
    """B0: every request is executed."""

    name = "B0"

    def authorize(self, asir: ASIR, *, approval_token: str | None = None) -> BaselineDecision:
        del asir, approval_token
        return BaselineDecision(
            name=self.name,
            decision=Decision.ALLOW,
            reason_code="B0_NO_POLICY",
            explanation="No protection: the tool executes the request",
            executed=True,
        )


class IndependentCallFilter:
    """B1: ``Policy(a_t)`` with no memory of prior calls.

    Single-call facts that *are* visible on ``a_t`` still apply: action membership,
    purpose, delegation depth, and whether *this* amount exceeds the configured
    limit. Cumulative use, session order, capability TTL, replay, and
    hash-bound approvals are invisible by construction.
    """

    name = "B1"

    def __init__(self, policy: CompiledPolicy) -> None:
        self.policy = policy

    def authorize(self, asir: ASIR, *, approval_token: str | None = None) -> BaselineDecision:
        rule = self.policy.actions.get(asir.action)
        if rule is None:
            return self._deny("ACTION_NOT_ALLOWED", "Action is absent from policy")
        if len(asir.delegation) > rule.max_delegation_depth:
            return self._deny(
                "DELEGATION_DEPTH_EXCEEDED",
                f"Delegation depth {len(asir.delegation)} exceeds {rule.max_delegation_depth}",
            )
        if rule.allowed_purposes and asir.purpose not in rule.allowed_purposes:
            return self._deny("PURPOSE_NOT_ALLOWED", "Purpose is not allowed")

        amount: int | None = None
        if rule.budget is not None:
            try:
                amount = rule.budget.amount(asir)
            except PolicyError as exc:
                return self._deny("INVALID_ACTION_ARGUMENTS", str(exc))
            if amount > rule.budget.limit:
                return self._deny(
                    "ATOMIC_LIMIT_EXCEEDED",
                    f"{amount} exceeds the per-call limit {rule.budget.limit}",
                )

        if rule.approval_above is not None and amount is not None and amount > rule.approval_above:
            if approval_token is None:
                return BaselineDecision(
                    name=self.name,
                    decision=Decision.REQUIRE_APPROVAL,
                    reason_code="APPROVAL_REQUIRED",
                    explanation="Per-call filter requires an approval flag for this amount",
                    executed=False,
                )
            return BaselineDecision(
                name=self.name,
                decision=Decision.ALLOW,
                reason_code="B1_UNBOUND_APPROVAL",
                explanation=(
                    "Approval is treated as a boolean on this call; it is not bound to the ASIR hash"
                ),
                executed=True,
            )

        return BaselineDecision(
            name=self.name,
            decision=Decision.ALLOW,
            reason_code="B1_CALL_OK",
            explanation="The independent call satisfies Policy(a_t)",
            executed=True,
        )

    def _deny(self, reason_code: str, explanation: str) -> BaselineDecision:
        return BaselineDecision(
            name=self.name,
            decision=Decision.DENY,
            reason_code=reason_code,
            explanation=explanation,
            executed=False,
        )
