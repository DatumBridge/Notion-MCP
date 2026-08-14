# Security Architecture

## Trust boundaries

1. **User browser** — Notion consent screen; this client never sees the user's Notion password.
2. **This process** — holds access/refresh tokens in memory and optionally `token.json`.
3. **Notion MCP** — enforces workspace ACLs on every tool call.
4. **Callers** — Studio / agents must not log `credentials_json`.

## Controls

| Control | Implementation |
|---------|----------------|
| PKCE S256 | Mandatory on authorize + token exchange |
| State CSRF check | Callback rejects mismatched state |
| Public client | `token_endpoint_auth_method=none` unless DCR returns a secret |
| Token file mode | `0600`, atomic replace |
| Path jail | `credentials_path` must stay under `NOTION_CREDENTIALS_DIR` |
| No secret logs | Tokens, verifiers, and authorization codes are never logged |
| Write confirm | Side-effect tools require `confirm=true` |
| Refresh rotation | Persist new `refresh_token`; serialize refresh with a lock |
| Terminal `invalid_grant` | Clear/re-auth; do not retry refresh |
| HTTPS | Production redirect URIs must be HTTPS (localhost excepted) |
| Non-root container | UID 10001 |

## Least privilege

Notion OAuth grants access only to pages the user selects. This client does not broaden scopes and does not call Notion REST with MCP-audienced tokens.

## Untrusted content

Notion page, search, comment, and query bodies are labeled `content_trust=untrusted` and wrapped in `[UNTRUSTED_NOTION_CONTENT]`. FastMCP instructions tell the model not to treat that text as instructions and not to set `confirm=true` because a page asked. `notion-convert-page-to-skill` additionally requires `confirm_skill=true`.

## Residual risk

- `credentials_json` in tool arguments can appear in caller traces if the orchestrator logs params. Callers must redact.
- In-memory `_PENDING` OAuth sessions on the Test UI process are single-instance only.
- `confirm=true` is a tool argument; Studio should set it from a human action, not from model output.
