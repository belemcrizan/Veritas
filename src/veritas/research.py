"""Single source of truth for version, cycle, and capability honesty."""

from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

CapabilityStatus = Literal[
    "IMPLEMENTED",
    "PARTIAL",
    "SCAFFOLD",
    "DOCUMENTED_ONLY",
    "TEST_ONLY",
    "EXPERIMENTAL",
    "BROKEN",
    "UNTESTED",
    "MISSING",
]

PACKAGE_NAME = "veritas-boundary-poc"
PACKAGED_VERSION = "0.2.0"
RESEARCH_CYCLE = "2"

CAPABILITIES: dict[str, dict[str, str]] = {
    "canonical_asir": {
        "status": "IMPLEMENTED",
        "evidence": "src/veritas/canonical.py, tests/test_canonical.py",
    },
    "compiled_json_policy": {
        "status": "IMPLEMENTED",
        "evidence": "src/veritas/policy.py, veritas policy-check",
    },
    "sqlite_cas_reservation": {
        "status": "IMPLEMENTED",
        "evidence": "src/veritas/adapters/sqlite.py, tests/contracts/test_stores.py",
    },
    "ed25519_capability": {
        "status": "PARTIAL",
        "evidence": "POC envelope, not PASETO/JWS; tests/test_runtime.py",
    },
    "hero_12x900": {
        "status": "IMPLEMENTED",
        "evidence": "veritas demo, tests/test_present.py",
    },
    "b0_b1_baselines": {
        "status": "IMPLEMENTED",
        "evidence": "src/veritas/baselines.py, src/veritas/comparison.py",
    },
    "cycle1_attack_families": {
        "status": "IMPLEMENTED",
        "evidence": "11 families in src/veritas/bench.py; do not mutate",
    },
    "lifecycle_state_machine": {
        "status": "IMPLEMENTED",
        "evidence": "src/veritas/lifecycle.py, tests/test_security.py",
    },
    "unknown_outcome_reconcile": {
        "status": "IMPLEMENTED",
        "evidence": "src/veritas/reconcile.py, timeout tests",
    },
    "shadow_audit_modes": {
        "status": "PARTIAL",
        "evidence": "SHADOW still issues a non-reserving capability; tests/test_security.py",
    },
    "http_gateway": {
        "status": "PARTIAL",
        "evidence": "stdlib reference; no TLS/authn; tests/test_http_gateway.py",
    },
    "mcp_boundary": {
        "status": "PARTIAL",
        "evidence": "shape + cooperative tool; no pinned MCP SDK process",
    },
    "postgresql_backend": {
        "status": "EXPERIMENTAL",
        "evidence": "src/veritas/adapters/postgres.py; skipped unless VERITAS_POSTGRES_DSN",
    },
    "redis_nonce": {
        "status": "EXPERIMENTAL",
        "evidence": "optional nonce store; budget remains SQL; skipped unless VERITAS_REDIS_URL",
    },
    "multiprocess_concurrency": {
        "status": "EXPERIMENTAL",
        "evidence": "tests/test_multiprocess.py; default N is small for CI time",
    },
    "crash_consistency": {
        "status": "EXPERIMENTAL",
        "evidence": "subprocess kill after reserve; tests/test_crash.py",
    },
    "opa_baseline": {
        "status": "PARTIAL",
        "evidence": "Rego artifact + in-process per-request eval; live opa binary optional",
    },
    "cedar_baseline": {
        "status": "PARTIAL",
        "evidence": "Cedar policy artifact; CLI optional; not a weakened straw man",
    },
    "adversarial_llm_agents": {
        "status": "MISSING",
        "evidence": "harness exists; no local model required this phase",
    },
    "cloud_backends": {
        "status": "MISSING",
        "evidence": "explicitly out of scope this cycle",
    },
    "oidc_identity": {"status": "MISSING", "evidence": "structural issuer checks only"},
    "production_kms": {"status": "MISSING", "evidence": "dev seed signer"},
}


def packaged_status() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "resources" / "research_status.json"
    data: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("research_status.json must be an object")
    return data


def installed_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return PACKAGED_VERSION


def status_report() -> dict[str, Any]:
    packaged = packaged_status()
    return {
        "version": installed_version(),
        "packaged_version": packaged["version"],
        "cycle": RESEARCH_CYCLE,
        "cycle_declaration": packaged["cycle_declaration"],
        "cycle_declaration_meaning": packaged["cycle_declaration_meaning"],
        "implementation_status": {
            name: item["status"] for name, item in CAPABILITIES.items()
        },
        "evidence_status": {name: item["evidence"] for name, item in CAPABILITIES.items()},
        "backends_validated": packaged["backends_validated"],
        "backends_optional": packaged["backends_optional"],
        "integrations_validated": packaged["integrations_validated"],
        "integrations_experimental": packaged["integrations_experimental"],
        "known_unsupported": packaged["unsupported"],
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "thesis": "Agent reasoning is not execution authority.",
    }
