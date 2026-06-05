"""Minimal health HTTP server so the agent (a Pub/Sub pull worker) is Cloud Run-deployable.

Cloud Run expects the container to listen on ``$PORT``; the agent's real work is a background pull
loop, so this serves only ``/health`` and ``/ready`` on a daemon thread.
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        if self.path in ("/health", "/ready"):
            body = b'{"status":"ok","service":"agent"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args: object) -> None:
        """Silence the default stderr access log (structured logging is elsewhere)."""


def start_health_server() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
