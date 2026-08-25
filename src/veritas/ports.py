"""Infrastructure ports. Domain modules import these protocols, never cloud SDKs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    resource_key: str
    amount: int
    residual: int
    status: str


class Clock(Protocol):
    def now(self) -> datetime: ...


class Signer(Protocol):
    @property
    def kid(self) -> str: ...

    def sign(self, payload: bytes) -> bytes: ...

    def verify(self, payload: bytes, signature: bytes) -> None: ...


class BudgetStore(Protocol):
    def reserve(
        self,
        *,
        resource_key: str,
        policy_version: str,
        limit: int,
        amount: int,
        window_seconds: int,
        now: datetime,
        idempotency_key: str,
        agent_id: str,
    ) -> Reservation: ...

    def commit(self, reservation_id: str) -> None: ...

    def compensate(self, reservation_id: str) -> bool: ...

    def used(self, resource_key: str, window_seconds: int, now: datetime) -> int: ...


class LedgerStore(Protocol):
    def append(
        self,
        *,
        trace_id: str,
        node_type: str,
        payload: dict[str, Any],
        now: datetime,
        parents: tuple[str, ...] | None = None,
    ) -> str: ...

    def trace(self, trace_id: str) -> list[dict[str, Any]]: ...

    def replay(
        self,
        trace_id: str,
        interventions: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]: ...

    def verify_integrity(self) -> bool: ...


class NonceStore(Protocol):
    def consume(self, nonce: str, cap_id: str, now: datetime) -> bool: ...


class SessionStateStore(Protocol):
    def has_action(self, session_id: str, action: str) -> bool: ...

    def record_action(self, session_id: str, action: str, now: datetime) -> None: ...


class Telemetry(Protocol):
    def record(self, event: str, attributes: dict[str, Any]) -> None: ...
