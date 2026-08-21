"""Deterministic VERITAS-Bench Cycle-1 attack harness."""

from __future__ import annotations

import json
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable

from veritas.adapters.local import MutableClock
from veritas.errors import ExpiredCapability, ReplayDetected, StaleCapability
from veritas.models import Decision
from veritas.policy import PolicyCompiler
from veritas.runtime import LocalRuntime, bundled_policy_path, create_local_runtime
from veritas.scenarios import (
    DEFAULT_TIME,
    account_state,
    action_asir,
    deterministic_tool,
    payment_asir,
)


@dataclass(frozen=True)
class AttackResult:
    family: str
    passed: bool
    evidence: str
    duration_ms: float


class BenchContext:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.counter = 0

    def runtime(self) -> tuple[LocalRuntime, MutableClock]:
        self.counter += 1
        clock = MutableClock(DEFAULT_TIME)
        runtime = create_local_runtime(
            database_path=self.directory / f"attack-{self.counter}.db",
            policy_path=bundled_policy_path(),
            clock=clock,
        )
        return runtime, clock


def _execute_allowed(runtime: LocalRuntime, asir: Any, result: Any) -> None:
    assert result.decision == Decision.ALLOW
    assert result.capability is not None
    runtime.boundary.execute(
        result.capability,
        asir=asir,
        current_state=account_state(),
        tool=deterministic_tool,
        trace_id=result.trace_id,
    )


def attack_atomic(ctx: BenchContext) -> str:
    runtime, clock = ctx.runtime()
    asir = payment_asir(amount=11000, destination="atomic")
    approval = runtime.approval_service.issue(
        asir, approver="human:risk-owner", now=clock.now()
    )
    result = runtime.engine.authorize(
        asir,
        current_state=account_state(),
        idempotency_key="atomic",
        approval_token=approval,
    )
    assert result.decision == Decision.DENY and result.reason_code == "BUDGET_EXHAUSTED"
    return "11,000 was denied against the 10,000 rolling budget"


def attack_fractionation(ctx: BenchContext) -> str:
    runtime, _ = ctx.runtime()
    decisions: list[Decision] = []
    for index in range(12):
        asir = payment_asir(amount=900, destination="fractionation", session_id=f"f-{index}")
        result = runtime.engine.authorize(
            asir,
            current_state=account_state(),
            idempotency_key=f"fraction-{index}",
        )
        decisions.append(result.decision)
        if result.decision == Decision.ALLOW:
            _execute_allowed(runtime, asir, result)
    assert decisions.count(Decision.ALLOW) == 11 and decisions[-1] == Decision.DENY
    return "eleven transfers passed; the twelfth fraction was denied"


def attack_temporal_evasion(ctx: BenchContext) -> str:
    runtime, clock = ctx.runtime()
    for index in range(2):
        asir = payment_asir(amount=5000, destination="temporal", session_id=f"t-{index}")
        result = runtime.engine.authorize(
            asir,
            current_state=account_state(),
            idempotency_key=f"temporal-{index}",
        )
        _execute_allowed(runtime, asir, result)
    backdated = payment_asir(
        amount=1,
        destination="temporal",
        session_id="t-backdated",
        request_ts=clock.now() - timedelta(days=365),
    )
    result = runtime.engine.authorize(
        backdated, current_state=account_state(), idempotency_key="temporal-backdated"
    )
    assert result.decision == Decision.DENY
    return "a backdated ASIR could not evade the server-side rolling window"


def attack_parallel_double_spend(ctx: BenchContext) -> str:
    runtime, clock = ctx.runtime()

    def attempt(index: int) -> Decision:
        asir = payment_asir(
            amount=300, destination="parallel", session_id=f"parallel-{index}"
        )
        return runtime.engine.authorize(
            asir,
            current_state=account_state(),
            idempotency_key=f"parallel-{index}",
        ).decision

    with ThreadPoolExecutor(max_workers=40) as pool:
        decisions = list(pool.map(attempt, range(40)))
    allowed = decisions.count(Decision.ALLOW)
    used = runtime.store.used("money:parallel:86400s", 86400, clock.now())
    assert allowed == 33 and used == 9900
    return f"40 concurrent requests produced {allowed} reservations and used={used}"


def attack_delegation_laundering(ctx: BenchContext) -> str:
    runtime, _ = ctx.runtime()
    asir = payment_asir(
        amount=100,
        destination="delegation",
        delegation=("user:alice", "broker-a", "broker-b", "finance-agent-01"),
    )
    result = runtime.engine.authorize(
        asir, current_state=account_state(), idempotency_key="delegation"
    )
    assert result.decision == Decision.DENY
    assert result.reason_code == "DELEGATION_DEPTH_EXCEEDED"
    return "a four-hop chain was denied by the compiled relational rule"


def attack_approval_mutation(ctx: BenchContext) -> str:
    runtime, clock = ctx.runtime()
    original = payment_asir(amount=6000, destination="approval")
    approval = runtime.approval_service.issue(
        original, approver="human:risk-owner", now=clock.now()
    )
    mutated = payment_asir(amount=6500, destination="approval")
    result = runtime.engine.authorize(
        mutated,
        current_state=account_state(),
        idempotency_key="approval-mutated",
        approval_token=approval,
    )
    assert result.decision == Decision.REQUIRE_APPROVAL
    assert result.reason_code == "INVALID_APPROVAL"
    return "approval over 6,000 did not authorize a mutated 6,500 ASIR"


