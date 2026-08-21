# Requirements Traceability

Status definitions:

- **Implemented:** executable behavior exists and is covered by a local test or benchmark.
- **Partial:** the core mechanism exists, but one or more design-plan obligations remain.
- **Skeleton:** an interface, example, or isolated component exists but is not in the main path.
- **Planned:** intentionally absent from this POC.

This matrix prevents documentation from overstating the artifact.

## Design rules R1-R14

| ID | Status | Evidence | Remaining work |
| --- | --- | --- | --- |
| R1 - Tool requires valid capability | Implemented | `ToolBoundary.execute`; replay, expiry, state, and policy benchmark cases | Enforce that every real tool route uses the boundary; add attestation/proxy controls |
| R2 - Consumable successor capabilities | Partial | One-time nonce and committed reservation prevent reuse | `parent_cap` and `chain_index` are modeled but successor-chain issuance is not implemented |
| R3 - Residuals only by CAS or prior partition | Implemented locally | SQLite CAS, partition, hybrid adapters; concurrency and hybrid tests | Durable distributed partition allocation and rebalancing |
| R4 - Bind ASIR, state, policy, nonce, identity | Partial | Capability binds ASIR hash, exact state hash, policy version/digest, nonce; ASIR contains identity | Capability does not independently carry a verified upstream identity-token digest |
| R5 - Policy change invalidates live capabilities | Implemented | `attack_policy_race`; boundary compares version and digest | Distributed atomic policy rollout and revocation propagation |
| R6 - Human approval signs canonical ASIR | Implemented locally | `ApprovalService`, deterministic rendering, approval-mutation benchmark | Real human authentication, UI, separation of duties, durable approval nonce store |
| R7 - SMT never on hot path | Implemented | Runtime tables in `policy.py`; SMT is under `formal/` and `tools/` | Build one compiler that emits both artifacts from one DSL |
| R8 - Every decision in hash-linked ledger | Partial | Engine and boundary decisions append before return; audit fields tested indirectly | Transactionally couple ledger append and outward response under all partial failures; external anchoring |
| R9 - Calibration mass before guarantee | Implemented as isolated Cycle-2 slice | `SplitConformalFieldGate`; calibration-mass test | Integrate field distributions and labeled calibration sets into main engine path |
| R10 - High risk not decided statistically | Implemented in isolated gate | `high_risk` and `alpha < 0.01` force review | Central risk classification and policy integration |
| R11 - Timed compensation after status check | Partial | Idempotent PREPARED-only compensation and abuse benchmark | Timeout worker, tool status inquiry, indeterminate-loss state, event bus |
| R12 - No cloud SDK in domain | Implemented | Ports plus `tools/check_portability.py` | Add cloud adapters and run conformance suite |
| R13 - Missing dependency fails closed | Partial | Missing/invalid policy, identity, signature, store calls yield no tool execution | Normalize all infrastructure exceptions into audited denial outcomes |
| R14 - Tool credentials never reach agent | Architectural | No tool credentials exist in ASIR, capability, or ledger | Secret-store adapter and integration test that scans traces for canary secrets |

## Functional requirements RF01-RF11

| ID | Status | POC evidence | Gap to design-plan completion |
| --- | --- | --- | --- |
| RF01 - LangGraph call to canonical ASIR | Implemented | `LangGraphToolCallAdapter`, ASIR hash test | Validate against pinned real LangGraph versions |
| RF02 - Cedar + invariant DSL to tables and SMT | Partial | JSON compiler, Cedar sketch, SMT bounded model | Actual Cedar parser/binding and unified compiler |
| RF03 - Signed consumable capability | Partial | Ed25519 envelope with all listed binding fields | Reviewed PASETO v4.public implementation and successor chain |
| RF04 - CAS, partition, hybrid reservation | Implemented for local POC | Three adapters and tests | Durable partitions, rebalancing, multi-process conformance |
| RF05 - Offline checks and Prepare/Verify/Commit | Partial | End-to-end hero and attack scenarios | Automated timeout/status compensation and retry/HITL controller |
| RF06 - Merkle ledger and three replay modes | Partial | Hash-linked DAG-compatible chain, trace and intervention replay | Named tool replay with recorded mocks; durable DAG branching API |
| RF07 - Signed human approval | Implemented locally | Exact ASIR/rendering binding | Production identity, UI, and approval policy |
| RF08 - All attacks and two baselines | Implemented as deterministic harness | 11/11 families; no-protection and unit-filter baselines | Pin real Cedar/OPA/OAuth products and publish statistical repetitions |
| RF09 - Conformal gate and shift monitor | Skeleton | Functional categorical gate; shift input can suspend guarantee | Calibration pipeline, embeddings, density-ratio shift estimator, coverage study |
| RF10 - Temporal automaton | Partial | Sensitive-read -> no-external-send state | General policy-compiled automata, expiry/reset semantics, model checking |
| RF11 - MCP adapter | Implemented at shape level | `MCPToolCallAdapter` | Test against a pinned MCP SDK and signed identity context |

## Non-functional requirements RNF01-RNF08

| ID | Status | How to measure | Current interpretation |
| --- | --- | --- | --- |
| RNF01 - policy p95 < 5 ms | Measurable | `veritas perf` policy lookup | Met in the supplied environment; rerun on target hardware |
| RNF02 - offline verification p95 < 1 ms | Measurable | `veritas perf` signature/envelope scope | Met at p95 in the supplied environment; excludes nonce and ledger I/O |
| RNF03 - throughput at 1/10/100/1000 | Partial | Concurrency benchmark currently exercises 40 | Add full sweep, repetitions, confidence intervals, and every coordinator |
| RNF04 - partition survives global CAS outage | Partial | Partition adapter has no global dependency | It is in-memory; process restart loses state and no outage harness exists |
| RNF05 - one-command reproducibility | Implemented functionally | `make demo`, `make bench`, Docker commands | Timing and random identifiers are intentionally not byte-identical |
| RNF06 - local/AWS/Azure/GCP parity | Planned | One conformance suite per port | Only local reference adapters exist |
| RNF07 - OTel on every decision | Skeleton | Telemetry port receives engine/boundary decisions | Replace in-memory/JSON adapter with OTel spans, metrics, trace propagation |
| RNF08 - certificate < 1 KB | Implemented | Issuer rejects certificate metadata >= 1,024 bytes | Measure complete standardized capability after PASETO migration |

## Acceptance claims that may be stated now

- In the deterministic Cycle-1 harness, all eleven defined attacks produced the expected safe behavior.
- In a 40-thread local SQLite test, 33 reservations of 300 succeeded against a 10,000 limit and the
  recorded used amount was 9,900.
- The twelve-by-900 hero scenario denied the twelfth request and authorized the maximal safe prefix.
- The boundary rejects stale, state-mismatched, expired, mutated, and replayed capabilities.
- The focused in-process policy and cryptographic scopes can be measured independently.

## Claims that must not be stated yet

- “Formally verified implementation.”
- “RFC 8785 compliant” or “PASETO compliant.”
- “Production-ready zero-trust authorization.”
- “Statistical uncertainty guarantee for agent tool use.”
- “Multi-cloud invariant preservation.”
- “EU AI Act compliant,” “NIST compliant,” or independently audited.
- “Novel” or “patentable” before professional prior-art and legal review.

