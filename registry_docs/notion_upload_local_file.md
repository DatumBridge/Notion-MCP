# notion_upload_local_file

Create a Notion file-upload URL and POST the local file (client-side multipart).

The gateway injects `credentials_json` from the connected account. Do not invent a token or paste a secret into the arguments.

## Parameters

| Name | Required | Meaning |
|---|---|---|
| `file_path` | yes | Local file path (max 20 MiB) |
| `extra_arguments_json` | no | Optional[str] |
| `confirm` | no | Must be true to upload |
| `dry_run` | no | Preview without uploading |

## Cases

### Typical call

Input:

```json
{
  "file_path": "example",
  "dry_run": true
}
```

Output:

```json
{
  "success": true,
  "suggested_markdown": "example",
  "upload": "example",
  "message": "example"
}
```

### Missing `file_path`

The tool rejects the call and does not guess the missing value.

Input:

```json
{
  "dry_run": true
}
```

Output:

```json
{
  "success": false,
  "error": {
    "error_code": "invalid_argument",
    "error_message": "file_path is required",
    "retryable": false
  }
}
```

### Preview the write

Set `dry_run` to true. The tool returns the planned change and does not send it.

Input:

```json
{
  "file_path": "example",
  "dry_run": true
}
```

### Confirmed write

Set `confirm` to true. Omit `dry_run`.

Input:

```json
{
  "file_path": "example",
  "confirm": true
}
```

### Write without confirm or dry_run

Input:

```json
{
  "file_path": "example"
}
```

Output:

```json
{
  "success": false,
  "error_message": "confirm=true required for write tools (or dry_run=true to preview)"
}
```
