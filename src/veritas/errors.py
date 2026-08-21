"""Domain exceptions with stable machine-readable reason codes."""


class VeritasError(Exception):
    """Base class for expected VERITAS failures."""

    code = "VERITAS_ERROR"


class CanonicalizationError(VeritasError):
    code = "INVALID_CANONICAL_VALUE"


class PolicyError(VeritasError):
    code = "INVALID_POLICY"


class BudgetDenied(VeritasError):
    code = "BUDGET_EXHAUSTED"


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
