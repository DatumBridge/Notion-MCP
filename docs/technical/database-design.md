# Database Design

v1 stores no database.

| Data | Location | Notes |
|------|----------|-------|
| OAuth tokens | `token.json` or caller-supplied JSON | mode 0600; not a shared DB |
| Pending OAuth state | in-memory (`_PENDING`) | 10 minute expiry |
| Tool catalog | `app/schemas/catalog.py` | static, versioned in git |

No migrations. If a future vault is added, persist only ciphertext and identity labels (`workspace_id`, `user_id`), never raw tokens in logs.
