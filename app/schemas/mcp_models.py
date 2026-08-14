"""Pydantic models for Notion MCP façade tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class BaseToolResponse(BaseModel):
    success: bool
    error: Optional[dict] = None


class ToolCallResponse(BaseToolResponse):
    tool: Optional[str] = None
    result: Optional[Any] = None
    content: Optional[List[Dict[str, Any]]] = None
    is_error: bool = False
    dry_run: bool = False
    request_body: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    transport: Optional[str] = None


class ToolListResponse(BaseToolResponse):
    catalog: List[Dict[str, Any]] = []
    live_tools: List[Dict[str, Any]] = []
    workspace: Optional[Dict[str, Any]] = None
    current_tool_access: Optional[Dict[str, Any]] = None


class IdentityResponse(BaseToolResponse):
    workspace: Optional[Dict[str, Any]] = None
    user: Optional[Dict[str, Any]] = None
    current_tool_access: Optional[Dict[str, Any]] = None
    raw: Optional[Any] = None


class FileUploadResponse(BaseToolResponse):
    suggested_markdown: Optional[str] = None
    upload: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
