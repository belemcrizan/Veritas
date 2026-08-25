"""Stable reason codes with two audiences: operator and engineer.

Every authorization and boundary outcome should use a code from this catalog.
Unknown codes are still fail-closed: they must never be treated as ALLOW.
"""

from __future__ import annotations

from dataclasses import dataclass

from veritas.models import AuthorizationResult, Decision


@dataclass(frozen=True)
class Reason:
    code: str
    decision: str
    operator: str
    engineer: str
    next_step: str
    retryable: bool


REASONS: dict[str, Reason] = {
    "CAPABILITY_ISSUED": Reason(
        "CAPABILITY_ISSUED",
        "ALLOW",
        "The request was checked against history, current state, and policy. A one-time pass was issued.",
        "Policy tables passed; residual reserved when required; Ed25519 capability issued.",
        "Send the capability to the tool boundary in the same request. Do not store it as a standing right.",
        False,
    ),
    "POLICY_ALLOW": Reason(
        "POLICY_ALLOW",
        "ALLOW",
        "The written rules allow this kind of action. Budget and capability steps may still follow.",
        "RuntimeVerifier produced an allow evaluation before reservation.",
        "Continue; this is an intermediate evaluation, not tool execution.",
        False,
    ),
    "COMMITTED": Reason(
        "COMMITTED",
        "ALLOW",
        "The tool ran and the reservation was recorded as spent.",
        "Boundary verified the capability, executed the tool, and committed the reservation.",
        "Treat the action as done. Repeating the same capability must fail.",
        False,
    ),
    "BUDGET_EXHAUSTED": Reason(
        "BUDGET_EXHAUSTED",
        "DENY",
        "This step would spend more than the remaining pool for that destination and window.",
        "Atomic reservation saw used + amount > limit inside BEGIN IMMEDIATE.",
        "Wait for the window to roll, raise the reviewed limit, or split work across allowed destinations.",
        False,
    ),
    "ATOMIC_LIMIT_EXCEEDED": Reason(
        "ATOMIC_LIMIT_EXCEEDED",
        "DENY",
        "A single request is larger than the per-call ceiling.",
        "B1/per-call filter compared amount to budget.limit without trajectory memory.",
        "Reduce the amount or change the reviewed policy.",
        False,
    ),
    "ACTION_NOT_ALLOWED": Reason(
        "ACTION_NOT_ALLOWED",
        "DENY",
        "This action is not on the approved list.",
        "Compiled policy has no ActionRule for asir.action.",
        "Add the action in a reviewed policy version, or stop requesting it.",
        False,
    ),
    "PURPOSE_NOT_ALLOWED": Reason(
        "PURPOSE_NOT_ALLOWED",
        "DENY",
        "The stated purpose is not one of the purposes this action may serve.",
        "asir.purpose is outside ActionRule.allowed_purposes.",
        "Use an allowed purpose string, or extend the policy after review.",
        False,
    ),
    "DELEGATION_DEPTH_EXCEEDED": Reason(
        "DELEGATION_DEPTH_EXCEEDED",
        "DENY",
        "Authority passed through too many hands before this agent.",
        "len(delegation) > max_delegation_depth.",
        "Shorten the chain or raise the reviewed depth.",
        False,
    ),
    "TEMPORAL_INVARIANT_VIOLATION": Reason(
        "TEMPORAL_INVARIANT_VIOLATION",
        "DENY",
        "An earlier step in this session makes this later step unsafe, even if each step looks fine alone.",
        "SessionStateStore.has_action matched a TemporalRule predecessor.",
        "Use a new session, drop the forbidden successor, or change the reviewed temporal rule.",
        False,
    ),
    "INVALID_ACTION_ARGUMENTS": Reason(
        "INVALID_ACTION_ARGUMENTS",
        "DENY",
        "The request is missing a required amount or destination, or uses a forbidden number format.",
        "BudgetRule.amount/resource_key raised PolicyError (floats, non-positive ints, missing keys).",
        "Send positive integer minor units and a non-empty string key.",
        False,
    ),
    "IDENTITY_MISSING": Reason(
        "IDENTITY_MISSING",
        "DENY",
        "The system cannot tell who is asking.",
        "principal.sub or principal.iss is empty after validation.",
        "Attach authentic identity from the IdP. Cycle 1 does not cryptographically validate OIDC.",
        False,
    ),
    "ACTOR_BINDING_MISSING": Reason(
        "ACTOR_BINDING_MISSING",
        "DENY",
        "The identity does not name this agent as the actor.",
        "agent_id not in principal.act.",
        "Issue an identity whose act claim lists the executing agent.",
        False,
    ),
    "APPROVAL_REQUIRED": Reason(
        "APPROVAL_REQUIRED",
        "REQUIRE_APPROVAL",
        "A person must sign this exact request before it can run.",
        "amount > approval_above and no valid approval_token.",
        "Show render_for_approval(asir) to a reviewer; attach the signed token; do not mutate the ASIR.",
        True,
    ),
    "INVALID_APPROVAL": Reason(
        "INVALID_APPROVAL",
        "REQUIRE_APPROVAL",
        "The approval does not match this exact request, or it expired.",
        "ApprovalService.verify failed (hash, expiry, signature, or nonce).",
        "Re-render the current ASIR and collect a fresh signature.",
        True,
    ),
    "VALID_CAPABILITY_REQUIRED": Reason(
        "VALID_CAPABILITY_REQUIRED",
        "DENY",
        "The tool will not run on a bare request. It needs a one-time pass from VERITAS.",
        "GuardedTool.invoke received a missing or blank capability.",
        "Call engine.authorize first and pass result.capability into the boundary.",
        False,
    ),
    "INVALID_CAPABILITY": Reason(
        "INVALID_CAPABILITY",
        "DENY",
        "The pass is damaged, forged, or bound to a different request.",
        "Envelope, signature, canonical payload, issuer kid, ASIR hash, or certificate failed.",
        "Re-authorize. Do not repair the token locally.",
        False,
    ),
    "EXPIRED_CAPABILITY": Reason(
        "EXPIRED_CAPABILITY",
        "DENY",
        "The pass was used too late, or the clocks disagree beyond the allowed skew.",
        "now is outside issued_at/expires_at ± max_clock_skew.",
        "Re-authorize with a fresh capability. Check clock skew.",
        True,
    ),
    "STALE_CAPABILITY": Reason(
        "STALE_CAPABILITY",
        "DENY",
        "The rules changed after the pass was issued.",
        "capability policy_version/digest != current compiled policy.",
        "Re-authorize under the current policy.",
        True,
    ),
    "CAPABILITY_REPLAY": Reason(
        "CAPABILITY_REPLAY",
        "DENY",
        "This pass was already used.",
        "NonceStore.consume returned False.",
        "If the first run succeeded, stop. If it failed before the tool, compensate only after confirmed non-execution.",
        False,
    ),
    "STATE_HASH_MISMATCH": Reason(
        "STATE_HASH_MISMATCH",
        "DENY",
        "The world changed between the check and the tool. The old pass is no longer valid.",
        "digest(current_state) != claims.state_hash.",
        "Refresh state and re-authorize (bounded retries), then escalate to a human.",
        True,
    ),
    "STORE_UNAVAILABLE": Reason(
        "STORE_UNAVAILABLE",
        "DENY",
        "The local ledger or budget store could not complete the check. Nothing was authorized.",
        "SQLite operational error wrapped as StoreUnavailable; fail closed.",
        "Check disk, file locks, and path. Do not retry blindly against a corrupted file.",
        True,
    ),
    "RESERVATION_INVALID": Reason(
        "RESERVATION_INVALID",
        "DENY",
        "The hold on the budget cannot be committed or released in its current state.",
        "Unknown reservation_id, compensated-then-commit, or inconsistent lifecycle.",
        "Inspect the ledger. Do not compensate on timeout alone.",
        False,
    ),
    "INVALID_POLICY": Reason(
        "INVALID_POLICY",
        "DENY",
        "The policy file cannot be used. No requests will be authorized from it.",
        "PolicyCompiler rejected JSON shape, types, or missing fields.",
        "Fix the file and run veritas policy-check. Increment version after review.",
        False,
    ),
    "INVALID_CANONICAL_VALUE": Reason(
        "INVALID_CANONICAL_VALUE",
        "DENY",
        "The request contains a number format that VERITAS refuses to hash (for example a float).",
        "canonical_json rejected a non-canonical value.",
        "Use integer minor units and JSON-serializable canonical types.",
        False,
    ),
    "B0_NO_POLICY": Reason(
        "B0_NO_POLICY",
        "ALLOW",
        "Baseline B0 has no protection: every call runs.",
        "AlwaysAllowBaseline executed the request.",
        "Use only as a comparison, never as a control.",
        False,
    ),
    "B1_CALL_OK": Reason(
        "B1_CALL_OK",
        "ALLOW",
        "Baseline B1 allowed this single call. It does not remember earlier spend.",
        "IndependentCallFilter Policy(a_t) passed.",
        "Compare with VERITAS on cumulative properties.",
        False,
    ),
    "B1_UNBOUND_APPROVAL": Reason(
        "B1_UNBOUND_APPROVAL",
        "ALLOW",
        "Baseline B1 treated approval as a yes/no flag, not a signature over this exact request.",
        "IndependentCallFilter accepted any non-empty approval_token.",
        "Do not use B1 as a production approval control.",
        False,
    ),
}