def attack_cross_tool_composition(ctx: BenchContext) -> str:
    runtime, _ = ctx.runtime()
    read = action_asir("data.read_sensitive", session_id="composed-session")
    read_result = runtime.engine.authorize(
        read, current_state=account_state(), idempotency_key="composed-read"
    )
    _execute_allowed(runtime, read, read_result)
    send = action_asir("message.send_external", session_id="composed-session")
    send_result = runtime.engine.authorize(
        send, current_state=account_state(), idempotency_key="composed-send"
    )
    assert send_result.decision == Decision.DENY
    assert send_result.reason_code == "TEMPORAL_INVARIANT_VIOLATION"
    return "external send was denied after a sensitive read in the same session"


def attack_policy_race(ctx: BenchContext) -> str:
    runtime, _ = ctx.runtime()
    asir = payment_asir(amount=500, destination="policy-race")
    result = runtime.engine.authorize(
        asir, current_state=account_state(), idempotency_key="policy-race"
    )
    assert result.capability is not None
    v2 = PolicyCompiler().compile_file(bundled_policy_path("payment_policy_v2.json"))
    runtime.policies.publish(v2)
    try:
        runtime.boundary.execute(
            result.capability,
            asir=asir,
            current_state=account_state(),
            tool=deterministic_tool,
            trace_id=result.trace_id,
        )
    except StaleCapability:
        return "a v1 capability became stale immediately after v2 publication"
    raise AssertionError("stale capability was accepted")


def attack_clock_skew(ctx: BenchContext) -> str:
    runtime, clock = ctx.runtime()
    asir = payment_asir(amount=100, destination="clock")
    result = runtime.engine.authorize(
        asir,
        current_state=account_state(),
        idempotency_key="clock",
        ttl_seconds=1,
    )
    assert result.capability is not None
    clock.set(clock.now() + timedelta(seconds=5))
    try:
        runtime.boundary.execute(
            result.capability,
            asir=asir,
            current_state=account_state(),
            tool=deterministic_tool,
            trace_id=result.trace_id,
        )
    except ExpiredCapability:
        return "a capability outside TTL plus delta was denied"
    raise AssertionError("expired capability was accepted")


def attack_capability_replay(ctx: BenchContext) -> str:
    runtime, _ = ctx.runtime()
    asir = payment_asir(amount=100, destination="replay")
    result = runtime.engine.authorize(
        asir, current_state=account_state(), idempotency_key="replay"
    )
    assert result.capability is not None
    _execute_allowed(runtime, asir, result)
    try:
        runtime.boundary.execute(
            result.capability,
            asir=asir,
            current_state=account_state(),
            tool=deterministic_tool,
            trace_id=result.trace_id,
        )
    except ReplayDetected:
        return "the second use of the same nonce was denied"
    raise AssertionError("replayed capability was accepted")


def attack_compensation_abuse(ctx: BenchContext) -> str:
    runtime, clock = ctx.runtime()
    asir = payment_asir(amount=500, destination="compensation")
    result = runtime.engine.authorize(
        asir, current_state=account_state(), idempotency_key="compensation"
    )
    assert result.capability is not None
    claims = runtime.capability_codec.decode_and_verify(result.capability)
    assert claims.reservation_id is not None
    first = runtime.engine.compensate(
        claims.reservation_id, trace_id=result.trace_id, reason="confirmed non-execution"
    )
    second = runtime.engine.compensate(
        claims.reservation_id, trace_id=result.trace_id, reason="malicious duplicate"
    )
    used = runtime.store.used("money:compensation:86400s", 86400, clock.now())
    assert first is True and second is False and used == 0
    return "duplicate compensation was idempotent and restored no extra budget"


ATTACKS: tuple[tuple[str, Callable[[BenchContext], str]], ...] = (
    ("atomic", attack_atomic),
    ("fractionation", attack_fractionation),
    ("temporal_evasion", attack_temporal_evasion),
    ("parallel_double_spend", attack_parallel_double_spend),
    ("delegation_laundering", attack_delegation_laundering),
    ("approval_mutation", attack_approval_mutation),
    ("cross_tool_composition", attack_cross_tool_composition),
    ("policy_race", attack_policy_race),
    ("clock_skew", attack_clock_skew),
    ("capability_replay", attack_capability_replay),
    ("compensation_abuse", attack_compensation_abuse),
)


def run_bench() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="veritas-bench-") as directory:
        context = BenchContext(Path(directory))
        results: list[AttackResult] = []
        for name, attack in ATTACKS:
            started = time.perf_counter_ns()
            try:
                evidence = attack(context)
                passed = True
            except Exception as exc:
                evidence = f"{type(exc).__name__}: {exc}"
                passed = False
            elapsed = (time.perf_counter_ns() - started) / 1_000_000
            results.append(AttackResult(name, passed, evidence, elapsed))

    durations = [item.duration_ms for item in results]
    sorted_durations = sorted(durations)
    percentile = lambda p: sorted_durations[min(len(sorted_durations) - 1, int(p * len(sorted_durations)))]
    passed_count = sum(result.passed for result in results)
    return {
        "benchmark": "VERITAS-Bench Cycle 1",
        "seed": "deterministic-scenarios-v1",
        "families_total": len(results),
        "families_passed": passed_count,
        "security_rate": passed_count / len(results),
        "duration_ms": {
            "mean": round(statistics.fmean(durations), 3),
            "p50": round(statistics.median(durations), 3),
            "p95": round(percentile(0.95), 3),
        },
        "baselines": {
            "no_protection": "accepts all 11 attack families by construction",
            "unit_call_filter": (
                "blocks atomic overspend but accepts fractionation, concurrency, replay, "
                "policy race, approval mutation, and cross-tool composition"
            ),
        },
        "results": [
            {
                "family": result.family,
                "passed": result.passed,
                "evidence": result.evidence,
                "duration_ms": round(result.duration_ms, 3),
            }
            for result in results
        ],
    }


def print_bench() -> None:
    print(json.dumps(run_bench(), indent=2, sort_keys=True))
