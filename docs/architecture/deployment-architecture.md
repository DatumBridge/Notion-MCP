# Deployment Architecture

## Local

```text
developer machine
  python scripts/oauth_connect.py  → token.json (0600)
  uvicorn app.mcp_server:http_app  → :8000
```

Redirect URI default: `http://127.0.0.1:8765/callback`.

## Docker

Multi-stage Python 3.11 image, non-root UID 10001, `HEALTHCHECK` on `/health`.

OAuth consent is interactive. Recommended pattern:

1. Run `oauth_connect.py` on a machine with a browser.
2. Mount `token.json` read-only into the container under `NOTION_CREDENTIALS_DIR`.

Do not bake tokens into the image.

## Kubernetes (optional)

Same as sibling tool-servers:

- Service port 8000
- Probe `/health`
- Secret volume for `token.json` or per-call `credentials_json` from datumbridge-mcp vault
- No privileged containers

## Rollback

Remove the deployment and registry entry `mcpServer=notion`. Tokens live only in the credential file/vault; deleting them revokes local use (user should also revoke the Notion connection in Notion settings).
