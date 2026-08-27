# Next-cycle gap analysis

This register is the Cycle-2 audit of the repository after the control-plane evolution.
Classifications are evidence-based. Unresolved items remain listed.

| ID | Área | Estado | Evidência | Risco | Prioridade | Correção proposta | Teste exigido | Claim permitido |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GAP-01 | Enforcement | IMPLEMENTED | `GuardedTool`, `ToolBoundary.execute` | Tool bypass if SDK omitted | P0 | Keep cooperative boundary; proxy later | `tests/test_present.py` | Execute requires a capability on guarded paths |
| GAP-02 | Trajectory budget | IMPLEMENTED | SQLite CAS + hero demo | Policy correctness assumed | P0 | Keep CAS | `test_twelfth_fraction_is_denied` | Cumulative 24h budget holds under the modeled window |
| GAP-03 | Concurrent reservation | IMPLEMENTED | `BEGIN IMMEDIATE`; showcase race | Single SQLite file only | P0 | PostgreSQL adapter when a real store exists | `test_concurrent_reservations_do_not_overspend` | No overspend on one SQLite file under the tested worker counts |
| GAP-04 | Replay | IMPLEMENTED | nonce table | Crash after consume still manual | P1 | Recovery protocol | `test_capability_is_consumed_once` | Consumed nonce is not reusable |
| GAP-05 | Policy freshness | IMPLEMENTED | version+digest at boundary | In-process publish only | P1 | Signed policy artifacts | bench `policy_race` | Stale capability cannot execute after in-process publish |
| GAP-06 | Approval binding | IMPLEMENTED | WYSIWYS + SoD | Local approver key | P1 | Real reviewer auth | showcase + `SEPARATION_OF_DUTIES` | Mutated ASIR invalidates approval |
| GAP-07 | Identity | PARTIAL | `TrustedInputIdentityVerifier` | No OIDC/SPIFFE signatures | P0 | Real IdentityVerifier adapter | `test_forged_issuer_is_denied` | Structural issuer/delegation checks only |
| GAP-08 | Key management | PARTIAL | `KeyProvider` + local Ed25519 | Dev seed in repo | P0 | Real KMS when credentials exist | `KEY_PROVIDER_UNAVAILABLE` test | Local signing is not production KMS |
| GAP-09 | Capability format | PARTIAL | `veritas.v1` envelope; signer/verifier split | Not PASETO/JWS | P2 | Implement and test PASETO before claiming it | codec tests | POC envelope only |
| GAP-10 | Storage ports | PARTIAL | Protocols + SQLite contract tests | No PostgreSQL/Redis adapters | P1 | Real adapters with the same contracts | `tests/contracts/test_stores.py` | SQLite implements the ports |
| GAP-11 | PostgreSQL | MISSING | — | Cannot claim distributed SQL | P1 | Real psycopg adapter + contracts | contract suite on Postgres | None |
| GAP-12 | Redis | MISSING | — | Cannot claim distributed nonce TTL | P2 | Real Redis nonce/idempotency | contract suite on Redis | None |
| GAP-13 | Lifecycle | IMPLEMENTED | `lifecycle.py` | Not persisted as a first-class row | P2 | Durable execution records | `tests/test_security.py` | Invalid transitions raise |
| GAP-14 | UNKNOWN/reconcile | IMPLEMENTED | `OutcomeUnknown`, `Reconciler` | Probe honesty assumed | P0 | Tool status APIs | timeout test | Timeout is not treated as failure |
| GAP-15 | Shadow/Audit | IMPLEMENTED | `EnforcementMode` | Shadow still issues a token | P1 | Distinct shadow token type | `test_shadow_mode_does_not_block_budget` | SHADOW does not reserve |
| GAP-16 | MCP gateway | PARTIAL | `MCPExecutionGateway` | No live MCP SDK pin | P2 | Pin MCP and add demo process | adapter tests | Shape normalization + engine path |
| GAP-17 | HTTP gateway | PARTIAL | stdlib `/authorize|/execute|/commit|/reconcile|/health` | Not hardened | P2 | Authn, TLS, limits | manual/local | Reference gateway over domain |
| GAP-18 | OpenAI Agents SDK | MISSING | — | — | P3 | Adapter only if SDK shape is stable | adapter test | None |
| GAP-19 | Policy DSL | RESEARCH_ONLY | JSON tables + Cedar sketch | Not a language | P2 | Testable DSL or keep JSON | `policy lint` | Lint is not a proof |
| GAP-20 | Policy static analysis | PARTIAL | unreachable, impossible approval, counterexample sequences | No SAT solver in lint | P2 | Optional Z3 path labeled bounded | `test_policy_lint_emits_temporal_counterexample` | Bounded counterexamples only |
| GAP-21 | Policy prove | MISSING | Intentionally absent | Misuse of the word prove | P0 | Do not add | — | Never claim proof from lint |
| GAP-22 | Replay twin | PARTIAL | `veritas replay --ledger --policy` | Full ASIR required on new traces | P2 | Always persist ASIR body | replay module | Policy differences, not incidents prevented |
| GAP-23 | Execution graph | PARTIAL | derived from ledger | Optional | P3 | Visualization UI | graph test | Research representation |
| GAP-24 | Information flow | PARTIAL | optional `flow_rules` | Not DLP | P2 | Broader label lattice | security test | Session-label enforcement only |
| GAP-25 | Approval UI | SCAFFOLD | CLI rendering exists | No screen | P3 | Minimal reviewer UI | render_for_approval | Canonical text exists |
| GAP-26 | OpenTelemetry | PARTIAL | `MetricsTelemetry` + redaction | otel extra unused | P3 | Optional otel exporter | telemetry counters | No secrets in events |
| GAP-27 | Ledger | PARTIAL | content-addressed, mutation test | Tamper-evident not tamper-proof | P1 | External anchor | contract mutation test | Tamper-evident locally |
| GAP-28 | Fault injection | PARTIAL | store down, key down | Incomplete matrix | P1 | Expand | `tests/test_fault_injection.py` | Those faults fail closed |
| GAP-29 | Property tests | PARTIAL | Hypothesis optional | CI compat job has no hypothesis | P2 | Dev extra | skip if missing | — |
| GAP-30 | Fuzzing | PARTIAL | malformed capability | No coverage-guided fuzzer | P2 | atheris later | security test | Malformed token is not ALLOW |
| GAP-31 | Distributed scale | UNTESTED | 40 workers local | No 1_000 worker evidence | P1 | Measure before claiming | bench parallel | Claims only at measured N |
| GAP-32 | Cloud | MISSING | ports only | — | P2 | One real cloud later | — | None |
| GAP-33 | Formal | PARTIAL | SMT resource invariant | Bounded, not implementation proof | P1 | Keep labels honest | `tools/check_smt.py` | Bounded model of the invariant |
| GAP-34 | LLM authorization | IMPLEMENTED | no LLM on hot path | Future misuse | P0 | Keep solver/tables | architecture | LLM is not the authority |
| GAP-35 | Enterprise readiness | PRODUCTION_GAP | research prototype | Operators may over-trust | P0 | Honest README | this file | Not production |

## Checkpoint

What existed before: Cycle-1 local POC with hero demo, SQLite CAS, Ed25519 envelope, B0/B1, 11 attack families.

What changed: control-plane modules, enforcement modes, identity/key/lifecycle/reconcile abstractions, policy engineering CLI, showcase, HTTP/MCP gateways, contract tests, claim registry.

Which claims remain unsupported: distributed correctness, KMS, OIDC, PASETO, tamper-proof ledger, DLP, enterprise production.
