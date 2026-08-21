"""Cycle-1 deterministic gate and a small split-conformal field gate for Cycle 2."""

from __future__ import annotations

import math
from dataclasses import dataclass

from veritas.models import ASIR, GateDecision


@dataclass(frozen=True)
class GateOutcome:
    decision: GateDecision
    reason: str
    prediction_set: tuple[str, ...] = ()
    alpha: float | None = None
    calibration_size: int = 0


class DeterministicBypassGate:
    """Cycle-1 behavior: no statistical claim, and the bypass is auditable."""

    def evaluate(self, asir: ASIR) -> GateOutcome:
        del asir
        return GateOutcome(
            GateDecision.BYPASS_RECORDED,
            "Cycle 1: uncertainty gate bypassed; no statistical guarantee claimed",
        )


class SplitConformalFieldGate:
    """Categorical split conformal prediction with explicit calibration-mass checks."""

    def __init__(self, calibration_scores: list[float]) -> None:
        if any(score < 0 or score > 1 for score in calibration_scores):
            raise ValueError("nonconformity scores must be within [0, 1]")
        self._scores = sorted(calibration_scores)

    def evaluate_scores(
        self,
        candidate_scores: dict[str, float],
        *,
        alpha: float,
        high_risk: bool = False,
        shift_detected: bool = False,
    ) -> GateOutcome:
        if not 0 < alpha < 1:
            raise ValueError("alpha must be in (0, 1)")
        n = len(self._scores)
        if high_risk and alpha < 0.01:
            return GateOutcome(
                GateDecision.FIELD_REVIEW,
                "High-risk actions cannot rely on the statistical gate",
                alpha=alpha,
                calibration_size=n,
            )
        if shift_detected:
            return GateOutcome(
                GateDecision.NO_GUARANTEE,
                "Distribution shift detected; coverage guarantee suspended",
                alpha=alpha,
                calibration_size=n,
            )
        if n < math.ceil(1 / alpha):
            return GateOutcome(
                GateDecision.NO_GUARANTEE,
                "Insufficient calibration mass for the requested alpha",
                alpha=alpha,
                calibration_size=n,
            )
        rank = min(n, math.ceil((n + 1) * (1 - alpha)))
        threshold = self._scores[rank - 1]
        prediction_set = tuple(
            sorted(label for label, score in candidate_scores.items() if score <= threshold)
        )
        decision = GateDecision.PROCEED if len(prediction_set) == 1 else GateDecision.FIELD_REVIEW
        return GateOutcome(
            decision,
            "Singleton prediction set" if decision == GateDecision.PROCEED else "Ambiguous field",
            prediction_set=prediction_set,
            alpha=alpha,
            calibration_size=n,
        )
