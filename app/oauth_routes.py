"""Browser OAuth routes for local test UI and optional Studio callback."""

from __future__ import annotations

import hmac
import logging
import os
import time
import urllib.parse
from typing import Any, Dict

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.config import oauth_redirect_uri, studio_public_url
from app.core.exceptions import NotionMcpError
from app.services.oauth import complete_auth_session, start_auth_session
from app.services.safety import loopback_request, project_relative_token_path
from app.services.token_store import apply_token_response, save_credentials

logger = logging.getLogger(__name__)

_PENDING: Dict[str, Dict[str, Any]] = {}


def _header_matches(expected: str, got: str) -> bool:
    if not expected or not got:
        return False
    return hmac.compare_digest(expected, got)


def _service_auth_ok(request: Request) -> bool:
    expected = os.environ.get("MCP_SERVICE_API_KEY", "").strip()
    if expected:
        got_key = request.headers.get("X-API-Key", "").strip()
        auth = request.headers.get("Authorization", "").strip()
        bearer = auth[7:].strip() if auth.startswith("Bearer ") else ""
        return _header_matches(expected, got_key) or _header_matches(expected, bearer)
    if os.environ.get("NOTION_OAUTH_ALLOW_ANONYMOUS", "").strip() in {"1", "true", "yes"}:
        return True
    host = request.client.host if request.client else ""
    return loopback_request(host)


def _http_redirect_uri(request: Request) -> str:
    """Use an explicit env URI, otherwise this process's /oauth/callback."""
    if os.environ.get("OAUTH_REDIRECT_URI"):
        return oauth_redirect_uri()
    return str(request.base_url).rstrip("/") + "/oauth/callback"


def _prune_pending() -> None:
    now = time.time()
    expired = [key for key, value in _PENDING.items() if value.get("expires_at", 0) < now]
    for key in expired:
        _PENDING.pop(key, None)


async def oauth_info_route(request: Request):
    return JSONResponse(
        {
            "redirect_uri": _http_redirect_uri(request),
            "provider": "notion",
            "mcp_url": "https://mcp.notion.com/mcp",
        }
    )


async def oauth_start_route(request: Request):
    if not _service_auth_ok(request):
        return JSONResponse(
            {"error_code": "UNAUTHORIZED", "error_message": "service authentication required"},
            status_code=401,
        )
    try:
        session = start_auth_session(_http_redirect_uri(request))
    except NotionMcpError as exc:
        logger.error("oauth start failed: %s", exc.error_code)
        return JSONResponse(exc.to_dict(), status_code=503)
    _prune_pending()
    _PENDING[session["state"]] = {**session, "expires_at": time.time() + 600}
    if request.query_params.get("format") == "redirect":
        return RedirectResponse(session["authorization_url"], status_code=302)
    return JSONResponse(
        {
            "auth_url": session["authorization_url"],
            "provider": "notion",
        }
    )


async def oauth_callback(request: Request):
    query = {key: request.query_params.get(key, "") for key in request.query_params}
    state = query.get("state", "")
    session = _PENDING.pop(state, None)
    if not session:
        return HTMLResponse(
            "<html><body><p>OAuth session expired or state mismatch. Restart Connect.</p></body></html>",
            status_code=400,
        )
    try:
        creds = complete_auth_session(session, query)
        creds = apply_token_response(creds, creds)
    except NotionMcpError as exc:
        logger.error("oauth callback failed: %s", exc.error_code)
        studio = studio_public_url()
        if os.environ.get("STUDIO_PUBLIC_URL"):
            return RedirectResponse(
                f"{studio}/account/integrations?notion=error&reason={urllib.parse.quote(exc.error_code)}",
                status_code=302,
            )
        return HTMLResponse(
            f"<html><body><p>OAuth failed: {exc.error_code}</p></body></html>",
            status_code=400,
        )

    persist = os.environ.get("NOTION_OAUTH_PERSIST_TOKEN", "").strip() in {"1", "true", "yes"}
    if persist:
        save_credentials(project_relative_token_path(), creds)
        saved = " Token saved under NOTION_CREDENTIALS_DIR. Use credentials_path=token.json."
    else:
        saved = (
            " Token was not written to disk. Re-run python scripts/oauth_connect.py "
            "to persist token.json for tool calls."
        )

    studio = studio_public_url()
    if os.environ.get("STUDIO_PUBLIC_URL"):
        return RedirectResponse(f"{studio}/account/integrations?notion=connected", status_code=302)

    return HTMLResponse(
        "<html><body><p>Notion connected. You can close this tab.</p>"
        f"<p>{saved}</p></body></html>"
    )
