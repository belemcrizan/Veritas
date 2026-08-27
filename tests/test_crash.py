from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from veritas.adapters.sqlite import SQLiteAdapter
from veritas.scenarios import DEFAULT_TIME

WORKER = r"""
import os, sys
from pathlib import Path
from veritas.adapters.sqlite import SQLiteAdapter
from veritas.scenarios import DEFAULT_TIME

path = sys.argv[1]
store = SQLiteAdapter(path)
store.reserve(
    resource_key="money:crash:86400s",
    policy_version="v1",
    limit=10000,
    amount=900,
    window_seconds=86400,
    now=DEFAULT_TIME,
    idempotency_key="crash-1",
    agent_id="agent",
)
os._exit(1)
"""


class CrashConsistencyTests(unittest.TestCase):
    def test_prepared_reservation_survives_kill(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-crash-") as directory:
            path = str(Path(directory) / "crash.db")
            SQLiteAdapter(path)
            completed = subprocess.run(
                [sys.executable, "-c", WORKER, path],
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            store = SQLiteAdapter(path)
            used = store.used("money:crash:86400s", 86400, DEFAULT_TIME)
            self.assertEqual(used, 900)
