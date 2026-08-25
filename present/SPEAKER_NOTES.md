# Speaker notes (under 90 seconds)

Do not open architecture slides first.

1. State the failed question: "Is 900 less than 10,000?"
2. Run `veritas demo`. Point at B1: 12 ALLOW, 10,800 spent, cumulative FAIL.
3. Point at VERITAS: 11 ALLOW, 12th DENY, 9,900 spent, cumulative PASS.
4. Point at the boundary line: direct `payment_api` call is REJECT `VALID_CAPABILITY_REQUIRED`.
5. Say: "The agent still plans. We changed the question at the tool boundary: is this step still safe given what already happened?"
6. After the terminal: "We are not trying to make the agent trustworthy. We are making execution verifiable."

If asked about Cedar or OPA: they are the next baselines, not this demo. See `docs/PRIOR_ART.md`.

If asked whether 11/11 means secure: no. It means the implemented families behaved as specified.
