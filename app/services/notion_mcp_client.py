"""Streamable HTTP MCP client for Notion hosted MCP, with SSE fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import httpx

from app.core.config import (
    CLIENT_NAME,
    CLIENT_VERSION,
    USER_AGENT,
    http_timeout_sec,
    mcp_url,
    protocol_version,
    sse_url,
)
from app.core.exceptions import (
    NotionAuthError,
    NotionMcpError,
    NotionReauthRequired,
    NotionValidationError,
    normalize_provider_error,
)
from app.schemas.catalog import resolve_remote_name
from app.services import oauth
from app.services.safety import (
    assert_mcp_endpoint_url,
    assert_public_https_url,
    resolve_upload_path,
)
from app.services.token_store import (
    apply_token_response,
    load_credentials_dict,
    persist_if_path,
    token_needs_refresh,
)

_CLIENT_CACHE: Dict[str, "NotionMcpClient"] = {}
_CLIENT_CACHE_LOCK = threading.Lock()

logger = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"


def merge_arguments(
    typed: Optional[Dict[str, Any]] = None,
    extra_json: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge documented fields with extra_arguments_json. Extra keys win."""
    merged: Dict[str, Any] = {}
    if typed:
        for key, value in typed.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            merged[key] = value
    if extra_json and str(extra_json).strip():
        try:
            extra = json.loads(extra_json)
        except json.JSONDecodeError as exc:
            raise NotionValidationError(
                f"Invalid extra_arguments_json: {exc}",
                original_error=exc,
            ) from exc
        if not isinstance(extra, dict):
            raise NotionValidationError("extra_arguments_json must be a JSON object")
        merged.update(extra)
    return merged


