# Use Cases

1. **Workspace search** — find pages or connected-source hits (`notion-search`).
2. **Read a ticket or spec** — `notion-fetch` by URL/ID; follow truncated subtrees.
3. **Create project docs** — `notion-create-pages` under a parent or database template.
4. **Update task status** — `notion-update-page` properties.
5. **Meeting follow-up** — `notion-query-meeting-notes` then comment with `notion-create-comment`.
6. **Cross-database status** — `notion-query-data-sources` SQL or view mode.
7. **Attach a local diagram** — `notion_upload_local_file` then include `suggested_markdown`.
8. **Label a connection** — `notion-fetch id=self` after OAuth to store workspace/user names.
9. **Duplicate a template** — `notion-duplicate-page` + `notion-get-async-task`.
10. **Studio workflows** — Execution Engine calls the local façade like other `mcpServer` tools.
