# ADR-002: Solver Outside the Runtime Path

- Status: Accepted
- Date: 2026-08-21

## Context

SMT solvers are useful for policy consistency and bounded reachability but introduce unpredictable
latency and a large operational surface when called per tool action.

## Decision

Use solver artifacts only in development and CI. Compile reviewed policy into immutable runtime
tables. The online path performs lookup, integer residual arithmetic, hashing, and signature checks.

## Consequences

Runtime latency is predictable and does not depend on a solver. The compiler becomes safety-critical:
future work must show that the runtime table and SMT artifact preserve the same source semantics.

