"""Normalized errors for the Notion MCP client."""

from __future__ import annotations

from typing import Any, Optional


class NotionMcpError(Exception):
    """Base error for Notion MCP operations."""

    def __init__(
        self,
        message: str,
        error_code: str = "NOTION_MCP_ERROR",
        retryable: bool = False,
        original_error: Optional[Any] = None,
        status_code: Optional[int] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.retryable = retryable
        self.original_error = original_error
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "error_message": self.message,
            "retryable": self.retryable,
            "original_provider_error": str(self.original_error)
            if self.original_error
            else None,
        }


class NotionAuthError(NotionMcpError):
    def __init__(
        self,
        message: str = "Token expired, invalid, or re-authentication required",
        original_error: Optional[Any] = None,
        error_code: str = "AUTH_ERROR",
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            retryable=True,
            original_error=original_error,
        )


class NotionReauthRequired(NotionMcpError):
    def __init__(
        self,
        message: str = "Re-authentication required (invalid_grant)",
        original_error: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="REAUTH_REQUIRED",
            retryable=False,
            original_error=original_error,
        )


class NotionNotFoundError(NotionMcpError):
    def __init__(
        self,
        message: str = "Resource not found",
        original_error: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            retryable=False,
            original_error=original_error,
        )


class NotionPermissionError(NotionMcpError):
    def __init__(
        self,
        message: str = "Permission denied",
        original_error: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            retryable=False,
            original_error=original_error,
        )


class NotionRateLimitError(NotionMcpError):
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        original_error: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT",
            retryable=True,
            original_error=original_error,
        )


class NotionValidationError(NotionMcpError):
    def __init__(
        self,
        message: str,
        original_error: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            retryable=False,
            original_error=original_error,
        )


class NotionUpgradeRequired(NotionMcpError):
    def __init__(
        self,
        message: str = "Workspace plan must be upgraded to use this tool",
        original_error: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="UPGRADE_REQUIRED",
            retryable=False,
            original_error=original_error,
        )


def normalize_provider_error(
    exc: Exception,
    status_code: Optional[int] = None,
    body_text: str = "",
) -> NotionMcpError:
    """Map HTTP / Notion MCP failures to a stable error object."""
    if isinstance(exc, NotionMcpError) and exc.error_code not in (
        "NOTION_MCP_ERROR",
        "UNKNOWN_ERROR",
    ):
        return exc

    combined = f"{status_code or ''} {body_text} {exc}".lower()

    if "invalid_grant" in combined:
        return NotionReauthRequired(original_error=exc)
    if "upgrade" in combined and ("required" in combined or "prompt" in combined):
        return NotionUpgradeRequired(original_error=exc)
    if status_code == 401 or "unauthorized" in combined or "invalid_token" in combined:
        return NotionAuthError(original_error=exc)
    if status_code == 403 or "permission" in combined or "forbidden" in combined:
        return NotionPermissionError(original_error=exc)
    if (
        status_code == 404
        or "object_not_found" in combined
        or "not found" in combined
    ):
        return NotionNotFoundError(original_error=exc)
    if status_code == 429 or "rate limit" in combined or "too many requests" in combined:
        return NotionRateLimitError(original_error=exc)
    if status_code in (500, 502, 503, 504):
        return NotionMcpError(
            message="Notion MCP server error",
            error_code="PROVIDER_ERROR",
            retryable=True,
            original_error=exc,
            status_code=status_code,
        )
    return NotionMcpError(
        message=str(exc),
        error_code="UNKNOWN_ERROR",
        retryable=False,
        original_error=exc,
        status_code=status_code,
    )
