# VERITAS Documentation

VERITAS is an experimental Python library and research prototype for trajectory-aware authorization
of autonomous agents. It places a verifiable execution boundary between an agent and consequential
tools such as payment APIs, databases, messaging systems, and infrastructure controls.

## Start here

- New to the project: [Getting Started](GETTING_STARTED.md)
- Integrating the library: [Public API](API_REFERENCE.md)
- Preparing a package or release: [Library and Release Guide](LIBRARY_RELEASE_GUIDE.md)
- Reviewing security assumptions: [Threat Model](THREAT_MODEL.md)
- Reproducing the evidence: [Validation Report](VALIDATION_REPORT.md)

## Current scope

The Cycle-2 prototype keeps Cycle-1 enforcement and adds a control-plane layer: identity and key
abstractions, lifecycle and reconciliation, shadow/audit modes, policy lint/diff/simulate, showcase
demos, and a reference HTTP gateway. PostgreSQL, Redis, and cloud KMS are not implemented.

It is research and evaluation software, not a production security control. The package remains
pre-1.0 and uses a provisional license while prior-art and intellectual-property decisions are
pending.
