# Cycle-2 checkpoint

## What existed before

A research POC: canonical ASIR, compiled JSON policy, SQLite CAS, Ed25519 capabilities, WYSIWYS approvals, hero 12×900 demo, B0/B1, eleven attack families.

## What changed

Control-plane modules (identity, keys, lifecycle, reconcile, enforcement modes, policy lint/diff/simulate, replay twin, graph, HTTP and MCP gateways, showcase, contract and fault tests) without replacing the public Cycle-1 facade.

## Why it changed

The thesis stayed: execution must be verifiable. The prototype needed explicit failure modes, honest claim tracking, and demonstrable composition beyond a single hero script.

## Gaps closed

GAP-13, GAP-14, GAP-15, GAP-22 (partial), GAP-24 (partial), GAP-26 (partial), GAP-28 (partial), GAP-30 (partial).

## Properties protected

Budget safety on one SQLite file, replay, approval hash binding, policy freshness, fail-closed store/key faults, timeout ambiguity.

## Tests

`tests/test_security.py`, `tests/test_fault_injection.py`, `tests/test_control_plane.py`, `tests/contracts/test_stores.py`, existing Cycle-1 tests.

## Stronger claims

CLAIM-TIMEOUT-01, CLAIM-FAILCLOSED-01, CLAIM-TAMPER-01 (local evidence), SoD on approvals.

## Unsupported claims

Distributed overspend, cloud KMS, OIDC, PASETO, tamper-proof logs, enterprise production.

## Bugs found and fixed

Key-provider exceptions after reserve now compensate and deny. Timeout is UNKNOWN rather than implicit failure.

## Risks remaining

Cooperative boundary, development signing seed, SQLite admin trust, identity still structural.
