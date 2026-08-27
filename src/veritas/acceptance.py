"""Cycle-2 acceptance runner. Failures are reported, not rewritten into PASS."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

SUITES: tuple[tuple[str, str], ...] = (
    ("Core invariants", "tests.test_runtime"),
    ("Canonicalization", "tests.test_canonical"),
    ("Security regressions", "tests.test_security"),
    ("Fault handling", "tests.test_fault_injection"),
    ("Store contracts", "tests.contracts.test_stores"),
    ("Policy / showcase", "tests.test_control_plane"),
    ("Fuzz / malformed", "tests.test_fuzz"),
    ("Public API", "tests.test_public_api"),
    ("Cycle-2 additions", "tests.test_cycle2"),
)


def _run_module(module: str) -> dict[str, Any]:
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    loader = unittest.defaultTestLoader
    try:
        suite = loader.loadTestsFromName(module)
    except Exception as exc:
        return {"status": "FAIL", "detail": f"load error: {exc}", "tests": 0, "failures": 1}
    result = unittest.TestResult()
    suite.run(result)
    failures = len(result.failures) + len(result.errors)
    skipped = len(result.skipped)
    total = result.testsRun
    if failures:
        status = "FAIL"
    elif total == 0:
        status = "UNSUPPORTED"
    elif skipped and skipped == total:
        status = "PARTIAL"
    else:
        status = "PASS"
    detail = f"ran={total} failures={failures} skipped={skipped}"
    if result.failures:
        detail += "; " + result.failures[0][1].splitlines()[-1]
    if result.errors:
        detail += "; " + result.errors[0][1].splitlines()[-1]
    return {"status": status, "detail": detail, "tests": total, "failures": failures}


def run_cycle2_acceptance() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for name, module in SUITES:
        outcome = _run_module(module)
        checks.append({"name": name, "module": module, **outcome})
    validated = sum(1 for item in checks if item["status"] == "PASS")
    partial = sum(1 for item in checks if item["status"] == "PARTIAL")
    failed = sum(1 for item in checks if item["status"] == "FAIL")
    unsupported = sum(1 for item in checks if item["status"] == "UNSUPPORTED")
    if failed:
        declaration = "NOT VALIDATED"
    elif partial or unsupported:
        declaration = "PARTIAL"
    else:
        declaration = "EXPERIMENTALLY VALIDATED"
    return {
        "title": "VERITAS CYCLE-2 ACCEPTANCE",
        "checks": checks,
        "validated": validated,
        "partial": partial,
        "failed": failed,
        "unsupported": unsupported,
        "cycle2_status": declaration,
        "honesty": "PASS is unittest success, not a production certification.",
    }


def format_acceptance(report: dict[str, Any]) -> str:
    lines = [report["title"], ""]
    for item in report["checks"]:
        lines.append(f"{item['name']:<28} {item['status']}")
    lines += [
        "",
        f"Validated: {report['validated']}",
        f"Partial:    {report['partial']}",
        f"Failed:     {report['failed']}",
        f"Unsupported:{report['unsupported']}",
        "",
        "Cycle-2 status:",
        str(report["cycle2_status"]),
        report["honesty"],
    ]
    return "\n".join(lines)
