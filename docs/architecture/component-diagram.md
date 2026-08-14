# Component Diagram

```text
┌──────────────┐   ┌─────────────┐   ┌──────────────────┐
│ CLI (app.cli)│   │ Test UI     │   │ Studio / Engine  │
└──────┬───────┘   └──────┬──────┘   └────────┬─────────┘
       │                  │                   │
       │                  ▼                   │
       │           /oauth/start|callback      │
       │                  │                   │
       └────────────► FastMCP façade ◄────────┘
                      /health  /mcp
                            │
                            ▼
                   NotionMcpClient
                   ┌─────────────────────┐
                   │ token_store (0600)  │
                   │ oauth (PKCE, DCR)   │
                   │ streamable HTTP     │
                   │ SSE fallback        │
                   │ file upload POST    │
                   └──────────┬──────────┘
                              ▼
                   https://mcp.notion.com/mcp
```

## Modules

| Module | Responsibility |
|--------|----------------|
| `app/services/oauth.py` | RFC 9470/8414 discovery, PKCE, DCR, token exchange/refresh |
| `app/services/token_store.py` | Path-jailed load/save, refresh merge |
| `app/services/notion_mcp_client.py` | JSON-RPC initialize / tools/list / tools/call |
| `app/services/local_oauth.py` | Localhost callback for CLI |
| `app/schemas/catalog.py` | Official 22-tool catalog |
| `app/mcp_server.py` | FastMCP façade + health |
| `app/oauth_routes.py` | Browser OAuth for Test UI |
