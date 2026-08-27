"""One-command modeled-protection showcase. Not a security certification."""

from __future__ import annotations

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from veritas.errors import InvalidApproval, ReplayDetected, StaleCapability
from veritas.guarded import GuardedTool
from veritas.models import Decision
from veritas.policy import PolicyCompiler
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import (
    DEFAULT_TIME,
    account_state,
    action_asir,
    deterministic_tool,
    payment_asir,
)


def _pass(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": ok, "detail": detail}


def _trajectory_budget(directory: Path) -> dict[str, Any]:
    runtime = create_local_runtime(
        database_path=directory / "budget.db", policy_path=bundled_policy_path()
    )
    decisions: list[str] = []
    for index in range(1, 13):
        asir = payment_asir(amount=900, destination="showcase-budget", session_id=f"tb-{index}")
        result = runtime.engine.authorize(
            asir, current_state=account_state(), idempotency_key=f"tb-{index}"
        )
        decisions.append(result.decision.value)
        if result.decision is Decision.ALLOW and result.capability:
            runtime.boundary.execute(
                result.capability,
                asir=asir,
                current_state=account_state(),
                tool=deterministic_tool,
                trace_id=result.trace_id,
            )
    ok = decisions.count("ALLOW") == 11 and decisions[-1] == "DENY"
    return _pass(
        "trajectory budget", ok, f"ALLOW x {decisions.count('ALLOW')}, 12th {decisions[-1]}"
    )


def _concurrent_reservation(directory: Path) -> dict[str, Any]:
    runtime = create_local_runtime(
        database_path=directory / "conc.db", policy_path=bundled_policy_path()
    )
    for index in range(10):
        asir = payment_asir(amount=910, destination="showcase-race", session_id=f"fill-{index}")
        result = runtime.engine.authorize(
            asir, current_state=account_state(), idempotency_key=f"fill-{index}"
        )
        if result.decision is Decision.ALLOW and result.capability:
            runtime.boundary.execute(
                result.capability,
                asir=asir,
                current_state=account_state(),
                tool=deterministic_tool,
                trace_id=result.trace_id,
            )

    def attempt(agent: str) -> str:
        asir = payment_asir(amount=900, destination="showcase-race", session_id=agent)
        return runtime.engine.authorize(
            asir, current_state=account_state(), idempotency_key=f"race-{agent}"
        ).decision.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, ("A", "B")))
    used = runtime.store.used("money:showcase-race:86400s", 86400, runtime.clock.now())
    ok = outcomes.count("ALLOW") == 1 and outcomes.count("DENY") == 1 and used <= 10000
    return _pass(
        "concurrent reservation",
        ok,
        f"outcomes={outcomes} used={used}",
    )


def _approval_binding(directory: Path) -> dict[str, Any]:
    runtime = create_local_runtime(
        database_path=directory / "appr.db", policy_path=bundled_policy_path()
    )
    approved = payment_asir(amount=900, destination="showcase-appr", session_id="appr-900")
    mutated = payment_asir(amount=9000, destination="showcase-appr", session_id="appr-900")
    token = runtime.approval_service.issue(approved, approver="human:risk-owner", now=DEFAULT_TIME)
    try:
        runtime.approval_service.verify(token, mutated, now=DEFAULT_TIME)
        ok = False
        detail = "mutated ASIR was accepted"
    except InvalidApproval:
        result = runtime.engine.authorize(
            mutated,
            current_state=account_state(),
            idempotency_key="appr-mut",
            approval_token=token,
        )
        ok = result.reason_code == "INVALID_APPROVAL"
        detail = result.reason_code
    return _pass("approval binding", ok, detail)


def _cross_tool(directory: Path) -> dict[str, Any]:
    runtime = create_local_runtime(
        database_path=directory / "cross.db", policy_path=bundled_policy_path()
    )
    tool = GuardedTool(runtime.boundary, deterministic_tool)
    read = action_asir("data.read_sensitive", session_id="cross")
    send = action_asir("message.send_external", session_id="cross")
    first = runtime.engine.authorize(read, current_state={}, idempotency_key="cross-read")
    if first.decision is Decision.ALLOW and first.capability:
        tool.invoke(read, capability=first.capability, current_state={}, trace_id=first.trace_id)
    second = runtime.engine.authorize(send, current_state={}, idempotency_key="cross-send")
    ok = first.decision is Decision.ALLOW and second.decision is Decision.DENY
    return _pass(
        "cross-tool invariant",
        ok,
        f"read={first.decision.value} send={second.decision.value} {second.reason_code}",
    )


def _replay(directory: Path) -> dict[str, Any]:
    runtime = create_local_runtime(
        database_path=directory / "replay.db", policy_path=bundled_policy_path()
    )
    asir = payment_asir(amount=100, destination="showcase-replay", session_id="replay")
    result = runtime.engine.authorize(asir, current_state=account_state(), idempotency_key="rp")
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
        ok = False
        detail = "replay succeeded"
    except ReplayDetected as exc:
        ok = exc.code == "CAPABILITY_REPLAY"
        detail = exc.code
    return _pass("replay protection", ok, detail)


def _policy_freshness(directory: Path) -> dict[str, Any]:
    runtime = create_local_runtime(
        database_path=directory / "stale.db", policy_path=bundled_policy_path()
    )
    asir = payment_asir(amount=100, destination="showcase-stale", session_id="stale")
    result = runtime.engine.authorize(asir, current_state=account_state(), idempotency_key="stale")
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
        ok = False
        detail = "stale capability executed"
    except StaleCapability as exc:
        ok = exc.code == "STALE_CAPABILITY"
        detail = exc.code
    return _pass("policy freshness", ok, detail)


def run_showcase() -> dict[str, Any]:
    checks: list[dict[str, Any]]
    with tempfile.TemporaryDirectory(prefix="veritas-showcase-") as directory:
        root = Path(directory)
        checks = [
            _trajectory_budget(root),
            _concurrent_reservation(root),
            _approval_binding(root),
            _cross_tool(root),
            _replay(root),
            _policy_freshness(root),
        ]
    passed = sum(1 for item in checks if item["passed"])
    return {
        "title": "VERITAS SHOWCASE",
        "passed": passed,
        "total": len(checks),
        "checks": checks,
        "claim": f"{passed}/{len(checks)} modeled protections demonstrated.",
        "not_claimed": "This is not a 100% secure or production-readiness result.",
    }


def format_showcase(report: dict[str, Any]) -> str:
    lines = [report["title"], ""]
    for item in report["checks"]:
        mark = "PASS" if item["passed"] else "FAIL"
        lines.append(f"[{mark}] {item['name']}")
    lines.append("")
    lines.append(report["claim"])
    lines.append(report["not_claimed"])
    return "\n".join(lines)


def print_showcase(*, as_json: bool = False) -> int:
    report = run_showcase()
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_showcase(report))
    return 0 if report["passed"] == report["total"] else 1
