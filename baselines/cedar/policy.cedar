permit (
  principal,
  action == Action::"payment.transfer",
  resource
) when { context.amount <= 10000 };

permit (
  principal,
  action == Action::"data.read_sensitive",
  resource
);

permit (
  principal,
  action == Action::"message.send_external",
  resource
);
