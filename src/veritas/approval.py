"""WYSIWYS human approvals signed over the canonical ASIR hash."""

from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature

from veritas.canonical import canonical_json, digest, pretty_json
from veritas.errors import InvalidApproval
from veritas.models import ASIR


def render_for_approval(asir: ASIR) -> str:
    """The exact deterministic representation a reviewer must see."""

    return pretty_json(asir)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class ApprovalService:
    prefix = "veritas-approval.v1"

    def __init__(self, signer: Any) -> None:
        self._signer = signer

    def issue(
        self,
        asir: ASIR,
        *,
        approver: str,
        now: datetime,
        ttl_seconds: int = 120,
    ) -> str:
        claims = {
            "asir_hash": asir.hash,
            "rendered_hash": digest(render_for_approval(asir)),
            "approver": approver,
            "nonce": secrets.token_urlsafe(16),
            "issued_at": now,
            "expires_at": now + timedelta(seconds=ttl_seconds),
            "issuer_kid": self._signer.kid,
        }
        payload = canonical_json(claims)
        return f"{self.prefix}.{_encode(payload)}.{_encode(self._signer.sign(payload))}"

    def verify(self, token: str, asir: ASIR, *, now: datetime) -> dict[str, Any]:
        try:
            name, version, payload_part, signature_part = token.split(".")
            if f"{name}.{version}" != self.prefix:
                raise InvalidApproval("unsupported approval format")
            payload = _decode(payload_part)
            self._signer.verify(payload, _decode(signature_part))
            claims = json.loads(payload.decode("utf-8"))
            if claims["asir_hash"] != asir.hash:
                raise InvalidApproval("approval is bound to a different ASIR")
            if claims["rendered_hash"] != digest(render_for_approval(asir)):
                raise InvalidApproval("displayed action does not match the ASIR")
            expires = datetime.fromisoformat(claims["expires_at"].replace("Z", "+00:00"))
            if now > expires:
                raise InvalidApproval("approval has expired")
            return claims
        except InvalidApproval:
            raise
        except (ValueError, KeyError, json.JSONDecodeError, InvalidSignature) as exc:
            raise InvalidApproval("approval validation failed") from exc

