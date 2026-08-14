#!/usr/bin/env python3
"""Browser OAuth 2.0 + PKCE against Notion hosted MCP.

Usage:
    python scripts/oauth_connect.py
    # token.json is written to the project root
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import project_root
from app.core.exceptions import NotionMcpError
from app.services.local_oauth import run_local_oauth
from app.services.token_store import apply_token_response, save_credentials


def main() -> int:
    try:
        creds = run_local_oauth()
    except NotionMcpError as exc:
        print(f"Error: {exc.error_code}: {exc.message}")
        return 1
    path = project_root() / "token.json"
    save_credentials(path, apply_token_response(creds, creds))
    print(f"Success. Token saved to {path}")
    print("Use credentials_path=token.json on MCP tools or: python -m app.cli whoami")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
