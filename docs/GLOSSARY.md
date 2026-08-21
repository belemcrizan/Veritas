# Glossary

| Term | Plain-language meaning |
| --- | --- |
| Action | One consequential operation requested by an agent, such as transferring money. |
| Agent | Software that selects and requests actions, potentially using an LLM. |
| ASIR | Agent Safety Intermediate Representation: the normalized, validated description of an action. |
| Atomic operation | An operation that other concurrent callers observe as happening all at once. |
| Boundary | Code next to a protected tool that refuses execution without a valid capability. |
| Capability | A short-lived, signed, narrowly scoped authorization that can be consumed once. |
| CAS | Compare-and-swap; a conditional update used to serialize competing reservations. SQLite `BEGIN IMMEDIATE` is the stronger local reference mechanism used here. |
| Canonical JSON | One deterministic byte representation of the same structured value, needed for stable hashes and signatures. |
| Certificate | Compact metadata that binds a capability to the compiled policy artifact. It is not a general theorem proof in this POC. |
| Commit | The point where the protected tool has executed and its reservation becomes permanent consumption. |
| Compensation | Safe release of a prepared reservation after confirmed non-execution. |
| Conformal prediction | A method that forms prediction sets with a coverage guarantee under stated assumptions and sufficient calibration data. |
| Content address | An identifier derived from the hash of content. Changing content changes the identifier. |
| Delegation | The chain of principals and agents through which authority reaches the executing agent. |
| Double-spend | Two concurrent actions consuming the same residual resource. |
| Fail-closed | Missing or unverifiable safety information results in no authorization. |
| HITL | Human in the loop; a person must review or approve before execution. |
| Idempotent | Repeating the same operation produces no additional effect. |
| Invariant | A property that must remain true for every authorized point in a trajectory. |
| Ledger | Append-only, hash-linked audit records of observations, decisions, capabilities, and commits. |
| Nonce | A unique value used to detect reuse of a capability or approval. |
| Partition | A pre-allocated share of a global resource assigned to an agent or region. |
| Policy race | A capability is issued under one policy and used after another policy becomes current. |
| Prepare | Atomically reserve resources before issuing a capability. |
| Residual | The safe amount remaining after prior prepared or committed consumption. |
| Replay | Reusing a consumed capability, or deterministically re-running an audit trace for analysis. Context distinguishes the meanings. |
| State hash | A hash of tool-visible preconditions that makes a capability stale when the state changes. |
| SMT | Satisfiability modulo theories; solver technology used for bounded policy checks outside the runtime path. |
| Tool | A consequential API or function an agent wants to call. |
| Trajectory | The ordered and concurrent collection of actions produced by one or more agents. |
| WYSIWYS | What You See Is What You Sign: human approval is bound to the exact deterministic ASIR rendering. |

