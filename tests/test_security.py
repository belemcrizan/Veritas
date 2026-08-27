from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from veritas.enforcement import EnforcementMode
from veritas.errors import InvalidCapability, ReplayDetected
from veritas.identity import TrustedInputIdentityVerifier
from veritas.lifecycle import ExecutionPhase, InvalidLifecycleTransition, transition
from veritas.models import Decision, Principal
from veritas.reconcile import OutcomeUnknown, ProbeResult
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import (
    DEFAULT_TIME,
    account_state,
    action_asir,
    deterministic_tool,
    payment_asir,
)


class SecurityRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="veritas-sec-")
        self.runtime = create_local_runtime(
            database_path=Path(self.temp.name) / "sec.db",
            policy_path=bundled_policy_path(),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_delegation_cycle_is_denied(self) -> None:
        asir = payment_asir(
            amount=100,
            destination="cycle",
            session_id="cycle",
            delegation=("user:alice", "finance-agent-01", "user:alice", "finance-agent-01"),
        )
        result = self.runtime.engine.authorize(
            asir, current_state=account_state(), idempotency_key="cycle"
        )
        self.assertEqual(result.decision, Decision.DENY)
        self.assertEqual(result.reason_code, "DELEGATION_CYCLE")

    def test_forged_issuer_is_denied(self) -> None:
        verifier = TrustedInputIdentityVerifier(allowed_issuers=frozenset({"https://idp.example"}))
        asir = payment_asir(amount=100, destination="iss", session_id="iss")
        evil = asir.model_copy(
            update={
                "principal": Principal(
                    sub="user:alice", iss="https://evil.example", act=asir.principal.act
                )
            }
        )
        decision = verifier.verify(evil)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "IDENTITY_ISSUER_REJECTED")

    def test_approver_cannot_be_initiator(self) -> None:
        asir = payment_asir(amount=9000, destination="sod", session_id="sod")
        token = self.runtime.approval_service.issue(
            asir, approver="user:alice", now=self.runtime.clock.now()
        )
        result = self.runtime.engine.authorize(
            asir,
            current_state=account_state(),
            idempotency_key="sod",
            approval_token=token,
        )
        self.assertEqual(result.decision, Decision.REQUIRE_APPROVAL)
        self.assertEqual(result.reason_code, "SEPARATION_OF_DUTIES")

    def test_information_flow_denies_external_after_pii(self) -> None:
        read = action_asir(
            "data.read_sensitive",
            session_id="flow",
            parameters={},
        )
        read = read.model_copy(update={"labels": {"classification": "PII"}})
        send = action_asir("message.send_external", session_id="flow")
        first = self.runtime.engine.authorize(read, current_state={}, idempotency_key="flow-read")
        self.assertEqual(first.decision, Decision.ALLOW)
        assert first.capability is not None
        self.runtime.boundary.execute(
            first.capability,
            asir=read,
            current_state={},
            tool=deterministic_tool,
            trace_id=first.trace_id,
        )
        second = self.runtime.engine.authorize(send, current_state={}, idempotency_key="flow-send")
        self.assertEqual(second.decision, Decision.DENY)
        self.assertIn(
            second.reason_code, {"TEMPORAL_INVARIANT_VIOLATION", "INFORMATION_FLOW_VIOLATION"}
        )

    def test_malformed_capability_does_not_allow(self) -> None:
        asir = payment_asir(amount=100, destination="fuzz", session_id="fuzz")
        with self.assertRaises(InvalidCapability):
            self.runtime.boundary.execute(
                "not-a-capability",
                asir=asir,
                current_state=account_state(),
                tool=deterministic_tool,
                trace_id="fuzz",
            )

    def test_shadow_mode_does_not_block_budget(self) -> None:
        shadow = create_local_runtime(
            database_path=Path(self.temp.name) / "shadow.db",
            policy_path=bundled_policy_path(),
            enforcement_mode=EnforcementMode.SHADOW,
        )
        asir = payment_asir(
            amount=11000, destination="shadow", session_id="shadow", purpose="not-allowed"
        )
        result = shadow.engine.authorize(
            asir, current_state=account_state(), idempotency_key="shadow"
        )
        self.assertEqual(result.decision, Decision.ALLOW)
        self.assertEqual(result.reason_code, "SHADOW_PASSTHROUGH")
        self.assertEqual(result.hypothetical_decision, Decision.DENY.value)
        self.assertEqual(shadow.store.used("money:shadow:86400s", 86400, DEFAULT_TIME), 0)

    def test_timeout_is_unknown_not_failure(self) -> None:
        asir = payment_asir(amount=100, destination="timeout", session_id="timeout")
        result = self.runtime.engine.authorize(
            asir, current_state=account_state(), idempotency_key="timeout"
        )
        assert result.capability is not None

        def boom(_asir: object) -> None:
            raise TimeoutError("network")

        with self.assertRaises(OutcomeUnknown) as ctx:
            self.runtime.boundary.execute(
                result.capability,
                asir=asir,
                current_state=account_state(),
                tool=boom,
                trace_id=result.trace_id,
            )
        self.assertEqual(ctx.exception.code, "EXECUTION_UNKNOWN")
        recon = self.runtime.reconciler.reconcile(
            reservation_id=ctx.exception.reservation_id,
            trace_id=result.trace_id,
            probe=lambda: ProbeResult.CONFIRMED_NOT_EXECUTED,
        )
        self.assertEqual(recon.status, ProbeResult.CONFIRMED_NOT_EXECUTED)
        self.assertTrue(recon.compensated)

    def test_replay_still_denied_after_success(self) -> None:
        asir = payment_asir(amount=100, destination="rp2", session_id="rp2")
        result = self.runtime.engine.authorize(
            asir, current_state=account_state(), idempotency_key="rp2"
        )
        assert result.capability is not None
        self.runtime.boundary.execute(
            result.capability,
            asir=asir,
            current_state=account_state(),
            tool=deterministic_tool,
            trace_id=result.trace_id,
        )
        with self.assertRaises(ReplayDetected):
            self.runtime.boundary.execute(
                result.capability,
                asir=asir,
                current_state=account_state(),
                tool=deterministic_tool,
                trace_id=result.trace_id,
            )


class LifecycleTests(unittest.TestCase):
    def test_invalid_terminal_jump_is_rejected(self) -> None:
        with self.assertRaises(InvalidLifecycleTransition):
            transition(ExecutionPhase.COMMITTED, ExecutionPhase.AUTHORIZED)

    def test_unknown_to_reconciling_is_allowed(self) -> None:
        self.assertEqual(
            transition(ExecutionPhase.UNKNOWN, ExecutionPhase.RECONCILING),
            ExecutionPhase.RECONCILING,
        )
