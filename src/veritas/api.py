"""Supported public API for the experimental VERITAS Python library.

Applications should import the names in this module, or their re-exports from
``veritas``, instead of depending on internal modules such as
``veritas.adapters``. The public API is still pre-1.0 and may change between
minor releases.
"""

from veritas.adapters.frameworks import LangGraphToolCallAdapter, MCPToolCallAdapter
from veritas.engine import VeritasEngine
from veritas.errors import (
    BudgetDenied,
    ExpiredCapability,
    InvalidApproval,
    InvalidCapability,
    PolicyError,
    ReplayDetected,
    StaleCapability,
    StateMismatch,
    VeritasError,
)
from veritas.models import (
    ASIR,
    AuthorizationResult,
    BoundaryResult,
    Decision,
    Principal,
    RequestContext,
)
from veritas.runtime import LocalRuntime, bundled_policy_path, create_local_runtime

__all__ = [
    "ASIR",
    "AuthorizationResult",
    "BoundaryResult",
    "BudgetDenied",
    "Decision",
    "ExpiredCapability",
    "InvalidApproval",
    "InvalidCapability",
    "LangGraphToolCallAdapter",
    "LocalRuntime",
    "MCPToolCallAdapter",
    "PolicyError",
    "Principal",
    "ReplayDetected",
    "RequestContext",
    "StaleCapability",
    "StateMismatch",
    "VeritasEngine",
    "VeritasError",
    "bundled_policy_path",
    "create_local_runtime",
]
