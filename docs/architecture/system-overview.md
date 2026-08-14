# System Overview

## What changed

Added `mcp/notion-mcp`, a DatumBridge MCP **client** for Notion hosted MCP.

## Why

Notion already operates `https://mcp.notion.com/mcp` with OAuth and the official tool catalog. Re-implementing the Notion REST API would drift from Notion's MCP surface and miss tools such as `notion-query-meeting-notes` and `notion-convert-page-to-skill`.

## Role

| Layer | Owner |
|-------|--------|
| Tool semantics & schemas | Notion hosted MCP |
| Auth, transport, catalog, confirm/dry-run | this client |
| Workflow / policy decisions | Studio / LangGraph / Execution Engine |

## Impacted components

- New service: `notion-mcp` (this repository folder)
- Upstream: Notion MCP (`mcp.notion.com`)
- Downstream callers: CLI, Test UI, DatumBridge MCP registry (`mcpServer=notion`)

## Dependencies

- Python 3.10+
- `httpx` for OAuth and Streamable HTTP
- `fastmcp` + `uvicorn` for the local façade
- Browser for the initial OAuth consent

## Risks

- Notion hosted MCP is OAuth-only; headless automation must reuse a stored refresh token.
- Refresh tokens rotate and expire (inactivity / 180-day cap). `invalid_grant` requires user reconnect.
- Tool availability depends on workspace plan (`current_tool_access` from `notion-fetch id=self`).
