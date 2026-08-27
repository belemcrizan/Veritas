# Changelog

## Unreleased

## 0.2.0 - 2026-08-26

- Evolved the local POC toward an execution control plane without replacing the Cycle-1 public facade.
- Added enforcement modes `ENFORCE`, `SHADOW`, and `AUDIT`.
- Added structural identity/delegation checks, key-provider abstraction, execution lifecycle, and UNKNOWN reconciliation.
- Added policy `lint`/`test`/`diff`/`simulate`, ledger policy replay, showcase, explain demo, and a reference HTTP gateway.
- Added SQLite store contract tests, fault injection, and a security claim registry. PostgreSQL, Redis, and cloud KMS are documented as absent, not faked.
- Added a supported pre-1.0 API facade at `veritas` and `veritas.api`.
- Added public LangGraph and MCP normalization imports without requiring adapter-module imports.
- Added an executable library integration example and public-API regression tests.
- Expanded CI, typing metadata, MkDocs, and wheel smoke tests. PyPI remains disabled pending IP review.


## 0.1.2 - 2026-08-25

- Documented every stable reason code for operators and engineers (`veritas reasons`).
- Added `veritas doctor`, CLI exit codes, and JSON stderr on configuration failures.
- Fail-closed store and reservation errors (`STORE_UNAVAILABLE`, `RESERVATION_INVALID`).
- Policy compiler now rejects missing files and invalid JSON with `INVALID_POLICY`.
- Dual-audience guides: `docs/FOR_OPERATORS.md` and `docs/FOR_ENGINEERS.md`.

## 0.1.1 - 2026-08-24

- Added executable B0/B1 baselines (`Policy(a_t)` with no trajectory memory).
- Turned the hero scenario into a differential experiment: B1 spends 10,800; VERITAS denies the 12th.
- Required a capability at the tool (`VALID_CAPABILITY_REQUIRED` on direct calls).
- Added a property-named comparison table; NA and baseline wins are first-class.
- Added `docs/PRIOR_ART.md`, `docs/V01_PRESENT.md`, and speaker notes.
- Default CLI output for `demo` is human-readable; `--json` remains available.

## 0.1.0 - 2026-08-21

- Added canonical ASIR and framework adapters.
- Added compiled policy tables and temporal composition rule.
- Added CAS, partition, and conservative hybrid budget coordination.
- Added short-lived consumable Ed25519 capabilities.
- Added WYSIWYS human approvals and cooperative tool boundary.
- Added append-only ledger with trace and intervention replay.
- Added split-conformal categorical field gate.
- Added eleven-family adversarial benchmark and twelve automated tests.
- Added focused performance microbenchmarks and detailed documentation.
