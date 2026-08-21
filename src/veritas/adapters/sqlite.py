from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from veritas.canonical import canonical_json, digest
from veritas.errors import BudgetDenied
from veritas.ports import Reservation


class SQLiteAdapter:
    """A single file with independent transactional tables for all local ports."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a short-lived connection and always release the database file."""

        connection = sqlite3.connect(
            self.path,
            timeout=30.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row

        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 30000")
            yield connection
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS reservations (
                    reservation_id TEXT PRIMARY KEY,
                    resource_key TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    amount INTEGER NOT NULL CHECK(amount > 0),
                    limit_amount INTEGER NOT NULL CHECK(limit_amount > 0),
                    window_seconds INTEGER NOT NULL CHECK(window_seconds > 0),
                    created_at REAL NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('PREPARED','COMMITTED','COMPENSATED')),
                    idempotency_key TEXT NOT NULL UNIQUE,
                    agent_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_reservations_window
                    ON reservations(resource_key, created_at, status);

                CREATE TABLE IF NOT EXISTS consumed_nonces (
                    nonce TEXT PRIMARY KEY,
                    cap_id TEXT NOT NULL,
                    consumed_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS session_actions (
                    session_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    occurred_at REAL NOT NULL,
                    PRIMARY KEY(session_id, action)
                );

                CREATE TABLE IF NOT EXISTS ledger_nodes (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL UNIQUE,
                    trace_id TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    parents_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ledger_trace ON ledger_nodes(trace_id, seq);
                """
            )

    @staticmethod
    def _timestamp(value: datetime) -> float:
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value.timestamp()

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
        now_ts = self._timestamp(now)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM reservations WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["status"] == "COMPENSATED":
                    connection.rollback()
                    raise BudgetDenied("idempotency key refers to a compensated reservation")
                used = self._used_in_transaction(
                    connection, existing["resource_key"], existing["window_seconds"], now_ts
                )
                connection.commit()
                return Reservation(
                    reservation_id=existing["reservation_id"],
                    resource_key=existing["resource_key"],
                    amount=existing["amount"],
                    residual=max(0, existing["limit_amount"] - used),
                    status=existing["status"],
                )

            used = self._used_in_transaction(connection, resource_key, window_seconds, now_ts)
            if used + amount > limit:
                connection.rollback()
                raise BudgetDenied(
                    f"resource budget exceeded: used={used}, requested={amount}, limit={limit}"
                )
            reservation_id = "res:" + uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO reservations(
                    reservation_id, resource_key, policy_version, amount, limit_amount,
                    window_seconds, created_at, status, idempotency_key, agent_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PREPARED', ?, ?)
                """,
                (
                    reservation_id,
                    resource_key,
                    policy_version,
                    amount,
                    limit,
                    window_seconds,
                    now_ts,
                    idempotency_key,
                    agent_id,
                ),
            )
            residual = limit - used - amount
            connection.commit()
            return Reservation(reservation_id, resource_key, amount, residual, "PREPARED")

    @staticmethod
    def _used_in_transaction(
        connection: sqlite3.Connection,
        resource_key: str,
        window_seconds: int,
        now_ts: float,
    ) -> int:
        row = connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS used
            FROM reservations
            WHERE resource_key = ? AND created_at > ?
              AND status IN ('PREPARED','COMMITTED')
            """,
            (resource_key, now_ts - window_seconds),
        ).fetchone()
        return int(row["used"])

    def commit(self, reservation_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM reservations WHERE reservation_id = ?", (reservation_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise KeyError(f"unknown reservation: {reservation_id}")
            if row["status"] == "COMPENSATED":
                connection.rollback()
                raise RuntimeError("cannot commit a compensated reservation")
            if row["status"] == "PREPARED":
                connection.execute(
                    "UPDATE reservations SET status = 'COMMITTED' WHERE reservation_id = ?",
                    (reservation_id,),
                )
            connection.commit()

    def compensate(self, reservation_id: str) -> bool:
        """Release only a PREPARED reservation; repeated calls are harmless."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM reservations WHERE reservation_id = ?", (reservation_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise KeyError(f"unknown reservation: {reservation_id}")
            changed = row["status"] == "PREPARED"
            if changed:
                connection.execute(
                    "UPDATE reservations SET status = 'COMPENSATED' WHERE reservation_id = ?",
                    (reservation_id,),
                )
            connection.commit()
            return changed

    def used(self, resource_key: str, window_seconds: int, now: datetime) -> int:
        with self._connect() as connection:
            return self._used_in_transaction(
                connection, resource_key, window_seconds, self._timestamp(now)
            )

    def reservation_status(self, reservation_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM reservations WHERE reservation_id = ?", (reservation_id,)
            ).fetchone()
            if row is None:
                raise KeyError(reservation_id)
            return str(row["status"])

    def consume(self, nonce: str, cap_id: str, now: datetime) -> bool:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO consumed_nonces(nonce, cap_id, consumed_at) VALUES (?, ?, ?)",
                    (nonce, cap_id, self._timestamp(now)),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def has_action(self, session_id: str, action: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM session_actions WHERE session_id = ? AND action = ?",
                (session_id, action),
            ).fetchone()
            return row is not None

    def record_action(self, session_id: str, action: str, now: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO session_actions(session_id, action, occurred_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id, action)
                DO UPDATE SET occurred_at = excluded.occurred_at
                """,
                (session_id, action, self._timestamp(now)),
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
            connection.execute("BEGIN IMMEDIATE")
            if parents is None:
                previous = connection.execute(
                    "SELECT node_id FROM ledger_nodes WHERE trace_id = ? ORDER BY seq DESC LIMIT 1",
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
                ) VALUES (?, ?, ?, ?, ?, ?)
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
            connection.commit()
            return node_id

    def trace(self, trace_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ledger_nodes WHERE trace_id = ? ORDER BY seq", (trace_id,)
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
        remapped: dict[str, str] = {}
        replayed: list[dict[str, Any]] = []
        for node in self.trace(trace_id):
            payload = changes.get(node["node_id"], node["payload"])
            parents = tuple(remapped.get(parent, parent) for parent in node["parents"])
            envelope = {
                "trace_id": trace_id,
                "type": node["type"],
                "payload": payload,
                "parents": parents,
                "recorded_at": node["recorded_at"],
            }
            replayed_id = digest(envelope, prefix="node:sha256:")
            remapped[node["node_id"]] = replayed_id
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

