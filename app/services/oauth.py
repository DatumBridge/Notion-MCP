"""OAuth 2.0 + PKCE for Notion hosted MCP (RFC 9470, 8414, 7591, 7636)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode, urlparse

import httpx

from app.core.config import (
    USER_AGENT,
    http_timeout_sec,
    mcp_url,
    oauth_client_name,
)
from app.core.exceptions import (
    NotionAuthError,
    NotionMcpError,
    NotionReauthRequired,
    NotionValidationError,
    normalize_provider_error,
)
from app.services.safety import assert_notion_oauth_url

logger = logging.getLogger(__name__)

_REFRESH_LOCK = threading.Lock()


def _timeout() -> float:
    return float(http_timeout_sec())


def _headers() -> Dict[str, str]:
    return {"Accept": "application/json", "User-Agent": USER_AGENT}


def base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_code_verifier() -> str:
    return base64url_encode(secrets.token_bytes(32))


def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64url_encode(digest)


def generate_state() -> str:
    return secrets.token_hex(32)


def _well_known_protected_resource(resource_url: str) -> str:
    parsed = urlparse(resource_url)
    return f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource"


def _well_known_auth_server(issuer: str) -> str:
    parsed = urlparse(issuer if "://" in issuer else f"https://{issuer}")
    path = parsed.path.rstrip("/")
    if path and path != "/":
        return f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-authorization-server{path}"
    return f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-authorization-server"


def discover_oauth_metadata(resource_url: Optional[str] = None) -> Dict[str, Any]:
    """RFC 9470 protected-resource metadata, then RFC 8414 authorization server metadata."""
    target = resource_url or mcp_url()
    protected_url = _well_known_protected_resource(target)
    try:
        with httpx.Client(timeout=_timeout(), headers=_headers(), follow_redirects=False) as client:
            protected_resp = client.get(protected_url)
            if not protected_resp.is_success:
                raise NotionMcpError(
                    f"Failed to fetch protected resource metadata: {protected_resp.status_code}",
                    error_code="OAUTH_DISCOVERY_FAILED",
                    retryable=protected_resp.status_code >= 500,
                    status_code=protected_resp.status_code,
                )
            protected = protected_resp.json()
            auth_servers = protected.get("authorization_servers") or []
            if not isinstance(auth_servers, list) or not auth_servers:
                raise NotionMcpError(
                    "No authorization servers in protected resource metadata",
                    error_code="OAUTH_DISCOVERY_FAILED",
                    retryable=False,
                )
            issuer = str(auth_servers[0])
            metadata_url = _well_known_auth_server(issuer)
            metadata_resp = client.get(metadata_url)
            if not metadata_resp.is_success:
                raise NotionMcpError(
                    f"Failed to fetch authorization server metadata: {metadata_resp.status_code}",
                    error_code="OAUTH_DISCOVERY_FAILED",
                    retryable=metadata_resp.status_code >= 500,
                    status_code=metadata_resp.status_code,
                )
            metadata = metadata_resp.json()
    except NotionMcpError:
        raise
    except Exception as exc:
        raise normalize_provider_error(exc) from exc

    if not metadata.get("authorization_endpoint") or not metadata.get("token_endpoint"):
        raise NotionMcpError(
            "Authorization server metadata missing required endpoints",
            error_code="OAUTH_DISCOVERY_FAILED",
            retryable=False,
        )
    assert_notion_oauth_url(metadata["authorization_endpoint"], "authorization_endpoint")
    assert_notion_oauth_url(metadata["token_endpoint"], "token_endpoint")
    if metadata.get("registration_endpoint"):
        assert_notion_oauth_url(metadata["registration_endpoint"], "registration_endpoint")
    methods = metadata.get("code_challenge_methods_supported") or []
    if "S256" not in methods:
        logger.warning("Authorization server does not advertise S256 PKCE; using S256 anyway")
    metadata["_protected_resource"] = protected
    metadata["_issuer"] = issuer
    return metadata


def register_client(metadata: Dict[str, Any], redirect_uri: str) -> Dict[str, Any]:
    """RFC 7591 dynamic client registration (public client, PKCE)."""
    endpoint = metadata.get("registration_endpoint")
    if not endpoint:
        raise NotionMcpError(
            "Server does not support dynamic client registration",
            error_code="OAUTH_REGISTRATION_UNSUPPORTED",
            retryable=False,
        )
    body = {
        "client_name": oauth_client_name(),
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    try:
        with httpx.Client(timeout=_timeout(), headers=_headers(), follow_redirects=False) as client:
            response = client.post(
                endpoint,
                json=body,
                headers={"Content-Type": "application/json", **_headers()},
            )
            if not response.is_success:
                raise NotionMcpError(
                    f"Client registration failed: {response.status_code}",
                    error_code="OAUTH_REGISTRATION_FAILED",
                    retryable=response.status_code >= 500,
                    status_code=response.status_code,
                    original_error=response.text[:500],
                )
            credentials = response.json()
    except NotionMcpError:
        raise
    except Exception as exc:
        raise normalize_provider_error(exc) from exc

    if not credentials.get("client_id"):
        raise NotionMcpError(
            "Registration response missing client_id",
            error_code="OAUTH_REGISTRATION_FAILED",
            retryable=False,
        )
    return credentials


def build_authorization_url(
    metadata: Dict[str, Any],
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
    scopes: Optional[list] = None,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "consent",
    }
    if scopes:
        params["scope"] = " ".join(scopes)
    return f"{metadata['authorization_endpoint']}?{urlencode(params)}"


def parse_callback_params(query: Dict[str, str]) -> Tuple[str, str]:
    if query.get("error"):
        desc = query.get("error_description") or "Unknown error"
        raise NotionAuthError(f"OAuth error: {query['error']} - {desc}")
    code = query.get("code")
    state = query.get("state")
    if not code:
        raise NotionValidationError("Missing authorization code")
    if not state:
        raise NotionValidationError("Missing state parameter")
    return code, state


def exchange_code_for_tokens(
    *,
    code: str,
    code_verifier: str,
    metadata: Dict[str, Any],
    client_id: str,
    redirect_uri: str,
    client_secret: Optional[str] = None,
) -> Dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    return _token_request(metadata["token_endpoint"], data)


def refresh_access_token(
    *,
    refresh_token: str,
    metadata: Optional[Dict[str, Any]] = None,
    token_endpoint: Optional[str] = None,
    client_id: str,
    client_secret: Optional[str] = None,
) -> Dict[str, Any]:
    endpoint = token_endpoint or (metadata or {}).get("token_endpoint")
    if not endpoint:
        raise NotionValidationError("token_endpoint is required to refresh")
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if client_secret:
        data["client_secret"] = client_secret
    with _REFRESH_LOCK:
        return _token_request(endpoint, data)


def _token_request(endpoint: str, data: Dict[str, str]) -> Dict[str, Any]:
    assert_notion_oauth_url(endpoint, "token_endpoint")
    try:
        with httpx.Client(timeout=_timeout(), headers=_headers(), follow_redirects=False) as client:
            response = client.post(
                endpoint,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    **_headers(),
                },
            )
            body_text = response.text
            if not response.is_success:
                try:
                    err = response.json()
                except Exception:
                    err = {}
                error_code = err.get("error") if isinstance(err, dict) else None
                if error_code == "invalid_grant":
                    raise NotionReauthRequired(original_error=body_text[:300])
                if error_code == "invalid_client":
                    raise NotionAuthError(
                        "Invalid OAuth client credentials",
                        original_error=body_text[:300],
                        error_code="INVALID_CLIENT",
                    )
                raise NotionAuthError(
                    f"Token request failed: {response.status_code}",
                    original_error=body_text[:300],
                )
            tokens = response.json()
    except NotionMcpError:
        raise
    except Exception as exc:
        raise normalize_provider_error(exc) from exc

    if not tokens.get("access_token"):
        raise NotionValidationError("Token response missing access_token")
    return tokens


def start_auth_session(redirect_uri: str) -> Dict[str, Any]:
    """Discover, register, and return values the callback must keep secret."""
    metadata = discover_oauth_metadata()
    registration = register_client(metadata, redirect_uri)
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    state = generate_state()
    auth_url = build_authorization_url(
        metadata,
        registration["client_id"],
        redirect_uri,
        challenge,
        state,
    )
    return {
        "authorization_url": auth_url,
        "state": state,
        "code_verifier": verifier,
        "client_id": registration["client_id"],
        "client_secret": registration.get("client_secret"),
        "redirect_uri": redirect_uri,
        "token_endpoint": metadata["token_endpoint"],
        "authorization_endpoint": metadata["authorization_endpoint"],
        "registration_endpoint": metadata.get("registration_endpoint"),
        "metadata": {
            "authorization_endpoint": metadata["authorization_endpoint"],
            "token_endpoint": metadata["token_endpoint"],
            "registration_endpoint": metadata.get("registration_endpoint"),
        },
    }


def complete_auth_session(session: Dict[str, Any], query: Dict[str, str]) -> Dict[str, Any]:
    code, state = parse_callback_params(query)
    stored_state = session.get("state") or ""
    if not stored_state or not hmac.compare_digest(state, stored_state):
        raise NotionAuthError("Invalid state parameter - possible CSRF attack")
    tokens = exchange_code_for_tokens(
        code=code,
        code_verifier=session["code_verifier"],
        metadata=session.get("metadata") or {"token_endpoint": session["token_endpoint"]},
        client_id=session["client_id"],
        redirect_uri=session["redirect_uri"],
        client_secret=session.get("client_secret"),
    )
    return {
        "type": "oauth",
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "token_type": tokens.get("token_type", "Bearer"),
        "expires_in": tokens.get("expires_in"),
        "scope": tokens.get("scope"),
        "user_id": tokens.get("user_id"),
        "workspace_id": tokens.get("workspace_id"),
        "email_domain": tokens.get("email_domain"),
        "client_id": session["client_id"],
        "client_secret": session.get("client_secret"),
        "token_endpoint": session["token_endpoint"],
    }


def load_pending_session(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_pending_session(path: str, session: Dict[str, Any]) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile_path(directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(session, handle)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def tempfile_path(directory: str) -> Tuple[int, str]:
    import tempfile

    fd, name = tempfile.mkstemp(prefix=".notion-oauth.", dir=directory)
    return fd, name
