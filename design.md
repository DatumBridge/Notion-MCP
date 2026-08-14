# Design: Notion MCP Client

## Class

**Python MCP client** of Notion hosted MCP, with a **FastMCP tool-server façade** for DatumBridge Studio / LangGraph.

This is not a transport/relay. Do not copy `datumbridge-mcp-ws-hub` WebSocket, pairing, or correlation patterns.

This is not a Notion REST API wrapper. Tools execute on `https://mcp.notion.com/mcp`.

## Purpose

Connect DatumBridge (and local CLI users) to [Notion MCP](https://developers.notion.com/guides/mcp/get-started-with-mcp) using the official tool list from [Supported tools](https://developers.notion.com/guides/mcp/mcp-supported-tools).

## Architecture

```text
CLI / Studio / Execution Engine
        │
        ▼
FastMCP façade  GET /health  POST /mcp
        │
        ▼
NotionMcpClient  (OAuth 2.0 + PKCE, token refresh)
        │  Streamable HTTP, SSE fallback
        ▼
https://mcp.notion.com/mcp
        │
        ▼
Notion workspace (user-granted pages)
```

## Key decisions

1. **Client of hosted MCP** — Notion maintains the tool implementations. This repo authenticates, transports, catalogs, and re-exposes them.
2. **OAuth 2.0 + PKCE + DCR** — follows [Build an MCP client for Notion](https://developers.notion.com/guides/mcp/build-mcp-client). No integration secret in git. Dynamic client registration credentials are persisted with the token so grants are not orphaned.
3. **Pass-through credentials** — each façade tool accepts `credentials_path` or `credentials_json` (same as gmail-mcp / trello-mcp).
4. **Official names** — remote tools keep `notion-*` hyphen names. Local FastMCP names are `snake_case` (`notion_search`). OpenAI aliases `search` / `fetch` resolve to `notion-search` / `notion-fetch`.
5. **Write tools require confirm=true** — create/update/move/duplicate/comment/upload. `dry_run=true` previews the payload.
6. **Live schemas win** — static catalog documents the 22 official tools; `tools/list` from Notion is the runtime schema. `extra_arguments_json` / `arguments_json` pass through unknown fields.
7. **Fail fast** — missing credentials, invalid state, and `invalid_grant` are explicit errors. `invalid_grant` is terminal (re-auth), never retried.
8. **File upload is client-side** — after `notion-create-file-upload`, this client POSTs multipart/form-data. Notion requires that of the MCP client.
9. **Data ≠ decisions** — tools return Notion content; workflows decide what to do next. `current_tool_access` from `notion-fetch id=self` is surfaced so callers can avoid upgrade-only tools.

## Non-goals (v1)

- Re-implementing Notion REST API v1
- Multi-tenant encrypted vault (use datumbridge-mcp credential vault when wired)
- Resources / prompts beyond tool call
- WS hub / edge relay patterns
- Hard-coded Notion tool JSON Schema (Notion owns schema evolution)

## Platform contracts

- `GET /health`
- `POST /mcp/` Streamable HTTP (`initialize` → `Mcp-Session-Id` → `tools/list` | `tools/call`)
- Registry: `mcpServer=notion`

See ADRs under `docs/adr/`.
