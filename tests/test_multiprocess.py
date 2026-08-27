from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from veritas.adapters.sqlite import SQLiteAdapter
from veritas.lab import _reserve_worker
from veritas.scenarios import DEFAULT_TIME


class MultiprocessReservationTests(unittest.TestCase):
    def test_two_processes_do_not_overspend(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-mp-") as directory:
            path = str(Path(directory) / "mp.db")
            store = SQLiteAdapter(path)
            key = "money:mp:86400s"
            with ProcessPoolExecutor(max_workers=2) as pool:
                outcomes = list(
                    pool.map(_reserve_worker, [(path, key, index) for index in range(16)])
                )
            used = store.used(key, 86400, DEFAULT_TIME)
            self.assertLessEqual(used, 10000)
            self.assertEqual(len(outcomes), 16)
            self.assertIn("DENY", outcomes)
            self.assertIn("ALLOW", outcomes)
