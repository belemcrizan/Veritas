"""VERITAS: verified execution boundary proof of concept."""

from veritas.models import ASIR, AuthorizationResult, Decision

__all__ = [
    "ASIR",
    "AuthorizationResult",
    "Decision",
    "GuardedTool",
    "MissingCapability",
    "VeritasError",
    "bundled_policy_path",
    "create_local_runtime",
    "describe_result",
    "lookup",
]
__version__ = "0.1.2"


def __getattr__(name: str):
    if name == "GuardedTool":
        from veritas.guarded import GuardedTool

        return GuardedTool
    if name in {"MissingCapability", "VeritasError"}:
        from veritas import errors

        return getattr(errors, name)
    if name in {"bundled_policy_path", "create_local_runtime"}:
        from veritas import runtime

        return getattr(runtime, name)
    if name in {"describe_result", "lookup"}:
        from veritas import reasons

        return getattr(reasons, name)
    raise AttributeError(f"module 'veritas' has no attribute {name!r}")
