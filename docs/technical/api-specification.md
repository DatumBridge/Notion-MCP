# API Specification

## HTTP

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | none | Liveness |
| GET | `/test` | none | Manual test UI |
| GET | `/oauth/info` | none | Redirect URI |
| GET | `/oauth/start` | optional `MCP_SERVICE_API_KEY` | Begin OAuth |
| GET | `/oauth/callback` | none (state-bound) | OAuth redirect |
| POST | `/mcp/` | MCP session after initialize | Streamable HTTP MCP |

### Health

```json
{"status":"ok","service":"notion-mcp","class":"mcp-client-facade","upstream":"https://mcp.notion.com/mcp","tools":22}
```

## MCP methods

- `initialize` → sets `Mcp-Session-Id`
- `tools/list`
- `tools/call`

Protocol version: `2025-03-26` (override with `NOTION_MCP_PROTOCOL_VERSION`; the server-selected version is stored).

## Façade tools

Every catalog tool accepts its own `primary_fields` plus:

| Field | Type | Notes |
|-------|------|-------|
| `credentials_path` | string | Path under `NOTION_CREDENTIALS_DIR` |
| `credentials_json` | string | Token JSON |
| `extra_arguments_json` | string | Merged last (wins); live Notion schema fields |
| `confirm` | bool | Required for writes |
| `dry_run` | bool | No upstream call |
| `confirm_skill` | bool | Required for `notion_convert_page_to_skill` |

Helpers:

| Tool | Purpose |
|------|---------|
| `list_notion_tools` | Official catalog + optional live `tools/list` |
| `notion_whoami` | `notion-fetch` `id=self` |
| `notion_upload_local_file` | Upload helper (20 MiB) |

Remote tool argument schemas are owned by Notion. Pass-through JSON is the contract for fields not listed above. See [Supported tools](https://developers.notion.com/guides/mcp/mcp-supported-tools).

### Async example

`notion-create-pages` / `notion-update-page` may include `allow_async: true`. Poll:

```json
{"task_id":"task_abc123"}
```

against `notion-get-async-task`.

## Error object

```json
{
  "error_code": "AUTH_ERROR",
  "error_message": "Token expired, invalid, or re-authentication required",
  "retryable": true,
  "original_provider_error": null
}
```

| error_code | HTTP analog | retryable |
|------------|-------------|-----------|
| `CREDENTIALS_REQUIRED` | 401 | no |
| `CONFIRM_REQUIRED` | 400 | no |
| `VALIDATION_ERROR` | 400 | no |
| `AUTH_ERROR` | 401 | yes (refresh) |
| `REAUTH_REQUIRED` | 401 | no |
| `INVALID_CLIENT` | 401 | no |
| `PERMISSION_DENIED` | 403 | no |
| `NOT_FOUND` | 404 | no |
| `RATE_LIMIT` | 429 | yes |
| `UPGRADE_REQUIRED` | 402/403 | no |
| `ASYNC_TIMEOUT` | 504 | yes |
| `PROVIDER_ERROR` | 5xx | yes |
| `MCP_RPC_ERROR` | 502 | no |

REST routes outside `/mcp` use the same `{error_code, error_message, retryable}` shape.
