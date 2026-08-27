"""Key provider abstraction. Local development keys are not a production architecture.

AWS KMS, Azure Key Vault, GCP KMS, and HashiCorp Vault adapters are intentionally absent
until real credentials and contract tests exist. Do not treat this module as cloud validation.
"""

from __future__ import annotations

from typing import Protocol

from veritas.crypto import Ed25519Verifier, LocalEd25519Signer


class KeyProvider(Protocol):
    @property
    def kid(self) -> str: ...

    def sign(self, payload: bytes) -> bytes: ...

    def verify(self, payload: bytes, signature: bytes) -> None: ...


class LocalKeyProvider:
    """Reference provider for tests and the local runtime. Not a KMS."""

    def __init__(self, signer: LocalEd25519Signer) -> None:
        self._signer = signer

    @classmethod
    def from_seed(cls, seed: str, kid: str) -> LocalKeyProvider:
        return cls(LocalEd25519Signer.from_seed(seed, kid=kid))

    @property
    def kid(self) -> str:
        return self._signer.kid

    def sign(self, payload: bytes) -> bytes:
        return self._signer.sign(payload)

    def verify(self, payload: bytes, signature: bytes) -> None:
        self._signer.verify(payload, signature)

    def public_verifier(self) -> Ed25519Verifier:
        return self._signer.public_verifier()
