# Security Policy

VERITAS is research code. Do not place it in front of production payments, databases, messaging
systems, or other consequential tools.

## Reporting

Report suspected vulnerabilities privately to the repository owner. Include the affected commit,
attack prerequisites, reproduction steps, observed impact, and any proposed mitigation. Do not
open a public issue while the repository remains under pre-publication review.

## Never use in production

- The deterministic local development signing seed.
- The POC-specific signed envelope as a substitute for reviewed PASETO.
- Structural identity checks as a substitute for OIDC/SPIFFE signature and audience validation.
- In-memory partition state for durable authorization.
- SQLite on a network filesystem or as a multi-region consensus system.

The complete assumptions and gaps are documented in [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

