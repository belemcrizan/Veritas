"""Cycle-2 attack families. The original 11 Cycle-1 families stay in bench.py."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from veritas.bench import BenchContext
from veritas.errors import InvalidCapability, ReplayDetected
from veritas.identity import TrustedInputIdentityVerifier
from veritas.lifecycle import ExecutionPhase, InvalidLifecycleTransition, transition
from veritas.models import Decision, Principal
from veritas.reconcile import ProbeResult
from veritas.scenarios import account_state, action_asir, deterministic_tool, payment_asir


def attack_identity_forgery(ctx: BenchContext) -> str:
    verifier = TrustedInputIdentityVerifier(allowed_issuers=frozenset({"https://idp.example"}))
    asir = payment_asir(amount=100, destination="id-forge", session_id="id-forge")
    forged = asir.model_copy(
        update={
            "principal": Principal(sub="user:alice", iss="https://evil.example", act=asir.principal.act)
        }
    )
    decision = verifier.verify(forged)
    assert not decision.allowed
    return "forged issuer is rejected by the structural verifier"


def attack_delegation_cycle(ctx: BenchContext) -> str:
    runtime, _clock = ctx.runtime()
    asir = payment_asir(
        amount=100,
        destination="del-cycle",
        session_id="del-cycle",
        delegation=("user:alice", "finance-agent-01", "user:alice", "finance-agent-01"),
    )
    result = runtime.engine.authorize(asir, current_state=account_state(), idempotency_key="del-cycle")
    assert result.reason_code == "DELEGATION_CYCLE"
    return "delegation cycle denied"


def attack_nonce_reuse_race(ctx: BenchContext) -> str:
    runtime, _clock = ctx.runtime()
    asir = payment_asir(amount=100, destination="nonce-race", session_id="nonce-race")
    result = runtime.engine.authorize(asir, current_state=account_state(), idempotency_key="nonce-race")
    assert result.capability is not None
    runtime.boundary.execute(
        result.capability,
        asir=asir,
        current_state=account_state(),
        tool=deterministic_tool,
        trace_id=result.trace_id,
    )
    try:
        runtime.boundary.execute(
            result.capability,
            asir=asir,
            current_state=account_state(),
            tool=deterministic_tool,
            trace_id=result.trace_id,
        )
    except ReplayDetected:
        return "second consume of the same nonce failed"
    raise AssertionError("nonce reused")


def attack_duplicate_commit(ctx: BenchContext) -> str:
    runtime, clock = ctx.runtime()
    asir = payment_asir(amount=100, destination="dup-commit", session_id="dup-commit")
    result = runtime.engine.authorize(asir, current_state=account_state(), idempotency_key="dup-commit")
    assert result.capability is not None
    runtime.boundary.execute(
        result.capability,
        asir=asir,
        current_state=account_state(),
        tool=deterministic_tool,
        trace_id=result.trace_id,
    )
    claims = runtime.capability_codec.decode_and_verify(result.capability)
    assert claims.reservation_id is not None
    runtime.store.commit(claims.reservation_id)
    used = runtime.store.used("money:dup-commit:86400s", 86400, clock.now())
    assert used == 100
    return "duplicate commit did not double-count"


def attack_malformed_capability(ctx: BenchContext) -> str:
    runtime, _clock = ctx.runtime()
    asir = payment_asir(amount=100, destination="malformed", session_id="malformed")
    try:
        runtime.boundary.execute(
            "not-a-capability",
            asir=asir,
            current_state=account_state(),
            tool=deterministic_tool,
            trace_id="t-malformed",
        )
    except InvalidCapability:
        return "malformed capability is not ALLOW"
    raise AssertionError("malformed capability executed")


def attack_direct_boundary_bypass(ctx: BenchContext) -> str:
    from veritas.errors import MissingCapability
    from veritas.guarded import GuardedTool

    runtime, _clock = ctx.runtime()
    tool = GuardedTool(runtime.boundary, deterministic_tool)
    asir = payment_asir(amount=100, destination="bypass", session_id="bypass")
    try:
        tool.invoke(asir, capability=None, current_state=account_state(), trace_id="bypass")
    except MissingCapability:
        return "unguarded invoke without capability is denied"
    raise AssertionError("bypass succeeded")


def attack_forbidden_lifecycle(ctx: BenchContext) -> str:
    del ctx
    try:
        transition(ExecutionPhase.REQUESTED, ExecutionPhase.COMMITTED)
    except InvalidLifecycleTransition:
        return "REQUESTED → COMMITTED is impossible"
    raise AssertionError("illegal transition accepted")


def attack_timeout_after_execution(ctx: BenchContext) -> str:
    runtime, _clock = ctx.runtime()
    asir = payment_asir(amount=100, destination="unk", session_id="unk")
    result = runtime.engine.authorize(asir, current_state=account_state(), idempotency_key="unk")
    recon = runtime.reconciler.reconcile(
        reservation_id=None,
        trace_id=result.trace_id,
        probe=lambda: ProbeResult.CONFIRMED_EXECUTED,
    )
    assert recon.committed is True
    recon2 = runtime.reconciler.reconcile(
        reservation_id=None,
        trace_id=result.trace_id,
        probe=lambda: ProbeResult.CONFIRMED_EXECUTED,
    )
    assert recon2.committed is True
    return "duplicate reconciliation of CONFIRMED_EXECUTED stays committed"


def attack_ledger_mutation(ctx: BenchContext) -> str:
    runtime, clock = ctx.runtime()
    runtime.store.append(trace_id="mut", node_type="ASIR", payload={"x": 1}, now=clock.now())
    assert runtime.store.verify_integrity()
    with runtime.store._connect() as connection:
        connection.execute("UPDATE ledger_nodes SET payload_json = '{\"x\":9}'")
    assert not runtime.store.verify_integrity()
    return "payload mutation is detected"


def attack_cross_tool_export(ctx: BenchContext) -> str:
    runtime, _clock = ctx.runtime()
    read = action_asir("data.read_sensitive", session_id="exfil")
    first = runtime.engine.authorize(read, current_state={}, idempotency_key="exfil-read")
    assert first.decision is Decision.ALLOW
    assert first.capability is not None
    runtime.boundary.execute(
        first.capability,
        asir=read,
        current_state={},
        tool=deterministic_tool,
        trace_id=first.trace_id,
    )
    second = runtime.engine.authorize(
        action_asir("message.send_external", session_id="exfil"),
        current_state={},
        idempotency_key="exfil-send",
    )
    assert second.decision is Decision.DENY
    return "PII-then-external remains denied after the read executes"


CYCLE2_ATTACKS: tuple[tuple[str, Callable[[BenchContext], str]], ...] = (
    ("identity_forgery", attack_identity_forgery),
    ("delegation_cycle", attack_delegation_cycle),
    ("nonce_reuse_race", attack_nonce_reuse_race),
    ("duplicate_commit", attack_duplicate_commit),
    ("malformed_capability", attack_malformed_capability),
    ("direct_boundary_bypass", attack_direct_boundary_bypass),
    ("forbidden_lifecycle", attack_forbidden_lifecycle),
    ("timeout_after_execution", attack_timeout_after_execution),
    ("ledger_mutation", attack_ledger_mutation),
    ("cross_tool_export", attack_cross_tool_export),
)


def run_cycle2_attacks() -> dict[str, Any]:
    import tempfile
    import time
    from pathlib import Path

    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="veritas-c2-") as directory:
        ctx = BenchContext(Path(directory))
        for name, attack in CYCLE2_ATTACKS:
            started = time.perf_counter()
            try:
                evidence = attack(ctx)
                passed = True
            except Exception as exc:
                evidence = f"{type(exc).__name__}: {exc}"
                passed = False
            rows.append(
                {
                    "family": name,
                    "passed": passed,
                    "evidence": evidence,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
    return {
        "benchmark": "VERITAS-Bench Cycle 2 additions",
        "note": "Cycle-1 ATTACKS tuple is unchanged",
        "families_total": len(rows),
        "families_passed": sum(1 for row in rows if row["passed"]),
        "results": rows,
    }
