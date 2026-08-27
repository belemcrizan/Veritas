# Scorecard (honest, 0–10)

Scores below 9 include why, evidence, and the next improvement. This is not a marketing sheet.

| Dimension | Score | Why / evidence | Next improvement |
| --- | --- | --- | --- |
| Conceptual novelty | 8 | Trajectory + reservation + capability is distinctive; not a new crypto primitive | Publish with prior-art discipline |
| Architecture | 8 | Ports, engine, boundary, gateways | Real second backend |
| Implementation quality | 7 | Typed local runtime; some new modules are thin | Harden HTTP, persist lifecycle |
| Security model | 8 | Threat model + claim registry | Independent review |
| Formal rigor | 6 | One bounded SMT artifact | Expand models; never call them proofs |
| Concurrency | 7 | Threaded SQLite tests and showcase race | Measure 100/1000 workers |
| Distributed correctness | 3 | No Postgres/Redis | Real adapter + contracts |
| Identity | 5 | Structural verifier + allowlists | OIDC/SPIFFE |
| Cryptography | 5 | Ed25519 POC envelope | Reviewed capability format + KMS |
| Policy engineering | 7 | lint/diff/simulate/counterexamples | DSL only if tested |
| Integrations | 6 | LangGraph/MCP shapes, HTTP reference | Pin real SDKs |
| Observability | 5 | In-process counters, redaction | Optional OTel exporter |
| Operability | 6 | doctor, init, showcase, gateway | Packaging and runbooks |
| Testing | 8 | Unit, contract, showcase, faults | Broader fault matrix |
| Adversarial testing | 8 | Original 11 families kept | New families as separate benches |
| Failure handling | 7 | Fail closed + UNKNOWN | Crash recovery |
| Demonstrability | 9 | demo, explain, showcase | Keep claims modest |
| Developer experience | 8 | pip install + veritas doctor/demo | One-command Docker showcase |
| Enterprise readiness | 3 | Explicit production gap | Do not skip honesty |
| Scientific reproducibility | 8 | Scripts, versions, local benches | Pin machine metadata in published runs |
| Documentation | 8 | Layered docs + gap register | Keep claims matched to tests |
