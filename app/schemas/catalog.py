"""Official Notion MCP tools from https://developers.notion.com/guides/mcp/mcp-supported-tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from app.core.exceptions import NotionValidationError


@dataclass(frozen=True)
class NotionToolSpec:
    """Static catalog entry for one hosted Notion MCP tool."""

    remote_name: str
    local_name: str
    title: str
    description: str
    category: str
    side_effect: bool
    rate_limit_note: str = ""
    primary_fields: Tuple[str, ...] = ()
    example_arguments: Dict[str, object] = field(default_factory=dict)
    example_prompts: Tuple[str, ...] = ()


NOTION_TOOLS: Tuple[NotionToolSpec, ...] = (
    NotionToolSpec(
        remote_name="notion-search",
        local_name="notion_search",
        title="Search Notion and connected sources",
        description=(
            "Search across the Notion workspace and connected tools such as Slack, "
            "Google Drive, and Jira. Requires Notion AI for connected sources; "
            "without it, search is limited to the Notion workspace."
        ),
        category="search",
        side_effect=False,
        rate_limit_note="30 requests per minute",
        primary_fields=("query",),
        example_arguments={"query": "budget approval process"},
        example_prompts=(
            "Search for documents mentioning 'budget approval process'",
            "Find all project pages that mention 'ready for dev'",
        ),
    ),
    NotionToolSpec(
        remote_name="notion-fetch",
        local_name="notion_fetch",
        title="Fetch Notion content",
        description=(
            "Retrieve a Notion page, database, or data source by URL or ID. "
            "Pass id='self' to read the connected workspace, user identity, and "
            "current_tool_access map. When truncated=true, retry with an "
            "unknown_block_ids entry to load a subtree."
        ),
        category="read",
        side_effect=False,
        primary_fields=("id",),
        example_arguments={"id": "self"},
        example_prompts=(
            "Fetch self to see which workspace and user this connection is for",
            "Fetch a page URL to read product requirements",
        ),
    ),
    NotionToolSpec(
        remote_name="notion-create-file-upload",
        local_name="notion_create_file_upload",
        title="Create a file upload URL",
        description=(
            "Create a short-lived URL for uploading one local file (max 20 MiB). "
            "The client must POST multipart/form-data using the returned URL, "
            "headers, and form field, then pass suggested_markdown to create/update "
            "page or comment tools."
        ),
        category="files",
        side_effect=True,
        primary_fields=("filename",),
        example_arguments={"filename": "diagram.png"},
        example_prompts=("Upload diagram.png and add it to the project plan",),
    ),
    NotionToolSpec(
        remote_name="notion-create-attachment",
        local_name="notion_create_attachment",
        title="Create an attachment",
        description=(
            "Create a Notion attachment from exactly one source: inline UTF-8 text, "
            "a direct public HTTPS URL, or a completed file upload from this "
            "integration (source_file_id)."
        ),
        category="files",
        side_effect=True,
        primary_fields=("filename", "content", "url", "source_file_id"),
        example_arguments={"filename": "notes.md", "content": "# Notes"},
        example_prompts=("Create an HTML attachment from this report",),
    ),
    NotionToolSpec(
        remote_name="notion-download-attachment",
        local_name="notion_download_attachment",
        title="Download a text attachment",
        description=(
            "Download UTF-8 text of an attachment created by notion-create-attachment. "
            "Limited to 200 KiB. Does not fetch arbitrary URLs or binary files."
        ),
        category="files",
        side_effect=False,
        primary_fields=("file_upload_id",),
        example_arguments={"file_upload_id": "file_upload_id"},
        example_prompts=("Read the contents of this Markdown attachment",),
    ),
    NotionToolSpec(
        remote_name="notion-create-pages",
        local_name="notion_create_pages",
        title="Create pages",
        description=(
            "Create one or more Notion pages with properties and markdown content. "
            "Supports database templates, icon, and cover. If parent is omitted, "
            "a private page is created. Set allow_async=true for large markdown."
        ),
        category="pages",
        side_effect=True,
        primary_fields=("pages", "parent", "allow_async"),
        example_arguments={
            "pages": [{"properties": {"title": "Kickoff"}, "content": "# Agenda"}],
        },
        example_prompts=("Create a project kickoff page with agenda and team info",),
    ),
    NotionToolSpec(
        remote_name="notion-update-page",
        local_name="notion_update_page",
        title="Update a page",
        description=(
            "Update a page's properties, content, icon, or cover. Supports applying "
            "database templates. Set allow_async=true for large replacements."
        ),
        category="pages",
        side_effect=True,
        primary_fields=("page_id", "command", "new_str", "allow_async"),
        example_arguments={
            "page_id": "PAGE_ID",
            "command": "replace_content",
            "new_str": "# Updated plan",
        },
        example_prompts=("Change the status of this task to Complete",),
    ),
    NotionToolSpec(
        remote_name="notion-convert-page-to-skill",
        local_name="notion_convert_page_to_skill",
        title="Convert a page to a skill",
        description=(
            "Mark a Notion page as an AI skill. Pass the page's full Notion URL. "
            "Requires edit permission in the connected workspace."
        ),
        category="pages",
        side_effect=True,
        primary_fields=("url",),
        example_arguments={"url": "https://www.notion.so/example-page-url"},
        example_prompts=("Convert this page into a skill",),
    ),
    NotionToolSpec(
        remote_name="notion-move-pages",
        local_name="notion_move_pages",
        title="Move pages",
        description="Move one or more Notion pages or databases to a new parent.",
        category="pages",
        side_effect=True,
        primary_fields=("page_ids", "new_parent"),
        example_arguments={"page_ids": ["PAGE_ID"], "new_parent": {"page_id": "PARENT_ID"}},
        example_prompts=("Move weekly notes under Team Meetings",),
    ),
    NotionToolSpec(
        remote_name="notion-duplicate-page",
        local_name="notion_duplicate_page",
        title="Duplicate a page",
        description=(
            "Duplicate a Notion page asynchronously. Poll notion-get-async-task "
            "with the returned task_id."
        ),
        category="pages",
        side_effect=True,
        primary_fields=("page_id",),
        example_arguments={"page_id": "PAGE_ID"},
        example_prompts=("Duplicate my project template page",),
    ),
    NotionToolSpec(
        remote_name="notion-create-database",
        local_name="notion_create_database",
        title="Create a database",
        description=(
            "Create a new Notion database, initial data source, and initial view "
            "with the specified properties."
        ),
        category="databases",
        side_effect=True,
        primary_fields=("title", "properties", "parent"),
        example_arguments={
            "title": "Customer feedback",
            "properties": {"Customer": {"type": "title"}, "Status": {"type": "status"}},
        },
        example_prompts=("Create a database to track customer feedback",),
    ),
    NotionToolSpec(
        remote_name="notion-create-folder",
        local_name="notion_create_folder",
        title="Create a folder",
        description="Create an empty Folder under a parent page.",
        category="pages",
        side_effect=True,
        primary_fields=("name", "parent"),
        example_arguments={"name": "Project files", "parent": {"page_id": "PAGE_ID"}},
        example_prompts=("Create a folder named Project files under this page",),
    ),
    NotionToolSpec(
        remote_name="notion-update-data-source",
        local_name="notion_update_data_source",
        title="Update a data source",
        description="Update a data source's properties, name, description, or other attributes.",
        category="databases",
        side_effect=True,
        primary_fields=("data_source_id", "name", "properties"),
        example_arguments={"data_source_id": "DATA_SOURCE_ID", "name": "Tasks"},
        example_prompts=("Add a status field to track project completion",),
    ),
    NotionToolSpec(
        remote_name="notion-create-view",
        local_name="notion_create_view",
        title="Create a view",
        description=(
            "Create a view on a Notion database: table, board, list, calendar, "
            "timeline, gallery, form, chart, map, or dashboard. Optional view DSL "
            "for filters, sorts, grouping, and display. Read notion://docs/view-dsl-spec."
        ),
        category="databases",
        side_effect=True,
        primary_fields=("database_id", "type", "name", "configuration"),
        example_arguments={"database_id": "DB_ID", "type": "board", "name": "By status"},
        example_prompts=("Create a board view grouped by Status",),
    ),
    NotionToolSpec(
        remote_name="notion-update-view",
        local_name="notion_update_view",
        title="Update a view",
        description=(
            "Update a view's name, filters, sorts, or display configuration. "
            "Only specified fields change. Uses the same view DSL as create-view."
        ),
        category="databases",
        side_effect=True,
        primary_fields=("view_id", "name", "configuration"),
        example_arguments={"view_id": "VIEW_ID", "name": "Sprint Board"},
        example_prompts=("Rename the All Tasks view to Sprint Board",),
    ),
    NotionToolSpec(
        remote_name="notion-query-data-sources",
        local_name="notion_query_data_sources",
        title="Query across data sources",
        description=(
            "Query data sources with SQL or run an existing view. View mode is "
            "available on every plan. Multi-source SQL requires Business/Enterprise "
            "with Notion AI on some plans."
        ),
        category="query",
        side_effect=False,
        primary_fields=("query", "sql", "view_id"),
        example_arguments={"sql": "SELECT * FROM tasks LIMIT 20"},
        example_prompts=("What's due for me this week? Group by priority.",),
    ),
    NotionToolSpec(
        remote_name="notion-query-meeting-notes",
        local_name="notion_query_meeting_notes",
        title="Query meeting notes",
        description=(
            "Query the current user's meeting notes. Requires Business or higher "
            "with Notion AI; other plans receive an upgrade prompt."
        ),
        category="query",
        side_effect=False,
        primary_fields=("query",),
        example_arguments={"query": "sprint planning"},
        example_prompts=("Find my meeting notes from this week",),
    ),
    NotionToolSpec(
        remote_name="notion-create-comment",
        local_name="notion_create_comment",
        title="Add a comment",
        description=(
            "Add a page-level comment, a block-level comment, or a reply to an "
            "existing discussion. Markdown may include attachment suggested_markdown."
        ),
        category="comments",
        side_effect=True,
        primary_fields=("page_id", "markdown", "discussion_id"),
        example_arguments={"page_id": "PAGE_ID", "markdown": "Looks good — ship it."},
        example_prompts=("Add a feedback comment to this design proposal",),
    ),
    NotionToolSpec(
        remote_name="notion-get-comments",
        local_name="notion_get_comments",
        title="Get comments",
        description=(
            "List comments and discussions on a page, including block-level and "
            "inline threads when requested."
        ),
        category="comments",
        side_effect=False,
        primary_fields=("page_id",),
        example_arguments={"page_id": "PAGE_ID"},
        example_prompts=("Get all discussions on this page, including resolved ones",),
    ),
    NotionToolSpec(
        remote_name="notion-get-teams",
        local_name="notion_get_teams",
        title="Get teams",
        description="Retrieve teamspaces in the current workspace, optionally filtered by name.",
        category="workspace",
        side_effect=False,
        primary_fields=("query",),
        example_arguments={"query": "Engineering"},
        example_prompts=("Search for teams by name and membership status",),
    ),
    NotionToolSpec(
        remote_name="notion-get-users",
        local_name="notion_get_users",
        title="Get users",
        description=(
            "List workspace members and guests. Supports pagination, search by "
            "name or email, lookup by user ID, or id='self' for the current user."
        ),
        category="workspace",
        side_effect=False,
        primary_fields=("query", "user_id"),
        example_arguments={"query": "self"},
        example_prompts=("What's my Notion user ID and email?",),
    ),
    NotionToolSpec(
        remote_name="notion-get-async-task",
        local_name="notion_get_async_task",
        title="Get async task status",
        description=(
            "Poll an async task from notion-duplicate-page or allow_async create/update. "
            "Status is queued, running, retrying, succeeded, or failed. Honor "
            "poll_after_seconds from the original response."
        ),
        category="async",
        side_effect=False,
        primary_fields=("task_id",),
        example_arguments={"task_id": "task_abc123"},
        example_prompts=("Check whether the page I just duplicated is ready",),
    ),
)

TOOLS_BY_REMOTE: Dict[str, NotionToolSpec] = {t.remote_name: t for t in NOTION_TOOLS}
TOOLS_BY_LOCAL: Dict[str, NotionToolSpec] = {t.local_name: t for t in NOTION_TOOLS}

# OpenAI Deep Research clients may see fetch/search without the notion- prefix.
OPENAI_NAME_ALIASES: Dict[str, str] = {
    "fetch": "notion-fetch",
    "search": "notion-search",
}

WRITE_TOOLS: Tuple[str, ...] = tuple(t.remote_name for t in NOTION_TOOLS if t.side_effect)
READ_TOOLS: Tuple[str, ...] = tuple(t.remote_name for t in NOTION_TOOLS if not t.side_effect)


def resolve_remote_name(name: str) -> str:
    """Accept local snake_case, official hyphen names, or OpenAI aliases."""
    key = (name or "").strip()
    if not key:
        raise NotionValidationError("tool name is required")
    if key in TOOLS_BY_REMOTE:
        return key
    if key in TOOLS_BY_LOCAL:
        return TOOLS_BY_LOCAL[key].remote_name
    if key in OPENAI_NAME_ALIASES:
        return OPENAI_NAME_ALIASES[key]
    hyphen = key.replace("_", "-")
    if hyphen in TOOLS_BY_REMOTE:
        return hyphen
    if not hyphen.startswith("notion-") and f"notion-{hyphen}" in TOOLS_BY_REMOTE:
        return f"notion-{hyphen}"
    raise NotionValidationError(f"Unknown Notion MCP tool: {key}")


def catalog_as_dicts() -> List[dict]:
    return [
        {
            "remote_name": t.remote_name,
            "local_name": t.local_name,
            "title": t.title,
            "description": t.description,
            "category": t.category,
            "side_effect": t.side_effect,
            "rate_limit_note": t.rate_limit_note,
            "primary_fields": list(t.primary_fields),
            "example_arguments": t.example_arguments,
            "example_prompts": list(t.example_prompts),
        }
        for t in NOTION_TOOLS
    ]
