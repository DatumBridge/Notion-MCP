# Integrations

## Notion hosted MCP

| Item | Value |
|------|-------|
| Streamable HTTP | `https://mcp.notion.com/mcp` |
| SSE | `https://mcp.notion.com/sse` |
| Discovery | `https://www.notion.com/.well-known/mcp.json` |
| Tools doc | https://developers.notion.com/guides/mcp/mcp-supported-tools |
| Client guide | https://developers.notion.com/guides/mcp/build-mcp-client |

Auth: OAuth 2.0 authorization code + PKCE. Dynamic client registration when advertised.

This client does **not** call `https://api.notion.com` with MCP tokens. Identity display names come from `notion-fetch` `id=self`.

## DatumBridge registry

| Field | Value |
|-------|-------|
| `mcpServer` | `notion` |
| Execute base URL | service `/mcp/` |
| Credential style | per-call `credentials_path` / `credentials_json` |

## OpenAI Deep Research alias

When talking to OpenAI MCP clients, Notion may advertise `search` and `fetch`. This client maps those names to `notion-search` and `notion-fetch`.

## Rate limits

Documented by Notion: 180 rpm per user, 30 rpm for search, plus a shared workspace cap.
