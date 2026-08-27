"""Validated domain contracts shared by adapters and the execution boundary."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from veritas.canonical import digest


def _reject_floats(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError("floats are forbidden; use integer minor units")
    if isinstance(value, dict):
        for nested in value.values():
            _reject_floats(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_floats(nested)
    return value


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Principal(FrozenModel):
    sub: str = Field(min_length=1)
    iss: str = Field(min_length=1)
    act: tuple[str, ...] = ()
    aud: str | None = None


class RequestContext(FrozenModel):
    session_id: str = Field(min_length=1)
    request_ts: datetime
    source_observations: tuple[str, ...] = ()


class ASIR(FrozenModel):
    """Agent Safety Intermediate Representation.

    Schema versions: ``1.0`` is the Cycle-1 contract. ``1.1`` adds optional correlation
    and sensitivity fields that are omitted from the canonical hash when unset.
    """

    asir_version: str = "1.0"
    agent_id: str = Field(min_length=1)
    principal: Principal
    delegation: tuple[str, ...] = Field(min_length=1)
    action: str = Field(min_length=1)
    resource: str = Field(min_length=1)
    parameters: dict[str, Any]
    purpose: str = Field(min_length=1)
    labels: dict[str, Any] = Field(default_factory=dict)
    context: RequestContext
    correlation_id: str | None = None
    sensitivity: str | None = None

    @field_validator("parameters", "labels", mode="before")
    @classmethod
    def values_must_be_canonical(cls, value: Any) -> Any:
        return _reject_floats(value)

    @model_validator(mode="after")
    def delegation_ends_at_agent(self) -> ASIR:
        if self.delegation[-1] != self.agent_id:
            raise ValueError("delegation chain must end at agent_id")
        return self

    @property
    def hash(self) -> str:
        return digest(self)


class Decision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    STALE = "STALE"


class GateDecision(StrEnum):
    BYPASS_RECORDED = "BYPASS_RECORDED"
    PROCEED = "PROCEED"
    FIELD_REVIEW = "FIELD_REVIEW"
    NO_GUARANTEE = "NO_GUARANTEE"


class Certificate(FrozenModel):
    claim: str
    proof_digest: str
    compiler: str = "veritas-table-v1"


class CapabilityClaims(FrozenModel):
    cap_id: str
    reservation_id: str | None = None
    chain_index: int = Field(ge=0)
    parent_cap: str | None = None
    asir_hash: str
    state_hash: str
    residual: dict[str, int]
    policy_version: str
    policy_digest: str
    issued_at: datetime
    expires_at: datetime
    nonce: str
    issuer_kid: str
    certificate: Certificate


class AuthorizationResult(FrozenModel):
    decision: Decision
    reason_code: str
    explanation: str
    trace_id: str
    capability: str | None = None
    cap_id: str | None = None
    residual: dict[str, int] = Field(default_factory=dict)
    enforcement_mode: str = "ENFORCE"
    hypothetical_decision: str | None = None
    lifecycle: str | None = None


class BoundaryResult(FrozenModel):
    cap_id: str
    trace_id: str
    tool_output: Any
    commit_status: str = "COMMITTED"
