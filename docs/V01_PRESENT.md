# v0.1-present freeze

VERITAS `v0.1-present` exists only when all five exit criteria are true.
After that: freeze. The next tag is `v0.2-evidence`, not more features.

## Exit criteria

1. **B1 is executable** and appears beside VERITAS (`veritas demo`, `veritas bench`).
2. **Hero demo is human**, reproducible, and shorter than 90 seconds.
3. **Execution boundary is real**: `GuardedTool` raises `VALID_CAPABILITY_REQUIRED` if the tool is invoked without a capability.
4. **Eleven families have named properties.** The comparison table records PASS / FAIL / NA. Baseline wins are kept.
5. **Prior-art memo exists** (`docs/PRIOR_ART.md`) and states what we may still call a contribution.

## Frozen

- No dashboard, cloud, LLM, distributed database, extra agents, or extra domains.
- SMT stays off the hot path.
- Cedar/OPA stay out of the product. They enter as pinned baselines in v0.2-evidence.

## Commands

```bash
veritas demo
veritas demo --json
veritas bench
veritas bench --json
veritas doctor
veritas reasons
```

## Stage lines (do not improvise)

1. The agent still plans. We changed the question at the tool boundary: is this step still safe given what already happened?
2. We are not trying to make the agent trustworthy. We are making execution verifiable.
