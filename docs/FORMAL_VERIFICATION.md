# Formal Verification Scope

## What exists today

The repository contains two bounded checks:

1. A dependency-free function that constructs the twelve-by-900 counterexample against a unit-call
   filter.
2. `formal/resource_invariant.smt2`, which asks Z3 whether all twelve calls can be individually below
   10,000 while their sum exceeds 10,000. The expected result is `sat`.

With development dependencies installed, run:

```bash
python tools/check_smt.py
```

The script also constructs the residual transition system and asks whether twelve authorized 900
steps can leave every residual non-negative. The expected result is `unsat`.

## What `sat` and `unsat` mean here

- `sat` for the unit filter supplies a concrete unsafe trajectory inside the bounded integer model.
- `unsat` for the residual model means no assignment satisfies all encoded constraints at depth 12.

It does not prove that the Python, SQLite, cryptography, clock, or deployment correctly implements
the model. That requires a refinement argument and evidence connecting code transitions to model
transitions.

## Proof obligations for the research claim

The intended trajectory-safety statement should explicitly connect:

1. **Policy artifact:** reviewed source compiles to a runtime table and SMT model with the same
   meaning.
2. **Prepare linearization:** every successful reservation corresponds to exactly one monotonic
   resource transition.
3. **Capability containment:** issued scope is a subset of the compiled allow set and is bound to the
   successful reservation.
4. **Boundary refinement:** every tool execution corresponds to one valid, current, unconsumed
   capability.
5. **Lifecycle:** commit, compensation, expiry, and crash recovery cannot create residual.
6. **Composition:** temporal and relational transitions preserve their declared state invariants.

## Recommended next model

Use a small transition system with states:

```text
(residual, reservations, consumed_nonces, policy_version, session_automaton)
```

Transitions:

```text
Prepare, Issue, BoundaryVerify, Execute, Commit, Compensate, Expire, PublishPolicy
```

Safety properties:

- residual is never negative;
- live partition residuals plus central residual never exceed the global residual;
- one capability produces at most one execution;
- old-policy capabilities never execute after publication;
- forbidden temporal states are unreachable.

Model crashes between every pair of writes. Without crash states, the compensation argument is
incomplete.

## Cedar and compilation

`policies/cedar/payment.cedar` illustrates unit authorization only. The aggregate invariant is not
delegated to Cedar. A future compiler should produce:

- a signed runtime table;
- a Cedar artifact for unit and relational checks;
- an SMT formula for consistency and bounded reachability;
- one shared semantic test corpus.

Until that compiler exists, the JSON policy is the executable source of truth and the Cedar file is
documentation only.

