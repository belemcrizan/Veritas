"""PostgreSQL adapter for reservation, nonce, session, and ledger ports.

Isolation: each mutating method opens a transaction at REPEATABLE READ and takes a
transaction-scoped advisory lock hashed from the resource key before reading used()
and inserting. This is not a distributed consensus protocol. It is SQL locking.

Do not copy the SQLite BEGIN IMMEDIATE pattern blindly. PostgreSQL serializes writers
on the advisory lock rather than on a whole-file write lock.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from veritas.canonical import canonical_json, digest
from veritas.errors import BudgetDenied, ReservationError, StoreUnavailable
from veritas.ports import Reservation

SCHEMA = """
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY,
    resource_key TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    amount BIGINT NOT NULL CHECK (amount > 0),
    limit_amount BIGINT NOT NULL CHECK (limit_amount > 0),
    window_seconds INTEGER NOT NULL CHECK (window_seconds > 0),
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PREPARED','COMMITTED','COMPENSATED')),
    idempotency_key TEXT NOT NULL UNIQUE,
    agent_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reservations_window
    ON reservations(resource_key, created_at, status);
CREATE TABLE IF NOT EXISTS consumed_nonces (
    nonce TEXT PRIMARY KEY,
    cap_id TEXT NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS session_actions (
    session_id TEXT NOT NULL,
    action TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (session_id, action)
);
CREATE TABLE IF NOT EXISTS session_labels (
    session_id TEXT NOT NULL,
    label TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (session_id, label)
);
CREATE TABLE IF NOT EXISTS ledger_nodes (
    seq BIGSERIAL PRIMARY KEY,
    node_id TEXT NOT NULL UNIQUE,
    trace_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    parents_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ledger_trace ON ledger_nodes(trace_id, seq);
"""


def postgres_available() -> bool:
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return False
    return True


class PostgresAdapter:
    def __init__(self, dsn: str) -> None:
        if not postgres_available():
            raise StoreUnavailable("psycopg is not installed; pip install 'veritas-boundary-poc[postgres]'")
        self.dsn = dsn
        self.path = dsn
        self._initialise()

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        import psycopg
        from psycopg.rows import dict_row

        try:
            connection = psycopg.connect(self.dsn, row_factory=dict_row, autocommit=True)
        except Exception as exc:
            raise StoreUnavailable(f"postgres unavailable: {exc}") from exc
        try:
            yield connection
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connect() as connection:
            for statement in SCHEMA.split(";"):
                sql = statement.strip()
                if sql:
                    connection.execute(sql)

    @staticmethod
    def _lock(connection: Any, resource_key: str) -> None:
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (resource_key,))

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
        with self._connect() as connection:
            connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")
            try:
                self._lock(connection, resource_key)
                existing = connection.execute(
                    "SELECT * FROM reservations WHERE idempotency_key = %s",
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    if existing["status"] == "COMPENSATED":
                        connection.execute("ROLLBACK")
                        raise BudgetDenied("idempotency key refers to a compensated reservation")
                    used = self._used(connection, existing["resource_key"], existing["window_seconds"], now)
                    connection.execute("COMMIT")
                    return Reservation(
                        reservation_id=existing["reservation_id"],
                        resource_key=existing["resource_key"],
                        amount=int(existing["amount"]),
                        residual=max(0, int(existing["limit_amount"]) - used),
                        status=existing["status"],
                    )
                used = self._used(connection, resource_key, window_seconds, now)
                if used + amount > limit:
                    connection.execute("ROLLBACK")
                    raise BudgetDenied(
                        f"resource budget exceeded: used={used}, requested={amount}, limit={limit}"
                    )
                reservation_id = "res:" + uuid.uuid4().hex
                connection.execute(
                    """
                    INSERT INTO reservations(
                        reservation_id, resource_key, policy_version, amount, limit_amount,
                        window_seconds, created_at, status, idempotency_key, agent_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'PREPARED', %s, %s)
                    """,
                    (
                        reservation_id,
                        resource_key,
                        policy_version,
                        amount,
                        limit,
                        window_seconds,
                        now,
                        idempotency_key,
                        agent_id,
                    ),
                )
                connection.execute("COMMIT")
                return Reservation(reservation_id, resource_key, amount, limit - used - amount, "PREPARED")
            except (BudgetDenied, ReservationError):
                raise
            except Exception as exc:
                connection.execute("ROLLBACK")
                raise StoreUnavailable(f"postgres reserve failed: {exc}") from exc

    @staticmethod
    def _used(connection: Any, resource_key: str, window_seconds: int, now: datetime) -> int:
        row = connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS used
            FROM reservations
            WHERE resource_key = %s
              AND created_at > %s - make_interval(secs => %s)
              AND status IN ('PREPARED','COMMITTED')
            """,
            (resource_key, now, window_seconds),
        ).fetchone()
        return int(row["used"])

    def commit(self, reservation_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN")
            row = connection.execute(
                "SELECT status FROM reservations WHERE reservation_id = %s",
                (reservation_id,),
            ).fetchone()
            if row is None:
                connection.execute("ROLLBACK")
                raise ReservationError(f"unknown reservation: {reservation_id}")
            if row["status"] == "COMPENSATED":
                connection.execute("ROLLBACK")
                raise ReservationError("cannot commit a compensated reservation")
            if row["status"] == "PREPARED":
                connection.execute(
                    "UPDATE reservations SET status = 'COMMITTED' WHERE reservation_id = %s",
                    (reservation_id,),
                )
            connection.execute("COMMIT")

    def compensate(self, reservation_id: str) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN")
            row = connection.execute(
                "SELECT status FROM reservations WHERE reservation_id = %s",
                (reservation_id,),
            ).fetchone()
            if row is None:
                connection.execute("ROLLBACK")
                raise ReservationError(f"unknown reservation: {reservation_id}")
            changed = row["status"] == "PREPARED"
            if changed:
                connection.execute(
                    "UPDATE reservations SET status = 'COMPENSATED' WHERE reservation_id = %s",
                    (reservation_id,),
                )
            connection.execute("COMMIT")
            return bool(changed)

    def used(self, resource_key: str, window_seconds: int, now: datetime) -> int:
        with self._connect() as connection:
            connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")
            value = self._used(connection, resource_key, window_seconds, now)
            connection.execute("COMMIT")
            return value

    def reservation_status(self, reservation_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM reservations WHERE reservation_id = %s",
                (reservation_id,),
            ).fetchone()
            if row is None:
                raise ReservationError(f"unknown reservation: {reservation_id}")
            return str(row["status"])

    def consume(self, nonce: str, cap_id: str, now: datetime) -> bool:
        from psycopg.errors import UniqueViolation

        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO consumed_nonces(nonce, cap_id, consumed_at) VALUES (%s, %s, %s)",
                    (nonce, cap_id, now),
                )
                return True
            except UniqueViolation:
                return False

    def has_action(self, session_id: str, action: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM session_actions WHERE session_id = %s AND action = %s",
                (session_id, action),
            ).fetchone()
            return row is not None

    def record_action(self, session_id: str, action: str, now: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO session_actions(session_id, action, occurred_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (session_id, action)
                DO UPDATE SET occurred_at = EXCLUDED.occurred_at
                """,
                (session_id, action, now),
            )

    def has_label(self, session_id: str, label: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM session_labels WHERE session_id = %s AND label = %s",
                (session_id, label),
            ).fetchone()
            return row is not None

    def record_labels(self, session_id: str, labels: tuple[str, ...], now: datetime) -> None:
        if not labels:
            return
        with self._connect() as connection:
            for label in labels:
                connection.execute(
                    """
                    INSERT INTO session_labels(session_id, label, occurred_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (session_id, label)
                    DO UPDATE SET occurred_at = EXCLUDED.occurred_at
                    """,
                    (session_id, label, now),
                )

    def append(
        self,
        *,
        trace_id: str,
        node_type: str,
        payload: dict[str, Any],
        now: datetime,
        parents: tuple[str, ...] | None = None,
    ) -> str:
        recorded_at = now.isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN")
            resolved_parents: tuple[str, ...]
            if parents is None:
                previous = connection.execute(
                    "SELECT node_id FROM ledger_nodes WHERE trace_id = %s ORDER BY seq DESC LIMIT 1",
                    (trace_id,),
                ).fetchone()
                resolved_parents = () if previous is None else (str(previous["node_id"]),)
            else:
                resolved_parents = tuple(sorted(parents))
            envelope = {
                "trace_id": trace_id,
                "type": node_type,
                "payload": payload,
                "parents": resolved_parents,
                "recorded_at": recorded_at,
            }
            node_id = digest(envelope, prefix="node:sha256:")
            connection.execute(
                """
                INSERT INTO ledger_nodes(
                    node_id, trace_id, node_type, payload_json, parents_json, recorded_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    node_id,
                    trace_id,
                    node_type,
                    canonical_json(payload).decode("utf-8"),
                    canonical_json(resolved_parents).decode("utf-8"),
                    recorded_at,
                ),
            )
            connection.execute("COMMIT")
            return node_id

    def trace(self, trace_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ledger_nodes WHERE trace_id = %s ORDER BY seq",
                (trace_id,),
            ).fetchall()
        return [
            {
                "seq": row["seq"],
                "node_id": row["node_id"],
                "trace_id": row["trace_id"],
                "type": row["node_type"],
                "payload": json.loads(row["payload_json"]),
                "parents": tuple(json.loads(row["parents_json"])),
                "recorded_at": row["recorded_at"],
            }
            for row in rows
        ]

    def replay(
        self,
        trace_id: str,
        interventions: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        changes = interventions or {}
        remapped_map: dict[str, str] = {}
        replayed: list[dict[str, Any]] = []
        for node in self.trace(trace_id):
            payload = changes.get(node["node_id"], node["payload"])
            parents = tuple(remapped_map.get(parent, parent) for parent in node["parents"])
            envelope = {
                "trace_id": trace_id,
                "type": node["type"],
                "payload": payload,
                "parents": parents,
                "recorded_at": node["recorded_at"],
            }
            replayed_id = digest(envelope, prefix="node:sha256:")
            remapped_map[node["node_id"]] = replayed_id
            replayed.append(
                {
                    "original_node_id": node["node_id"],
                    "replayed_node_id": replayed_id,
                    "changed": replayed_id != node["node_id"],
                    "type": node["type"],
                    "payload": payload,
                    "parents": parents,
                }
            )
        return replayed

    def verify_integrity(self) -> bool:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM ledger_nodes ORDER BY seq").fetchall()
        seen: set[str] = set()
        for row in rows:
            parents = tuple(json.loads(row["parents_json"]))
            if any(parent not in seen for parent in parents):
                return False
            envelope = {
                "trace_id": row["trace_id"],
                "type": row["node_type"],
                "payload": json.loads(row["payload_json"]),
                "parents": parents,
                "recorded_at": row["recorded_at"],
            }
            if digest(envelope, prefix="node:sha256:") != row["node_id"]:
                return False
            seen.add(str(row["node_id"]))
        return True
