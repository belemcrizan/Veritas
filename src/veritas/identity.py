"""Identity and delegation verification architecture.

Cycle 2 verifies structure, issuer allowlists, delegation shape, and actor binding.
It does not verify OIDC, SPIFFE, or mTLS signatures. Those adapters remain unimplemented
until a real verifier and credentials exist.
"""

from __future__ import annotations

from typing import Protocol

from veritas.models import ASIR, Principal


class IdentityDecision:
    def __init__(self, allowed: bool, reason_code: str, explanation: str) -> None:
        self.allowed = allowed
        self.reason_code = reason_code
        self.explanation = explanation


class IdentityVerifier(Protocol):
    def verify(self, asir: ASIR) -> IdentityDecision: ...


class PrincipalResolver(Protocol):
    def resolve(self, principal: Principal) -> Principal: ...


class DelegationVerifier(Protocol):
    def verify(self, asir: ASIR) -> IdentityDecision: ...


class TrustedInputIdentityVerifier:
    """Fail-closed structural verifier for trusted upstream identity claims."""

    def __init__(
        self,
        *,
        allowed_issuers: frozenset[str] | None = None,
        allowed_audiences: frozenset[str] | None = None,
        max_delegation_depth: int | None = None,
    ) -> None:
        self.allowed_issuers = allowed_issuers
        self.allowed_audiences = allowed_audiences
        self.max_delegation_depth = max_delegation_depth

    def verify(self, asir: ASIR) -> IdentityDecision:
        if not asir.principal.sub or not asir.principal.iss:
            return IdentityDecision(
                False, "IDENTITY_MISSING", "Signed upstream identity is required"
            )
        if self.allowed_issuers is not None and asir.principal.iss not in self.allowed_issuers:
            return IdentityDecision(
                False,
                "IDENTITY_ISSUER_REJECTED",
                "Principal issuer is not in the configured allowlist",
            )
        if self.allowed_audiences is not None:
            if asir.principal.aud is None or asir.principal.aud not in self.allowed_audiences:
                return IdentityDecision(
                    False,
                    "IDENTITY_AUDIENCE_REJECTED",
                    "Principal audience is missing or not allowed",
                )
        if asir.agent_id not in asir.principal.act:
            return IdentityDecision(
                False,
                "ACTOR_BINDING_MISSING",
                "Principal act claim does not name the executing agent",
            )
        return StructuralDelegationVerifier(self.max_delegation_depth).verify(asir)


class PassthroughPrincipalResolver:
    def resolve(self, principal: Principal) -> Principal:
        return principal


class StructuralDelegationVerifier:
    def __init__(self, max_delegation_depth: int | None = None) -> None:
        self.max_delegation_depth = max_delegation_depth

    def verify(self, asir: ASIR) -> IdentityDecision:
        chain = asir.delegation
        if len(chain) != len(set(chain)):
            return IdentityDecision(
                False,
                "DELEGATION_CYCLE",
                "Delegation chain contains a repeated principal (cycle or duplicate hop)",
            )
        if chain[-1] != asir.agent_id:
            return IdentityDecision(
                False,
                "ACTOR_BINDING_MISSING",
                "Delegation chain must end at the executing agent",
            )
        if self.max_delegation_depth is not None and len(chain) > self.max_delegation_depth:
            return IdentityDecision(
                False,
                "DELEGATION_DEPTH_EXCEEDED",
                f"Delegation depth {len(chain)} exceeds {self.max_delegation_depth}",
            )
        return IdentityDecision(True, "IDENTITY_OK", "Structural identity checks passed")
