#!/bin/bash
# HTTP entrypoint for the Notion MCP client façade
cd "$(dirname "$0")"
uvicorn app.mcp_server:http_app --host 0.0.0.0 --port "${PORT:-8000}"
