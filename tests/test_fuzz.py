from __future__ import annotations

import unittest

from veritas.canonical import canonical_json
from veritas.crypto import CapabilityCodec, LocalEd25519Signer
from veritas.errors import CanonicalizationError, InvalidCapability, PolicyError
from veritas.policy import PolicyCompiler


class FuzzTests(unittest.TestCase):
    def test_malformed_policy_never_compiles_to_runtime_allow_table(self) -> None:
        compiler = PolicyCompiler()
        for raw in ({}, {"version": 1}, {"version": "v", "actions": []}):
            with self.assertRaises(PolicyError):
                compiler.compile(raw)  # type: ignore[arg-type]

    def test_malformed_capability_never_verifies(self) -> None:
        codec = CapabilityCodec(LocalEd25519Signer.from_seed("fuzz", kid="fuzz"))
        for token in ("", "veritas.v1.a.b.c.d", "....", "veritas.v1.@@@.@@@", "tampered"):
            with self.assertRaises(InvalidCapability):
                codec.decode_and_verify(token)

    def test_malformed_canonical_input_is_rejected(self) -> None:
        with self.assertRaises(CanonicalizationError):
            canonical_json({"amount": 1.5})
        with self.assertRaises(CanonicalizationError):
            canonical_json({1: "bad-key"})  # type: ignore[dict-item]
