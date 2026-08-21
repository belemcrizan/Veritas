"""Command-line interface for demos, policy checks, and benchmarks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from veritas.adapters.sqlite import SQLiteAdapter
from veritas.bench import print_bench
from veritas.demo import print_demo
from veritas.perf import print_perf
from veritas.policy import PolicyCompiler, bounded_fractionation_counterexample


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veritas", description="VERITAS verified execution boundary POC"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="run the twelve-transfer hero scenario")
    demo.add_argument("--database", help="optional persistent SQLite path")

    subparsers.add_parser("bench", help="run all Cycle-1 attack families")

    perf = subparsers.add_parser("perf", help="run focused RNF01/RNF02 microbenchmarks")
    perf.add_argument("--iterations", type=int, default=1000)

    check = subparsers.add_parser("policy-check", help="compile and inspect a policy")
    check.add_argument("policy", type=Path)

    ledger = subparsers.add_parser("ledger-verify", help="verify a local ledger hash chain")
    ledger.add_argument("database", type=Path)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        print_demo(args.database)
    elif args.command == "bench":
        print_bench()
    elif args.command == "perf":
        print_perf(args.iterations)
    elif args.command == "policy-check":
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
    elif args.command == "ledger-verify":
        store = SQLiteAdapter(args.database)
        print(json.dumps({"integrity": store.verify_integrity()}))


if __name__ == "__main__":
    main()
