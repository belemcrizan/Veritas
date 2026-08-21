# Validation Report

- Artifact version: 0.1.0
- Validation date: 2026-08-21
- Runtime: Python 3.12.13
- Scope: local POC in the supplied isolated work environment

## Executed checks

### Portability

Command:

```bash
python tools/check_portability.py
```

Result: `PASS`. No AWS, Azure, or GCP SDK import was found outside `src/veritas/adapters/`.

### Automated tests

Command:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Result: 12 tests passed in approximately 1.1 seconds. Covered deterministic hashing, float rejection,
calibration mass, singleton conformal sets, bounded fractionation, capability replay, concurrent CAS,
hybrid residual preservation, intervention replay, state mutation, framework normalization, and the
twelve-transfer trajectory.

### Hero scenario

Command:

```bash
PYTHONPATH=src python -m veritas demo
```

Result:

| Measure | Observed |
| --- | ---: |
| Authorized transfers | 11 |
| Denied transfers | 1 |
| Used rolling budget | 9,900 |
| Twelfth decision | DENY |
| Ledger integrity | true |

### Adversarial benchmark

Command:

```bash
PYTHONPATH=src python -m veritas bench
```

Result: 11 of 11 defined attack families passed. The parallel scenario produced 33 successful
reservations of 300 from 40 concurrent attempts, with total used equal to 9,900.

### Focused microbenchmarks

Command:

```bash
PYTHONPATH=src python -m veritas perf --iterations 1000
```

Observed snapshot:

| Scope | p95 | Target | Result |
| --- | ---: | ---: | --- |
| Compiled policy lookup | 0.001425 ms | < 5 ms | Met |
| Ed25519 envelope verification | 0.312123 ms | < 1 ms | Met |

These values exclude SQLite, ledger I/O, nonce persistence, network, and tool execution. They are a
single local snapshot, not a statistically controlled publication result.

## Not executed in this environment

- The optional Z3 script, because `z3-solver` was not installed in the base runtime. The SMT-LIB model,
  dependency declaration, and CI command are included.
- Docker image build, because container-engine availability was not part of the validation runtime.
- Cloud conformance, because cloud adapters and credentials are intentionally outside Cycle 1.

## Validation conclusion

The artifact is internally consistent and runnable as a local research POC. It demonstrates the
intended composition/concurrency mechanism and records known gaps. This report is not a security
certification, formal proof of implementation, production-readiness finding, or cloud parity claim.

