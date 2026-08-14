# Business Rules

## New rules

1. **Hosted MCP only** — workspace mutations go through Notion MCP tools, not a parallel REST client.
2. **User consent required** — first connection always uses interactive OAuth. There is no silent service-account path in v1.
3. **Confirm writes** — create, update, move, duplicate, comment, upload, convert-to-skill, folder, database, view, and data-source changes require `confirm=true`.
4. **Dry run is non-mutating** — `dry_run=true` must not call Notion.
5. **Plan gating** — if `current_tool_access` marks a tool `upgrade_required` or `not_enabled`, callers should not invoke it.
6. **Truncated fetch** — when `notion-fetch` returns `truncated=true`, retry with an `unknown_block_ids` entry. Treat `object_not_found` on retry as a permissions signal.
7. **Async completion** — `notion-duplicate-page` and `allow_async` create/update return a task; poll `notion-get-async-task` using `poll_after_seconds`.
8. **File size** — local upload helper rejects files over 20 MiB.
9. **Rate limits** — 180 rpm overall, 30 rpm for search. Surface `RATE_LIMIT` as retryable.
10. **Re-auth** — `invalid_grant` means the connection is dead. Prompt reconnect; do not loop.

## Business impact

Agents can search, read, and change Notion content the user granted, using the same tool names Notion documents for other MCP clients.
