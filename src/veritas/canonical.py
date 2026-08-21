"""Canonical JSON for hashes and signatures.

This POC implements the interoperable subset used by its schemas: objects with string
keys, arrays, strings, booleans, null, and integers. Floating-point numbers are rejected
because their cross-language textual representation is a common source of signature drift.
The production target is full RFC 8785/JCS compatibility.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel

from veritas.errors import CanonicalizationError


def _normalise(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalise(value.model_dump(mode="json", exclude_none=True))
    if dataclasses.is_dataclass(value):
        return _normalise(dataclasses.asdict(value))
    if isinstance(value, Enum):
        return _normalise(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise CanonicalizationError("Naive datetimes are forbidden")
        utc_value = value.astimezone(timezone.utc)
        return utc_value.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CanonicalizationError("Non-finite decimals are forbidden")
        return format(value.normalize(), "f")
    if isinstance(value, float):
        raise CanonicalizationError("Floats are forbidden; use integer minor units")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalizationError("Canonical objects require string keys")
        return {key: _normalise(item) for key, item in value.items()}
    raise CanonicalizationError(f"Unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for the supported canonical subset."""

    normalised = _normalise(value)
    return json.dumps(
        normalised,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any, prefix: str = "sha256:") -> str:
    return prefix + hashlib.sha256(canonical_json(value)).hexdigest()


def pretty_json(value: Any) -> str:
    return json.dumps(_normalise(value), ensure_ascii=False, sort_keys=True, indent=2)

