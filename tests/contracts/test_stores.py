from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from veritas.adapters.sqlite import SQLiteAdapter
from veritas.errors import BudgetDenied
from veritas.scenarios import DEFAULT_TIME


def make_store() -> tuple[SQLiteAdapter, tempfile.TemporaryDirectory[str]]:
    temp = tempfile.TemporaryDirectory(prefix="veritas-contract-")
    return SQLiteAdapter(Path(temp.name) / "store.db"), temp


class ReservationStoreContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store, self.temp = make_store()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_concurrent_style_overspend_is_rejected_sequentially(self) -> None:
        now = DEFAULT_TIME
        first = self.store.reserve(
            resource_key="money:contract:86400s",
            policy_version="v1",
            limit=1000,
            amount=900,
            window_seconds=86400,
            now=now,
            idempotency_key="a",
            agent_id="agent",
        )
        self.assertEqual(first.status, "PREPARED")
        with self.assertRaises(BudgetDenied):
            self.store.reserve(
                resource_key="money:contract:86400s",
                policy_version="v1",
                limit=1000,
                amount=900,
                window_seconds=86400,
                now=now,
                idempotency_key="b",
                agent_id="agent",
            )
        self.assertLessEqual(self.store.used("money:contract:86400s", 86400, now), 1000)

    def test_commit_is_idempotent(self) -> None:
        reservation = self.store.reserve(
            resource_key="money:idem:86400s",
            policy_version="v1",
            limit=1000,
            amount=100,
            window_seconds=86400,
            now=DEFAULT_TIME,
            idempotency_key="idem",
            agent_id="agent",
        )
        self.store.commit(reservation.reservation_id)
        self.store.commit(reservation.reservation_id)
        self.assertEqual(self.store.reservation_status(reservation.reservation_id), "COMMITTED")


class NonceStoreContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store, self.temp = make_store()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_nonce_is_single_use(self) -> None:
        now = DEFAULT_TIME
        self.assertTrue(self.store.consume("nonce-1", "cap-1", now))
        self.assertFalse(self.store.consume("nonce-1", "cap-1", now))


class LedgerStoreContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store, self.temp = make_store()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_payload_mutation_breaks_integrity(self) -> None:
        now = DEFAULT_TIME
        self.store.append(
            trace_id="t1",
            node_type="ASIR",
            payload={"x": 1},
            now=now,
        )
        self.assertTrue(self.store.verify_integrity())
        with self.store._connect() as connection:
            connection.execute("UPDATE ledger_nodes SET payload_json = '{\"x\":2}'")
        self.assertFalse(self.store.verify_integrity())
