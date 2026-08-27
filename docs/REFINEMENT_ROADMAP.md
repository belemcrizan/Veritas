# Refinement map

```text
Policy semantics          tested (JSON tables)
       ↓
Compiled representation   tested (PolicyCompiler digest)
       ↓
Authorization engine      tested (VeritasEngine)
       ↓
Reservation protocol      tested locally (SQLite CAS); unverified distributed
       ↓
Capability lifecycle      tested (issue/verify/consume); envelope not a standard
       ↓
Boundary verification     tested (ToolBoundary)
       ↓
Execution event           tested (ledger + UNKNOWN/reconcile)
```

| Relation | Status |
| --- | --- |
| JSON policy → compiled tables | tested |
| Tables → engine evaluation | tested |
| Engine → atomic reserve | tested on SQLite |
| Reserve → capability bind | tested |
| Capability → boundary | tested |
| Timeout → UNKNOWN → probe | tested |
| SMT model ↔ implementation | bounded-verified model, assumed correspondence |
| OIDC ↔ Principal | assumed trusted input |
| KMS ↔ LocalEd25519 | unverified / not implemented |
