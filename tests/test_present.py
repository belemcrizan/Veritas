from __future__ import annotations

import unittest

from veritas.comparison import run_comparison
from veritas.demo import format_demo, run_demo
from veritas.errors import MissingCapability
from veritas.guarded import GuardedTool
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import account_state, deterministic_tool, payment_asir


class PresentFreezeTests(unittest.TestCase):
    def test_hero_is_a_differential_experiment(self) -> None:
        report = run_demo()
        b1 = report["B1"]
        veritas = report["VERITAS"]
        self.assertEqual(b1["allowed"], 12)
        self.assertEqual(b1["spent"], 10800)
        self.assertEqual(b1["cumulative_budget"], "FAIL")
        self.assertEqual(veritas["allowed"], 11)
        self.assertEqual(veritas["twelfth_decision"], "DENY")
        self.assertLessEqual(veritas["spent"], 10000)
        self.assertEqual(veritas["cumulative_budget"], "PASS")
        self.assertTrue(veritas["direct_tool_call_without_capability"]["rejected"])
        text = format_demo(report)
        self.assertIn("We are not trying to make the agent trustworthy", text)
        self.assertLess(len(text), 2500)

    def test_tool_rejects_direct_call_without_capability(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="veritas-guard-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "guard.db",
                policy_path=bundled_policy_path(),
            )
            tool = GuardedTool(runtime.boundary, deterministic_tool)
            with self.assertRaises(MissingCapability) as ctx:
                tool.invoke(
                    payment_asir(amount=900, session_id="bypass"),
                    capability=None,
                    current_state=account_state(),
                    trace_id="trace:bypass",
                )
            self.assertEqual(ctx.exception.code, "VALID_CAPABILITY_REQUIRED")

    def test_comparison_does_not_force_b1_to_lose(self) -> None:
        report = run_comparison()
        by_family = {row["family"]: row for row in report["rows"]}
        self.assertEqual(by_family["atomic"]["B1"], "PASS")
        self.assertEqual(by_family["delegation_laundering"]["B1"], "PASS")
        self.assertEqual(by_family["fractionation"]["B1"], "FAIL")
        self.assertEqual(by_family["fractionation"]["VERITAS"], "PASS")
        self.assertEqual(by_family["policy_race"]["B1"], "NA")
        self.assertEqual(by_family["clock_skew"]["B1"], "NA")
        self.assertEqual(by_family["compensation_abuse"]["B1"], "NA")
        for row in report["rows"]:
            self.assertEqual(row["VERITAS"], "PASS", msg=row)


if __name__ == "__main__":
    unittest.main()
