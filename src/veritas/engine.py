"""Prepare and verify orchestration for trajectory-aware authorization."""

from __future__ import annotations

import uuid
from typing import Any

from veritas.approval import ApprovalService
from veritas.canonical import digest
from veritas.crypto import CapabilityCodec
from veritas.errors import BudgetDenied, InvalidApproval
from veritas.gate import DeterministicBypassGate
from veritas.models import ASIR, AuthorizationResult, Decision
from veritas.policy import InMemoryPolicyStore, RuntimeVerifier
from veritas.ports import BudgetStore, Clock, LedgerStore, Telemetry


class VeritasEngine:
    """The verified boundary's online authorization service.

    The engine never executes tools. It records the action, evaluates compiled policy, reserves
    monotonic resources, and issues a short-lived signed capability.
    """

    def __init__(
        self,
        *,
        policies: InMemoryPolicyStore,
        verifier: RuntimeVerifier,
        budgets: BudgetStore,
        ledger: LedgerStore,
        codec: CapabilityCodec,
        approvals: ApprovalService,
        clock: Clock,
        telemetry: Telemetry,
        gate: DeterministicBypassGate | None = None,
    ) -> None:
        self.policies = policies
        self.verifier = verifier
        self.budgets = budgets
        self.ledger = ledger
        self.codec = codec
        self.approvals = approvals
        self.clock = clock
        self.telemetry = telemetry
        self.gate = gate or DeterministicBypassGate()

    def authorize(
        self,
        asir: ASIR,
        *,
        current_state: dict[str, Any],
        idempotency_key: str,
        approval_token: str | None = None,
        ttl_seconds: int = 30,
        trace_id: str | None = None,
    ) -> AuthorizationResult:
        now = self.clock.now()
        resolved_trace = trace_id or f"trace:{asir.context.session_id}:{uuid.uuid4().hex[:10]}"
        policy = self.policies.current()

        self.ledger.append(
            trace_id=resolved_trace,
            node_type="ASIR",
            payload={
                "asir_hash": asir.hash,
                "agent_id": asir.agent_id,
                "principal": asir.principal.sub,
                "delegation": list(asir.delegation),
                "action": asir.action,
                "resource": asir.resource,
                "purpose": asir.purpose,
            },
            now=now,
        )

        if not asir.principal.sub or not asir.principal.iss:
            return self._decision(
                resolved_trace,
                asir,
                policy.version,
                Decision.DENY,
                "IDENTITY_MISSING",
                "Signed upstream identity is required",
            )
        if asir.agent_id not in asir.principal.act:
            return self._decision(
                resolved_trace,
                asir,
                policy.version,
                Decision.DENY,
                "ACTOR_BINDING_MISSING",
                "Principal act claim does not name the executing agent",
            )

        gate_outcome = self.gate.evaluate(asir)
        self.ledger.append(
            trace_id=resolved_trace,
            node_type="GATE_DECISION",
            payload={
                "decision": gate_outcome.decision.value,
                "reason": gate_outcome.reason,
                "statistical_guarantee": False,
            },
            now=now,
        )

        evaluation = self.verifier.evaluate(asir, policy)
        if not evaluation.allowed:
            return self._decision(
                resolved_trace,
                asir,
                policy.version,
                Decision.DENY,
                evaluation.reason_code,
                evaluation.explanation,
            )

        if evaluation.requires_approval:
            if approval_token is None:
                return self._decision(
                    resolved_trace,
                    asir,
                    policy.version,
                    Decision.REQUIRE_APPROVAL,
                    "APPROVAL_REQUIRED",
                    "The deterministic policy requires a signed human approval",
                )
            try:
                approval_claims = self.approvals.verify(approval_token, asir, now=now)
                self.ledger.append(
                    trace_id=resolved_trace,
                    node_type="HUMAN_APPROVAL",
                    payload={
                        "asir_hash": asir.hash,
                        "approver": approval_claims["approver"],
                        "approval_nonce": approval_claims["nonce"],
                    },
                    now=now,
                )
            except InvalidApproval as exc:
                return self._decision(
                    resolved_trace,
                    asir,
                    policy.version,
                    Decision.REQUIRE_APPROVAL,
                    exc.code,
                    str(exc),
                )

        reservation_id: str | None = None
        residual: dict[str, int] = {}
        if evaluation.budget is not None:
            assert evaluation.amount is not None
            assert evaluation.resource_key is not None
            try:
                reservation = self.budgets.reserve(
                    resource_key=evaluation.resource_key,
                    policy_version=policy.version,
                    limit=evaluation.budget.limit,
                    amount=evaluation.amount,
                    window_seconds=evaluation.budget.window_seconds,
                    now=now,
                    idempotency_key=idempotency_key,
                    agent_id=asir.agent_id,
                )
            except BudgetDenied as exc:
                return self._decision(
                    resolved_trace,
                    asir,
                    policy.version,
                    Decision.DENY,
                    exc.code,
                    str(exc),
                )
            reservation_id = reservation.reservation_id
            residual[evaluation.resource_key] = reservation.residual
            self.ledger.append(
                trace_id=resolved_trace,
                node_type="PREPARE",
                payload={
                    "reservation_id": reservation.reservation_id,
                    "resource_key": evaluation.resource_key,
                    "amount": evaluation.amount,
                    "residual": reservation.residual,
                },
                now=now,
            )

        token, claims = self.codec.issue(
            reservation_id=reservation_id,
            chain_index=0,
            parent_cap=None,
            asir_hash=asir.hash,
            state_hash=digest(current_state, prefix="state:sha256:"),
            residual=residual,
            policy_version=policy.version,
            policy_digest=policy.digest,
            now=now,
            ttl_seconds=ttl_seconds,
        )
        self.ledger.append(
            trace_id=resolved_trace,
            node_type="CAPABILITY",
            payload={
                "cap_id": claims.cap_id,
                "asir_hash": claims.asir_hash,
                "policy_version": claims.policy_version,
                "policy_digest": claims.policy_digest,
                "expires_at": claims.expires_at,
                "residual": residual,
            },
            now=now,
        )
        return self._decision(
            resolved_trace,
            asir,
            policy.version,
            Decision.ALLOW,
            "CAPABILITY_ISSUED",
            "Policy passed and a consumable capability was issued",
            capability=token,
            cap_id=claims.cap_id,
            residual=residual,
        )

    def compensate(self, reservation_id: str, *, trace_id: str, reason: str) -> bool:
        now = self.clock.now()
        released = self.budgets.compensate(reservation_id)
        self.ledger.append(
            trace_id=trace_id,
            node_type="COMPENSATION",
            payload={
                "reservation_id": reservation_id,
                "released": released,
                "reason": reason,
            },
            now=now,
        )
        return released

    def _decision(
        self,
        trace_id: str,
        asir: ASIR,
        policy_version: str,
        decision: Decision,
        reason_code: str,
        explanation: str,
        *,
        capability: str | None = None,
        cap_id: str | None = None,
        residual: dict[str, int] | None = None,
    ) -> AuthorizationResult:
        now = self.clock.now()
        audit = {
            "decision": decision.value,
            "reason_code": reason_code,
            "identity": asir.principal.sub,
            "delegation": list(asir.delegation),
            "action": asir.action,
            "policy_version": policy_version,
            "asir_hash": asir.hash,
        }
        self.ledger.append(
            trace_id=trace_id,
            node_type="VERIFIER_DECISION",
            payload=audit,
            now=now,
        )
        self.telemetry.record("verifier.decision", {"trace_id": trace_id, **audit})
        return AuthorizationResult(
            decision=decision,
            reason_code=reason_code,
            explanation=explanation,
            trace_id=trace_id,
            capability=capability,
            cap_id=cap_id,
            residual=residual or {},
        )
