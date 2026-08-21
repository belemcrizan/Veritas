# ADR-001: Canonical ASIR Contract

- Status: Accepted for POC
- Date: 2026-08-21

## Context

Capabilities and approvals must bind to the same action across processes and languages. Ordinary
JSON permits multiple byte representations of the same logical object, and floating-point rendering
can differ.

## Decision

Use frozen Pydantic models and a deterministic JSON subset containing string-keyed objects, arrays,
strings, booleans, null, integers, and UTC timestamps. Reject floats. Hash canonical UTF-8 bytes with
SHA-256.

## Consequences

The POC has stable hashes for its schemas and avoids monetary rounding ambiguity. It must not claim
full RFC 8785 compatibility until it passes the RFC test corpus and defines Unicode handling across
languages.

