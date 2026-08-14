# Configuration

All values are environment variables. See `.env.example`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `8000` | HTTP listen port (entrypoint) |
| `LOG_LEVEL` | `INFO` | Process log level |
| `NOTION_MCP_URL` | `https://mcp.notion.com/mcp` | Streamable HTTP endpoint |
| `NOTION_MCP_SSE_URL` | `https://mcp.notion.com/sse` | SSE fallback |
| `NOTION_MCP_ORIGIN` | `https://mcp.notion.com` | Origin for discovery |
| `NOTION_MCP_PROTOCOL_VERSION` | `2025-03-26` | Advertised MCP version; server choice is stored |
| `OAUTH_REDIRECT_URI` | CLI: `http://127.0.0.1:8765/callback`; HTTP Test UI: `{request}/oauth/callback` when unset | Must match the listener |
| `OAUTH_LISTEN_HOST` | `127.0.0.1` | CLI callback bind |
| `OAUTH_LISTEN_PORT` | `8765` | CLI callback port |
| `NOTION_OAUTH_CLIENT_NAME` | `DatumBridge Notion MCP Client` | DCR client_name |
| `NOTION_CREDENTIALS_DIR` | project root | Path jail for `credentials_path` |
| `NOTION_HTTP_TIMEOUT_SEC` | `60` | Outbound timeout |
| `NOTION_TOKEN_REFRESH_SKEW_SEC` | `300` | Refresh this many seconds early |
| `STUDIO_PUBLIC_URL` | unset | If set, OAuth callback redirects to Studio |
| `MCP_SERVICE_API_KEY` | unset | If set, `/oauth/start` requires it |
| `NOTION_UPLOAD_DIR` | `NOTION_CREDENTIALS_DIR` | Path jail for `notion_upload_local_file` |
| `NOTION_OAUTH_ALLOW_ANONYMOUS` | unset | If `1`, `/oauth/start` is allowed off loopback without an API key (dev only) |
| `NOTION_OAUTH_PERSIST_TOKEN` | unset | If `1`, HTTP `/oauth/callback` writes `token.json` under `NOTION_CREDENTIALS_DIR` |

## Token JSON

```json
{
  "type": "oauth",
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "Bearer",
  "expires_in": 28800,
  "expires_at": 1710000000,
  "client_id": "...",
  "client_secret": null,
  "token_endpoint": "https://...",
  "user_id": "...",
  "workspace_id": "...",
  "email_domain": "example.com"
}
```

Never commit this file. `.gitignore` excludes `token.json` and `*.json` credential dumps.
