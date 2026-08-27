# Threat Model

## Scope

This model covers the local Cycle-1 POC: a caller proposes an ASIR, the engine reserves a rolling
resource, the issuer creates a signed capability, and a cooperative boundary verifies it before a
deterministic tool runs.

It does not cover model quality, prompt-injection detection, long-term memory, RAG, general identity
issuance, cloud control planes, endpoint compromise, or legal compliance certification.

## Protected assets

- The global residual for each invariant.
- The integrity and confidentiality of signing keys.
- The exact action, state, policy, and identity approved for execution.
- The one-time nature of a capability.
- The audit history and its content hashes.
- Tool credentials, which must never enter agent or LLM context.

## Trust boundaries

| Boundary | Trusted behavior in the POC | Production requirement |
| --- | --- | --- |
| Upstream identity | `sub`, `iss`, and `act` are structurally present | Verify OIDC/SPIFFE signature, issuer, audience, expiry, delegation semantics, and revocation |
| Capability issuer | Local process and deterministic development key are honest | KMS/HSM signing, rotation, access policy, audit, separation of duties |
| SQLite | Local filesystem and transaction semantics are honest | Managed linearizable store or consensus system with conformance evidence |
| Tool boundary | Always verifies before execution | Hardened SDK/proxy, protected deployment, attestation where justified |
| Clock | One injected or system clock | Authenticated time source, bounded skew monitoring, fail-closed behavior |
| Policy publication | In-process store publishes reviewed artifacts | Signed versioned artifact, approval workflow, atomic rollout and rollback |

## Explicit assumptions H1-H6

1. **Honest issuer:** the capability issuer follows the protocol and its private key is not compromised.
2. **Signature security:** Ed25519 signatures cannot be forged under the standard computational model.
3. **Cooperative boundary:** every protected tool path executes the verification middleware first.
4. **Bounded clock skew:** issuer and boundary differ by no more than the configured delta.
5. **Authentic upstream identity:** the production identity verifier has validated the chain.
6. **Capability lifecycle:** no prepared capability remains usable after commit, compensation, or expiry.

The POC fully enforces neither H1 nor H5. They are deployment assumptions and benchmark directions.

## Adversaries

- A prompt-injected or fully compromised agent.
- Multiple colluding agents that divide and parallelize actions.
- A caller that mutates arguments after policy evaluation or human approval.
- A caller that replays a valid token.
- An operator that publishes a new policy between issuance and execution.
- A caller that lies about request time.
- A network or tool that loses a commit acknowledgement.
- A signing service that fails after a reservation is prepared.
- A caller that presents a cyclic delegation chain or self-approval.
- A malicious database or host administrator. This adversary is outside the local trust model.

## Attack-to-control mapping

| Attack | Control | Residual limitation |
| --- | --- | --- |
| Atomic overspend | Compiled limit + atomic reservation | Policy correctness is assumed after compilation |
| Fractionation | Rolling trajectory sum | Window uses the trusted server clock |
| Parallel double-spend | `BEGIN IMMEDIATE` transaction | One SQLite file only; not distributed consensus |
| Delegation laundering | Maximum chain depth + actor binding | No upstream token signature validation yet |
| Approval mutation | Signature over ASIR and deterministic rendering | Local dev approver key is not human-authentication infrastructure |
| Cross-tool exfiltration | Session temporal predecessor rule | Only a minimal action-pair automaton is implemented |
| Policy race | Version and artifact digest at boundary | Publication is in-process, not distributed |
| Clock skew/expiry | Short TTL and delta checks | No secure time synchronization adapter |
| Capability replay | Unique nonce persisted before tool execution | A crash after nonce consumption needs recovery design |
| Compensation abuse | Only `PREPARED -> COMPENSATED`, idempotently | Non-execution status inquiry is manual |
| State TOCTOU | Exact state hash at boundary | A non-cooperative tool may expose only reduced preconditions |

## Failure behavior

- Invalid identity or policy returns no capability.
- Store exceptions propagate; no tool executes because no capability was issued.
- Invalid, expired, stale, replayed, or state-mismatched capability raises a typed boundary error and
  records a boundary denial when the ledger remains available.
- Tool exceptions leave reservations prepared. An operator must confirm non-execution before release.
- Ledger failure currently fails the request by exception. Production should make this explicit and
  test partial failures around every append.

## Known security gaps

1. The default key is deterministically derived from a published development string.
2. The signed envelope has not received protocol or cryptographic design review.
3. The JSON implementation supports a safe subset rather than all RFC 8785 numbers and strings.
4. Nonce consumption happens before tool execution; crash recovery is not automated.
5. SQLite tables are not protected from a privileged local administrator.
6. The ledger has no external Merkle-root anchor.
7. The identity check is structural and does not verify a real token.
8. Partitions are process memory and disappear on restart.
9. Human approval issuance is simulated by a local key.
10. Dependency hashes, SBOM, container signing, and SLSA provenance are not generated yet.

## Production hardening gate

Do not protect a real tool until all of the following are complete:

- Independent security and cryptographic review.
- OIDC/SPIFFE validation and authorization conformance tests.
- KMS/HSM signer with rotation and overlap.
- Reviewed PASETO v4.public or another standardized capability format.
- Durable anti-replay design and crash-recovery protocol.
- Distributed residual store or formally bounded disjoint partitions.
- Automated status inquiry before compensation.
- Immutable ledger anchoring and retention policy.
- Fault injection, property-based testing, dependency scanning, SBOM, and signed release artifacts.

