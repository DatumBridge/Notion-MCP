"""Safety helpers: untrusted content labels, URL allowlists, upload path jail."""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from app.core.config import credentials_dir
from app.core.exceptions import NotionValidationError

UNTRUSTED_PREFIX = "[UNTRUSTED_NOTION_CONTENT]"
UNTRUSTED_SUFFIX = "[/UNTRUSTED_NOTION_CONTENT]"

ALLOWED_OAUTH_HOST_SUFFIXES = (
    "notion.so",
    "notion.com",
    "mcp.notion.com",
)

PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def wrap_untrusted(value: Any) -> Any:
    """Mark Notion-originated payloads as untrusted for the calling model."""
    if value is None:
        return None
    if isinstance(value, str):
        if value.startswith(UNTRUSTED_PREFIX):
            return value
        return f"{UNTRUSTED_PREFIX}\n{value}\n{UNTRUSTED_SUFFIX}"
    if isinstance(value, list):
        return [wrap_untrusted(item) for item in value]
    if isinstance(value, dict):
        wrapped = {key: wrap_untrusted(item) for key, item in value.items()}
        wrapped["content_trust"] = "untrusted"
        return wrapped
    return value


def upload_dir() -> Path:
    raw = os.environ.get("NOTION_UPLOAD_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return credentials_dir()


def resolve_upload_path(file_path: str) -> Path:
    """Resolve a local upload path inside NOTION_UPLOAD_DIR (path jail)."""
    base = upload_dir()
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = (base / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise NotionValidationError(
            "file_path must be under NOTION_UPLOAD_DIR",
            original_error=exc,
        ) from exc
    return candidate


def host_allowed(hostname: str, suffixes: tuple = ALLOWED_OAUTH_HOST_SUFFIXES) -> bool:
    host = (hostname or "").lower().rstrip(".")
    if not host:
        return False
    for suffix in suffixes:
        if host == suffix or host.endswith("." + suffix):
            return True
    return False


def assert_public_https_url(url: str, *, purpose: str, host_suffixes: Optional[tuple] = None) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise NotionValidationError(f"{purpose} must be HTTPS")
    host = parsed.hostname or ""
    if host_suffixes is not None and not host_allowed(host, host_suffixes):
        raise NotionValidationError(f"{purpose} host is not allowlisted")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if any(ip in network for network in PRIVATE_NETWORKS):
        raise NotionValidationError(f"{purpose} must not target a private address")


def assert_notion_oauth_url(url: str, purpose: str) -> None:
    assert_public_https_url(url, purpose=purpose, host_suffixes=ALLOWED_OAUTH_HOST_SUFFIXES)


def assert_mcp_endpoint_url(url: str, purpose: str) -> None:
    assert_public_https_url(
        url,
        purpose=purpose,
        host_suffixes=("mcp.notion.com", "notion.com", "notion.so"),
    )


def loopback_request(host: str) -> bool:
    value = (host or "").split(":")[0].lower()
    return value in {"127.0.0.1", "localhost", "::1"}


def project_relative_token_path() -> Path:
    return credentials_dir() / "token.json"
