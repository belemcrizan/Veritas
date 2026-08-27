"""Reference HTTP execution gateway over the existing domain. Not a second VERITAS."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from veritas.models import ASIR, Decision
from veritas.reconcile import ProbeResult, Reconciler
from veritas.runtime import LocalRuntime
from veritas.scenarios import deterministic_tool


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


def make_gateway_handler(runtime: LocalRuntime) -> type[BaseHTTPRequestHandler]:
    reconciler = Reconciler(budgets=runtime.budget_store, ledger=runtime.store, clock=runtime.clock)

    class VeritasGatewayHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "enforcement": runtime.engine.enforcement_mode.value,
                    },
                )
                return
            if parsed.path.startswith("/decisions/"):
                trace_id = parsed.path.removeprefix("/decisions/")
                self._send(
                    HTTPStatus.OK, {"trace_id": trace_id, "nodes": runtime.store.trace(trace_id)}
                )
                return
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                body = _read_json(self)
            except ValueError as exc:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            if parsed.path == "/authorize":
                asir = ASIR.model_validate(body["asir"])
                result = runtime.engine.authorize(
                    asir,
                    current_state=body.get("current_state") or {},
                    idempotency_key=str(body["idempotency_key"]),
                    approval_token=body.get("approval_token"),
                    trace_id=body.get("trace_id"),
                )
                self._send(
                    HTTPStatus.OK,
                    {
                        "decision": result.decision.value,
                        "reason_code": result.reason_code,
                        "explanation": result.explanation,
                        "trace_id": result.trace_id,
                        "capability": result.capability,
                        "cap_id": result.cap_id,
                        "residual": result.residual,
                        "hypothetical_decision": result.hypothetical_decision,
                        "enforcement_mode": result.enforcement_mode,
                    },
                )
                return
            if parsed.path == "/execute":
                asir = ASIR.model_validate(body["asir"])
                capability = body.get("capability")
                if not isinstance(capability, str) or not capability:
                    self._send(
                        HTTPStatus.FORBIDDEN,
                        {"error": "VALID_CAPABILITY_REQUIRED", "decision": Decision.DENY.value},
                    )
                    return
                committed = runtime.boundary.execute(
                    capability,
                    asir=asir,
                    current_state=body.get("current_state") or {},
                    tool=deterministic_tool,
                    trace_id=str(body.get("trace_id") or "http"),
                )
                self._send(
                    HTTPStatus.OK,
                    {
                        "cap_id": committed.cap_id,
                        "trace_id": committed.trace_id,
                        "commit_status": committed.commit_status,
                        "tool_output": committed.tool_output,
                    },
                )
                return
            if parsed.path == "/commit":
                reservation_id = str(body["reservation_id"])
                runtime.budget_store.commit(reservation_id)
                self._send(HTTPStatus.OK, {"reservation_id": reservation_id, "status": "COMMITTED"})
                return
            if parsed.path == "/reconcile":
                probe_value = ProbeResult(str(body.get("probe", ProbeResult.UNRESOLVED.value)))
                recon = reconciler.reconcile(
                    reservation_id=body.get("reservation_id"),
                    trace_id=str(body.get("trace_id") or "http-reconcile"),
                    probe=lambda: probe_value,
                )
                self._send(
                    HTTPStatus.OK,
                    {
                        "status": recon.status.value,
                        "phase": recon.phase.value,
                        "committed": recon.committed,
                        "compensated": recon.compensated,
                    },
                )
                return
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    return VeritasGatewayHandler


def serve_gateway(runtime: LocalRuntime, *, host: str = "127.0.0.1", port: int = 8080) -> None:
    handler = make_gateway_handler(runtime)
    server = ThreadingHTTPServer((host, port), handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
