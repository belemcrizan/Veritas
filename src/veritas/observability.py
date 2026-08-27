"""Local metrics. OpenTelemetry is optional and never receives raw secrets."""

from __future__ import annotations

import threading
from typing import Any

from veritas.adapters.local import InMemoryTelemetry

_REDACT_KEYS = frozenset(
    {
        "capability",
        "approval_token",
        "signature",
        "nonce",
        "token",
        "secret",
        "key",
        "password",
        "private_key",
        "privatekey",
        "pii",
        "raw_pii",
        "email",
    }
)


def redact(attributes: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        lowered = key.lower()
        if (
            lowered in _REDACT_KEYS
            or "token" in lowered
            or "secret" in lowered
            or "password" in lowered
            or "private" in lowered
        ):
            cleaned[key] = "[redacted]"
        else:
            cleaned[key] = value
    return cleaned


class MetricsTelemetry(InMemoryTelemetry):
    def __init__(self) -> None:
        super().__init__()
        self.counters: dict[str, int] = {}
        self._counter_lock = threading.Lock()

    def record(self, event: str, attributes: dict[str, Any]) -> None:
        safe = redact(attributes)
        super().record(event, safe)
        decision = str(safe.get("decision", ""))
        reason = str(safe.get("reason_code", ""))
        self._bump("events_total")
        self._bump(f"event.{event}")
        if decision:
            self._bump(f"decision.{decision}")
        if reason:
            self._bump(f"reason.{reason}")
        if event == "verifier.decision":
            self._bump("authorizations_total")
            if decision == "ALLOW":
                self._bump("allows_total")
            elif decision == "DENY":
                self._bump("denials_total")
            elif decision == "REQUIRE_APPROVAL":
                self._bump("approvals_total")
        if reason == "STALE_CAPABILITY":
            self._bump("stale_capabilities_total")
        if reason == "CAPABILITY_REPLAY":
            self._bump("replays_total")
        if reason == "BUDGET_EXHAUSTED":
            self._bump("reservation_conflicts_total")
        if event == "reconcile":
            self._bump("reconciliations_total")

    def _bump(self, name: str) -> None:
        with self._counter_lock:
            self.counters[name] = self.counters.get(name, 0) + 1

    def prometheus_text(self) -> str:
        lines = ["# VERITAS local counters. Not a production metric API."]
        mapping = {
            "authorizations_total": "veritas_authorizations_total",
            "denials_total": "veritas_denials_total",
            "approvals_total": "veritas_approvals_total",
            "replays_total": "veritas_replays_denied_total",
            "stale_capabilities_total": "veritas_stale_total",
            "reconciliations_total": "veritas_reconciliations_total",
            "reservation_conflicts_total": "veritas_reservation_conflicts_total",
        }
        with self._counter_lock:
            for internal, exported in mapping.items():
                lines.append(f"{exported} {self.counters.get(internal, 0)}")
        return "\n".join(lines) + "\n"
