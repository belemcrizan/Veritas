from __future__ import annotations

import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from veritas.adapters.postgres import postgres_available
from veritas.bench_cycle2 import run_cycle2_attacks
from veritas.cli import EXIT_OK, main
from veritas.lifecycle import ExecutionPhase, InvalidLifecycleTransition, transition
from veritas.observability import redact
from veritas.research import PACKAGED_VERSION, RESEARCH_CYCLE, status_report
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import DEFAULT_TIME, account_state, payment_asir
from veritas.science import AutonomyCost, FeasibleDenial
from veritas.traces import ActionTrace, asir_from_trace, replay_traces
from veritas.workloads import run_email_workload, run_sql_workload

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ResearchStatusTests(unittest.TestCase):
    def test_packaged_version_matches_pyproject(self) -> None:
        text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{PACKAGED_VERSION}"', text)
        report = status_report()
        self.assertEqual(report["cycle"], RESEARCH_CYCLE)
        self.assertEqual(report["cycle_declaration"], "PARTIAL")

    def test_cli_status_and_version(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            self.assertEqual(main(["status"]), EXIT_OK)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["cycle"], "2")
        with patch("sys.stdout", new=StringIO()) as stdout:
            self.assertEqual(main(["version"]), EXIT_OK)
        self.assertIn("cycle 2", stdout.getvalue())


class Cycle2AttackTests(unittest.TestCase):
    def test_cycle2_families_pass(self) -> None:
        report = run_cycle2_attacks()
        self.assertEqual(report["families_passed"], report["families_total"])
        self.assertGreaterEqual(report["families_total"], 10)

    def test_requested_to_committed_is_illegal(self) -> None:
        with self.assertRaises(InvalidLifecycleTransition):
            transition(ExecutionPhase.REQUESTED, ExecutionPhase.COMMITTED)


class WorkloadAndScienceTests(unittest.TestCase):
    def test_sql_exfil_is_denied(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-sql-") as directory:
            result = run_sql_workload(Path(directory))
        self.assertTrue(result["property_held"])

    def test_email_exfil_is_denied(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-mail-") as directory:
            result = run_email_workload(Path(directory))
        self.assertTrue(result["property_held"])

    def test_fdr_and_autonomy_cost_are_defined(self) -> None:
        self.assertEqual(FeasibleDenial(1, 4).fdr, 0.25)
        self.assertEqual(AutonomyCost(1, 1, 10).ac, 0.2)

    def test_trace_replay_does_not_call_newly_denied_an_attack(self) -> None:
        trace = ActionTrace(
            trace_id="t",
            session_id="s",
            principal="user:alice",
            agent="finance-agent-01",
            action="payment.transfer",
            resource="account-123",
            parameters={"amount": 900, "currency": "BRL", "destination": "x"},
            timestamp="2026-08-26T00:00:00+00:00",
            policy_version="v1",
            decision="ALLOW",
            ground_truth="legitimate",
        )
        asir = asir_from_trace(trace)
        self.assertEqual(asir.action, "payment.transfer")
        metrics = replay_traces([trace], [{"allowed": False}])
        self.assertEqual(metrics["newly_denied"], 1)
        self.assertIn("not 'attacks prevented'", metrics["interpretation"])


class TelemetryRedactionTests(unittest.TestCase):
    def test_secrets_are_redacted(self) -> None:
        cleaned = redact({"password": "hunter2", "private_key": "pk", "amount": 1})
        self.assertEqual(cleaned["password"], "[redacted]")
        self.assertEqual(cleaned["private_key"], "[redacted]")
        self.assertEqual(cleaned["amount"], 1)


class OptionalPostgresTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("VERITAS_POSTGRES_DSN") and postgres_available(), "no postgres")
    def test_postgres_contract_overspend(self) -> None:
        from veritas.adapters.postgres import PostgresAdapter
        from veritas.errors import BudgetDenied

        store = PostgresAdapter(os.environ["VERITAS_POSTGRES_DSN"])
        store.reserve(
            resource_key="money:pg:86400s",
            policy_version="v1",
            limit=1000,
            amount=900,
            window_seconds=86400,
            now=DEFAULT_TIME,
            idempotency_key="pg-a",
            agent_id="agent",
        )
        with self.assertRaises(BudgetDenied):
            store.reserve(
                resource_key="money:pg:86400s",
                policy_version="v1",
                limit=1000,
                amount=900,
                window_seconds=86400,
                now=DEFAULT_TIME,
                idempotency_key="pg-b",
                agent_id="agent",
            )


class ShadowDoesNotReserveTests(unittest.TestCase):
    def test_status_is_partial(self) -> None:
        self.assertEqual(status_report()["cycle_declaration"], "PARTIAL")


class IdempotencyAfterAuthorize(unittest.TestCase):
    def test_same_idempotency_key_replays_reservation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-idem-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "i.db", policy_path=bundled_policy_path()
            )
            asir = payment_asir(amount=100, destination="idem", session_id="idem")
            first = runtime.engine.authorize(
                asir, current_state=account_state(), idempotency_key="same"
            )
            second = runtime.engine.authorize(
                asir, current_state=account_state(), idempotency_key="same"
            )
            self.assertEqual(first.decision.value, "ALLOW")
            self.assertEqual(second.decision.value, "ALLOW")
