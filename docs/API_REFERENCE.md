# API Reference and Integration Examples

The stable POC integration surface is Python. The CLI is a thin wrapper around the same classes.

## Build an ASIR

```python
from datetime import datetime, timezone
from veritas.models import ASIR, Principal, RequestContext

asir = ASIR(
    agent_id="finance-agent-01",
    principal=Principal(
        sub="user:alice",
        iss="https://idp.example",
        act=("finance-agent-01",),
    ),
    delegation=("user:alice", "orchestrator-07", "finance-agent-01"),
    action="payment.transfer",
    resource="account-123",
    parameters={
        "amount": 900,
        "currency": "BRL",
        "destination": "acct-987",
    },
    purpose="invoice-payment",
    labels={"data_sensitivity": "financial", "irreversible": True},
    context=RequestContext(
        session_id="s-42",
        request_ts=datetime.now(timezone.utc),
    ),
)

print(asir.hash)
```

Amounts are positive integers. Define whether they mean cents or whole units in the policy and tool
contract; do not send floats.

## Normalize a LangGraph call

```python
from veritas.adapters.frameworks import LangGraphToolCallAdapter

asir = LangGraphToolCallAdapter().adapt(
    {"name": "payment.transfer", "args": {"amount": 900, "destination": "acct-987"}, "id": "call-1"},
    agent_id="finance-agent-01",
    principal=principal,
    delegation=("user:alice", "finance-agent-01"),
    resource="account-123",
    purpose="invoice-payment",
    session_id="s-42",
    request_ts=datetime.now(timezone.utc),
)
```

The adapter deliberately does not import LangGraph. This keeps the domain package small and makes
the adapter usable with serialized calls from multiple framework versions.

## Create the local composition root

```python
from veritas import describe_result
from veritas.runtime import create_local_runtime

runtime = create_local_runtime(
    database_path=".veritas/veritas.db",
    policy_path="policies/payment_policy.json",
    budget_mode="cas",  # cas | partition | hybrid
)
```

The returned object exposes:

- `runtime.engine`: prepare, policy verification, reservation, issuance, compensation.
- `runtime.boundary`: capability verification, execution, commit acknowledgement.
- `runtime.store`: local ledger, budget, nonce, and session state adapter.
- `runtime.policies`: current compiled policy and atomic in-process publication.
- `runtime.approval_service`: local development approval issuer.

## Authorize, then execute

```python
result = runtime.engine.authorize(
    asir,
    current_state={"account-123.balance": 50000, "currency": "BRL"},
    idempotency_key="invoice-2026-00042",
)

if result.decision == "ALLOW":
    committed = runtime.boundary.execute(
        result.capability,
        asir=asir,
        current_state={"account-123.balance": 50000, "currency": "BRL"},
        tool=my_payment_tool,
        trace_id=result.trace_id,
    )
elif result.decision == "REQUIRE_APPROVAL":
    send_to_human_review(asir)
else:
    print(describe_result(result))
    record_denial(result.reason_code)
```

The `current_state` passed to the boundary must match the state used at authorization. If the state
changes, `StateMismatch` is raised. A production integration should refresh state and re-authorize
at most the configured retry count before escalating.

## High-value action with human approval

```python
approval = runtime.approval_service.issue(
    asir,
    approver="human:risk-owner",
    now=runtime.clock.now(),
    ttl_seconds=120,
)

result = runtime.engine.authorize(
    asir,
    current_state=current_state,
    idempotency_key="high-value-42",
    approval_token=approval,
)
```

The token authorizes only the exact ASIR displayed by `render_for_approval(asir)`. Any mutation to
amount, destination, purpose, principal, delegation, labels, or context changes the hash.

## Compensation

If the tool failed before execution and non-execution was confirmed:

```python
claims = runtime.capability_codec.decode_and_verify(result.capability)
runtime.engine.compensate(
    claims.reservation_id,
    trace_id=result.trace_id,
    reason="tool status endpoint confirmed non-execution",
)
```

Never compensate merely because an acknowledgement timed out. The tool may have executed. The POC
provides the idempotent state transition; automated status inquiry is a roadmap item.

## Replay

```python
nodes = runtime.store.trace(result.trace_id)

intervention = {
    nodes[0]["node_id"]: {"asir_hash": "replacement-observation"}
}
replayed = runtime.store.replay(result.trace_id, interventions=intervention)
```

Every descendant of the changed node receives a new replayed content address. This is a claim about
the captured deterministic environment, not general causal identification.

## Stable decision codes

The executable catalog is `src/veritas/reasons.py`. List or explain codes with:

```bash
veritas reasons
veritas reasons BUDGET_EXHAUSTED
```

In Python, `describe_result(result)` adds operator text, engineer text, and a next step.

| Code | Meaning |
| --- | --- |
| `CAPABILITY_ISSUED` | Policy passed and reservation succeeded. |
| `BUDGET_EXHAUSTED` | The rolling invariant has insufficient residual. |
| `APPROVAL_REQUIRED` | Deterministic policy requires human approval. |
| `INVALID_APPROVAL` | Approval is invalid, expired, or bound to another ASIR. |
| `DELEGATION_DEPTH_EXCEEDED` | The delegation chain is too deep. |
| `TEMPORAL_INVARIANT_VIOLATION` | Session history makes the action unsafe. |
| `STALE_CAPABILITY` | Policy changed before boundary use. |
| `STATE_HASH_MISMATCH` | Tool-visible state changed after verification. |
| `CAPABILITY_REPLAY` | The nonce has already been consumed. |
| `VALID_CAPABILITY_REQUIRED` | The tool was invoked without a capability. |
| `STORE_UNAVAILABLE` | Local store could not complete the check; authorize returns DENY. |
| `INVALID_POLICY` | Policy file is missing or not compilable. |

