# Refinement map

Maps the bounded resource invariant to code. This is not an implementation proof.

| Formal state | Python | Store | Transaction | Test |
| --- | --- | --- | --- | --- |
| Prepared(r) | `Reservation.status == PREPARED` | `reservations.status` | SQLite `BEGIN IMMEDIATE` / PG advisory lock | contract overspend |
| Committed(r) | `commit()` | status `COMMITTED` | same connection as status check | `test_commit_is_idempotent` |
| Compensated(r) | `compensate()` | status `COMPENSATED` | no release of COMMITTED | compensation family |
| Used(W) | `used()` | SUM PREPARED+COMMITTED in window | under lock | multiprocess |
| Nonce consumed | `consume()` | PRIMARY KEY / SET NX | insert conflict | replay family |
| UNKNOWN | `OutcomeUnknown` | reservation remains PREPARED | no auto compensate | timeout test |

## Gaps

- Formal SMT model does not include PostgreSQL locking or process crash.
- Hybrid/partition budget modes are in-process overlays, not a distributed protocol.
- Ledger hash chain is tamper-evident locally, not an external checkpoint.
