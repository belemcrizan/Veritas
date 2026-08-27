"""Timeout and unknown-outcome reconciliation.

A network timeout after an external call is not treated as failure. Compensation is allowed
only after a probe confirms the action did not execute.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from veritas.errors import ReservationError, VeritasError
from veritas.lifecycle import ExecutionPhase, transition
from veritas.ports import BudgetStore, Clock, LedgerStore


class OutcomeUnknown(VeritasError):
    code = "EXECUTION_UNKNOWN"

    def __init__(
        self,
        message: str,
        *,
        reservation_id: str | None,
        cap_id: str,
        trace_id: str,
    ) -> None:
        super().__init__(message)
        self.reservation_id = reservation_id
        self.cap_id = cap_id
        self.trace_id = trace_id


class ProbeResult(StrEnum):
    CONFIRMED_EXECUTED = "CONFIRMED_EXECUTED"
    CONFIRMED_NOT_EXECUTED = "CONFIRMED_NOT_EXECUTED"
    UNRESOLVED = "UNRESOLVED"


Probe = Callable[[], ProbeResult]


@dataclass(frozen=True)
class ReconciliationResult:
    status: ProbeResult
    phase: ExecutionPhase
    reservation_id: str | None
    compensated: bool
    committed: bool


class Reconciler:
    def __init__(self, *, budgets: BudgetStore, ledger: LedgerStore, clock: Clock) -> None:
        self.budgets = budgets
        self.ledger = ledger
        self.clock = clock

    def reconcile(
        self,
        *,
        reservation_id: str | None,
        trace_id: str,
        probe: Probe,
        phase: ExecutionPhase = ExecutionPhase.UNKNOWN,
    ) -> ReconciliationResult:
        current = transition(phase, ExecutionPhase.RECONCILING)
        outcome = probe()
        now = self.clock.now()
        self.ledger.append(
            trace_id=trace_id,
            node_type="RECONCILE",
            payload={
                "reservation_id": reservation_id,
                "probe": outcome.value,
            },
            now=now,
        )
        if outcome is ProbeResult.UNRESOLVED:
            return ReconciliationResult(
                status=outcome,
                phase=transition(current, ExecutionPhase.UNKNOWN),
                reservation_id=reservation_id,
                compensated=False,
                committed=False,
            )
        if reservation_id is None:
            if outcome is ProbeResult.CONFIRMED_EXECUTED:
                return ReconciliationResult(
                    status=outcome,
                    phase=transition(current, ExecutionPhase.COMMITTED),
                    reservation_id=None,
                    compensated=False,
                    committed=True,
                )
            return ReconciliationResult(
                status=outcome,
                phase=transition(current, ExecutionPhase.COMPENSATED),
                reservation_id=None,
                compensated=True,
                committed=False,
            )
        if outcome is ProbeResult.CONFIRMED_EXECUTED:
            self.budgets.commit(reservation_id)
            return ReconciliationResult(
                status=outcome,
                phase=transition(current, ExecutionPhase.COMMITTED),
                reservation_id=reservation_id,
                compensated=False,
                committed=True,
            )
        try:
            released = self.budgets.compensate(reservation_id)
        except ReservationError:
            released = False
        return ReconciliationResult(
            status=outcome,
            phase=transition(current, ExecutionPhase.COMPENSATED),
            reservation_id=reservation_id,
            compensated=released,
            committed=False,
        )
