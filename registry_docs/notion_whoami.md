# notion_whoami

Fetch connected workspace and user via notion-fetch id=self.

The gateway injects `credentials_json` from the connected account. Do not invent a token or paste a secret into the arguments.

## Parameters

| Name | Required | Meaning |
|---|---|---|
| — | — | This call takes no model arguments. |

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
  "workspace": "example",
  "user": "example",
  "current_tool_access": [],
  "raw": "example"
}
```
