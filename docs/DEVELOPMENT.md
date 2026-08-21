# Development Guide

## Principles

1. Domain modules must not import cloud SDKs.
2. Every safety-relevant state transition needs a stable reason code and ledger event.
3. No floating-point resource accounting.
4. The solver remains outside the runtime path.
5. Missing identity, policy, state, key, or store behavior must never result in tool execution.
6. A new feature must either strengthen the thesis or replace equivalent scope.
7. Consumer code imports only from `veritas`; internal adapter imports are not a compatibility contract.

## Public API changes

The supported experimental API is defined by `src/veritas/api.py`, re-exported by
`src/veritas/__init__.py`, and listed in `veritas.__all__`.

When adding or changing a public symbol:

1. implement the behavior in the appropriate domain or runtime module;
2. export it from `src/veritas/api.py`;
3. re-export it from `src/veritas/__init__.py` and add it to `__all__`;
4. document it in `docs/API_REFERENCE.md`;
5. add or update `tests/test_public_api.py`;
6. update `examples/library_integration.py` when the primary workflow changes;
7. record the compatibility impact in `CHANGELOG.md`;
8. select the next semantic version before release.

Do not place infrastructure construction logic directly in `__init__.py`. Keep it in runtime or
factory modules and use the public facade only to expose supported names.

## Local workflow

```bash
python -m pip install -e .[dev]
make quality
make bench
make perf
```

The core tests use `unittest` so the safety suite can run with only runtime dependencies. Development
extras add Hypothesis, mypy, pytest, ruff, and Z3 for the next verification layer.

## Test layers

| Layer | Location | Current purpose |
| --- | --- | --- |
| Unit | `tests/` | Canonicalization, gate, policy, token lifecycle |
| Concurrency | `tests/test_runtime.py` | Atomic residual under parallel writers |
| Adversarial | `src/veritas/bench.py` | Eleven complete attack stories |
| Formal | `formal/`, `tools/check_smt.py` | Bounded counterexample and residual safety model |
| Portability | `tools/check_portability.py` | Prevent cloud imports in domain code |
| Conformance | Future `tests/conformance/` | Same semantics for every store, signer, ledger, and identity adapter |

## Adding a policy action

1. Add the action to `policies/payment_policy.json`.
2. Decide its allowed purposes and maximum delegation depth.
3. If it consumes a monotonic resource, define integer amount and key parameters, limit, and window.
4. Add temporal predecessor rules only when session semantics are explicit.
5. Increment the policy version.
6. Run `veritas policy-check` and tests.
7. Add at least one safe and one unsafe trajectory.

Do not encode raw probability as a subtractive resource. Money, call count, exported bytes, and
expected loss with a declared additive model are appropriate Class-I resources. Probability and
delegation depth belong to other invariant classes.

## Adding an infrastructure adapter

1. Implement the relevant protocol in `src/veritas/ports.py`.
2. Put vendor imports under `src/veritas/adapters/` only.
3. Preserve atomicity, idempotency, time-window, and error semantics.
4. Run the local adapter's conformance tests unchanged.
5. Add fault injection for timeout, retry, duplicate request, and stale version.
6. Document consistency assumptions and the exact service configuration required.

A cloud transaction API is not automatically linearizable for the VERITAS operation. The proof
obligation includes the full read-sum-conditional-write transition or an equivalent materialized
counter.

## Adding a tool integration

Keep credentials inside the tool process or its secret adapter. The agent supplies only ASIR and a
capability. The integration should:

- compute current preconditions itself;
- verify immediately before the consequential operation;
- use a tool-level idempotency key;
- expose a status endpoint for compensation recovery;
- record a hashed output and commit acknowledgement;
- reject direct routes that bypass middleware.

## Coding rules

- Python 3.12 type syntax.
- Pydantic frozen models for signed contracts.
- Integer minor units for budgets.
- Timezone-aware UTC datetimes.
- Stable reason codes; human explanations may evolve.
- No secrets, tokens, or full sensitive payloads in logs or ledger nodes.
- Explicit `Partial` documentation when a protocol obligation is not implemented.

## Release checklist

- Tests and all benchmark families pass on a clean environment.
- Performance report includes machine metadata and raw samples.
- Policy and formal artifacts have stable digests.
- Threat model and traceability matrix match the code.
- Dependency hashes, SBOM, and vulnerability scan are attached.
- Container and release artifacts are signed.
- IP/publication decision is recorded before the repository becomes public.
- Development seed and approval issuer are impossible to enable in production configuration.
- Public imports, the executable library example, and `veritas.__all__` agree.
- `python -m mkdocs build --strict` succeeds after installing the `docs` extra.
- Wheel and source distribution pass `python -m twine check dist/*`.
- The wheel is imported and exercised outside the repository.
- TestPyPI/PyPI publication remains disabled until the IP and license gate is approved.

See [Library and Release Guide](LIBRARY_RELEASE_GUIDE.md) for exact commands and file locations.
