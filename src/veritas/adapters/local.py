"""Dependency-free local infrastructure adapters."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class MutableClock:
    """Deterministic clock used by tests and benchmarks."""

    def __init__(self, current: datetime) -> None:
        if current.tzinfo is None:
            raise ValueError("clock requires a timezone-aware datetime")
        self._current = current
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            return self._current

    def set(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("clock requires a timezone-aware datetime")
        with self._lock:
            self._current = value


class JsonTelemetry:
    """Small structured-logging adapter; replace with OTel in deployment."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("veritas.telemetry")

    def record(self, event: str, attributes: dict[str, Any]) -> None:
        self._logger.info(json.dumps({"event": event, **attributes}, sort_keys=True))


class InMemoryTelemetry:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def record(self, event: str, attributes: dict[str, Any]) -> None:
        with self._lock:
            self.events.append({"event": event, **attributes})