def parse_tool_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize MCP tools/call result (content blocks + structured content)."""
    result = payload.get("result") if "result" in payload else payload
    if not isinstance(result, dict):
        return {"result": result, "content": None, "is_error": False, "parsed": result}

    is_error = bool(result.get("isError"))
    content = result.get("content") or []
    parsed: Any = result.get("structuredContent")
    if parsed is None and isinstance(content, list):
        texts = [
            block.get("text")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
        ]
        if len(texts) == 1:
            try:
                parsed = json.loads(texts[0])
            except (json.JSONDecodeError, TypeError):
                parsed = texts[0]
        elif texts:
            parsed = texts
    return {
        "result": result,
        "content": content,
        "is_error": is_error,
        "parsed": parsed,
    }


class NotionMcpClient:
    """Authenticated client for https://mcp.notion.com/mcp."""

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        credentials_json: Optional[str] = None,
        creds: Optional[Dict[str, Any]] = None,
    ):
        if creds is not None:
            self._creds = dict(creds)
        else:
            self._creds = load_credentials_dict(credentials_path, credentials_json)
        self._credentials_path = credentials_path
        self._request_id = 0
        self._session_id: Optional[str] = None
        self._initialized = False
        self._transport = "streamable-http"
        self._sse_message_url: Optional[str] = None
        self._protocol_version = protocol_version()
        self._lock = threading.Lock()

    @property
    def transport(self) -> str:
        return self._transport

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _ensure_fresh_token(self) -> None:
        if not token_needs_refresh(self._creds):
            return
        refresh = self._creds.get("refresh_token")
        client_id = self._creds.get("client_id")
        token_endpoint = self._creds.get("token_endpoint")
        if not refresh or not client_id or not token_endpoint:
            raise NotionAuthError("Access token expired and refresh is not configured")
        try:
            tokens = oauth.refresh_access_token(
                refresh_token=refresh,
                token_endpoint=token_endpoint,
                client_id=client_id,
                client_secret=self._creds.get("client_secret"),
            )
        except NotionReauthRequired:
            self._tombstone_tokens()
            raise
        self._creds = apply_token_response(self._creds, tokens)
        persist_if_path(self._credentials_path, self._creds)
        logger.info("Refreshed Notion MCP access token")

    def _auth_headers(self) -> Dict[str, str]:
        self._ensure_fresh_token()
        token = self._creds.get("access_token")
        if not token:
            raise NotionAuthError("Missing access_token")
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": self._protocol_version,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None, notify: bool = False) -> Dict[str, Any]:
        message: Dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
        if not notify:
            message["id"] = self._next_id()
        if params is not None:
            message["params"] = params
        return message

    def _post_jsonrpc(self, url: str, message: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], httpx.Response]:
        timeout = httpx.Timeout(http_timeout_sec(), read=max(http_timeout_sec(), 120))
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.post(url, headers=self._auth_headers(), json=message)
        session = response.headers.get("mcp-session-id") or response.headers.get("Mcp-Session-Id")
        if session:
            self._session_id = session
        return _decode_mcp_response(response), response

    def _tombstone_tokens(self) -> None:
        self._creds["access_token"] = ""
        self._creds["refresh_token"] = ""
        self._creds["client_secret"] = None
        self._creds["revoked"] = True
        persist_if_path(self._credentials_path, self._creds)

    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            return self._request_locked(method, params)

    def _request_locked(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.connect()
        message = self._rpc(method, params)
        try:
            payload, response = self._try_transports(message)
        except NotionReauthRequired:
            self._tombstone_tokens()
            raise
        except NotionAuthError:
            if self._creds.get("refresh_token"):
                self._force_refresh()
                self._initialized = False
                self._session_id = None
                self._sse_message_url = None
                self.connect()
                payload, response = self._try_transports(message)
            else:
                raise
        if payload is None:
            raise NotionMcpError(
                f"Empty MCP response for {method}",
                error_code="PROVIDER_ERROR",
                retryable=True,
                status_code=response.status_code,
            )
        if "error" in payload:
            err = payload["error"] or {}
            message_text = err.get("message") or str(err)
            raise normalize_provider_error(
                NotionMcpError(message_text, error_code="MCP_RPC_ERROR"),
                status_code=response.status_code,
                body_text=json.dumps(err),
            )
        return payload

    def _force_refresh(self) -> None:
        refresh = self._creds.get("refresh_token")
        client_id = self._creds.get("client_id")
        token_endpoint = self._creds.get("token_endpoint")
        if not refresh or not client_id or not token_endpoint:
            self._tombstone_tokens()
            raise NotionReauthRequired("Refresh failed; re-authentication required")
        try:
            tokens = oauth.refresh_access_token(
                refresh_token=refresh,
                token_endpoint=token_endpoint,
                client_id=client_id,
                client_secret=self._creds.get("client_secret"),
            )
        except NotionReauthRequired:
            self._tombstone_tokens()
            raise
        self._creds = apply_token_response(self._creds, tokens)
        persist_if_path(self._credentials_path, self._creds)

    def _try_transports(self, message: Dict[str, Any]) -> Tuple[Dict[str, Any], httpx.Response]:
        if self._transport == "sse" and self._sse_message_url:
            payload, response = self._post_jsonrpc(self._sse_message_url, message)
            _raise_for_http(response)
            if payload is None:
                raise NotionMcpError("Empty SSE MCP response", error_code="PROVIDER_ERROR", retryable=True)
            return payload, response
        try:
            payload, response = self._post_jsonrpc(mcp_url(), message)
            if response.status_code in (404, 405) or (
                response.status_code >= 500 and not payload
            ):
                raise NotionMcpError(
                    "Streamable HTTP unavailable",
                    error_code="TRANSPORT_FALLBACK",
                    retryable=True,
                    status_code=response.status_code,
                )
            _raise_for_http(response)
            if payload is None and message.get("id") is not None:
                raise NotionMcpError("Empty Streamable HTTP response", error_code="PROVIDER_ERROR", retryable=True)
            self._transport = "streamable-http"
            return payload or {}, response
        except (NotionMcpError, httpx.HTTPError) as exc:
            if isinstance(exc, NotionAuthError) or isinstance(exc, NotionReauthRequired):
                raise
            logger.warning("Streamable HTTP failed, falling back to SSE")
            self._initialized = False
            self._session_id = None
            self._open_sse()
            if not self._sse_message_url:
                raise
            if method_name(message) != "initialize":
                self.connect()
            payload, response = self._post_jsonrpc(self._sse_message_url, message)
            _raise_for_http(response)
            if payload is None:
                raise NotionMcpError("Empty SSE MCP response", error_code="PROVIDER_ERROR", retryable=True)
            return payload, response

    def _open_sse(self) -> None:
        timeout = httpx.Timeout(http_timeout_sec(), read=30)
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(
                sse_url(),
                headers={
                    "Authorization": self._auth_headers()["Authorization"],
                    "Accept": "text/event-stream",
                    "User-Agent": USER_AGENT,
                },
            )
        _raise_for_http(response)
        endpoint = _first_sse_endpoint(response.text)
        if not endpoint:
            raise NotionMcpError(
                "SSE transport did not return an endpoint event",
                error_code="TRANSPORT_ERROR",
                retryable=True,
            )
        message_url = urljoin(sse_url() + "/", endpoint)
        assert_mcp_endpoint_url(message_url, "SSE message endpoint")
        self._sse_message_url = message_url
        self._transport = "sse"

    def connect(self) -> None:
        if self._initialized:
            return
        init = self._rpc(
            "initialize",
            {
                "protocolVersion": self._protocol_version,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        )
        payload, response = self._try_transports(init)
        _raise_for_http(response)
        if payload.get("error"):
            raise NotionMcpError(
                str(payload["error"]),
                error_code="INITIALIZE_FAILED",
                retryable=False,
            )
        negotiated = ((payload.get("result") or {}).get("protocolVersion"))
        if negotiated:
            self._protocol_version = str(negotiated)
        notify = self._rpc("notifications/initialized", notify=True)
        try:
            self._try_transports(notify)
        except NotionMcpError:
            logger.debug("initialized notification failed; continuing")
        self._initialized = True

    def list_tools(self) -> List[Dict[str, Any]]:
        payload = self._request("tools/list", {})
        result = payload.get("result") or {}
        tools = result.get("tools") or []
        return tools if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        remote = resolve_remote_name(name)
        payload = self._request(
            "tools/call",
            {"name": remote, "arguments": arguments or {}},
        )
        parsed = parse_tool_result(payload)
        parsed["tool"] = remote
        parsed["transport"] = self._transport
        return parsed

    def fetch_self(self) -> Dict[str, Any]:
        parsed = self.call_tool("notion-fetch", {"id": "self"})
        body = parsed.get("parsed")
        if isinstance(body, dict) and isinstance(body.get("self"), dict):
            return body["self"]
        if isinstance(body, dict):
            return body
        raise NotionMcpError(
            "notion-fetch self did not return a self object",
            error_code="PROVIDER_ERROR",
            retryable=False,
        )

    def upload_local_file(self, file_path: str, extra_arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run notion-create-file-upload then POST the file as multipart/form-data."""
        path = resolve_upload_path(file_path)
        if not path.is_file():
            raise NotionValidationError(f"File not found: {file_path}")
        size = path.stat().st_size
        if size > 20 * 1024 * 1024:
            raise NotionValidationError("Local upload is limited to 20 MiB")
        args = {"filename": path.name}
        if extra_arguments:
            args.update(extra_arguments)
        created = self.call_tool("notion-create-file-upload", args)
        body = created.get("parsed") if isinstance(created.get("parsed"), dict) else {}
        upload_url = body.get("upload_url") or body.get("url")
        form_field = body.get("form_field") or body.get("file_field") or "file"
        extra_headers = body.get("headers") or {}
        if not upload_url:
            raise NotionMcpError(
                "notion-create-file-upload did not return an upload URL",
                error_code="PROVIDER_ERROR",
                retryable=False,
                original_error=created.get("parsed"),
            )
        assert_public_https_url(str(upload_url), purpose="upload_url")
        timeout = httpx.Timeout(http_timeout_sec(), read=max(http_timeout_sec(), 120))
        with path.open("rb") as handle, httpx.Client(timeout=timeout, follow_redirects=False) as client:
            files = {form_field: (path.name, handle)}
            response = client.post(upload_url, headers=dict(extra_headers), files=files)
        if not response.is_success:
            raise normalize_provider_error(
                NotionMcpError("File upload POST failed"),
                status_code=response.status_code,
                body_text=response.text[:300],
            )
        try:
            uploaded = response.json()
        except Exception:
            uploaded = {"status_code": response.status_code, "text": response.text[:500]}
        return {
            "create": created.get("parsed"),
            "upload": uploaded,
            "suggested_markdown": (uploaded.get("suggested_markdown") if isinstance(uploaded, dict) else None)
            or body.get("suggested_markdown"),
        }

    def poll_async_task(
        self,
        task_id: str,
        *,
        max_wait_sec: int = 60,
        default_interval_sec: float = 2.0,
    ) -> Dict[str, Any]:
        deadline = time.time() + max_wait_sec
        interval = default_interval_sec
        last: Dict[str, Any] = {}
        while time.time() < deadline:
            last = self.call_tool("notion-get-async-task", {"task_id": task_id})
            body = last.get("parsed") if isinstance(last.get("parsed"), dict) else {}
            status = (body.get("status") or "").lower()
            if status in ("succeeded", "failed"):
                return last
            interval = float(body.get("poll_after_seconds") or interval)
            time.sleep(max(0.5, interval))
        raise NotionMcpError(
            "Async task did not complete before timeout",
            error_code="ASYNC_TIMEOUT",
            retryable=True,
            original_error=last.get("parsed"),
        )


def method_name(message: Dict[str, Any]) -> str:
    return str(message.get("method") or "")


def client_from_credentials(
    credentials_path: Optional[str] = None,
    credentials_json: Optional[str] = None,
) -> NotionMcpClient:
    """Reuse an initialized client for the same access token within this process."""
    probe = NotionMcpClient(
        credentials_path=credentials_path,
        credentials_json=credentials_json,
    )
    token = probe._creds.get("access_token") or ""
    key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _CLIENT_CACHE_LOCK:
        cached = _CLIENT_CACHE.get(key)
        if cached is not None:
            cached._creds = probe._creds
            cached._credentials_path = credentials_path
            return cached
        _CLIENT_CACHE[key] = probe
        return probe


def _raise_for_http(response: httpx.Response) -> None:
    if response.is_success:
        return
    raise normalize_provider_error(
        NotionMcpError(f"HTTP {response.status_code}"),
        status_code=response.status_code,
        body_text=response.text[:500],
    )


def _decode_mcp_response(response: httpx.Response) -> Optional[Dict[str, Any]]:
    if response.status_code == 204 or not response.content:
        return None
    content_type = (response.headers.get("content-type") or "").lower()
    text = response.text
    if "text/event-stream" in content_type or text.lstrip().startswith("event:") or "data:" in text[:80]:
        parsed = _last_sse_json(text)
        return parsed
    try:
        data = response.json()
    except Exception as exc:
        raise NotionMcpError(
            "Invalid JSON from Notion MCP",
            error_code="PROVIDER_ERROR",
            retryable=True,
            original_error=exc,
        ) from exc
    if isinstance(data, dict):
        return data
    raise NotionMcpError("Unexpected MCP payload type", error_code="PROVIDER_ERROR")


def _iter_sse_data(text: str) -> Iterable[str]:
    block: List[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            block.append(line[5:].lstrip())
        elif line.strip() == "" and block:
            yield "\n".join(block)
            block = []
    if block:
        yield "\n".join(block)


def _last_sse_json(text: str) -> Optional[Dict[str, Any]]:
    last: Optional[Dict[str, Any]] = None
    for data in _iter_sse_data(text):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            last = parsed
    return last


def _first_sse_endpoint(text: str) -> Optional[str]:
    event_name = ""
    for line in text.splitlines():
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:") and event_name == "endpoint":
            return line[5:].strip()
        elif line.strip() == "":
            event_name = ""
    for data in _iter_sse_data(text):
        if data.startswith("/"):
            return data
    return None
