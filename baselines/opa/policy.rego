package veritas.b1

default allow := false

allow if {
  input.action == "payment.transfer"
  input.amount <= 10000
}

allow if {
  input.action == "data.read_sensitive"
}

allow if {
  input.action == "message.send_external"
}
