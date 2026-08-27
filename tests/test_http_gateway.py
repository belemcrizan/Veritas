from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from veritas.http_gateway import make_gateway_handler
from veritas.runtime import bundled_policy_path, create_local_runtime


class HTTPGatewayTests(unittest.TestCase):
    def test_health_and_malformed_body(self) -> None:
        with tempfile.TemporaryDirectory(prefix="veritas-http-") as directory:
            runtime = create_local_runtime(
                database_path=Path(directory) / "g.db",
                policy_path=bundled_policy_path(),
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_gateway_handler(runtime))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            conn = None
            try:
                host, port = server.server_address
                conn = HTTPConnection(str(host), int(port), timeout=2)
                conn.request("GET", "/health")
                health = json.loads(conn.getresponse().read().decode("utf-8"))
                self.assertEqual(health["status"], "ok")
                conn.request(
                    "POST",
                    "/authorize",
                    body=b"not-json",
                    headers={"Content-Length": "8", "Content-Type": "application/json"},
                )
                response = conn.getresponse()
                self.assertEqual(response.status, 400)
            finally:
                if conn is not None:
                    conn.close()
                server.shutdown()
                server.server_close()
