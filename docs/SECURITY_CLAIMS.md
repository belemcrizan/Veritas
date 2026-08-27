# Security claim registry

Every claim must keep `implementation` and `tests` paths that exist in this repository.
Status values: `PROPOSED`, `IMPLEMENTED`, `TESTED`, `BOUNDED_VERIFIED`, `EXPERIMENTALLY_SUPPORTED`.

## CLAIM-EXEC-01

- **statement:** A guarded tool does not execute without a capability verified at the boundary.
- **scope:** `GuardedTool` cooperative SDK
- **assumptions:** the tool is wrapped; the agent cannot call the raw function
- **implementation:** `src/veritas/guarded.py`, `src/veritas/boundary.py`
- **tests:** `tests/test_present.py`
- **benchmark:** `veritas bench` replay/direct-call families
- **formal evidence:** none
- **known limitations:** a non-cooperative tool path bypasses VERITAS
- **status:** TESTED

## CLAIM-REPLAY-01

- **statement:** A consumed capability nonce cannot be consumed again.
- **scope:** SQLite `NonceStore`
- **assumptions:** the nonce table is intact and the process uses this store
- **implementation:** `src/veritas/adapters/sqlite.py`
- **tests:** `tests/test_runtime.py`, `tests/contracts/test_stores.py`
- **benchmark:** capability replay family
- **formal evidence:** none
- **known limitations:** crash between consume and commit needs reconciliation
- **status:** TESTED

## CLAIM-BUDGET-01

- **statement:** For a single SQLite resource key, committed plus prepared amounts do not exceed the compiled limit under the tested concurrency.
- **scope:** local CAS adapter
- **assumptions:** one database file; `BEGIN IMMEDIATE`; honest clocks
- **implementation:** `SQLiteAdapter.reserve`
- **tests:** `tests/test_runtime.py`, showcase concurrent reservation
- **benchmark:** parallel family
- **formal evidence:** `formal/resource_invariant.smt2` (bounded)
- **known limitations:** not a distributed consensus claim
- **status:** EXPERIMENTALLY_SUPPORTED

## CLAIM-APPROVAL-01

- **statement:** Execution of an approval-gated action requires a signature over the canonical ASIR hash; a mutated request is invalid.
- **scope:** local `ApprovalService`
- **assumptions:** approver key is not the production IdP
- **implementation:** `src/veritas/approval.py`, engine SoD check
- **tests:** showcase approval binding; `SEPARATION_OF_DUTIES`
- **benchmark:** approval mutation family
- **formal evidence:** none
- **known limitations:** simulated human
- **status:** TESTED

## CLAIM-POLICY-01

- **statement:** A capability issued under policy digest D cannot execute after a different current digest is published in-process.
- **scope:** `ToolBoundary` + `InMemoryPolicyStore`
- **assumptions:** issuer and verifier share the in-process store
- **implementation:** `src/veritas/boundary.py`
- **tests:** showcase policy freshness
- **benchmark:** policy_race
- **formal evidence:** none
- **known limitations:** not a distributed rollout
- **status:** TESTED

## CLAIM-TRAJECTORY-01

- **statement:** Individually allowed actions can be denied when a temporal or flow rule matches the session trajectory.
- **scope:** compiled temporal_rules and flow_rules
- **assumptions:** session store is the same runtime
- **implementation:** `RuntimeVerifier`
- **tests:** showcase cross-tool; information-flow test
- **benchmark:** composition family
- **formal evidence:** none
- **known limitations:** not general information-flow or DLP
- **status:** TESTED

## CLAIM-FAILCLOSED-01

- **statement:** Missing store or signing failures do not yield ALLOW with a capability.
- **scope:** local engine
- **assumptions:** exceptions surface as `StoreUnavailable` or `KEY_PROVIDER_UNAVAILABLE`
- **implementation:** `VeritasEngine.authorize`
- **tests:** `tests/test_fault_injection.py`
- **benchmark:** none
- **formal evidence:** none
- **known limitations:** some unexpected exceptions still propagate
- **status:** TESTED

## CLAIM-TIMEOUT-01

- **statement:** A tool `TimeoutError` after nonce consumption is recorded as UNKNOWN and is not compensated automatically.
- **scope:** cooperative boundary
- **assumptions:** the tool raises `TimeoutError` for ambiguous outcomes
- **implementation:** `src/veritas/boundary.py`, `src/veritas/reconcile.py`
- **tests:** `test_timeout_is_unknown_not_failure`
- **benchmark:** none
- **formal evidence:** none
- **known limitations:** probe honesty
- **status:** TESTED

## CLAIM-TAMPER-01

- **statement:** Local ledger verification detects payload mutation. This is tamper-evident, not tamper-proof.
- **scope:** SQLite ledger
- **assumptions:** attacker is not able to recompute and rewrite the full chain undetected in the same way the verifier reads
- **implementation:** `SQLiteAdapter.verify_integrity`
- **tests:** `tests/contracts/test_stores.py`
- **benchmark:** none
- **formal evidence:** none
- **known limitations:** privileged DB admin
- **status:** TESTED

## CLAIM-PG-01

- **statement:** A PostgreSQL adapter can implement the same reservation overspend property as SQLite when `VERITAS_POSTGRES_DSN` is set.
- **scope:** optional `PostgresAdapter`
- **assumptions:** one database; advisory locks; psycopg installed
- **implementation:** `src/veritas/adapters/postgres.py`
- **tests:** `tests/test_cycle2.py` (skipped without DSN)
- **benchmark:** none in default CI
- **formal evidence:** none
- **known limitations:** not run in the default OS matrix; not a multi-region claim
- **status:** IMPLEMENTED

## Negative claims (not made)

VERITAS does not guarantee LLM correctness, absence of malicious intent, tool correctness, OS security, cryptographic implementation correctness, protection if the boundary is bypassed, security after signing-key compromise, or all possible information leaks.
