"""Cooperative tool boundary that verifies and consumes capabilities."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from veritas.canonical import digest
from veritas.crypto import CapabilityCodec
from veritas.errors import (
    ExpiredCapability,
    InvalidCapability,
    ReplayDetected,
    ReservationError,
    StaleCapability,
    StateMismatch,
)
from veritas.lifecycle import ExecutionPhase
from veritas.models import ASIR, BoundaryResult
from veritas.policy import InMemoryPolicyStore, classification_labels
from veritas.ports import (
    BudgetStore,
    Clock,
    LedgerStore,
    NonceStore,
    SessionStateStore,
    Telemetry,
)
from veritas.reconcile import OutcomeUnknown

Tool = Callable[[ASIR], Any]


class ToolBoundary:
    def __init__(
        self,
        *,
        codec: CapabilityCodec,
        policies: InMemoryPolicyStore,
        budgets: BudgetStore,
        ledger: LedgerStore,
        nonces: NonceStore,
        sessions: SessionStateStore,
        clock: Clock,
        telemetry: Telemetry,
        max_clock_skew_seconds: int = 2,
    ) -> None:
        self.codec = codec
        self.policies = policies
        self.budgets = budgets
        self.ledger = ledger
        self.nonces = nonces
        self.sessions = sessions
        self.clock = clock
        self.telemetry = telemetry
        self.max_clock_skew = timedelta(seconds=max_clock_skew_seconds)

    def execute(
        self,
        capability: str,
        *,
        asir: ASIR,
        current_state: dict[str, Any],
        tool: Tool,
        trace_id: str,
    ) -> BoundaryResult:
        now = self.clock.now()
        try:
            claims = self.codec.decode_and_verify(capability)
            policy = self.policies.current()
            if claims.issuer_kid != self.codec.kid:
                raise InvalidCapability("unknown issuer key id")
            if claims.policy_version != policy.version or claims.policy_digest != policy.digest:
                raise StaleCapability("capability was issued under a non-current policy")
            if claims.certificate.proof_digest != policy.digest:
                raise InvalidCapability("certificate does not contain the current policy proof")
            if now - self.max_clock_skew > claims.expires_at:
                raise ExpiredCapability("capability expired outside the permitted clock skew")
            if claims.issued_at - now > self.max_clock_skew:
                raise ExpiredCapability("issuer clock is beyond the permitted skew")
            if claims.asir_hash != asir.hash:
                raise InvalidCapability("capability is bound to a different ASIR")
            expected_state = digest(current_state, prefix="state:sha256:")
            if claims.state_hash != expected_state:
                raise StateMismatch("current tool state differs from the verified preconditions")
            if not self.nonces.consume(claims.nonce, claims.cap_id, now):
                raise ReplayDetected("capability nonce has already been consumed")
        except InvalidCapability as exc:
            self._record_boundary_decision(trace_id, "DENY", exc.code, str(exc))
            raise

        self.ledger.append(
            trace_id=trace_id,
            node_type="TOOL_INPUT",
            payload={
                "cap_id": claims.cap_id,
                "asir_hash": asir.hash,
                "action": asir.action,
                "lifecycle": ExecutionPhase.EXECUTING.value,
            },
            now=now,
        )
        try:
            output = tool(asir)
        except TimeoutError as exc:
            self.ledger.append(
                trace_id=trace_id,
                node_type="TOOL_OUTPUT",
                payload={
                    "cap_id": claims.cap_id,
                    "status": "UNKNOWN",
                    "error_type": "TimeoutError",
                    "lifecycle": ExecutionPhase.UNKNOWN.value,
                },
                now=self.clock.now(),
            )
            self.telemetry.record(
                "boundary.unknown",
                {"trace_id": trace_id, "cap_id": claims.cap_id, "reason_code": "EXECUTION_UNKNOWN"},
            )
            raise OutcomeUnknown(
                "tool timed out after the capability was consumed; outcome is unknown",
                reservation_id=claims.reservation_id,
                cap_id=claims.cap_id,
                trace_id=trace_id,
            ) from exc
        except Exception as exc:
            self.ledger.append(
                trace_id=trace_id,
                node_type="TOOL_OUTPUT",
                payload={
                    "cap_id": claims.cap_id,
                    "status": "ERROR",
                    "error_type": type(exc).__name__,
                },
                now=self.clock.now(),
            )
            self.telemetry.record(
                "boundary.tool_error", {"trace_id": trace_id, "cap_id": claims.cap_id}
            )
            raise

        if claims.reservation_id is not None:
            try:
                self.budgets.commit(claims.reservation_id)
            except ReservationError as exc:
                self.ledger.append(
                    trace_id=trace_id,
                    node_type="COMMIT_FAILED",
                    payload={
                        "cap_id": claims.cap_id,
                        "reservation_id": claims.reservation_id,
                        "reason_code": exc.code,
                    },
                    now=self.clock.now(),
                )
                self._record_boundary_decision(trace_id, "DENY", exc.code, str(exc))
                raise
        self.sessions.record_action(asir.context.session_id, asir.action, self.clock.now())
        self.sessions.record_labels(
            asir.context.session_id, classification_labels(asir), self.clock.now()
        )
        output_hash = digest(output, prefix="output:sha256:")
        self.ledger.append(
            trace_id=trace_id,
            node_type="TOOL_OUTPUT",
            payload={"cap_id": claims.cap_id, "status": "OK", "output_hash": output_hash},
            now=self.clock.now(),
        )
        self.ledger.append(
            trace_id=trace_id,
            node_type="COMMIT_ACK",
            payload={
                "cap_id": claims.cap_id,
                "reservation_id": claims.reservation_id,
                "idempotent": True,
            },
            now=self.clock.now(),
        )
        self._record_boundary_decision(trace_id, "ALLOW", "COMMITTED", "Tool execution committed")
        return BoundaryResult(cap_id=claims.cap_id, trace_id=trace_id, tool_output=output)

    def _record_boundary_decision(
        self, trace_id: str, decision: str, reason_code: str, explanation: str
    ) -> None:
        payload = {
            "decision": decision,
            "reason_code": reason_code,
            "explanation": explanation,
        }
        self.ledger.append(
            trace_id=trace_id,
            node_type="BOUNDARY_DECISION",
            payload=payload,
            now=self.clock.now(),
        )
        self.telemetry.record("boundary.decision", {"trace_id": trace_id, **payload})
