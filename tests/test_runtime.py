from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from veritas.adapters.frameworks import LangGraphToolCallAdapter
from veritas.adapters.local import MutableClock
from veritas.errors import ReplayDetected, StateMismatch
from veritas.models import Decision, Principal
from veritas.runtime import create_local_runtime
from veritas.scenarios import DEFAULT_TIME, account_state, deterministic_tool, payment_asir

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="veritas-test-")
        self.clock = MutableClock(DEFAULT_TIME)
        self.runtime = create_local_runtime(
            database_path=Path(self.temp.name) / "test.db",
            policy_path=PROJECT_ROOT / "policies" / "payment_policy.json",
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_twelfth_fraction_is_denied(self) -> None:
        decisions = []
        for index in range(12):
            asir = payment_asir(amount=900, destination="test-fraction", session_id=str(index))
            result = self.runtime.engine.authorize(
                asir,
                current_state=account_state(),
                idempotency_key=f"fraction-{index}",
            )
            decisions.append(result.decision)
        self.assertEqual(decisions.count(Decision.ALLOW), 11)
        self.assertEqual(decisions[-1], Decision.DENY)

    def test_concurrent_reservations_do_not_overspend(self) -> None:
        def reserve(index: int) -> Decision:
            asir = payment_asir(amount=300, destination="test-parallel", session_id=str(index))
            return self.runtime.engine.authorize(
                asir,
                current_state=account_state(),
                idempotency_key=f"parallel-{index}",
            ).decision

        with ThreadPoolExecutor(max_workers=20) as pool:
            decisions = list(pool.map(reserve, range(40)))
        self.assertEqual(decisions.count(Decision.ALLOW), 33)
        self.assertEqual(
            self.runtime.store.used("money:test-parallel:86400s", 86400, self.clock.now()),
            9900,
        )

    def test_state_mutation_makes_capability_stale(self) -> None:
        asir = payment_asir(amount=100, destination="state")
        result = self.runtime.engine.authorize(
            asir, current_state=account_state(50000), idempotency_key="state"
        )
        assert result.capability is not None
        with self.assertRaises(StateMismatch):
            self.runtime.boundary.execute(
                result.capability,
                asir=asir,
                current_state=account_state(49999),
                tool=deterministic_tool,
                trace_id=result.trace_id,
            )

    def test_capability_is_consumed_once(self) -> None:
        asir = payment_asir(amount=100, destination="nonce")
        result = self.runtime.engine.authorize(
            asir, current_state=account_state(), idempotency_key="nonce"
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

    def test_intervention_replay_propagates_hash_change(self) -> None:
        asir = payment_asir(amount=100, destination="ledger")
        result = self.runtime.engine.authorize(
            asir, current_state=account_state(), idempotency_key="ledger"
        )
        nodes = self.runtime.store.trace(result.trace_id)
        first = nodes[0]
        replay = self.runtime.store.replay(
            result.trace_id,
            interventions={first["node_id"]: {"asir_hash": "injected"}},
        )
        self.assertTrue(all(item["changed"] for item in replay))
        self.assertTrue(self.runtime.store.verify_integrity())

    def test_hybrid_mode_preserves_global_limit(self) -> None:
        hybrid = create_local_runtime(
            database_path=Path(self.temp.name) / "hybrid.db",
            policy_path=PROJECT_ROOT / "policies" / "payment_policy.json",
            clock=self.clock,
            budget_mode="hybrid",
        )
        decisions = []
        for index in range(12):
            asir = payment_asir(amount=900, destination="hybrid", session_id=f"h-{index}")
            decisions.append(
                hybrid.engine.authorize(
                    asir,
                    current_state=account_state(),
                    idempotency_key=f"hybrid-{index}",
                ).decision
            )
        self.assertEqual(decisions.count(Decision.ALLOW), 11)
        self.assertEqual(decisions[-1], Decision.DENY)

    def test_langgraph_adapter_produces_asir(self) -> None:
        asir = LangGraphToolCallAdapter().adapt(
            {"name": "payment.transfer", "args": {"amount": 900, "destination": "a"}, "id": "1"},
            agent_id="finance-agent-01",
            principal=Principal(
                sub="user:alice", iss="https://idp.example", act=("finance-agent-01",)
            ),
            delegation=("user:alice", "finance-agent-01"),
            resource="account-123",
            purpose="benchmark",
            session_id="adapter",
            request_ts=self.clock.now(),
        )
        self.assertEqual(asir.action, "payment.transfer")
        self.assertEqual(asir.hash, asir.hash)


if __name__ == "__main__":
    unittest.main()
