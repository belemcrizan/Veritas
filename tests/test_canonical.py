from __future__ import annotations

import unittest

from veritas.canonical import canonical_json, digest
from veritas.errors import CanonicalizationError


class CanonicalJsonTests(unittest.TestCase):
    def test_object_order_does_not_change_hash(self) -> None:
        left = {"b": 2, "a": {"z": True, "x": 1}}
        right = {"a": {"x": 1, "z": True}, "b": 2}
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(digest(left), digest(right))

    def test_floats_are_rejected(self) -> None:
        with self.assertRaises(CanonicalizationError):
            canonical_json({"amount": 0.1})


if __name__ == "__main__":
    unittest.main()

