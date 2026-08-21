// Documentation-only Cedar sketch for the unit authorization layer.
// It is intentionally not evaluated by the Cycle-1 Python runtime.
// The compiled JSON table is the executable artifact in this POC.

permit (
  principal,
  action == Veritas::Action::"payment.transfer",
  resource
)
when {
  principal.agent_id == context.agent_id &&
  context.purpose in ["invoice-payment", "supplier-payment", "benchmark"] &&
  context.delegation_depth <= 3
};

// The 24-hour aggregate invariant cannot be represented as a unit-call check here.
// It is enforced by the atomic residual reservation in the capability service.

