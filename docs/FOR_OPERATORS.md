# VERITAS for operators and reviewers

This page is for people who decide whether an agent may move money, send mail, or change
infrastructure. You do not need to read Python.

## What this product is

VERITAS sits **between** an AI agent and a tool that can cause real harm. The agent may still plan.
The tool will not run unless VERITAS has checked this request against:

1. the written rules (policy);
2. what already happened (trajectory);
3. the current world (state);
4. who is asking (identity and delegation).

If the check passes, the tool receives a **one-time pass** (a capability), valid for seconds, for
that exact request. Using the same pass twice fails. Changing the amount after a human signed it
fails.

## What this product is not

It is **not** an antivirus for language models, a cloud dashboard, or a finished production control.
Treat Cycle 1 as a **runnable instrument**: you can reproduce attacks and see which rule stopped
them. You cannot yet drop it in front of a bank core and claim certification.

## The story in one minute

A rule says: *no more than 10,000 to one destination in 24 hours*.

An agent sends **twelve transfers of 900**. Each transfer is under 10,000. Together they move 10,800.

A filter that only looks at *this* transfer allows all twelve. VERITAS keeps a remaining pool. After
eleven transfers, 9,900 is used. The twelfth is refused. A call that tries to hit the payment tool
**without** a pass is also refused.

Run it:

```bash
veritas demo
```

Then:

```bash
veritas bench
```

You should see a table of named attacks. **PASS** on a baseline (B1) is expected for some rows: a
simple per-call limit *can* stop a single oversized transfer. VERITAS is for the attacks that only
show up when you remember history.

## How to read a decision

Every outcome has a **reason code** (stable spelling) plus two explanations: one for you, one for
engineers.

```bash
veritas reasons
veritas reasons BUDGET_EXHAUSTED
```

| You see | Meaning | Typical next step |
| --- | --- | --- |
| ALLOW / `CAPABILITY_ISSUED` | This exact step is still safe | Tool may run once with the pass |
| DENY / `BUDGET_EXHAUSTED` | Remaining pool is too small | Do not retry the same spend |
| REQUIRE_APPROVAL | A person must sign this exact request | Show the reviewer the rendered request |
| Tool error `VALID_CAPABILITY_REQUIRED` | Someone tried to skip VERITAS | Fix the integration; do not weaken the tool |

Unknown codes are **refusals**. Never treat an undocumented code as permission.

## Health check

```bash
veritas doctor
```

This only checks that *this computer* can compile the bundled policy and write a local database. It
does not mean the system is secure.

## What “11/11 passed” means

It means the eleven attacks **encoded in this repository** behaved as designed. It does **not** mean
the system is 100% secure, formally proven, or ready for production.

## If something looks wrong

1. Copy the reason code and the `trace_id`.
2. Run `veritas reasons <CODE>`.
3. If you have a saved database: `veritas ledger-verify path/to/veritas.db`.
4. Hand the engineer `docs/FOR_ENGINEERS.md`.

Further reading: [Getting Started](GETTING_STARTED.md) (how to install) · [Threat model](THREAT_MODEL.md) · [What we do not claim](../README.md#assumptions-and-what-is-not-claimed)
