#!/usr/bin/env python3
"""Synthetic OAuth 2.0 token endpoint for the lab. Client Credentials only."""

from __future__ import annotations

import base64
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

CLIENT_ID = os.environ.get("LAB_OAUTH_CLIENT_ID", "lab-client")
CLIENT_SECRET = os.environ.get("LAB_OAUTH_CLIENT_SECRET", "lab-secret")
ACCESS_TOKEN = os.environ.get("LAB_OAUTH_ACCESS_TOKEN", "lab-access-token")
EXPIRES_IN = int(os.environ.get("LAB_OAUTH_EXPIRES_IN", "3600"))


class TokenHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        super().log_message(format, *args)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/oauth/token":
            self._json(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        params = {key: values[0] if values else "" for key, values in parse_qs(raw, keep_blank_values=True).items()}
        grant_type = params.get("grant_type", "")
        client_id, client_secret = self._client_credentials(params)
        if grant_type != "client_credentials":
            self._json(400, {"error": "unsupported_grant_type"})
            return
        if not client_id or not client_secret:
            self._json(400, {"error": "invalid_request"})
            return
        if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
            self._json(401, {"error": "invalid_client"})
            return
        self._json(
            200,
            {
                "access_token": ACCESS_TOKEN,
                "token_type": "Bearer",
                "expires_in": EXPIRES_IN,
            },
        )

    def do_GET(self):
        self._json(405, {"error": "invalid_request"})

    def _client_credentials(self, params: dict[str, str]) -> tuple[str, str]:
        client_id = params.get("client_id", "")
        client_secret = params.get("client_secret", "")
        header = self.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:]).decode("utf-8")
                basic_id, basic_secret = decoded.split(":", 1)
                client_id = client_id or basic_id
                client_secret = client_secret or basic_secret
            except (ValueError, UnicodeDecodeError):
                return client_id, client_secret
        return client_id, client_secret

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9090), TokenHandler).serve_forever()
