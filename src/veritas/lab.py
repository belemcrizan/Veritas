"""Experimental lab: tests stay in unittest; this module measures and exports."""

from __future__ import annotations

import csv
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from veritas import __version__
from veritas.ablation import run_ablations
from veritas.adapters.postgres import postgres_available
from veritas.adapters.redis_nonce import redis_available
from veritas.agents import run_agent_bench
from veritas.baselines_ext import run_baseline_comparison
from veritas.bench import run_bench
from veritas.bench_cycle2 import run_cycle2_attacks
from veritas.errors import BudgetDenied
from veritas.science import AutonomyCost, FeasibleDenial, sensitivity
from veritas.workloads import run_all_workloads

RESULTS_SCHEMA = 1


def _manifest(scenario: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    commit = "unknown"
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        pass
    payload = {
        "schema_version": RESULTS_SCHEMA,
        "git_commit": commit,
        "veritas_version": __version__,
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "backend": "sqlite",
        "postgresql_available": postgres_available(),
        "redis_available": redis_available(),
        "worker_count": extra.get("workers") if extra else None,
        "seed": extra.get("seed") if extra else None,
        "scenario": scenario,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if extra:
        payload.update(extra)
    return payload


def _reserve_worker(payload: tuple[str, str, int]) -> str:
    from veritas.adapters.sqlite import SQLiteAdapter
    from veritas.scenarios import DEFAULT_TIME

    path, key, index = payload
    store = SQLiteAdapter(path)
    try:
        store.reserve(
            resource_key=key,
            policy_version="v1",
            limit=10000,
            amount=900,
            window_seconds=86400,
            now=DEFAULT_TIME,
            idempotency_key=f"w-{index}",
            agent_id=f"agent-{index}",
        )
        return "ALLOW"
    except BudgetDenied:
        return "DENY"


def run_concurrency(workers: int = 8, requests: int = 32) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="veritas-lab-c-") as directory:
        path = str(Path(directory) / "store.db")
        from veritas.adapters.sqlite import SQLiteAdapter
        from veritas.scenarios import DEFAULT_TIME

        store = SQLiteAdapter(path)
        key = "money:lab:86400s"
        started = time.perf_counter()
        with ProcessPoolExecutor(max_workers=workers) as pool:
            outcomes = list(
                pool.map(_reserve_worker, [(path, key, index) for index in range(requests)])
            )
        elapsed = time.perf_counter() - started
        used = store.used(key, 86400, DEFAULT_TIME)
        allows = outcomes.count("ALLOW")
        denials = outcomes.count("DENY")
        # Feasible denials: requests that would fit if serialized after current used.
        # Approximate: if used <= 10000, extra denials beyond the residual/900 are FDR-ish.
        residual_slots = max(0, (10000 - (used - 900 * max(0, allows - 1))) // 900)
        del residual_slots
        fdr = FeasibleDenial(legitimate_denied=0, legitimate_feasible=allows + denials)
        # Honest: we cannot label DENY as illegitimate here; contention denials may be correct.
        return {
            **_manifest("concurrency", {"workers": workers, "requests": requests}),
            "outcomes": {"ALLOW": allows, "DENY": denials},
            "used": used,
            "overspend": max(0, used - 10000),
            "elapsed_s": round(elapsed, 4),
            "throughput_rps": round(requests / elapsed, 2) if elapsed else 0,
            "feasible_denial_note": (
                "DENY under contention is often the safety property, not FDR. "
                "FDR requires labeled legitimate-feasible actions; this run does not invent them."
            ),
            "fdr_placeholder": fdr.fdr,
            "property_committed_plus_reserved_le_budget": used <= 10000,
        }


def run_faults() -> dict[str, Any]:
    from veritas.errors import StoreUnavailable
    from veritas.runtime import bundled_policy_path, create_local_runtime
    from veritas.scenarios import account_state, payment_asir

    with tempfile.TemporaryDirectory(prefix="veritas-lab-f-") as directory:
        runtime = create_local_runtime(
            database_path=Path(directory) / "f.db", policy_path=bundled_policy_path()
        )

        class DeadStore:
            def reserve(self, **kwargs: Any) -> Any:
                raise StoreUnavailable("injected")

        runtime.engine.budgets = DeadStore()  # type: ignore[assignment]
        result = runtime.engine.authorize(
            payment_asir(amount=100, destination="fault", session_id="fault"),
            current_state=account_state(),
            idempotency_key="fault",
        )
        return {
            **_manifest("faults"),
            "store_down_decision": result.decision.value,
            "reason": result.reason_code,
            "fail_closed": result.decision.value != "ALLOW" or result.reason_code != "CAPABILITY_ISSUED",
        }


def run_security() -> dict[str, Any]:
    cycle1 = run_bench()
    cycle2 = run_cycle2_attacks()
    return {
        **_manifest("security"),
        "cycle1": {
            "passed": cycle1["families_passed"],
            "total": cycle1["families_total"],
            "rate": cycle1["security_rate"],
        },
        "cycle2": {
            "passed": cycle2["families_passed"],
            "total": cycle2["families_total"],
        },
    }


def mixed_workload() -> dict[str, Any]:
    """70/15/10/5 mix is generated, not observed production traffic."""

    from veritas.runtime import bundled_policy_path, create_local_runtime
    from veritas.scenarios import account_state, action_asir, payment_asir

    sequence: list[str] = (
        ["legit"] * 70 + ["high"] * 15 + ["violation"] * 10 + ["adversarial"] * 5
    )
    with tempfile.TemporaryDirectory(prefix="veritas-mix-") as directory:
        runtime = create_local_runtime(
            database_path=Path(directory) / "mix.db", policy_path=bundled_policy_path()
        )
        counts = {"ALLOW": 0, "DENY": 0, "REQUIRE_APPROVAL": 0}
        for index, kind in enumerate(sequence):
            if kind == "legit":
                asir = payment_asir(amount=50, destination="mix", session_id=f"m-{index}")
            elif kind == "high":
                asir = payment_asir(amount=6000, destination="mix", session_id=f"m-{index}")
            elif kind == "violation":
                asir = payment_asir(amount=11000, destination="mix", session_id=f"m-{index}")
            else:
                asir = action_asir("message.send_external", session_id="mix-adv")
                runtime.engine.authorize(
                    action_asir("data.read_sensitive", session_id="mix-adv"),
                    current_state={},
                    idempotency_key=f"adv-read-{index}",
                )
            result = runtime.engine.authorize(
                asir, current_state=account_state(), idempotency_key=f"mix-{index}"
            )
            counts[result.decision.value] = counts.get(result.decision.value, 0) + 1
        used = runtime.store.used("money:mix:86400s", 86400, runtime.clock.now())
        cost = AutonomyCost(
            legitimate_denials=0,
            unnecessary_approvals=counts.get("REQUIRE_APPROVAL", 0),
            legitimate_actions=70,
        )
        return {
            **_manifest("mixed_workload", {"seed": 0}),
            "distribution": {"legitimate": 70, "high_risk": 15, "violations": 10, "adversarial": 5},
            "decisions": counts,
            "used": used,
            "autonomy_cost": cost.ac,
            "sensitivity": sensitivity(security_benefit=1.0, autonomy_cost=cost.ac, latency=1.0)[:4],
            "note": "Labels are synthetic. High-risk REQUIRE_APPROVAL is not automatically unnecessary.",
        }


def export_results(payload: dict[str, Any], directory: Path) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    stem = payload.get("scenario", "experiment")
    json_path = directory / f"{stem}.json"
    csv_path = directory / f"{stem}.csv"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "value"])
        for key, value in payload.items():
            if not isinstance(value, (dict, list)):
                writer.writerow([key, value])
    return {"json": str(json_path), "csv": str(csv_path)}