def lookup(code: str) -> Reason:
    known = REASONS.get(code)
    if known is not None:
        return known
    return Reason(
        code=code,
        decision="DENY",
        operator="An unexpected code was returned. Treat this as a refusal.",
        engineer="Code is absent from REASONS; fail closed and add it to the catalog before claiming coverage.",
        next_step="File a defect with the code, trace_id, and ledger excerpt. Do not interpret as ALLOW.",
        retryable=False,
    )


def describe_result(result: AuthorizationResult) -> dict[str, str | bool]:
    reason = lookup(result.reason_code)
    return {
        "decision": result.decision.value,
        "reason_code": result.reason_code,
        "explanation": result.explanation,
        "operator": reason.operator,
        "engineer": reason.engineer,
        "next_step": reason.next_step,
        "retryable": reason.retryable,
        "catalog_decision": reason.decision,
        "aligned": reason.decision == result.decision.value
        or (
            result.decision == Decision.STALE
            and result.reason_code in {"STALE_CAPABILITY", "STATE_HASH_MISMATCH"}
        ),
    }


def format_reason(code: str) -> str:
    reason = lookup(code)
    retry = "yes" if reason.retryable else "no"
    return "\n".join(
        [
            f"{reason.code}  ({reason.decision}, retryable={retry})",
            "",
            "For operators:",
            f"  {reason.operator}",
            "",
            "For engineers:",
            f"  {reason.engineer}",
            "",
            "What to do next:",
            f"  {reason.next_step}",
        ]
    )
