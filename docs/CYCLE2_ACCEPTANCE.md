# Cycle-2 acceptance gate

`veritas validate-cycle2` loads unittest modules and reports PASS/FAIL/PARTIAL/UNSUPPORTED without rewriting failures.

## Required suites

| Check | Module |
| --- | --- |
| Core invariants | `tests.test_runtime` |
| Canonicalization | `tests.test_canonical` |
| Security regressions | `tests.test_security` |
| Fault handling | `tests.test_fault_injection` |
| Store contracts | `tests.contracts.test_stores` |
| Policy / showcase | `tests.test_control_plane` |
| Fuzz / malformed | `tests.test_fuzz` |
| Public API | `tests.test_public_api` |
| Cycle-2 additions | `tests.test_cycle2` |

Multiprocess and crash tests run in the default `unittest discover` suite. They are not silently skipped in the acceptance command unless the module fails to import.

## Declaration rules

- All suites PASS, none skipped entirely → `EXPERIMENTALLY VALIDATED`
- Any FAIL → `NOT VALIDATED`
- Otherwise → `PARTIAL`

PostgreSQL and Redis are **not** required for a local PARTIAL declaration. Claiming distributed safety still requires those backends under load.

## Example output

```text
VERITAS CYCLE-2 ACCEPTANCE

Core invariants............... PASS
...
Cycle-2 status:
PARTIAL
```

`EXPERIMENTALLY VALIDATED` is not a production certification.
