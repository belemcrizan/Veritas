from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import veritas
from veritas import (
    Decision,
    LangGraphToolCallAdapter,
    Principal,
    bundled_policy_path,
    create_local_runtime,
)


class PublicApiTests(unittest.TestCase):
    def test_documented_symbols_are_exported(self) -> None:
        expected = {
            "ASIR",
            "AuthorizationResult",
            "BoundaryResult",
            "Decision",
            "LangGraphToolCallAdapter",
            "LocalRuntime",
            "MCPToolCallAdapter",
            "Principal",
            "RequestContext",
            "VeritasEngine",
            "bundled_policy_path",
            "create_local_runtime",
        }
        self.assertTrue(expected.issubset(set(veritas.__all__)))
        self.assertTrue(veritas.__version__)

    def test_public_api_authorizes_and_executes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-public-api-test-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "veritas.db",
                policy_path=bundled_policy_path(),
            )
            agent_id = "finance-agent-01"
            principal = Principal(
                sub="user:alice",
                iss="https://idp.example",
                act=(agent_id,),
            )
            asir = LangGraphToolCallAdapter().adapt(
                {
                    "name": "payment.transfer",
                    "args": {
                        "amount": 900,
                        "currency": "BRL",
                        "destination": "public-api-test",
                    },
                    "id": "call-public-api-test",
                },
                agent_id=agent_id,
                principal=principal,
                delegation=("user:alice", agent_id),
                resource="account-123",
                purpose="invoice-payment",
                session_id="public-api-test",
                request_ts=datetime.now(UTC),
            )
            state = {"account-123.balance": 50000, "currency": "BRL"}
            result = runtime.engine.authorize(
                asir,
                current_state=state,
                idempotency_key="public-api-test",
            )

            self.assertEqual(result.decision, Decision.ALLOW)
            self.assertIsNotNone(result.capability)
            assert result.capability is not None

            committed = runtime.boundary.execute(
                result.capability,
                asir=asir,
                current_state=state,
                tool=lambda request: {"action": request.action, "status": "accepted"},
                trace_id=result.trace_id,
            )

            self.assertEqual(committed.commit_status, "COMMITTED")
            self.assertTrue(runtime.store.verify_integrity())


if __name__ == "__main__":
    unittest.main()
