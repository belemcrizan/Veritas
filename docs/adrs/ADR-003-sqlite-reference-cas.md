# ADR-003: SQLite as the Local CAS Oracle

- Status: Accepted for local POC
- Date: 2026-08-21

## Context

Two agents must not derive successful reservations from the same residual. A read followed by an
unconditional write is unsafe under concurrency.

## Decision

Use SQLite `BEGIN IMMEDIATE` to serialize the rolling-window sum check and reservation insert. Count
both `PREPARED` and `COMMITTED` rows. Exclude only confirmed `COMPENSATED` rows.

## Consequences

The local mechanism is simple and testable and prevented overspend in the 40-thread scenario. It is
not a distributed CAS, should not live on a network filesystem, and is not evidence of cloud adapter
equivalence.

