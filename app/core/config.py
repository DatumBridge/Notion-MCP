"""Environment configuration for the Notion MCP client."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CLIENT_NAME = "datumbridge-notion-mcp-client"
CLIENT_VERSION = "1.0.0"
USER_AGENT = f"{CLIENT_NAME}/{CLIENT_VERSION}"

DEFAULT_MCP_URL = "https://mcp.notion.com/mcp"
DEFAULT_SSE_URL = "https://mcp.notion.com/sse"
DEFAULT_MCP_ORIGIN = "https://mcp.notion.com"
DEFAULT_PROTOCOL_VERSION = "2025-03-26"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
DEFAULT_OAUTH_HOST = "127.0.0.1"
DEFAULT_OAUTH_PORT = 8765
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_REFRESH_SKEW_SEC = 300

# Official hosted MCP discovery file (unofficial mcp.json convention).
NOTION_MCP_JSON_URL = "https://www.notion.com/.well-known/mcp.json"
SUPPORTED_TOOLS_DOC = "https://developers.notion.com/guides/mcp/mcp-supported-tools"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def mcp_url() -> str:
    return os.environ.get("NOTION_MCP_URL", DEFAULT_MCP_URL).rstrip("/")


def sse_url() -> str:
    return os.environ.get("NOTION_MCP_SSE_URL", DEFAULT_SSE_URL).rstrip("/")


def mcp_origin() -> str:
    return os.environ.get("NOTION_MCP_ORIGIN", DEFAULT_MCP_ORIGIN).rstrip("/")


def protocol_version() -> str:
    return os.environ.get("NOTION_MCP_PROTOCOL_VERSION", DEFAULT_PROTOCOL_VERSION)


def oauth_redirect_uri() -> str:
    return os.environ.get("OAUTH_REDIRECT_URI", DEFAULT_REDIRECT_URI)


def oauth_listen_host() -> str:
    return os.environ.get("OAUTH_LISTEN_HOST", DEFAULT_OAUTH_HOST)


def oauth_listen_port() -> int:
    raw = os.environ.get("OAUTH_LISTEN_PORT", str(DEFAULT_OAUTH_PORT))
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_OAUTH_PORT


def oauth_client_name() -> str:
    return os.environ.get("NOTION_OAUTH_CLIENT_NAME", "DatumBridge Notion MCP Client")


def http_timeout_sec() -> int:
    raw = os.environ.get("NOTION_HTTP_TIMEOUT_SEC", str(DEFAULT_TIMEOUT_SEC))
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_TIMEOUT_SEC


def token_refresh_skew_sec() -> int:
    raw = os.environ.get("NOTION_TOKEN_REFRESH_SKEW_SEC", str(DEFAULT_REFRESH_SKEW_SEC))
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_REFRESH_SKEW_SEC


def credentials_dir() -> Path:
    raw = os.environ.get("NOTION_CREDENTIALS_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return project_root()


def studio_public_url() -> str:
    return os.environ.get("STUDIO_PUBLIC_URL", "http://localhost:30080").rstrip("/")
