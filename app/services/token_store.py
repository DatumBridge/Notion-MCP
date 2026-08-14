"""Load, validate, and persist Notion OAuth tokens without logging secrets."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import credentials_dir, token_refresh_skew_sec
from app.core.exceptions import NotionMcpError, NotionValidationError

REQUIRED_TOKEN_FIELDS = ("access_token",)


def resolve_credentials_path(credentials_path: str) -> Path:
    """Resolve credentials_path inside NOTION_CREDENTIALS_DIR (path jail)."""
    base = credentials_dir()
    candidate = Path(credentials_path)
    if not candidate.is_absolute():
        candidate = (base / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        candidate.relative_to(base)
    except ValueError as e:
        raise NotionValidationError(
            "credentials_path must be under NOTION_CREDENTIALS_DIR",
            original_error=e,
        ) from e
    return candidate


def load_credentials_dict(
    credentials_path: Optional[str] = None,
    credentials_json: Optional[str] = None,
) -> Dict[str, Any]:
    if not credentials_path and not credentials_json:
        raise NotionMcpError(
            "Credentials required: provide credentials_path or credentials_json",
            error_code="CREDENTIALS_REQUIRED",
            retryable=False,
        )
    try:
        if credentials_json:
            data = json.loads(credentials_json)
        else:
            path = resolve_credentials_path(credentials_path or "")
            if not path.exists():
                raise NotionMcpError(
                    "Credentials file not found",
                    error_code="CREDENTIALS_REQUIRED",
                    retryable=False,
                )
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
    except NotionMcpError:
        raise
    except json.JSONDecodeError as e:
        raise NotionValidationError(
            "Invalid credentials JSON",
            original_error=e,
        ) from e
    except OSError as e:
        raise NotionMcpError(
            "Unable to read credentials file",
            error_code="INVALID_CREDENTIALS",
            retryable=False,
            original_error=e,
        ) from e

    if not isinstance(data, dict):
        raise NotionValidationError("Credentials must be a JSON object")

    token = data.get("access_token") or data.get("token")
    if not token:
        raise NotionValidationError("Credentials must include access_token")
    data = dict(data)
    data["access_token"] = token
    return data


def token_needs_refresh(creds: Dict[str, Any], now: Optional[float] = None) -> bool:
    if not creds.get("refresh_token"):
        return False
    expires_at = creds.get("expires_at")
    if expires_at is None:
        return False
    try:
        expiry = float(expires_at)
    except (TypeError, ValueError):
        return False
    current = time.time() if now is None else now
    return current >= (expiry - token_refresh_skew_sec())


def apply_token_response(
    creds: Dict[str, Any],
    token_response: Dict[str, Any],
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Merge a token endpoint response. Persist rotated refresh_token atomically."""
    updated = dict(creds)
    access = token_response.get("access_token")
    if not access:
        raise NotionValidationError("Token response missing access_token")
    updated["access_token"] = access
    updated["token_type"] = token_response.get("token_type", "Bearer")
    if token_response.get("refresh_token"):
        updated["refresh_token"] = token_response["refresh_token"]
    expires_in = token_response.get("expires_in")
    if expires_in is not None:
        try:
            updated["expires_at"] = int((now if now is not None else time.time()) + int(expires_in))
            updated["expires_in"] = int(expires_in)
        except (TypeError, ValueError):
            pass
    for identity_key in ("user_id", "workspace_id", "email_domain"):
        if token_response.get(identity_key) and not updated.get(identity_key):
            updated[identity_key] = token_response[identity_key]
    if token_response.get("scope"):
        updated["scope"] = token_response["scope"]
    return updated


def save_credentials(path: Path, creds: Dict[str, Any]) -> None:
    """Write credentials with 0600 permissions using a temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(creds, indent=2, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".notion-token.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def persist_if_path(credentials_path: Optional[str], creds: Dict[str, Any]) -> None:
    if not credentials_path:
        return
    save_credentials(resolve_credentials_path(credentials_path), creds)
