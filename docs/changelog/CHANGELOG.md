# Changelog

## 2026-08-14

### Added

- Notion MCP client for `https://mcp.notion.com/mcp` (Streamable HTTP, SSE fallback).
- OAuth 2.0 + PKCE + dynamic client registration and token refresh.
- Official 22-tool catalog from [Supported tools](https://developers.notion.com/guides/mcp/mcp-supported-tools).
- FastMCP façade (`mcpServer=notion`) with confirm/dry-run on write tools and `confirm_skill` for convert-to-skill.
- Untrusted-content labels on agent-facing Notion bodies.
- CLI: `auth`, `catalog`, `tools`, `whoami`, `call` (`--confirm`, `--confirm-skill`).
- Local file upload helper for `notion-create-file-upload` with upload path jail.
- Architecture, business, technical, ADR, and security documentation.

### Changed

- Default MCP protocol version is `2025-03-26`; the server-selected version is stored.
- HTTP OAuth no longer writes a process-global `token.json` unless `NOTION_OAUTH_PERSIST_TOKEN=1`.

### Fixed

- None (initial version).

### Removed

- None.
