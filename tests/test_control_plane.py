from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from veritas.cli import EXIT_OK, main
from veritas.graph import graph_from_trace
from veritas.policy import PolicyCompiler
from veritas.policy_ops import diff_policies, lint_policy
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import account_state, payment_asir
from veritas.showcase import run_showcase

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ShowcaseAndPolicyTests(unittest.TestCase):
    def test_showcase_all_pass(self) -> None:
        report = run_showcase()
        self.assertEqual(report["passed"], report["total"])
        self.assertEqual(report["total"], 6)

    def test_policy_lint_emits_temporal_counterexample(self) -> None:
        policy = PolicyCompiler().compile_file(PROJECT_ROOT / "policies" / "payment_policy.json")
        issues = lint_policy(policy)
        self.assertTrue(any(item.code == "COUNTEREXAMPLE" for item in issues))

    def test_policy_diff_detects_budget_decrease(self) -> None:
        compiler = PolicyCompiler()
        old = compiler.compile_file(PROJECT_ROOT / "policies" / "payment_policy.json")
        new = compiler.compile_file(PROJECT_ROOT / "policies" / "payment_policy_v2.json")
        kinds = {item["kind"] for item in diff_policies(old, new)}
        self.assertIn("budget_decreased", kinds)
        self.assertIn("approval_threshold_changed", kinds)

    def test_cli_policy_lint(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main(["policy", "lint", str(PROJECT_ROOT / "policies" / "payment_policy.json")])
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["version"], "v1")

    def test_cli_explain(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main(["demo", "--explain"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("DENY", stdout.getvalue())
        self.assertIn("No money was transferred", stdout.getvalue())

    def test_execution_graph_has_action_nodes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-graph-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "g.db",
                policy_path=bundled_policy_path(),
            )
            asir = payment_asir(amount=100, destination="graph", session_id="graph")
            result = runtime.engine.authorize(
                asir, current_state=account_state(), idempotency_key="graph"
            )
            graph = graph_from_trace(runtime.store, result.trace_id)
            kinds = {node["kind"] for node in graph["nodes"]}
            self.assertIn("action", kinds)
            self.assertTrue(graph["edges"])
