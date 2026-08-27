"""Prepare and verify orchestration for trajectory-aware authorization."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from veritas.approval import ApprovalService
from veritas.canonical import digest
from veritas.crypto import CapabilityCodec
from veritas.enforcement import EnforcementMode
from veritas.errors import BudgetDenied, InvalidApproval, StoreUnavailable
from veritas.gate import DeterministicBypassGate
from veritas.identity import IdentityVerifier, TrustedInputIdentityVerifier
from veritas.lifecycle import ExecutionPhase
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
        identity: IdentityVerifier | None = None,
        enforcement_mode: EnforcementMode = EnforcementMode.ENFORCE,
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
        self.identity = identity or TrustedInputIdentityVerifier()
        self.enforcement_mode = enforcement_mode

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
        try:
            return self._authorize(
                asir,
                current_state=current_state,
                idempotency_key=idempotency_key,
                approval_token=approval_token,
                ttl_seconds=ttl_seconds,
                resolved_trace=resolved_trace,
                now=now,
            )
        except StoreUnavailable as exc:
            return AuthorizationResult(
                decision=Decision.DENY,
                reason_code=exc.code,
                explanation=str(exc),
                trace_id=resolved_trace,
                enforcement_mode=self.enforcement_mode.value,
                hypothetical_decision=Decision.DENY.value,
                lifecycle=ExecutionPhase.FAILED.value,
            )

    def _authorize(
        self,
        asir: ASIR,
        *,
        current_state: dict[str, Any],
        idempotency_key: str,
        approval_token: str | None,
        ttl_seconds: int,
        resolved_trace: str,
        now: datetime,
    ) -> AuthorizationResult:
        policy = self.policies.current()

        self.ledger.append(
            trace_id=resolved_trace,
            node_type="ASIR",
            payload={
                "asir_hash": asir.hash,
                "asir": asir.model_dump(mode="json"),
                "agent_id": asir.agent_id,
                "principal": asir.principal.sub,
                "delegation": list(asir.delegation),
                "action": asir.action,
                "resource": asir.resource,
                "purpose": asir.purpose,
                "lifecycle": ExecutionPhase.REQUESTED.value,
            },
            now=now,
        )

        identity = self.identity.verify(asir)
        if not identity.allowed:
            return self._decision(
                resolved_trace,
                asir,
                policy.version,
                Decision.DENY,
                identity.reason_code,
                identity.explanation,
                lifecycle=ExecutionPhase.DENIED,
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
            return self._finish_non_allow(
                resolved_trace,
                asir,
                policy,
                Decision.DENY,
                evaluation.reason_code,
                evaluation.explanation,
                current_state=current_state,
                ttl_seconds=ttl_seconds,
                now=now,
            )

        if evaluation.requires_approval:
            if approval_token is None:
                return self._finish_non_allow(
                    resolved_trace,
                    asir,
                    policy,
                    Decision.REQUIRE_APPROVAL,
                    "APPROVAL_REQUIRED",
                    "The deterministic policy requires a signed human approval",
                    current_state=current_state,
                    ttl_seconds=ttl_seconds,
                    now=now,
                )
            try:
                approval_claims = self.approvals.verify(approval_token, asir, now=now)
                if str(approval_claims["approver"]) == asir.principal.sub:
                    return self._finish_non_allow(
                        resolved_trace,
                        asir,
                        policy,
                        Decision.REQUIRE_APPROVAL,
                        "SEPARATION_OF_DUTIES",
                        "The initiator cannot approve their own request",
                        current_state=current_state,
                        ttl_seconds=ttl_seconds,
                        now=now,
                    )
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
                return self._finish_non_allow(
                    resolved_trace,
                    asir,
                    policy,
                    Decision.REQUIRE_APPROVAL,
                    exc.code,
                    str(exc),
                    current_state=current_state,
                    ttl_seconds=ttl_seconds,
                    now=now,
                )

        reservation_id: str | None = None
        residual: dict[str, int] = {}
        skip_reservation = self.enforcement_mode in {EnforcementMode.SHADOW, EnforcementMode.AUDIT}
        if evaluation.budget is not None and not skip_reservation:
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
                return self._finish_non_allow(
                    resolved_trace,
                    asir,
                    policy,
                    Decision.DENY,
                    exc.code,
                    str(exc),
                    current_state=current_state,
                    ttl_seconds=ttl_seconds,
                    now=now,
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

        if self.enforcement_mode is EnforcementMode.AUDIT:
            return self._decision(
                resolved_trace,
                asir,
                policy.version,
                Decision.ALLOW,
                "AUDIT_RECORDED",
                "Audit mode recorded a hypothetical allow and issued no capability",
                lifecycle=ExecutionPhase.VERIFIED,
                hypothetical_decision=Decision.ALLOW.value,
            )

        try:
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
        except (RuntimeError, OSError) as exc:
            if reservation_id is not None:
                self.budgets.compensate(reservation_id)
            return self._decision(
                resolved_trace,
                asir,
                policy.version,
                Decision.DENY,
                "KEY_PROVIDER_UNAVAILABLE",
                str(exc),
                lifecycle=ExecutionPhase.FAILED,
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
            lifecycle=ExecutionPhase.AUTHORIZED,
            hypothetical_decision=Decision.ALLOW.value,
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
                "lifecycle": ExecutionPhase.COMPENSATED.value,
            },
            now=now,
        )
        return released

    def _finish_non_allow(
        self,
        trace_id: str,
        asir: ASIR,
        policy: Any,
        decision: Decision,
        reason_code: str,
        explanation: str,
        *,
        current_state: dict[str, Any],
        ttl_seconds: int,
        now: datetime,
    ) -> AuthorizationResult:
        if self.enforcement_mode is EnforcementMode.SHADOW:
            try:
                token, claims = self.codec.issue(
                    reservation_id=None,
                    chain_index=0,
                    parent_cap=None,
                    asir_hash=asir.hash,
                    state_hash=digest(current_state, prefix="state:sha256:"),
                    residual={},
                    policy_version=policy.version,
                    policy_digest=policy.digest,
                    now=now,
                    ttl_seconds=ttl_seconds,
                )
            except (RuntimeError, OSError) as exc:
                return self._decision(
                    trace_id,
                    asir,
                    policy.version,
                    Decision.DENY,
                    "KEY_PROVIDER_UNAVAILABLE",
                    str(exc),
                    lifecycle=ExecutionPhase.FAILED,
                    hypothetical_decision=decision.value,
                )
            return self._decision(
                trace_id,
                asir,
                policy.version,
                Decision.ALLOW,
                "SHADOW_PASSTHROUGH",
                "Shadow mode recorded a hypothetical block and did not enforce it",
                capability=token,
                cap_id=claims.cap_id,
                lifecycle=ExecutionPhase.AUTHORIZED,
                hypothetical_decision=decision.value,
            )
        return self._decision(
            trace_id,
            asir,
            policy.version,
            decision,
            reason_code,
            explanation,
            lifecycle=ExecutionPhase.DENIED
            if decision is Decision.DENY
            else ExecutionPhase.REQUESTED,
            hypothetical_decision=decision.value,
        )

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
        lifecycle: ExecutionPhase | None = None,
        hypothetical_decision: str | None = None,
    ) -> AuthorizationResult:
        if self.enforcement_mode is EnforcementMode.AUDIT:
            capability = None
            cap_id = None
        now = self.clock.now()
        audit = {
            "decision": decision.value,
            "reason_code": reason_code,
            "identity": asir.principal.sub,
            "delegation": list(asir.delegation),
            "action": asir.action,
            "policy_version": policy_version,
            "asir_hash": asir.hash,
            "enforcement_mode": self.enforcement_mode.value,
            "hypothetical_decision": hypothetical_decision or decision.value,
            "lifecycle": None if lifecycle is None else lifecycle.value,
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
            enforcement_mode=self.enforcement_mode.value,
            hypothetical_decision=hypothetical_decision or decision.value,
            lifecycle=None if lifecycle is None else lifecycle.value,
        )
