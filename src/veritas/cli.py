"""Command-line interface for demos, policy checks, and benchmarks."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import traceback
from pathlib import Path

from veritas import __version__
from veritas.adapters.sqlite import SQLiteAdapter
from veritas.bench import print_bench, run_bench
from veritas.comparison import format_comparison_table, run_comparison
from veritas.demo import print_demo
from veritas.errors import PolicyError, StoreUnavailable, VeritasError
from veritas.perf import print_perf
from veritas.policy import PolicyCompiler, bounded_fractionation_counterexample
from veritas.reasons import REASONS, format_reason
from veritas.runtime import bundled_policy_path, create_local_runtime


EXIT_OK = 0
EXIT_USAGE = 1
EXIT_INTEGRITY = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veritas",
        description=(
            "VERITAS verified execution boundary. "
            "Operators: start with `veritas demo` and `veritas reasons`. "
            "Engineers: see docs/FOR_ENGINEERS.md."
        ),
    )
    parser.add_argument("--debug", action="store_true", help="print a traceback on failure")
    parser.add_argument("--version", action="store_true", help="print the package version and exit")
    subparsers = parser.add_subparsers(dest="command")

    demo = subparsers.add_parser("demo", help="run the twelve-transfer differential hero scenario")
    demo.add_argument("--database", help="optional persistent SQLite path")
    demo.add_argument("--json", action="store_true", help="machine-readable report")

    bench = subparsers.add_parser("bench", help="run Cycle-1 families with B0/B1 comparison")
    bench.add_argument("--json", action="store_true", help="machine-readable report")

    perf = subparsers.add_parser("perf", help="run focused RNF01/RNF02 microbenchmarks")
    perf.add_argument("--iterations", type=int, default=1000)

    check = subparsers.add_parser("policy-check", help="compile and inspect a policy")
    check.add_argument("policy", type=Path)

    ledger = subparsers.add_parser("ledger-verify", help="verify a local ledger hash chain")
    ledger.add_argument("database", type=Path)

    reasons = subparsers.add_parser("reasons", help="explain a decision code in plain language")
    reasons.add_argument("code", nargs="?", help="reason code, e.g. BUDGET_EXHAUSTED")
    reasons.add_argument("--json", action="store_true", help="machine-readable catalog")

    subparsers.add_parser("doctor", help="check that this machine can run the local prototype")
    return parser


def _print_bench(as_json: bool) -> None:
    comparison = run_comparison()
    if as_json:
        payload = {"veritas_families": run_bench(), "comparison": comparison}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(format_comparison_table(comparison))
    print()
    print_bench()


def _print_reasons(code: str | None, *, as_json: bool) -> int:
    if code is None:
        if as_json:
            print(json.dumps({key: vars(value) for key, value in sorted(REASONS.items())}, indent=2))
            return EXIT_OK
        print("Stable reason codes. Pass a code for operator and engineer text.\n")
        for key in sorted(REASONS):
            reason = REASONS[key]
            print(f"  {key:<32} {reason.decision}")
        return EXIT_OK
    if as_json:
        from veritas.reasons import lookup

        print(json.dumps(vars(lookup(code)), indent=2, sort_keys=True))
        return EXIT_OK
    print(format_reason(code))
    return EXIT_OK


def _run_doctor(*, as_json: bool = False) -> int:
    checks: list[dict[str, object]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    record("python", sys.version_info >= (3, 12), f"{sys.version.split()[0]}")
    try:
        import cryptography  # noqa: F401
        import pydantic  # noqa: F401

        record("runtime_deps", True, "cryptography and pydantic import")
    except Exception as exc:  # pragma: no cover - environment failure
        record("runtime_deps", False, str(exc))
    try:
        policy = PolicyCompiler().compile_file(bundled_policy_path())
        record("bundled_policy", True, f"{policy.version} digest={policy.digest[:18]}…")
    except Exception as exc:
        record("bundled_policy", False, str(exc))
    try:
        with tempfile.TemporaryDirectory(prefix="veritas-doctor-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "doctor.db",
                policy_path=bundled_policy_path(),
            )
            ok = runtime.store.verify_integrity()
            record("local_store", ok, str(runtime.store.path))
    except Exception as exc:
        record("local_store", False, str(exc))

    healthy = all(bool(item["ok"]) for item in checks)
    payload = {
        "version": __version__,
        "healthy": healthy,
        "checks": checks,
        "next_step": "veritas demo" if healthy else "see docs/GETTING_STARTED.md troubleshooting",
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"VERITAS doctor  v{__version__}")
        for item in checks:
            mark = "ok" if item["ok"] else "FAIL"
            print(f"  [{mark}] {item['name']}: {item['detail']}")
        print()
        print("healthy" if healthy else "not ready")
        print(payload["next_step"])
    return EXIT_OK if healthy else EXIT_USAGE


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "demo":
        print_demo(args.database, as_json=args.json)
        return EXIT_OK
    if args.command == "bench":
        _print_bench(args.json)
        return EXIT_OK
    if args.command == "perf":
        print_perf(args.iterations)
        return EXIT_OK
    if args.command == "policy-check":
        policy = PolicyCompiler().compile_file(args.policy)
        counterexample = bounded_fractionation_counterexample(
            limit=10000, atomic_limit=10000, amount=900, depth=12
        )
        print(
            json.dumps(
                {
                    "version": policy.version,
                    "digest": policy.digest,
                    "actions": sorted(policy.actions),
                    "temporal_rules": [rule.rule_id for rule in policy.temporal_rules],
                    "unit_filter_counterexample": counterexample,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_OK
    if args.command == "ledger-verify":
        database = Path(args.database)
        if not database.is_file():
            raise FileNotFoundError(f"ledger database not found: {database}")
        store = SQLiteAdapter(database)
        integrity = store.verify_integrity()
        print(json.dumps({"integrity": integrity, "database": str(database)}))
        return EXIT_OK if integrity else EXIT_INTEGRITY
    if args.command == "reasons":
        return _print_reasons(args.code, as_json=args.json)
    if args.command == "doctor":
        return _run_doctor()
    build_parser().print_help()
    return EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return EXIT_OK
    if args.command is None:
        parser.print_help()
        return EXIT_USAGE
    try:
        return _dispatch(args)
    except BrokenPipeError:  # pragma: no cover - CLI piping
        return EXIT_OK
    except (FileNotFoundError, PolicyError, StoreUnavailable, VeritasError, ValueError, OSError) as exc:
        payload = exc.to_payload() if isinstance(exc, VeritasError) else {
            "error": type(exc).__name__,
            "code": getattr(exc, "code", "CLI_ERROR"),
            "message": str(exc),
            "operator": str(exc),
            "next_step": "Fix the path or file, then retry. Use --debug for a traceback.",
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return EXIT_USAGE


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
