"""Domain exceptions with stable machine-readable reason codes."""

from __future__ import annotations

from typing import Any


class VeritasError(Exception):
    """Base class for expected VERITAS failures."""

    code = "VERITAS_ERROR"

    def __init__(self, message: str | None = None) -> None:
        from veritas.reasons import lookup

        reason = lookup(self.code)
        text = message or reason.engineer
        super().__init__(text)
        self.operator_message = reason.operator
        self.next_step = reason.next_step

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "code": self.code,
            "message": str(self),
            "operator": getattr(self, "operator_message", str(self)),
            "next_step": getattr(self, "next_step", ""),
        }


class CanonicalizationError(VeritasError):
    code = "INVALID_CANONICAL_VALUE"


class PolicyError(VeritasError):
    code = "INVALID_POLICY"


class BudgetDenied(VeritasError):
    code = "BUDGET_EXHAUSTED"


class MissingCapability(VeritasError):
    code = "VALID_CAPABILITY_REQUIRED"


class InvalidCapability(VeritasError):
    code = "INVALID_CAPABILITY"


class ExpiredCapability(InvalidCapability):
    code = "EXPIRED_CAPABILITY"


class StaleCapability(InvalidCapability):
    code = "STALE_CAPABILITY"


class ReplayDetected(InvalidCapability):
    code = "CAPABILITY_REPLAY"


class StateMismatch(InvalidCapability):
    code = "STATE_HASH_MISMATCH"


class InvalidApproval(VeritasError):
    code = "INVALID_APPROVAL"


class StoreUnavailable(VeritasError):
    code = "STORE_UNAVAILABLE"


class ReservationError(VeritasError):
    code = "RESERVATION_INVALID"
