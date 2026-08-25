from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from veritas.cli import EXIT_OK, EXIT_USAGE, main
from veritas.errors import PolicyError, ReservationError
from veritas.models import Decision
from veritas.policy import PolicyCompiler
from veritas.reasons import REASONS, describe_result, lookup
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import account_state, payment_asir


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMITTED_CODES = {
    "ACTION_NOT_ALLOWED",
    "ACTOR_BINDING_MISSING",
    "APPROVAL_REQUIRED",
    "ATOMIC_LIMIT_EXCEEDED",
    "B0_NO_POLICY",
    "B1_CALL_OK",
    "B1_UNBOUND_APPROVAL",
    "BUDGET_EXHAUSTED",
    "CAPABILITY_ISSUED",
    "CAPABILITY_REPLAY",
    "COMMITTED",
    "DELEGATION_DEPTH_EXCEEDED",
    "EXPIRED_CAPABILITY",
    "IDENTITY_MISSING",
    "INVALID_ACTION_ARGUMENTS",
    "INVALID_APPROVAL",
    "INVALID_CANONICAL_VALUE",
    "INVALID_CAPABILITY",
    "INVALID_POLICY",
    "POLICY_ALLOW",
    "PURPOSE_NOT_ALLOWED",
    "RESERVATION_INVALID",
    "STATE_HASH_MISMATCH",
    "STALE_CAPABILITY",
    "STORE_UNAVAILABLE",
    "TEMPORAL_INVARIANT_VIOLATION",
    "VALID_CAPABILITY_REQUIRED",
}


class ReasonCatalogTests(unittest.TestCase):
    def test_emitted_codes_are_documented(self) -> None:
        missing = EMITTED_CODES - set(REASONS)
        self.assertEqual(missing, set())

    def test_unknown_code_is_fail_closed(self) -> None:
        reason = lookup("NOT_A_REAL_CODE")
        self.assertEqual(reason.decision, "DENY")
        self.assertFalse(reason.retryable)

    def test_describe_result_has_two_audiences(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-reason-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "t.db",
                policy_path=bundled_policy_path(),
            )
            asir = payment_asir(amount=900, destination="")
            result = runtime.engine.authorize(
                asir, current_state=account_state(), idempotency_key="empty-dest"
            )
            self.assertEqual(result.decision, Decision.DENY)
            self.assertEqual(result.reason_code, "INVALID_ACTION_ARGUMENTS")
            described = describe_result(result)
            self.assertIn("operator", described)
            self.assertIn("engineer", described)
            self.assertTrue(described["aligned"])


class PolicyAndStoreErrorTests(unittest.TestCase):
    def test_missing_policy_file_is_policy_error(self) -> None:
        with self.assertRaises(PolicyError) as ctx:
            PolicyCompiler().compile_file(PROJECT_ROOT / "policies" / "does-not-exist.json")
        self.assertEqual(ctx.exception.code, "INVALID_POLICY")

    def test_invalid_json_policy_is_policy_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-policy-") as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(PolicyError):
                PolicyCompiler().compile_file(path)

    def test_unknown_reservation_has_stable_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-res-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "t.db",
                policy_path=bundled_policy_path(),
            )
            with self.assertRaises(ReservationError) as ctx:
                runtime.store.reservation_status("res:missing")
            self.assertEqual(ctx.exception.code, "RESERVATION_INVALID")
            self.assertIn("operator", ctx.exception.to_payload())


class CliTests(unittest.TestCase):
    def test_version(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main(["--version"])
        self.assertEqual(code, EXIT_OK)
        self.assertRegex(stdout.getvalue().strip(), r"^0\.\d+\.\d+")

    def test_reasons_lists_budget_exhausted(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main(["reasons"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("BUDGET_EXHAUSTED", stdout.getvalue())

    def test_reasons_explains_a_code(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main(["reasons", "BUDGET_EXHAUSTED"])
        self.assertEqual(code, EXIT_OK)
        text = stdout.getvalue()
        self.assertIn("For operators:", text)
        self.assertIn("For engineers:", text)

    def test_policy_check_missing_file_exits_nonzero(self) -> None:
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()) as stderr:
            code = main(["policy-check", str(PROJECT_ROOT / "missing-policy.json")])
        self.assertEqual(code, EXIT_USAGE)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["code"], "INVALID_POLICY")

    def test_ledger_verify_missing_file_exits_nonzero(self) -> None:
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
            code = main(["ledger-verify", str(PROJECT_ROOT / "missing.db")])
        self.assertEqual(code, EXIT_USAGE)

    def test_doctor_passes_on_a_working_install(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main(["doctor"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("healthy", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
