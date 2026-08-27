"""Explicit execution lifecycle. Invalid transitions fail closed."""

from __future__ import annotations

from enum import StrEnum

from veritas.errors import VeritasError


class InvalidLifecycleTransition(VeritasError):
    code = "INVALID_LIFECYCLE_TRANSITION"


class ExecutionPhase(StrEnum):
    REQUESTED = "REQUESTED"
    VERIFIED = "VERIFIED"
    RESERVED = "RESERVED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    COMMITTED = "COMMITTED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    STALE = "STALE"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    RECONCILING = "RECONCILING"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"


SUCCESS_TERMINAL = frozenset({ExecutionPhase.COMMITTED, ExecutionPhase.COMPENSATED})
FAILURE_TERMINAL = frozenset(
    {
        ExecutionPhase.DENIED,
        ExecutionPhase.EXPIRED,
        ExecutionPhase.STALE,
        ExecutionPhase.FAILED,
    }
)
OPEN_TERMINAL = frozenset({ExecutionPhase.UNKNOWN})

ALLOWED_TRANSITIONS: dict[ExecutionPhase, frozenset[ExecutionPhase]] = {
    ExecutionPhase.REQUESTED: frozenset(
        {ExecutionPhase.VERIFIED, ExecutionPhase.DENIED, ExecutionPhase.FAILED}
    ),
    ExecutionPhase.VERIFIED: frozenset(
        {
            ExecutionPhase.RESERVED,
            ExecutionPhase.AUTHORIZED,
            ExecutionPhase.DENIED,
            ExecutionPhase.FAILED,
        }
    ),
    ExecutionPhase.RESERVED: frozenset(
        {
            ExecutionPhase.AUTHORIZED,
            ExecutionPhase.DENIED,
            ExecutionPhase.COMPENSATING,
            ExecutionPhase.FAILED,
        }
    ),
    ExecutionPhase.AUTHORIZED: frozenset(
        {
            ExecutionPhase.EXECUTING,
            ExecutionPhase.EXPIRED,
            ExecutionPhase.STALE,
            ExecutionPhase.DENIED,
            ExecutionPhase.COMPENSATING,
        }
    ),
    ExecutionPhase.EXECUTING: frozenset(
        {
            ExecutionPhase.EXECUTED,
            ExecutionPhase.FAILED,
            ExecutionPhase.UNKNOWN,
        }
    ),
    ExecutionPhase.EXECUTED: frozenset({ExecutionPhase.COMMITTED, ExecutionPhase.FAILED}),
    ExecutionPhase.COMMITTED: frozenset(),
    ExecutionPhase.DENIED: frozenset(),
    ExecutionPhase.EXPIRED: frozenset(),
    ExecutionPhase.STALE: frozenset(),
    ExecutionPhase.FAILED: frozenset({ExecutionPhase.COMPENSATING}),
    ExecutionPhase.UNKNOWN: frozenset({ExecutionPhase.RECONCILING}),
    ExecutionPhase.RECONCILING: frozenset(
        {
            ExecutionPhase.COMMITTED,
            ExecutionPhase.COMPENSATING,
            ExecutionPhase.COMPENSATED,
            ExecutionPhase.UNKNOWN,
        }
    ),
    ExecutionPhase.COMPENSATING: frozenset({ExecutionPhase.COMPENSATED, ExecutionPhase.FAILED}),
    ExecutionPhase.COMPENSATED: frozenset(),
}


def can_transition(current: ExecutionPhase, nxt: ExecutionPhase) -> bool:
    return nxt in ALLOWED_TRANSITIONS[current]


def transition(current: ExecutionPhase, nxt: ExecutionPhase) -> ExecutionPhase:
    if not can_transition(current, nxt):
        raise InvalidLifecycleTransition(f"cannot move from {current.value} to {nxt.value}")
    return nxt
