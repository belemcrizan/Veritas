# Source Plan and POC Scope

This repository was derived from:

- `VERITAS_MVP_Plano_End_to_End(1).pdf`
- Title: *VERITAS - Verified Execution Boundary for Autonomous Agents*
- Author: Crizan Belem Ribeiro
- Version: 1.0, August 2026
- Source status: pre-prior-art validation document; no novelty or patentability assumed

The source plan is the requirements baseline. `REQUIREMENTS_TRACEABILITY.md` is the authoritative map
from that plan to this code. Where implementation scope differs, the matrix and ADRs must say so.

The POC prioritizes the smallest end-to-end falsifiable slice:

1. Canonical action contract.
2. Compiled unit/relational/temporal checks.
3. Atomic monotonic resource reservation.
4. State- and policy-bound consumable authorization.
5. Cooperative boundary and commit.
6. Hash-verifiable evidence.
7. Adversarial composition and concurrency benchmark.

Cloud parity, complete statistical calibration, standardized token protocol, and a full refinement
proof remain later cycles.

