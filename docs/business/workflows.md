# Workflows

## 1. Connect

```text
CLI:  python scripts/oauth_connect.py
    → RFC 9470 + 8414 discovery
    → Dynamic client registration
    → Browser consent (PKCE)
    → localhost callback exchanges code
    → token.json saved under NOTION_CREDENTIALS_DIR (0600)

HTTP Test UI: GET /oauth/start (loopback or MCP_SERVICE_API_KEY)
    → same OAuth
    → /oauth/callback does not write token.json unless NOTION_OAUTH_PERSIST_TOKEN=1
    → use CLI persist or paste credentials_json from a local oauth_connect run
```

## 2. Read

```text
Caller → notion_search / notion_fetch / notion_get_*
      → NotionMcpClient.tools/call
      → structured JSON result
```

Identity check: `notion_whoami` or `notion-fetch` with `id=self`.

## 3. Write

```text
Caller → write tool with confirm=true
      → optional dry_run preview
      → Notion MCP mutates workspace
      → if async_task, poll notion_get_async_task
```

## 4. Local file attach

```text
notion_upload_local_file(confirm=true)
  → notion-create-file-upload
  → multipart POST to returned URL
  → suggested_markdown
  → notion-create-pages / notion-update-page / notion-create-comment
```

## 5. Token refresh

```text
Before request, if expires_at - skew is past
  → refresh_token grant (locked)
  → persist rotated refresh_token
  → retry original MCP call once on 401
  → invalid_grant → REAUTH_REQUIRED
```
