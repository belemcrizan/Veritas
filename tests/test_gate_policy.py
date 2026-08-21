from __future__ import annotations

import unittest

from veritas.gate import SplitConformalFieldGate
from veritas.models import GateDecision
from veritas.policy import bounded_fractionation_counterexample


class GateAndPolicyTests(unittest.TestCase):
    def test_gate_requires_calibration_mass(self) -> None:
        gate = SplitConformalFieldGate([0.1] * 9)
        outcome = gate.evaluate_scores({"a": 0.1}, alpha=0.1)
        self.assertEqual(outcome.decision, GateDecision.NO_GUARANTEE)

    def test_gate_emits_singleton(self) -> None:
        gate = SplitConformalFieldGate([0.1] * 100)
        outcome = gate.evaluate_scores({"safe": 0.05, "unsafe": 0.9}, alpha=0.1)
        self.assertEqual(outcome.decision, GateDecision.PROCEED)
        self.assertEqual(outcome.prediction_set, ("safe",))

    def test_unit_filter_fractionation_counterexample(self) -> None:
        counterexample = bounded_fractionation_counterexample(
            limit=10000, atomic_limit=10000, amount=900, depth=12
        )
        self.assertEqual(counterexample, [900] * 12)


if __name__ == "__main__":
    unittest.main()

