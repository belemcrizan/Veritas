"""In-memory partition and hybrid budget coordinators for the local POC."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime

from veritas.errors import BudgetDenied
from veritas.ports import BudgetStore, Reservation


@dataclass
class _PartitionEntry:
    reservation_id: str
    resource_key: str
    agent_id: str
    amount: int
    created_at: float
    window_seconds: int
    idempotency_key: str
    status: str = "PREPARED"


class InMemoryPartitionBudgetStore:
    """Pre-allocated, coordination-free shares.

    ``shares`` is a per-resource allocation template by agent. Its sum must not exceed the
    global limit supplied on reserve. State is intentionally ephemeral in this POC.
    """

    def __init__(self, shares: dict[str, int]) -> None:
        if not shares or any(value <= 0 for value in shares.values()):
            raise ValueError("shares must be positive")
        self.shares = dict(shares)
        self.allocated_total = sum(shares.values())
        self._entries: dict[str, _PartitionEntry] = {}
        self._by_idempotency: dict[str, str] = {}
        self._lock = threading.RLock()

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
    ) -> Reservation:
        del policy_version
        if self.allocated_total > limit:
            raise BudgetDenied("configured partitions exceed the global policy limit")
        share = self.shares.get(agent_id)
        if share is None:
            raise BudgetDenied("agent has no local budget partition")
        with self._lock:
            existing_id = self._by_idempotency.get(idempotency_key)
            if existing_id is not None:
                existing = self._entries[existing_id]
                if existing.status == "COMPENSATED":
                    raise BudgetDenied("idempotency key refers to compensated reservation")
                used = self._agent_used(resource_key, agent_id, window_seconds, now.timestamp())
                return Reservation(existing_id, resource_key, existing.amount, share - used, existing.status)
            used = self._agent_used(resource_key, agent_id, window_seconds, now.timestamp())
            if used + amount > share:
                raise BudgetDenied("agent partition is exhausted")
            reservation_id = "part:" + uuid.uuid4().hex
            self._entries[reservation_id] = _PartitionEntry(
                reservation_id,
                resource_key,
                agent_id,
                amount,
                now.timestamp(),
                window_seconds,
                idempotency_key,
            )
            self._by_idempotency[idempotency_key] = reservation_id
            return Reservation(reservation_id, resource_key, amount, share - used - amount, "PREPARED")

    def _agent_used(
        self, resource_key: str, agent_id: str, window_seconds: int, now_ts: float
    ) -> int:
        return sum(
            entry.amount
            for entry in self._entries.values()
            if entry.resource_key == resource_key
            and entry.agent_id == agent_id
            and entry.created_at > now_ts - window_seconds
            and entry.status in {"PREPARED", "COMMITTED"}
        )

    def commit(self, reservation_id: str) -> None:
        with self._lock:
            entry = self._entries[reservation_id]
            if entry.status == "COMPENSATED":
                raise RuntimeError("cannot commit a compensated partition reservation")
            entry.status = "COMMITTED"

    def compensate(self, reservation_id: str) -> bool:
        with self._lock:
            entry = self._entries[reservation_id]
            changed = entry.status == "PREPARED"
            if changed:
                entry.status = "COMPENSATED"
            return changed

    def used(self, resource_key: str, window_seconds: int, now: datetime) -> int:
        with self._lock:
            return sum(
                self._agent_used(resource_key, agent, window_seconds, now.timestamp())
                for agent in self.shares
            )


class HybridBudgetStore:
    """Use pre-allocated shares first, then a disjoint central residual.

    The central limit is ``global_limit - sum(partitions)``. This conservative separation
    preserves the global invariant without double-counting. Asynchronous rebalancing remains a
    production backlog item.
    """

    def __init__(self, partitions: InMemoryPartitionBudgetStore, central: BudgetStore) -> None:
        self.partitions = partitions
        self.central = central

    def reserve(self, **request: object) -> Reservation:
        try:
            return self.partitions.reserve(**request)  # type: ignore[arg-type]
        except BudgetDenied:
            central_request = dict(request)
            original_limit = int(central_request["limit"])
            central_limit = original_limit - self.partitions.allocated_total
            if central_limit <= 0:
                raise BudgetDenied("no unpartitioned residual is available")
            central_request["limit"] = central_limit
            central_request["resource_key"] = str(central_request["resource_key"]) + ":unpartitioned"
            central_request["idempotency_key"] = "central:" + str(central_request["idempotency_key"])
            return self.central.reserve(**central_request)  # type: ignore[arg-type]

    def commit(self, reservation_id: str) -> None:
        if reservation_id.startswith("part:"):
            self.partitions.commit(reservation_id)
        else:
            self.central.commit(reservation_id)

    def compensate(self, reservation_id: str) -> bool:
        if reservation_id.startswith("part:"):
            return self.partitions.compensate(reservation_id)
        return self.central.compensate(reservation_id)

    def used(self, resource_key: str, window_seconds: int, now: datetime) -> int:
        return self.partitions.used(resource_key, window_seconds, now) + self.central.used(
            resource_key + ":unpartitioned", window_seconds, now
        )

