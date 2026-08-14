# ADR-0001

## Context

DatumBridge MCP siblings usually wrap a vendor REST API and expose FastMCP tools. Notion already hosts an MCP server with OAuth and a documented tool list.

## Decision

Implement an MCP **client** of `https://mcp.notion.com/mcp` and a thin FastMCP façade that forwards the official tools.

## Alternatives Considered

1. Wrap Notion REST API v1 like gmail-mcp — duplicates Notion's investment and misses MCP-only tools.
2. Client library only, no façade — harder for Studio/Execution Engine to consume.
3. Relay/hub copy — wrong taxonomy class.

## Consequences

- Tool schemas evolve with Notion; we pass JSON through instead of freezing REST models.
- Auth is OAuth-only; no internal integration token path in v1.

## Trade-offs

+ Stays aligned with Notion's supported tools page
+ Smaller maintenance surface
− Depends on Notion MCP availability and OAuth browser consent

## Risks

Notion may rename or gate tools by plan. Mitigate with `list_notion_tools` + `current_tool_access`.
