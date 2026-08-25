# Prior art memo (v0.1-present)

Status: internal. Not a patentability opinion. Not a claim of novelty.

## Question this memo answers

What may we still call a contribution after B1 exists as an executable
independent-call filter?

Working hypothesis:

> There is a class of trajectory attacks that `Policy(a_t)` does not
> preserve, and that `V(a_t | H, S, P)` with a mandatory tool-side
> capability check does preserve, under the Cycle-1 model.

If a traditional mechanism already preserves a named property, the
comparison table must show PASS for that baseline. That is a result,
not a failure of the experiment.

## Nearby mechanisms (must be studied before any public claim)

| Mechanism | What it already does | Likely overlap with VERITAS | Likely gap vs trajectory thesis |
| --- | --- | --- | --- |
| Cedar | Policy-as-code, request-time authorization, strong identity/resource language | Per-call allow/deny, RBAC/ABAC | Cumulative residual, capability consumption, session order — unless encoded as extra context the caller supplies |
| Open Policy Agent / Rego | General policy engine, sidecar/library | Same as Cedar for independent requests | Memory of prior calls is not native; the PEP must feed residual/history |
| Zanzibar / ReBAC | Relationship tuples, consistency | Delegation and relational checks | Not a rolling budget or single-use capability protocol |
| OAuth 2 / DPoP / token binding | Proof-of-possession, sender-constrained tokens | Capability-like bearer replacement | Tokens are usually not one-shot, not residual-accounting |
| Macaroons / Biscuits / PASETO | Attenuated, caveat-carrying credentials | Short-lived, constrained capabilities | Need an external reservation/ledger to make spend monotonic |
| Object capabilities / E / Cap'n Proto | Authority is unforgeable reference | Tool cannot act without a cap | Composition and quota still need a resource monitor |
| Ulysses / transactional memory / 2PC | Atomic reserve-then-commit | Budget CAS | Not an agent-tool authorization protocol |
| Provenance / hash-chained logs | Tamper-evident history | Ledger | Logs do not block execution by themselves |
| LLM guardrails / NeMo Guardrails / Llama Guard | Prompt/output filters | None on the tool boundary | Advisors; the agent can ignore them |
| Agent frameworks (LangGraph, MCP) | Tool routing | Adapters | No trajectory invariant engine |

Cedar and OPA are **not** product dependencies in v0.1. They are the
correct next baselines for v0.2-evidence, pinned by version, with the
same families and the same property names.

## What we may say now

- Cycle-1 implements `V(a_t | H, S, P)` for a closed local model.
- B1 implements `Policy(a_t)` on the same policy tables.
- The hero case is a differential experiment on `cumulative_budget`.
- The payment tool rejects a missing capability (`VALID_CAPABILITY_REQUIRED`).
- Several families are capability-lifecycle properties (replay, TTL,
  policy-version binding, compensation). B1 is NA there, not FAIL.

## What we must not say

- That VERITAS is a Cedar/OPA replacement.
- That `security_rate = 1.0` is a probability of security.
- That the Ed25519 envelope is a standard.
- That identity tokens are cryptographically validated (they are not).
- That the bounded SMT model proves the Python implementation.
- That we have prior-art clearance for a patent.

## Contribution boundary (until Cedar/OPA are pinned)

The only contribution we currently defend in a room:

1. Independent per-call policy is an insufficient question for
   cumulative, concurrent, and ordered tool use.
2. A trajectory-conditioned authorizer plus a mandatory capability
   boundary changes that question, and the change is measurable.
3. Where a per-call filter already answers the question (atomic limit,
   delegation depth on `a_t`), we report that win.

Everything else is infrastructure for that measurement.
