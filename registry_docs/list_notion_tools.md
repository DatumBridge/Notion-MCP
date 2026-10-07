# list_notion_tools

List the official Notion MCP catalog and optionally live tools from the server.

The gateway injects `credentials_json` from the connected account. Do not invent a token or paste a secret into the arguments.

## Parameters

| Name | Required | Meaning |
|---|---|---|
| `include_live` | no | If true and credentials are present, also call Notion tools/list |
| `include_identity` | no | If true, also call notion-fetch id=self for workspace/tool access |

## Cases

### Typical call

Input:

```json
{}
```

Output:

```json
{
  "success": true,
  "catalog": "example",
  "live_tools": [],
  "workspace": "example",
  "current_tool_access": []
}
```
