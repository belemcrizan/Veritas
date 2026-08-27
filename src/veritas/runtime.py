"""Composition root for the reproducible local runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from veritas.adapters.local import SystemClock
from veritas.adapters.partition import HybridBudgetStore, InMemoryPartitionBudgetStore
from veritas.adapters.sqlite import SQLiteAdapter
from veritas.approval import ApprovalService
from veritas.boundary import ToolBoundary
from veritas.crypto import CapabilityCodec, LocalEd25519Signer
from veritas.enforcement import EnforcementMode
from veritas.engine import VeritasEngine
from veritas.observability import MetricsTelemetry
from veritas.policy import InMemoryPolicyStore, PolicyCompiler, RuntimeVerifier
from veritas.ports import BudgetStore, Clock, Telemetry
from veritas.reconcile import Reconciler


@dataclass
class LocalRuntime:
    engine: VeritasEngine
    boundary: ToolBoundary
    store: SQLiteAdapter
    policies: InMemoryPolicyStore
    capability_codec: CapabilityCodec
    approval_service: ApprovalService
    clock: Clock
    telemetry: Telemetry
    budget_store: BudgetStore
    reconciler: Reconciler

    def __enter__(self) -> LocalRuntime:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def bundled_policy_path(filename: str = "payment_policy.json") -> Path:
    """Return a policy shipped inside the installed package."""

    path = Path(__file__).resolve().parent / "resources" / filename
    if not path.is_file():
        raise FileNotFoundError(f"bundled policy is missing: {filename}")
    return path


def create_local_runtime(
    *,
    database_path: str | Path,
    policy_path: str | Path,
    clock: Clock | None = None,
    telemetry: Telemetry | None = None,
    dev_seed: str = "VERITAS-LOCAL-DEMO-KEY-DO-NOT-USE-IN-PRODUCTION",
    budget_mode: str = "cas",
    enforcement_mode: EnforcementMode | str = EnforcementMode.ENFORCE,
) -> LocalRuntime:
    resolved_clock = clock or SystemClock()
    resolved_telemetry = telemetry or MetricsTelemetry()
    store = SQLiteAdapter(database_path)
    policy = PolicyCompiler().compile_file(policy_path)
    policies = InMemoryPolicyStore(policy)
    budget_store: BudgetStore
    if budget_mode == "cas":
        budget_store = store
    elif budget_mode == "partition":
        budget_store = InMemoryPartitionBudgetStore({"finance-agent-01": 10000})
    elif budget_mode == "hybrid":
        partitions = InMemoryPartitionBudgetStore({"finance-agent-01": 7200})
        budget_store = HybridBudgetStore(partitions, store)
    else:
        raise ValueError("budget_mode must be cas, partition, or hybrid")
    mode = EnforcementMode(enforcement_mode)

    capability_signer = LocalEd25519Signer.from_seed(dev_seed, kid="local-capability-dev-v1")
    capability_issuer = CapabilityCodec(capability_signer)
    capability_verifier = CapabilityCodec(capability_signer.public_verifier())

    approval_signer = LocalEd25519Signer.from_seed(
        dev_seed + ":human-approval", kid="local-approver-dev-v1"
    )
    approval_issuer = ApprovalService(approval_signer)
    approval_verifier = ApprovalService(approval_signer.public_verifier())

    engine = VeritasEngine(
        policies=policies,
        verifier=RuntimeVerifier(store),
        budgets=budget_store,
        ledger=store,
        codec=capability_issuer,
        approvals=approval_verifier,
        clock=resolved_clock,
        telemetry=resolved_telemetry,
        enforcement_mode=mode,
    )
    boundary = ToolBoundary(
        codec=capability_verifier,
        policies=policies,
        budgets=budget_store,
        ledger=store,
        nonces=store,
        sessions=store,
        clock=resolved_clock,
        telemetry=resolved_telemetry,
    )
    return LocalRuntime(
        engine=engine,
        boundary=boundary,
        store=store,
        policies=policies,
        capability_codec=capability_issuer,
        approval_service=approval_issuer,
        clock=resolved_clock,
        telemetry=resolved_telemetry,
        budget_store=budget_store,
        reconciler=Reconciler(budgets=budget_store, ledger=store, clock=resolved_clock),
    )
