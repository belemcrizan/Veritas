"""Experimental metrics. Not security proofs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeasibleDenial:
    legitimate_denied: int
    legitimate_feasible: int

    @property
    def fdr(self) -> float:
        if self.legitimate_feasible == 0:
            return 0.0
        return self.legitimate_denied / self.legitimate_feasible


@dataclass(frozen=True)
class AutonomyCost:
    legitimate_denials: int
    unnecessary_approvals: int
    legitimate_actions: int
    latency_ms: float = 0.0

    @property
    def ac(self) -> float:
        if self.legitimate_actions == 0:
            return 0.0
        return (self.legitimate_denials + self.unnecessary_approvals) / self.legitimate_actions


def utility(security_benefit: float, autonomy_cost: float, latency: float, lam: float, mu: float) -> float:
    """U = SecurityBenefit - λ AutonomyCost - μ Latency. λ, μ are caller-chosen, not fitted to win."""

    return security_benefit - lam * autonomy_cost - mu * latency


def sensitivity(security_benefit: float, autonomy_cost: float, latency: float) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for lam in (0.0, 0.25, 0.5, 1.0, 2.0):
        for mu in (0.0, 0.001, 0.01, 0.1):
            rows.append(
                {
                    "lambda": lam,
                    "mu": mu,
                    "U": utility(security_benefit, autonomy_cost, latency, lam, mu),
                }
            )
    return rows
