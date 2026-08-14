# Notion MCP Client

MCP **client** for [Notion hosted MCP](https://developers.notion.com/guides/mcp/get-started-with-mcp) plus a DatumBridge FastMCP façade.

Connects to `https://mcp.notion.com/mcp` with OAuth 2.0 + PKCE and exposes the official tools from [Supported tools](https://developers.notion.com/guides/mcp/mcp-supported-tools).

**Class:** Python MCP client / tool-server façade. See [`docs/`](docs/README.md).

Registry id: **`mcpServer=notion`**.

## Official tools (22)

| Local name | Remote name | Side effect |
|------------|-------------|-------------|
| `notion_search` | `notion-search` | no (30 rpm) |
| `notion_fetch` | `notion-fetch` | no |
| `notion_create_file_upload` | `notion-create-file-upload` | yes |
| `notion_create_attachment` | `notion-create-attachment` | yes |
| `notion_download_attachment` | `notion-download-attachment` | no |
| `notion_create_pages` | `notion-create-pages` | yes |
| `notion_update_page` | `notion-update-page` | yes |
| `notion_convert_page_to_skill` | `notion-convert-page-to-skill` | yes |
| `notion_create_folder` | `notion-create-folder` | yes |
| `notion_move_pages` | `notion-move-pages` | yes |
| `notion_duplicate_page` | `notion-duplicate-page` | yes (async) |
| `notion_create_database` | `notion-create-database` | yes |
| `notion_update_data_source` | `notion-update-data-source` | yes |
| `notion_create_view` | `notion-create-view` | yes |
| `notion_update_view` | `notion-update-view` | yes |
| `notion_query_data_sources` | `notion-query-data-sources` | no |
| `notion_query_meeting_notes` | `notion-query-meeting-notes` | no (plan-gated) |
| `notion_create_comment` | `notion-create-comment` | yes |
| `notion_get_comments` | `notion-get-comments` | no |
| `notion_get_teams` | `notion-get-teams` | no |
| `notion_get_users` | `notion-get-users` | no |
| `notion_get_async_task` | `notion-get-async-task` | no |

Helpers: `list_notion_tools`, `notion_whoami`, `notion_upload_local_file`.

Write tools require **`confirm=true`**. Use **`dry_run=true`** to preview.

## Setup

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_mcp.txt
```

Requires **Python 3.10+** (Docker image uses 3.11).

## Authenticate

Notion hosted MCP requires a browser OAuth consent flow (no static integration token).

```bash
python scripts/oauth_connect.py
# or
python -m app.cli auth
```

This discovers OAuth metadata, registers a public client (PKCE), opens the browser, and writes `token.json` (mode `0600`).

Use `token.json` as `credentials_path` on every tool call.

## CLI

```bash
python -m app.cli catalog
python -m app.cli whoami
python -m app.cli tools
python -m app.cli call notion-search --arguments '{"query":"roadmap"}'
python -m app.cli call notion-fetch --arguments '{"id":"self"}'
```

## Running the façade

```bash
chmod +x mcp_server_entrypoint.sh
./mcp_server_entrypoint.sh
# or
uvicorn app.mcp_server:http_app --host 0.0.0.0 --port 8000
```

- Health: `GET http://localhost:8000/health`
- MCP: `POST http://localhost:8000/mcp/`
- Test UI: `http://localhost:8000/test`

Stdio mode (Claude Desktop / Cursor):

```bash
python -m app.mcp_server
```

## Docker

```bash
docker build -t notion-mcp .
docker run -p 8000:8000 notion-mcp
```

OAuth still needs a reachable redirect URI; prefer local `oauth_connect.py` and mount `token.json` when running in Docker.

## Rate limits

Notion applies **180 requests/minute** per user across all tools, plus **30 searches/minute**. A workspace-wide limit also applies. If you see `RATE_LIMIT`, reduce parallel calls.

## Architecture

```text
Caller → FastMCP /mcp → NotionMcpClient → https://mcp.notion.com/mcp → Notion
                 ↑
         OAuth token per call
```

See [docs/README.md](docs/README.md) for the full documentation index.
