"""Command-line interface for demos, policy checks, and benchmarks."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import traceback
from pathlib import Path

from veritas.acceptance import format_acceptance, run_cycle2_acceptance
from veritas.adapters.sqlite import SQLiteAdapter
from veritas.bench import print_bench, run_bench
from veritas.comparison import format_comparison_table, run_comparison
from veritas.demo import print_demo, print_explain
from veritas.errors import PolicyError, StoreUnavailable, VeritasError
from veritas.http_gateway import serve_gateway
from veritas.lab import export_results, run_lab
from veritas.models import ASIR
from veritas.perf import print_perf
from veritas.policy import PolicyCompiler, bounded_fractionation_counterexample
from veritas.policy_ops import diff_policies, format_diff, lint_policy, simulate
from veritas.reasons import REASONS, format_reason
from veritas.replay import replay_policy, replay_trace_file
from veritas.research import status_report
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.showcase import print_showcase

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
    demo.add_argument(
        "--explain",
        action="store_true",
        help="plain-language explanation of the twelfth denial",
    )

    bench = subparsers.add_parser("bench", help="run Cycle-1 families with B0/B1 comparison")
    bench.add_argument("--json", action="store_true", help="machine-readable report")

    perf = subparsers.add_parser("perf", help="run focused RNF01/RNF02 microbenchmarks")
    perf.add_argument("--iterations", type=int, default=1000)

    check = subparsers.add_parser("policy-check", help="compile and inspect a policy")
    check.add_argument("policy", type=Path)

    policy_cmd = subparsers.add_parser("policy", help="lint, test, diff, or simulate policies")
    policy_sub = policy_cmd.add_subparsers(dest="policy_command")
    policy_lint = policy_sub.add_parser("lint", help="static analysis (not a proof)")
    policy_lint.add_argument("policy", type=Path)
    policy_test = policy_sub.add_parser("test", help="compile and require a clean lint")
    policy_test.add_argument("policy", type=Path)
    policy_diff = policy_sub.add_parser("diff", help="classify privilege changes")
    policy_diff.add_argument("old", type=Path)
    policy_diff.add_argument("new", type=Path)
    policy_sim = policy_sub.add_parser("simulate", help="evaluate a JSON list of ASIR objects")
    policy_sim.add_argument("policy", type=Path)
    policy_sim.add_argument("asirs", type=Path, nargs="?")
    policy_sim.add_argument("--workload", type=Path, help="JSONL traces or JSON ASIR list")

    ledger = subparsers.add_parser("ledger-verify", help="verify a local ledger hash chain")
    ledger.add_argument("database", type=Path)

    replay = subparsers.add_parser(
        "replay", help="re-evaluate a ledger trace or JSONL traces under a candidate policy"
    )
    replay.add_argument("--ledger", type=Path)
    replay.add_argument("--policy", type=Path, required=True)
    replay.add_argument("--trace-id")
    replay.add_argument("--trace-data", type=Path, help="JSONL ActionTrace records")

    showcase = subparsers.add_parser("showcase", help="run modeled-protection demonstrations")
    showcase.add_argument("--json", action="store_true")
    showcase.add_argument("--explain", action="store_true", help="plain-language case writeups")
    showcase.add_argument("--technical", action="store_true", help="hashes, nonces, transitions")

    init_cmd = subparsers.add_parser("init", help="write a starter policy file")
    init_cmd.add_argument("--output", type=Path, default=Path("veritas-policy.json"))

    gateway = subparsers.add_parser("gateway", help="run the reference HTTP execution gateway")
    gateway.add_argument("--host", default="127.0.0.1")
    gateway.add_argument("--port", type=int, default=8080)
    gateway.add_argument("--database", default=":memory:")

    reasons = subparsers.add_parser("reasons", help="explain a decision code in plain language")
    reasons.add_argument("code", nargs="?", help="reason code, e.g. BUDGET_EXHAUSTED")
    reasons.add_argument("--json", action="store_true", help="machine-readable catalog")

    subparsers.add_parser("doctor", help="check that this machine can run the local prototype")
    subparsers.add_parser("status", help="print version, cycle, and honest capability status")
    subparsers.add_parser("version", help="print package version and research cycle")
    subparsers.add_parser(
        "validate-cycle2", help="run the Cycle-2 acceptance gate without rewriting failures"
    )
    lab = subparsers.add_parser("lab", help="run experimental measurements (not invariant tests)")
    lab.add_argument(
        "experiment",
        nargs="?",
        default="cycle2",
        choices=["security", "concurrency", "faults", "replay", "agents", "baselines", "cycle2"],
    )
    lab.add_argument("--out", type=Path, help="write JSON/CSV under this directory")
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
            print(
                json.dumps({key: vars(value) for key, value in sorted(REASONS.items())}, indent=2)
            )
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
    report = status_report()
    payload = {
        "version": report["version"],
        "cycle": report["cycle"],
        "cycle_declaration": report["cycle_declaration"],
        "healthy": healthy,
        "checks": checks,
        "next_step": "veritas demo" if healthy else "see docs/GETTING_STARTED.md troubleshooting",
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"VERITAS doctor  v{report['version']}  cycle {report['cycle']}")
        for item in checks:
            mark = "ok" if item["ok"] else "FAIL"
            print(f"  [{mark}] {item['name']}: {item['detail']}")
        print()
        print("healthy" if healthy else "not ready")
        print(payload["next_step"])
    return EXIT_OK if healthy else EXIT_USAGE


def _run_policy(args: argparse.Namespace) -> int:
    compiler = PolicyCompiler()
    if args.policy_command == "lint":
        policy = compiler.compile_file(args.policy)
        issues = lint_policy(policy)
        print(
            json.dumps(
                {
                    "version": policy.version,
                    "digest": policy.digest,
                    "issues": [item.__dict__ for item in issues],
                },
                indent=2,
            )
        )
        return EXIT_OK
    if args.policy_command == "test":
        policy = compiler.compile_file(args.policy)
        issues = [item for item in lint_policy(policy) if item.severity == "error"]
        print(
            json.dumps({"ok": not issues, "errors": [item.__dict__ for item in issues]}, indent=2)
        )
        return EXIT_OK if not issues else EXIT_USAGE
    if args.policy_command == "diff":
        old = compiler.compile_file(args.old)
        new = compiler.compile_file(args.new)
        changes = diff_policies(old, new)
        print(json.dumps({"changes": changes, "human": format_diff(changes)}, indent=2, sort_keys=True))
        return EXIT_OK
    if args.policy_command == "simulate":
        policy = compiler.compile_file(args.policy)
        source = args.workload or args.asirs
        if source is None:
            print("usage: veritas policy simulate POLICY [--workload FILE | ASIRS.json]")
            return EXIT_USAGE
        raw_text = Path(source).read_text(encoding="utf-8")
        if source.suffix == ".jsonl":
            from veritas.traces import asir_from_trace, load_jsonl

            asirs = [asir_from_trace(item) for item in load_jsonl(Path(source))]
        else:
            raw = json.loads(raw_text)
            asirs = [ASIR.model_validate(item) for item in raw]
        print(json.dumps({"results": simulate(policy, asirs)}, indent=2, sort_keys=True))
        return EXIT_OK
    print("usage: veritas policy {lint,test,diff,simulate}")
    return EXIT_USAGE


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "demo":
        if args.explain:
            print_explain(args.database, as_json=args.json)
            return EXIT_OK
        print_demo(args.database, as_json=args.json)
        return EXIT_OK
    if args.command == "bench":
        _print_bench(args.json)
        return EXIT_OK
    if args.command == "perf":
        print_perf(args.iterations)
        return EXIT_OK
    if args.command == "showcase":
        return print_showcase(as_json=args.json, explain=args.explain, technical=args.technical)
    if args.command == "init":
        source = bundled_policy_path()
        args.output.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        print(
            json.dumps(
                {
                    "wrote": str(args.output.resolve()),
                    "next_step": "veritas policy lint " + str(args.output),
                }
            )
        )
        return EXIT_OK
    if args.command == "gateway":
        database = args.database
        if database == ":memory:":
            database = str(Path(tempfile.mkdtemp(prefix="veritas-gw-")) / "veritas.db")
        runtime = create_local_runtime(database_path=database, policy_path=bundled_policy_path())
        print(json.dumps({"host": args.host, "port": args.port, "database": database}))
        serve_gateway(runtime, host=args.host, port=args.port)
        return EXIT_OK
    if args.command == "replay":
        policy = PolicyCompiler().compile_file(args.policy)
        if args.trace_data is not None:
            print(json.dumps(replay_trace_file(args.trace_data, policy), indent=2, sort_keys=True))
            return EXIT_OK
        if args.ledger is None or args.trace_id is None:
            print("replay requires --trace-data or both --ledger and --trace-id")
            return EXIT_USAGE
        store = SQLiteAdapter(args.ledger)
        print(
            json.dumps(
                replay_policy(store, trace_id=args.trace_id, candidate=policy),
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_OK
    if args.command == "policy":
        return _run_policy(args)
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
    if args.command == "status":
        print(json.dumps(status_report(), indent=2, sort_keys=True))
        return EXIT_OK
    if args.command == "version":
        report = status_report()
        print(f"{report['version']} cycle {report['cycle']} ({report['cycle_declaration']})")
        return EXIT_OK
    if args.command == "validate-cycle2":
        report = run_cycle2_acceptance()
        print(format_acceptance(report))
        return EXIT_OK if report["failed"] == 0 else EXIT_USAGE
    if args.command == "lab":
        payload = run_lab(args.experiment)
        if args.out is not None:
            payload["exports"] = export_results(payload, args.out)
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return EXIT_OK
    build_parser().print_help()
    return EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        report = status_report()
        print(report["version"])
        return EXIT_OK
    if args.command is None:
        parser.print_help()
        return EXIT_USAGE
    try:
        return _dispatch(args)
    except BrokenPipeError:  # pragma: no cover - CLI piping
        return EXIT_OK
    except (
        FileNotFoundError,
        PolicyError,
        StoreUnavailable,
        VeritasError,
        ValueError,
        OSError,
    ) as exc:
        payload = (
            exc.to_payload()
            if isinstance(exc, VeritasError)
            else {
                "error": type(exc).__name__,
                "code": getattr(exc, "code", "CLI_ERROR"),
                "message": str(exc),
                "operator": str(exc),
                "next_step": "Fix the path or file, then retry. Use --debug for a traceback.",
            }
        )
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return EXIT_USAGE


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