def run_lab(command: str) -> dict[str, Any]:
    if command in {"cycle2", "security"}:
        payload = run_security()
        if command == "cycle2":
            payload["workloads"] = run_all_workloads()
            payload["ablations"] = run_ablations()
            payload["baselines"] = run_baseline_comparison()
            payload["agents"] = run_agent_bench()
            payload["mixed"] = mixed_workload()
        return payload
    if command == "concurrency":
        workers = int(os.environ.get("VERITAS_LAB_WORKERS", "4"))
        requests = int(os.environ.get("VERITAS_LAB_REQUESTS", "16"))
        return run_concurrency(workers=workers, requests=requests)
    if command == "faults":
        return run_faults()
    if command == "replay":
        from veritas.policy import PolicyCompiler
        from veritas.policy_ops import simulate
        from veritas.runtime import bundled_policy_path
        from veritas.scenarios import payment_asir

        policy = PolicyCompiler().compile_file(bundled_policy_path())
        asirs = [
            payment_asir(amount=900, destination="replay-lab", session_id=f"r-{i}") for i in range(3)
        ]
        return {**_manifest("replay"), "simulate": simulate(policy, asirs)}
    if command == "agents":
        return {**_manifest("agents", {"seed": 0}), **run_agent_bench()}
    if command == "baselines":
        return {**_manifest("baselines"), **run_baseline_comparison()}
    raise ValueError(f"unknown lab command: {command}")


def mean_ci(samples: list[float]) -> dict[str, float]:
    if not samples:
        return {"mean": 0.0, "median": 0.0, "std": 0.0}
    mean = statistics.fmean(samples)
    std = statistics.pstdev(samples) if len(samples) > 1 else 0.0
    return {
        "mean": round(mean, 4),
        "median": round(statistics.median(samples), 4),
        "std": round(std, 4),
        "n": float(len(samples)),
    }
