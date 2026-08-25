# VERITAS-Bench Cycle 1

## Purpose

The benchmark is an executable falsification harness. It does not ask only whether VERITAS blocks a
request. It asks whether a family of trajectory attacks can make the supported invariant false while
the implementation authorizes the actions.

Run:

```bash
veritas bench
```

Every family receives a fresh SQLite database and deterministic clock. Cryptographic nonces and
reservation IDs are random, but the expected verdict is deterministic.

## Attack families

| Family | Scenario | Passing condition |
| --- | --- | --- |
| Atomic | One approved 11,000 transfer against a 10,000 budget | Denied by the residual limit |
| Fractionation | Twelve sequential transfers of 900 | Exactly eleven allowed; twelfth denied |
| Temporal evasion | Spend 10,000, then submit a backdated request | Backdated request denied using server time |
| Parallel double-spend | Forty threads reserve 300 against 10,000 | Exactly 33 reservations; used equals 9,900 |
| Delegation laundering | Four-hop chain against maximum depth three | Denied before reservation |
| Approval mutation | Approval signs 6,000; caller changes it to 6,500 | Mutated ASIR requires a new approval |
| Cross-tool composition | Sensitive read followed by external send | Second action denied in the same session |
| Policy race | Issue under v1, publish v2, then execute | Boundary reports stale capability |
| Clock skew | Issue with 1-second TTL and advance clock by 5 seconds | Boundary reports expiration |
| Capability replay | Execute the same token twice | Second use denied by nonce store |
| Compensation abuse | Release one prepared reservation twice | First release succeeds; second has no effect |

## Baselines

B0 and B1 are executable (`veritas.baselines`). The comparison table names the **property**
under test. PASS on B1 is kept. NA means the baseline has no corresponding control.

Cedar, OPA, and commercial gateways are **not** compared in Cycle 1. A publishable study must pin
and cite real baseline versions. That work is `v0.2-evidence`.

## Current validated result

On 2026-08-21 in the supplied Python 3.12 environment:

- Attack families: 11.
- Passing families: 11.
- Parallel case: 40 contenders, 33 successful reservations, 9,900 used.
- Hero case: 11 of 12 safe-prefix transfers passed; the violating suffix was denied.
- Automated tests: 12 passed.

Run the command on the target machine and retain its JSON. Timing is machine-dependent.

## Metrics and interpretation

### Security rate

```text
families with expected safe behavior / total defined families
```

Eleven of eleven means the known deterministic tests passed. It is not a probability of security and
does not generalize to missing attacks.

### Safe action pass rate

For the hero scenario, all eleven actions in the maximal safe prefix pass. The hybrid partition mode
can deny some globally feasible actions due to fragmentation; future benchmarks must publish that
autonomy cost by partition allocation.

### Latency

`veritas bench` durations include database creation and whole scenarios. Use:

```bash
veritas perf --iterations 5000
```

for the narrow RNF01/RNF02 measurements. Record CPU, operating system, Python version, sample count,
warm-up, and whether frequency scaling was active.

### Coordination x autonomy

The next benchmark version should sweep:

- concurrency: 1, 10, 100, and 1,000;
- CAS, partition, and hybrid modes;
- partition allocation imbalance;
- store latency and temporary unavailability;
- safe-action pass rate and serialized-decision fraction.

That curve is more informative than throughput alone.

## Adding an attack

1. State the invariant and attacker capability.
2. Define a deterministic unsafe outcome.
3. Add the attack function to `src/veritas/bench.py`.
4. Add a smaller regression test under `tests/`.
5. Show which baseline accepts it.
6. Document assumptions and any unmodeled real-world behavior.
7. Keep tool outputs deterministic or record the exact mock.

An attack that merely causes a Python exception is not automatically a pass. It passes only when no
consequential tool action occurs and the denial/failure mode matches the declared fail-closed policy.

