# Getting Started

This guide assumes you are comfortable opening a terminal but does not assume prior knowledge of
agent security, formal methods, cryptography, or SQLite.

## 1. Understand the idea before running code

Imagine a payment agent that may transfer at most 10,000 to one destination in 24 hours.

A normal filter can check one request:

```text
Is 900 less than 10,000? Yes, allow it.
```

That answer is locally correct but globally unsafe. Twelve concurrent agents can each request 900.
Every request passes the individual check, but the trajectory spends 10,800.

VERITAS keeps a residual. The first authorized 900 changes it from 10,000 to 9,100. The next changes
it to 8,200. The update is atomic, so two agents cannot both spend the same residual. The twelfth
request sees only 100 left and is denied.

## 2. Prerequisites

- Python 3.12 or newer.
- A terminal: PowerShell, Command Prompt, Bash, or a VS Code terminal.
- Internet access once, only if `pydantic` and `cryptography` must be installed.
- Optional: Docker Desktop.

You do not need an LLM, cloud account, database server, API key, or agent framework.

Check Python:

```bash
python --version
```

On Windows, use `py -3.12 --version` if `python` points to another version.

## 3. Create an isolated environment

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Linux/macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

`-e` means editable mode: changes to `src/` are immediately visible without reinstalling.

## 4. Run the hero scenario

```bash
veritas doctor
veritas demo
```

`doctor` must print `healthy` before you trust any other command on a new machine. If a command fails, it prints JSON on stderr with a `code`. Explain it with `veritas reasons <CODE>`.

The default output is a human differential table: B1 vs VERITAS on the same 12×900
attack, plus a direct tool call without a capability. JSON remains available:

```bash
veritas demo --json
```

Read these fields first:

- B1 `spent: 10800` and `cumulative_budget: FAIL`: per-call policy is the wrong question.
- VERITAS `allowed: 11`, `twelfth_decision: DENY`, `spent: 9900`: trajectory-conditioned authorization.
- `direct_tool_call_without_capability.rejected: true`: the tool is a boundary, not an advisor.

This is important: a secure system that denies everything is useless. VERITAS measures security
and safe autonomy together.

## 5. Run the adversarial benchmark

```bash
veritas bench
```

The first block is B0 / B1 / VERITAS with **named properties**. PASS on B1 is a baseline win.
NA means that baseline has no corresponding control — it is not scored as a VERITAS victory.

```bash
veritas bench --json
```

The benchmark creates a fresh temporary database for each attack. It checks:

1. A single oversized action.
2. Fractionation into individually safe actions.
3. Backdating to escape the time window.
4. Parallel double-spend.
5. Delegation laundering.
6. Mutation after human approval.
7. Unsafe cross-tool composition.
8. Policy version race.
9. Expiration and clock skew.
10. Capability replay.
11. Duplicate compensation.

`families_passed` must equal `families_total`. A pass means the expected safety behavior occurred;
it does not prove safety outside the modeled scope.

## 6. Run tests and focused performance checks

```bash
python -m unittest discover -s tests -v
veritas perf --iterations 1000
```

The performance command intentionally measures two narrow scopes:

- The compiled policy lookup, excluding storage and the tool.
- Signature and canonical-envelope verification, excluding nonce persistence and the tool.

Do not compare the whole attack duration to the `<5 ms` policy target. The attack duration includes
database setup, ledger writes, signing, and sometimes forty threads.

## 7. Inspect and change the policy

Open `policies/payment_policy.json`. The key rule is:

```json
"budget": {
  "name": "money",
  "amount_parameter": "amount",
  "key_parameter": "destination",
  "limit": 10000,
  "window_seconds": 86400
}
```

Interpretation:

- Read the action's `amount` parameter.
- Group consumption by `destination`.
- Keep the sum at or below 10,000.
- Count prepared and committed reservations inside the prior 86,400 seconds.

Compile and inspect the policy:

```bash
veritas policy-check policies/payment_policy.json
```

The output includes a stable policy digest and a twelve-step counterexample against a unit-call
filter.

When changing a policy, update its version. An already-issued capability with the old version will
then fail at the tool boundary with `STALE_CAPABILITY`.

## 8. Persist and inspect a local ledger

By default, the demo uses a temporary database. To retain it:

```bash
veritas demo --database .veritas/demo.db
veritas ledger-verify .veritas/demo.db
```

The second command recomputes every node identifier and checks that every parent existed before its
child. It should return `{"integrity": true}`.

## 9. Read the code in execution order

1. `src/veritas/scenarios.py` creates an ASIR.
2. `src/veritas/engine.py` records, evaluates, reserves, and signs.
3. `src/veritas/adapters/sqlite.py` serializes residual updates.
4. `src/veritas/crypto.py` creates the one-time capability.
5. `src/veritas/boundary.py` verifies and executes.
6. `src/veritas/bench.py` attacks the composition.

## Troubleshooting

### `ModuleNotFoundError: veritas`

Install the project with `python -m pip install -e .`, or run directly with:

```bash
PYTHONPATH=src python -m veritas demo
```

PowerShell equivalent:

```powershell
$env:PYTHONPATH = "src"
python -m veritas demo
```

### PowerShell will not activate the environment

Use `.venv\Scripts\python.exe` directly. Activation is a convenience, not a requirement.

### SQLite says the database is locked

The adapter waits up to 30 seconds. Keep the database on a local disk and do not share one SQLite
file across hosts. Delete no file while the demo is running.

### Performance target is not met

Repeat after warm-up, close heavy applications, record CPU/OS/Python version, and publish the full
distribution. Do not remove slow samples merely to meet a target.

