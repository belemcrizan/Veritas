"""Realistic local workloads. Sandbox data only."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

from veritas.guarded import GuardedTool
from veritas.models import ASIR, Decision, Principal, RequestContext
from veritas.runtime import bundled_policy_path, create_local_runtime
from veritas.scenarios import DEFAULT_TIME, action_asir


def _asir(action: str, session_id: str, parameters: dict[str, Any], resource: str = "local") -> ASIR:
    agent_id = "ops-agent-01"
    return ASIR(
        agent_id=agent_id,
        principal=Principal(sub="user:alice", iss="https://idp.example", act=(agent_id,)),
        delegation=("user:alice", agent_id),
        action=action,
        resource=resource,
        parameters=parameters,
        purpose="benchmark",
        labels={"data_sensitivity": "restricted"},
        context=RequestContext(session_id=session_id, request_ts=DEFAULT_TIME),
    )


def run_sql_workload(directory: Path) -> dict[str, Any]:
    """Execute real SQL after authorization. SQLite stands in for local Postgres-shaped data."""

    db = directory / "customers.db"
    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, pii INTEGER);
        INSERT INTO customers VALUES (1, 'Ada', 'ada@example.test', 1);
        INSERT INTO customers VALUES (2, 'Public', 'public@example.test', 0);
        """
    )
    connection.commit()
    runtime = create_local_runtime(database_path=directory / "veritas.db", policy_path=bundled_policy_path())

    def select_public(_asir: ASIR) -> dict[str, Any]:
        rows = connection.execute("SELECT id, name FROM customers WHERE pii = 0").fetchall()
        return {"rows": rows}

    read = runtime.engine.authorize(
        action_asir("data.read_sensitive", session_id="sql-exfil"),
        current_state={},
        idempotency_key="sql-read",
    )
    if read.decision is Decision.ALLOW and read.capability:
        GuardedTool(runtime.boundary, select_public).invoke(
            action_asir("data.read_sensitive", session_id="sql-exfil"),
            capability=read.capability,
            current_state={},
            trace_id=read.trace_id,
        )
    send = runtime.engine.authorize(
        action_asir("message.send_external", session_id="sql-exfil"),
        current_state={},
        idempotency_key="sql-send",
    )
    connection.close()
    return {
        "read": read.decision.value,
        "export": send.decision.value,
        "export_reason": send.reason_code,
        "property_held": read.decision is Decision.ALLOW and send.decision is Decision.DENY,
        "note": "SQL ran against a local sandbox database, not a mocked Python dict",
    }


def run_git_workload(directory: Path) -> dict[str, Any]:
    repo = directory / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("ok\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=lab@example.test", "-c", "user.name=lab", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    runtime = create_local_runtime(database_path=directory / "git.db", policy_path=bundled_policy_path())
    read_asir = _asir("data.read_sensitive", "git-sess", {"path": "README.md"})
    read = runtime.engine.authorize(read_asir, current_state={}, idempotency_key="git-read")
    if read.decision is Decision.ALLOW and read.capability:
        GuardedTool(
            runtime.boundary,
            lambda asir: {"text": (repo / "README.md").read_text(encoding="utf-8")},
        ).invoke(read_asir, capability=read.capability, current_state={}, trace_id=read.trace_id)
    send = runtime.engine.authorize(
        action_asir("message.send_external", session_id="git-sess"),
        current_state={},
        idempotency_key="git-send",
    )
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo, check=True, capture_output=True, text=True
    )
    return {
        "repo_commits": len(log.stdout.strip().splitlines()),
        "read": read.decision.value,
        "external_after_read": send.decision.value,
        "property_held": send.decision is Decision.DENY,
        "note": "Git operations are real; merge/approval SoD is still a composition demo",
    }


def run_email_workload(directory: Path) -> dict[str, Any]:
    captured: list[dict[str, str]] = []

    def send_mail(asir: ASIR) -> dict[str, Any]:
        captured.append({"to": str(asir.parameters.get("to", "ext@example.test")), "body": "summary"})
        return {"queued": True}

    runtime = create_local_runtime(database_path=directory / "mail.db", policy_path=bundled_policy_path())
    read = runtime.engine.authorize(
        action_asir("data.read_sensitive", session_id="mail"),
        current_state={},
        idempotency_key="mail-read",
    )
    if read.decision is Decision.ALLOW and read.capability:
        GuardedTool(runtime.boundary, lambda asir: {"pii": True}).invoke(
            action_asir("data.read_sensitive", session_id="mail"),
            capability=read.capability,
            current_state={},
            trace_id=read.trace_id,
        )
    outbound = action_asir(
        "message.send_external",
        session_id="mail",
        parameters={"to": "ext@example.test"},
    )
    send = runtime.engine.authorize(outbound, current_state={}, idempotency_key="mail-send")
    if send.decision is Decision.ALLOW and send.capability:
        GuardedTool(runtime.boundary, send_mail).invoke(
            outbound, capability=send.capability, current_state={}, trace_id=send.trace_id
        )
    return {
        "read": read.decision.value,
        "send": send.decision.value,
        "captured": captured,
        "property_held": send.decision is Decision.DENY and not captured,
        "note": "Class-II temporal invariant: PII read then external send",
    }


def run_export_workload(directory: Path) -> dict[str, Any]:
    received: list[bytes] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            received.append(self.rfile.read(length))
            self.send_response(204)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        runtime = create_local_runtime(
            database_path=directory / "export.db", policy_path=bundled_policy_path()
        )
        read = runtime.engine.authorize(
            action_asir("data.read_sensitive", session_id="export"),
            current_state={},
            idempotency_key="export-read",
        )
        export = runtime.engine.authorize(
            action_asir("message.send_external", session_id="export"),
            current_state={},
            idempotency_key="export-http",
        )
        (directory / "export.json").write_text(
            json.dumps({"blocked": export.decision.value}), encoding="utf-8"
        )
        return {
            "http_port": server.server_address[1],
            "read": read.decision.value,
            "http_export_decision": export.decision.value,
            "bytes_received": sum(len(item) for item in received),
            "property_held": export.decision is Decision.DENY,
            "note": "Not general DLP; composition enforcement inside the VERITAS session model",
        }
    finally:
        server.shutdown()


def run_all_workloads() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="veritas-work-") as directory:
        root = Path(directory)
        sql_dir = root / "sql"
        sql_dir.mkdir()
        git_dir = root / "git"
        git_dir.mkdir()
        mail_dir = root / "mail"
        mail_dir.mkdir()
        export_dir = root / "export"
        export_dir.mkdir()
        return {
            "sql": run_sql_workload(sql_dir),
            "git": run_git_workload(git_dir),
            "email": run_email_workload(mail_dir),
            "export": run_export_workload(export_dir),
        }
