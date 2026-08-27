# Cycle-2 reality check

Classifications are evidence-based. They were not adjusted to make VERITAS look complete.

Legend: `IMPLEMENTED` `PARTIAL` `SCAFFOLD` `DOCUMENTED_ONLY` `TEST_ONLY` `EXPERIMENTAL` `BROKEN` `UNTESTED` `MISSING`

| Capability | Status | Evidence |
| --- | --- | --- |
| Canonical ASIR | IMPLEMENTED | `src/veritas/canonical.py`, `tests/test_canonical.py` |
| Compiled JSON policy | IMPLEMENTED | `src/veritas/policy.py` |
| SQLite CAS reservation | IMPLEMENTED | `BEGIN IMMEDIATE`, contract tests |
| Hero 12×900 demo | IMPLEMENTED | `veritas demo` |
| B0 / B1 baselines | IMPLEMENTED | `src/veritas/baselines.py` — B1 is not weakened |
| Cycle-1 11 attack families | IMPLEMENTED | `src/veritas/bench.py` left intact |
| Lifecycle state machine | IMPLEMENTED | illegal transitions raise |
| UNKNOWN / reconcile | IMPLEMENTED | timeout ≠ failure; probe-driven commit/release |
| Shadow / audit | PARTIAL | SHADOW issues a non-reserving passthrough capability |
| HTTP gateway | PARTIAL | stdlib `/authorize` `/execute` `/reconcile` `/trace/{id}` `/health` `/metrics`; no TLS |
| MCP gateway | PARTIAL | cooperative Python adapter; no pinned MCP SDK server process |
| PostgreSQL backend | EXPERIMENTAL | `src/veritas/adapters/postgres.py`; tests skip without `VERITAS_POSTGRES_DSN` |
| Redis nonce | EXPERIMENTAL | optional; budget stays SQL |
| Multiprocess concurrency | EXPERIMENTAL | `tests/test_multiprocess.py` uses 2 processes / 16 requests, not 32×10_000 |
| Crash after reserve | EXPERIMENTAL | subprocess `os._exit(1)` keeps PREPARED amount |
| Feasible denial / autonomy cost | IMPLEMENTED | formulas exist; mixed workload labels are synthetic |
| SQL / git / email / export workloads | EXPERIMENTAL | real SQLite SQL, real git, captured mail, local HTTP; not production SaaS |
| OPA / Cedar | PARTIAL | artifacts + honest “needs external state” comparison; live `opa`/`cedar` CLIs not required |
| LLM adversarial agents | MISSING | scripted goal-seeking harness only; LLM is never the judge |
| Cloud KMS / OIDC / PASETO | MISSING | out of scope this phase |
| Production readiness | MISSING | research prototype |

## Version truth

| Field | Value |
| --- | --- |
| Package | `veritas-boundary-poc` 0.2.0 |
| Research cycle | 2 |
| Cycle declaration | **PARTIAL** |
| Validated backend | SQLite |
| Optional backends | PostgreSQL, Redis |

`veritas status` is the machine-readable copy of this table.

## What was not claimed

Distributed overspend safety, tamper-proof logs, general DLP, enterprise-grade anything, formally verified implementation.

## Commands that were actually run during this cycle

See `docs/CYCLE2_ACCEPTANCE.md`. If a command was not executed in CI, it is not listed as validated.
