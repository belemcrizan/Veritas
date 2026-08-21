# ADR-004: POC Ed25519 Envelope Before PASETO

- Status: Temporary
- Date: 2026-08-21

## Context

The design target is PASETO v4.public, but adding an unreviewed third-party implementation solely to
label the token “PASETO” would obscure rather than reduce protocol risk.

## Decision

Implement a small canonical Ed25519 signed envelope with an explicit `veritas.v1` prefix. Document
that it is not PASETO and isolate it behind `CapabilityCodec`.

## Consequences

The POC can test binding, expiration, policy race, state mutation, and replay now. Production work is
blocked until a reviewed standardized format replaces this envelope and interoperability vectors pass.

