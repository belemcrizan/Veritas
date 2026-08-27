# Red team guide

Try to falsify VERITAS. Do not ask the LLM to decide ALLOW/DENY.

## Cooperative-boundary assumption

If the agent can call the tool without `GuardedTool` / the HTTP/MCP gateway, **the property does not hold**. Demonstrate that first.

## Suggested attacks

1. Direct Python call to the unprotected function.
2. Replay a consumed capability.
3. Mutate ASIR after approval.
4. Two processes, one residual 900.
5. Kill -9 after reserve, restart, spend again.
6. Timeout after the tool actually ran; check duplicate execution.
7. Publish a new policy between issue and execute.
8. Delegation cycle / forged issuer.
9. Mutate a ledger payload and see if `ledger-verify` fails.
10. Send external after a sensitive read in the same session.
11. Malformed capability, huge integers, empty destination, duplicate idempotency keys.
12. Shadow mode: confirm the real action still happens and budget is not reserved.

## What a counterexample looks like

A short transcript: inputs, observed decision, leftover budget, and which claim it breaks (`docs/SECURITY_CLAIMS.md`).
