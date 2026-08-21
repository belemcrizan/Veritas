# Public API Reference

The supported integration surface is exported from the top-level `veritas` package. Application
code should prefer:

```python
from veritas import ASIR, Decision, create_local_runtime
```

over imports from implementation modules such as `veritas.adapters`, `veritas.engine`, or
`veritas.runtime`.

> **Pre-1.0 stability:** names listed in `veritas.__all__` form the supported experimental API.
> They can still change between minor releases until version 1.0. Internal modules can change at
> any time.

## Exported groups

| Group | Public names |
| --- | --- |
| Contracts | `ASIR`, `Principal`, `RequestContext`, `AuthorizationResult`, `BoundaryResult` |
| Decisions | `Decision` |
| Runtime | `LocalRuntime`, `VeritasEngine`, `create_local_runtime`, `bundled_policy_path` |
| Framework adapters | `LangGraphToolCallAdapter`, `MCPToolCallAdapter` |
| Expected failures | `VeritasError`, `BudgetDenied`, `PolicyError`, `InvalidCapability`, `ExpiredCapability`, `StaleCapability`, `ReplayDetected`, `StateMismatch`, `InvalidApproval` |
| Package metadata | `__version__` |

## Build an ASIR

```python
from datetime import datetime, timezone

from veritas import ASIR, Principal, RequestContext

agent_id = "finance-agent-01"
asir = ASIR(
    agent_id=agent_id,
    principal=Principal(
        sub="user:alice",
        iss="https://idp.example",
        act=(agent_id,),
    ),
    delegation=("user:alice", "orchestrator-07", agent_id),
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

Resource amounts are positive integers. Define in the policy and tool contract whether they
represent minor currency units, whole units, bytes, calls, or another additive resource. Do not use
floating-point values in canonical ASIR fields.

## Normalize a framework tool call

The public adapters do not import LangGraph or an MCP SDK. They normalize serialized call shapes.

```python
from datetime import datetime, timezone

from veritas import LangGraphToolCallAdapter, Principal

agent_id = "finance-agent-01"
principal = Principal(
    sub="user:alice",
    iss="https://idp.example",
    act=(agent_id,),
)

asir = LangGraphToolCallAdapter().adapt(
    {
        "name": "payment.transfer",
        "args": {"amount": 900, "currency": "BRL", "destination": "acct-987"},
        "id": "call-1",
    },
    agent_id=agent_id,
    principal=principal,
    delegation=("user:alice", agent_id),
    resource="account-123",
    purpose="invoice-payment",
    session_id="s-42",
    request_ts=datetime.now(timezone.utc),
)
```

`MCPToolCallAdapter` accepts an MCP `tools/call` parameter object with `name` and `arguments`, plus
the same identity and request context.

## Create the local runtime

```python
from veritas import bundled_policy_path, create_local_runtime

runtime = create_local_runtime(
    database_path=".veritas/veritas.db",
    policy_path=bundled_policy_path(),
    budget_mode="cas",  # cas | partition | hybrid
)
```

The returned `LocalRuntime` exposes:

- `runtime.engine`: policy verification, reservation, capability issuance, and compensation;
- `runtime.boundary`: final verification, tool execution, and commit acknowledgement;
- `runtime.store`: local ledger, budget, nonce, and session-state storage;
- `runtime.policies`: the current compiled policy;
- `runtime.approval_service`: the local development approval issuer;
- `runtime.clock` and `runtime.telemetry`: configured runtime ports.

The development signing seed inside `create_local_runtime` must not be used in production.

## Authorize and execute

```python
from veritas import Decision

current_state = {"account-123.balance": 50000, "currency": "BRL"}
result = runtime.engine.authorize(
    asir,
    current_state=current_state,
    idempotency_key="invoice-2026-00042",
)

if result.decision is Decision.ALLOW:
    if result.capability is None:
        raise RuntimeError("ALLOW result did not include a capability")
    committed = runtime.boundary.execute(
        result.capability,
        asir=asir,
        current_state=current_state,
        tool=my_payment_tool,
        trace_id=result.trace_id,
    )
elif result.decision is Decision.REQUIRE_APPROVAL:
    send_to_human_review(asir)
else:
    record_denial(result.reason_code)
```

The state passed to the boundary must canonicalize to the same hash used during authorization. If it
changes, `StateMismatch` is raised. A production integration should refresh state and re-authorize
with a bounded retry policy before escalating.

## Human approval

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

The approval authorizes only the canonical ASIR that was signed. A material mutation to the request
changes its hash and invalidates the approval.

## Compensation

Compensate only after non-execution is confirmed through a tool-specific idempotency or status
check:

```python
if result.capability is None:
    raise RuntimeError("no capability was issued")

claims = runtime.capability_codec.decode_and_verify(result.capability)
if claims.reservation_id is not None:
    runtime.engine.compensate(
        claims.reservation_id,
        trace_id=result.trace_id,
        reason="tool status endpoint confirmed non-execution",
    )
```

Never compensate only because an acknowledgement timed out: the tool might have executed. Automated
status inquiry and asynchronous recovery remain roadmap items.

## Complete executable example

The authoritative minimal integration is `examples/library_integration.py`. Run it from the
repository root after installing the project:

```bash
python examples/library_integration.py
```

This example is exercised by the public API test suite. Unlike an illustrative code fragment, it is
expected to remain executable.

## Generated API page

The documentation site uses mkdocstrings to render the current public facade:

::: veritas.api
