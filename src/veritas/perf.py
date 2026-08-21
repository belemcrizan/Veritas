"""Focused local microbenchmarks for RNF01 and RNF02."""

from __future__ import annotations

import json
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from veritas.adapters.local import MutableClock
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import DEFAULT_TIME, account_state, payment_asir


def _measure(operation: Callable[[], Any], iterations: int) -> dict[str, float]:
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        operation()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    ordered = sorted(samples)

    def p(fraction: float) -> float:
        index = min(len(ordered) - 1, int(fraction * len(ordered)))
        return ordered[index]

    return {
        "iterations": float(iterations),
        "mean_ms": round(statistics.fmean(samples), 6),
        "p50_ms": round(statistics.median(samples), 6),
        "p95_ms": round(p(0.95), 6),
        "p99_ms": round(p(0.99), 6),
    }


def run_perf(iterations: int = 1000) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="veritas-perf-") as directory:
        runtime = create_local_runtime(
            database_path=Path(directory) / "perf.db",
            policy_path=bundled_policy_path(),
            clock=MutableClock(DEFAULT_TIME),
        )
        asir = payment_asir(amount=100, destination="perf")
        policy = runtime.policies.current()
        policy_metrics = _measure(
            lambda: runtime.engine.verifier.evaluate(asir, policy), iterations
        )
        token, _ = runtime.capability_codec.issue(
            reservation_id="res:perf",
            chain_index=0,
            parent_cap=None,
            asir_hash=asir.hash,
            state_hash="state:sha256:perf",
            residual={"money:perf:86400s": 9900},
            policy_version=policy.version,
            policy_digest=policy.digest,
            now=runtime.clock.now(),
            ttl_seconds=30,
        )
        verification_metrics = _measure(
            lambda: runtime.capability_codec.decode_and_verify(token), iterations
        )
    return {
        "scope": "in-process runtime table and cryptographic envelope only; excludes SQLite and tool",
        "policy_lookup": policy_metrics,
        "offline_signature_verification": verification_metrics,
        "targets_ms": {"policy_p95": 5.0, "verification_p95": 1.0},
        "target_met": {
            "policy_p95": policy_metrics["p95_ms"] < 5.0,
            "verification_p95": verification_metrics["p95_ms"] < 1.0,
        },
    }


def print_perf(iterations: int = 1000) -> None:
    print(json.dumps(run_perf(iterations), indent=2, sort_keys=True))
