# Roadmap

The roadmap follows the source plan while making each exit criterion testable. Durations are
estimates for one primary implementer and should be adjusted after the first velocity sample.

## Cycle 0 - Prior art and foundation

Deliverables:

- Patent and literature search matrix for proof-carrying authorization, consumable capabilities,
  agent-tool conformal prediction, and intervention replay.
- Written novelty boundary with negative results.
- Name availability check for repository, package, and trademarks.
- Final decision on private, patent-first, or open-source path.
- ADRs 001-005 reviewed.

Exit: the repository remains private until a signed decision record exists.

## Cycle 1 - Strengthen ASIR and policy compilation

Current baseline: canonical subset, framework adapters, JSON tables, Cedar sketch, bounded SMT model.

Next work:

- Implement or adopt full RFC 8785 test vectors.
- Define the invariant DSL grammar and source locations.
- Compile one source into Cedar, runtime tables, and SMT.
- Use Z3 to emit counterexamples into CI artifacts.
- Add Hypothesis trajectory generation and monoid-law tests.
- Pin real LangGraph and MCP SDK conformance cases.

Exit: an intentionally unsafe compiler fixture is `sat` with a readable counterexample and the safe
fixture is `unsat` to the declared depth.

## Cycle 2 - Capability lifecycle and concurrency

Current baseline: Ed25519 POC envelope; local CAS, partition, and conservative hybrid modes.

Next work:

- Replace the envelope with reviewed PASETO v4.public.
- Implement parent/successor chains and monotonic chain index.
- Add durable partition allocation, lease expiry, reclaim, and rebalance.
- Model crashes at every lifecycle boundary.
- Add tool status inquiry and `INDETERMINATE_LOSS` state.
- Sweep 1/10/100/1000 concurrent agents and publish coordination/autonomy curves.

Exit: zero overspend in at least one million generated race attempts per mechanism, with raw evidence
and fault injection.

## Cycle 3 - Boundary, ledger, and approvals

Current baseline: cooperative SDK, local nonce table, content-addressed ledger, intervention replay,
local WYSIWYS approval.

Next work:

- General stale/reverify controller with maximum three attempts then HITL.
- Durable local anti-replay recovery protocol.
- Real approval UI with human authentication and separation of duties.
- General DAG branches and named trace/tool/intervention replay modes.
- External Merkle-root anchoring and immutable retention.
- Canary-secret tests and privacy retention controls.

Exit: end-to-end hero scenario plus intervention replay explains which substituted observation changed
the authorized trajectory.

## Cycle 4 - Identity and cloud adapters

- OIDC and SPIFFE identity/delegation validation.
- AWS, Azure, and GCP implementations for StateStore, LedgerStore, Signer, PolicyStore, and telemetry.
- Terraform modules with the same configuration contract.
- Cross-cloud partitions and signed Merkle root exchange.
- Optional global coordinator evaluated separately from disjoint partition mode.

Exit: one semantic conformance suite passes locally and in each selected cloud environment. Do not
claim equivalence from matching method names alone.

## Cycle 5 - Research benchmark and uncertainty

- Pin Cedar, OPA, attenuated OAuth, and relevant agent-security baselines.
- Publish deterministic environments for payments, databases, and messaging.
- Add calibration data, field distributions, coverage metrics, and shift experiments.
- Report coverage clean/shift/injection, abstention, set size, review cost, security, autonomy, and
  latency together.
- Add negative and ablation studies.

Exit: reproducible report with at least three composition/concurrency families that the pinned unit
baselines accept and VERITAS safely handles, plus measured autonomy cost.

## Cycle 6 - Paper, IP, and release

- Independent security and claims review.
- Final threat model and limitations section.
- Workshop paper and artifact appendix.
- Patent filing decision made before public disclosure where required.
- License, contribution policy, governance, package name, and disclosure process.
- Signed releases, SBOM, provenance, and public benchmark data.

Exit: submission or release completed under a recorded legal and technical decision.

## Recommended immediate sequence

1. Freeze this POC as `v0.1.0-private`.
2. Complete the prior-art matrix before adding product surface area.
3. Build the unified policy compiler and refinement tests.
4. Replace the signed envelope with a standard reviewed format.
5. Model lifecycle crashes before adding cloud adapters.
6. Run the million-race experiment and publish the coordination/autonomy curve.

