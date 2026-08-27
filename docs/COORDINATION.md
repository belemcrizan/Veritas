# PostgreSQL and Redis coordination notes

## PostgreSQL

`PostgresAdapter` uses `REPEATABLE READ` plus `pg_advisory_xact_lock(hashtextextended(resource_key, 0))` before computing `used` and inserting a PREPARED row.

Assumptions:

- one database; honest clocks
- lock hash collisions are theoretically possible and untested at scale
- this is not Raft/Spanner

Atomicity: reserve is one transaction. Commit/compensate are separate transactions. A crash after PREPARED leaves budget reserved until compensate or commit — same as SQLite.

## Redis

`RedisNonceStore` is SET NX with TTL. It is **not** a budget store.

PostgreSQL/SQLite already provide durable single-use nonces. Redis is only interesting if nonce TTL eviction is an operational requirement. For the rolling budget invariant, SQL is sufficient.

## Comparison

| Property | SQLite | PostgreSQL | Redis |
| --- | --- | --- | --- |
| Committed+Prepared ≤ budget | yes, one file | yes, advisory lock | no |
| Single-use nonce | yes | yes | yes (ephemeral) |
| Multi-process same machine | WAL, tested small N | designed for this | n/a for budget |
