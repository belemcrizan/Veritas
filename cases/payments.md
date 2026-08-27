# Payments

- Story: twelve 900 transfers against a 10,000 rolling limit.
- Threat: compositional overspend.
- Policy: `policies/payment_policy.json`
- Attack: fractionation (no recipe required for the hero; the demo is fixed).
- Expected: 11 ALLOW, 12th DENY, used 9900.
- Run: `veritas demo`
