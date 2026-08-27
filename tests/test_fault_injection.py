from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from veritas.errors import StoreUnavailable
from veritas.models import Decision
from veritas.ports import Reservation
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import account_state, payment_asir


class UnavailableBudget:
    def reserve(self, **_kwargs: object) -> Reservation:
        raise StoreUnavailable("injected: budget store down")

    def commit(self, reservation_id: str) -> None:
        raise StoreUnavailable("injected: budget store down")

    def compensate(self, reservation_id: str) -> bool:
        raise StoreUnavailable("injected: budget store down")

    def used(self, resource_key: str, window_seconds: int, now: object) -> int:
        raise StoreUnavailable("injected: budget store down")


class FaultInjectionTests(unittest.TestCase):
    def test_store_unavailable_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-fault-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "f.db",
                policy_path=bundled_policy_path(),
            )
            runtime.engine.budgets = UnavailableBudget()  # type: ignore[assignment]
            result = runtime.engine.authorize(
                payment_asir(amount=100, destination="fault", session_id="fault"),
                current_state=account_state(),
                idempotency_key="fault",
            )
            self.assertEqual(result.decision, Decision.DENY)
            self.assertEqual(result.reason_code, "STORE_UNAVAILABLE")
            self.assertIsNone(result.capability)

    def test_key_provider_unavailable_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-key-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "k.db",
                policy_path=bundled_policy_path(),
            )
            with patch.object(runtime.engine.codec, "issue", side_effect=RuntimeError("kms down")):
                result = runtime.engine.authorize(
                    payment_asir(amount=100, destination="kms", session_id="kms"),
                    current_state=account_state(),
                    idempotency_key="kms",
                )
            self.assertEqual(result.decision, Decision.DENY)
            self.assertEqual(result.reason_code, "KEY_PROVIDER_UNAVAILABLE")
            self.assertIsNone(result.capability)
