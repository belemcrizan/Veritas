"""Public package interface for the experimental VERITAS library.

Only names exported here and documented in ``docs/API_REFERENCE.md`` are part
of the supported public API. Internal modules can change without notice while
the project remains below version 1.0.
"""

from importlib.metadata import PackageNotFoundError, version

from veritas.api import (
    ASIR,
    AuthorizationResult,
    BoundaryResult,
    BudgetDenied,
    Decision,
    ExpiredCapability,
    InvalidApproval,
    InvalidCapability,
    LangGraphToolCallAdapter,
    LocalRuntime,
    MCPToolCallAdapter,
    PolicyError,
    Principal,
    ReplayDetected,
    RequestContext,
    StaleCapability,
    StateMismatch,
    VeritasEngine,
    VeritasError,
    bundled_policy_path,
    create_local_runtime,
)

try:
    __version__ = version("veritas-boundary-poc")
except PackageNotFoundError:
    __version__ = "0.1.0.dev0"


def __getattr__(name: str):
    if name == "GuardedTool":
        from veritas.guarded import GuardedTool

        return GuardedTool
    if name == "MissingCapability":
        from veritas.errors import MissingCapability

        return MissingCapability
    if name in {"describe_result", "lookup"}:
        from veritas.reasons import describe_result, lookup

        return {"describe_result": describe_result, "lookup": lookup}[name]
    raise AttributeError(f"module 'veritas' has no attribute {name!r}")


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
    "GuardedTool",
    "MissingCapability",
    "__version__",
    "bundled_policy_path",
    "create_local_runtime",
    "describe_result",
    "lookup",
]
