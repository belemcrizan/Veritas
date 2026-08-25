# VERITAS for engineers

This page is the technical map. For the decision-maker version, start with
[FOR_OPERATORS.md](FOR_OPERATORS.md).

## Install and prove the machine works

Follow [GETTING_STARTED.md](GETTING_STARTED.md), then:

```bash
veritas doctor
python -W error::ResourceWarning -m unittest discover -s tests -v
veritas demo
veritas bench
python tools/check_portability.py
```

`veritas doctor` must print `healthy`. Tests must pass. `families_passed` must equal `families_total`.

## Integration contract

1. Normalize the framework call to `ASIR` (`adapters/frameworks.py`).
2. `engine.authorize(...)` — never execute the tool here.
3. On `ALLOW`, pass `result.capability` into `GuardedTool` or `ToolBoundary.execute`.
4. Match `current_state` at authorize and at the boundary.
5. On `REQUIRE_APPROVAL`, sign `render_for_approval(asir)` and retry with the token.
6. On store or capability errors, **fail closed**. Do not invent a local allow.

Executable examples: [API_REFERENCE.md](API_REFERENCE.md). Public imports:

```python
from veritas import (
    ASIR,
    Decision,
    GuardedTool,
    create_local_runtime,
    describe_result,
)
```

`describe_result(result)` attaches operator text, engineer text, and a next step to any
`AuthorizationResult`.

## Errors are part of the protocol

| Situation | Type or code | Behaviour |
| --- | --- | --- |
| Missing tool pass | `MissingCapability` / `VALID_CAPABILITY_REQUIRED` | Tool does not run |
| Residual too small | `BudgetDenied` / `BUDGET_EXHAUSTED` | Authorize returns `DENY` |
| Bad policy file | `PolicyError` / `INVALID_POLICY` | Compiler refuses; CLI exit 1 |
| SQLite cannot complete a check | `StoreUnavailable` / `STORE_UNAVAILABLE` | Authorize returns `DENY` |
| Replay, expiry, stale policy, state change | subclasses of `InvalidCapability` | Boundary raises; nothing executes |
| Unknown reservation lifecycle | `ReservationError` / `RESERVATION_INVALID` | Commit/compensate refused |

CLI failures print a JSON object on stderr (`code`, `message`, `operator`, `next_step`). Use
`--debug` for a traceback. `veritas ledger-verify` exits `2` when the hash chain is broken.

A new safety-relevant outcome **must** add a row to `src/veritas/reasons.py` and a test that emits
the code. See [DEVELOPMENT.md](DEVELOPMENT.md).

## Where to read next

| Question | Document |
| --- | --- |
| How components fit | [ARCHITECTURE.md](ARCHITECTURE.md) |
| What is in / out of scope | [SOURCE_PLAN_SCOPE.md](SOURCE_PLAN_SCOPE.md) |
| Threats and assumptions | [THREAT_MODEL.md](THREAT_MODEL.md) |
| Requirement IDs | [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) |
| Attack families | [BENCHMARK.md](BENCHMARK.md) |
| SMT vs runtime | [FORMAL_VERIFICATION.md](FORMAL_VERIFICATION.md) |
| Why SQLite, envelope, private release | [docs/adrs/](adrs/) |
| What is frozen vs next | [V01_PRESENT.md](V01_PRESENT.md), [ROADMAP.md](ROADMAP.md) |

## Non-goals for this patch train

Do not add dashboards, cloud adapters, LLM judges, or extra domains here. Evidence against Cedar/OPA
and heavier concurrency belongs to **v0.2-evidence**.
