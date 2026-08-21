"""Local Ed25519 signer plus compact signed envelopes for capabilities."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from veritas.canonical import canonical_json, digest
from veritas.errors import InvalidCapability
from veritas.models import CapabilityClaims, Certificate


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class LocalEd25519Signer:
    """Development signer. Production adapters should delegate signing to KMS/HSM."""

    def __init__(self, private_key: Ed25519PrivateKey, kid: str) -> None:
        self._private_key = private_key
        self._public_key = private_key.public_key()
        self._kid = kid

    @classmethod
    def from_seed(cls, seed: str, kid: str = "local-dev-2026-08") -> "LocalEd25519Signer":
        material = hashlib.sha256(seed.encode("utf-8")).digest()
        return cls(Ed25519PrivateKey.from_private_bytes(material), kid)

    @property
    def kid(self) -> str:
        return self._kid

    def sign(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload)

    def verify(self, payload: bytes, signature: bytes) -> None:
        self._public_key.verify(signature, payload)

    def public_verifier(self) -> "Ed25519Verifier":
        return Ed25519Verifier(self._public_key, self._kid)


class Ed25519Verifier:
    def __init__(self, public_key: Ed25519PublicKey, kid: str) -> None:
        self._public_key = public_key
        self._kid = kid

    @property
    def kid(self) -> str:
        return self._kid

    def sign(self, payload: bytes) -> bytes:
        raise RuntimeError("public verifier cannot sign")

    def verify(self, payload: bytes, signature: bytes) -> None:
        self._public_key.verify(signature, payload)


class CapabilityCodec:
    """Sign and verify the POC envelope.

    Format: ``veritas.v1.<canonical-payload>.<ed25519-signature>`` (base64url). This is not
    represented as PASETO. The PASETO v4.public adapter is an explicit production backlog item.
    """

    prefix = "veritas.v1"

    def __init__(self, signer: Any) -> None:
        self._signer = signer

    @property
    def kid(self) -> str:
        return str(self._signer.kid)

    def issue(
        self,
        *,
        reservation_id: str | None,
        chain_index: int,
        parent_cap: str | None,
        asir_hash: str,
        state_hash: str,
        residual: dict[str, int],
        policy_version: str,
        policy_digest: str,
        now: datetime,
        ttl_seconds: int,
    ) -> tuple[str, CapabilityClaims]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        certificate = Certificate(
            claim=f"scope subset allow({policy_version})",
            proof_digest=policy_digest,
        )
        if len(canonical_json(certificate)) >= 1024:
            raise ValueError("certificate exceeds the 1 KB target")
        unsigned: dict[str, Any] = {
            "reservation_id": reservation_id,
            "chain_index": chain_index,
            "parent_cap": parent_cap,
            "asir_hash": asir_hash,
            "state_hash": state_hash,
            "residual": residual,
            "policy_version": policy_version,
            "policy_digest": policy_digest,
            "issued_at": now,
            "expires_at": now + timedelta(seconds=ttl_seconds),
            "nonce": secrets.token_urlsafe(18),
            "issuer_kid": self._signer.kid,
            "certificate": certificate,
        }
        cap_id = digest(unsigned, prefix="cap:sha256:")
        claims = CapabilityClaims(cap_id=cap_id, **unsigned)
        payload = canonical_json(claims)
        signature = self._signer.sign(payload)
        return f"{self.prefix}.{_b64e(payload)}.{_b64e(signature)}", claims

    def decode_and_verify(self, token: str) -> CapabilityClaims:
        try:
            prefix, version, payload_part, signature_part = token.split(".")
            if f"{prefix}.{version}" != self.prefix:
                raise InvalidCapability("unsupported capability format")
            payload = _b64d(payload_part)
            signature = _b64d(signature_part)
            self._signer.verify(payload, signature)
            raw = json.loads(payload.decode("utf-8"))
            claims = CapabilityClaims.model_validate(raw)
            unsigned = claims.model_dump(mode="python", exclude={"cap_id"}, exclude_none=False)
            expected = digest(unsigned, prefix="cap:sha256:")
            if expected != claims.cap_id:
                raise InvalidCapability("capability content id mismatch")
            if canonical_json(claims) != payload:
                raise InvalidCapability("payload is not canonical")
            return claims
        except InvalidCapability:
            raise
        except (ValueError, KeyError, json.JSONDecodeError, InvalidSignature) as exc:
            raise InvalidCapability("signature or envelope validation failed") from exc
