"""Localhost browser OAuth for development and CLI."""

from __future__ import annotations

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from app.core.config import oauth_listen_host, oauth_listen_port, oauth_redirect_uri
from app.core.exceptions import NotionMcpError
from app.services.oauth import complete_auth_session, start_auth_session
from app.services.token_store import apply_token_response


class _CallbackHandler(BaseHTTPRequestHandler):
    result: Dict[str, Any] = {}
    error: Optional[str] = None
    event: Optional[threading.Event] = None
    session: Dict[str, Any] = {}

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in ("/callback", "/"):
            self.send_response(404)
            self.end_headers()
            return
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        try:
            creds = complete_auth_session(self.session, query)
            self.result.clear()
            self.result.update(apply_token_response(creds, creds))
            body = b"<html><body><p>Notion connected. You can close this tab.</p></body></html>"
            self.send_response(200)
        except NotionMcpError as exc:
            self.error = exc.error_code
            body = f"<html><body><p>OAuth failed: {exc.error_code}</p></body></html>".encode()
            self.send_response(400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        if self.event:
            self.event.set()


def run_local_oauth(open_browser: bool = True) -> Dict[str, Any]:
    redirect = oauth_redirect_uri()
    session = start_auth_session(redirect)
    event = threading.Event()
    _CallbackHandler.session = session
    _CallbackHandler.result = {}
    _CallbackHandler.error = None
    _CallbackHandler.event = event

    host = oauth_listen_host()
    port = oauth_listen_port()
    server = HTTPServer((host, port), _CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if open_browser:
            webbrowser.open(session["authorization_url"])
        print(f"Open this URL if the browser does not start:\n{session['authorization_url']}")
        if not event.wait(timeout=300):
            raise NotionMcpError(
                "OAuth callback timed out after 5 minutes",
                error_code="OAUTH_TIMEOUT",
                retryable=True,
            )
        if _CallbackHandler.error:
            raise NotionMcpError(
                f"OAuth failed: {_CallbackHandler.error}",
                error_code=_CallbackHandler.error,
                retryable=False,
            )
        if not _CallbackHandler.result:
            raise NotionMcpError("OAuth completed without tokens", error_code="AUTH_ERROR")
        return dict(_CallbackHandler.result)
    finally:
        server.shutdown()
        server.server_close()
