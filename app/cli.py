"""CLI for Notion MCP OAuth, tool listing, and tool calls."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from app.core.config import project_root
from app.core.exceptions import NotionMcpError
from app.schemas.catalog import WRITE_TOOLS, catalog_as_dicts, resolve_remote_name
from app.services.notion_mcp_client import NotionMcpClient
from app.services.token_store import apply_token_response, save_credentials


def _token_path(path: str | None) -> Path:
    return Path(path) if path else project_root() / "token.json"


def cmd_catalog(_args: argparse.Namespace) -> int:
    print(json.dumps(catalog_as_dicts(), indent=2))
    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    client = NotionMcpClient(credentials_path=str(_token_path(args.token)))
    tools = client.list_tools()
    print(json.dumps(tools, indent=2))
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    client = NotionMcpClient(credentials_path=str(_token_path(args.token)))
    print(json.dumps(client.fetch_self(), indent=2))
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    arguments = json.loads(args.arguments) if args.arguments else {}
    remote = resolve_remote_name(args.tool)
    if remote in WRITE_TOOLS and not args.confirm:
        print(
            json.dumps(
                {
                    "error_code": "CONFIRM_REQUIRED",
                    "error_message": "Write tools require --confirm",
                    "retryable": False,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    if remote == "notion-convert-page-to-skill" and not args.confirm_skill:
        print(
            json.dumps(
                {
                    "error_code": "CONFIRM_SKILL_REQUIRED",
                    "error_message": "Convert-to-skill requires --confirm-skill",
                    "retryable": False,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    client = NotionMcpClient(credentials_path=str(_token_path(args.token)))
    result = client.call_tool(remote, arguments)
    print(json.dumps(result, indent=2, default=str))
    return 0 if not result.get("is_error") else 1


def cmd_auth(args: argparse.Namespace) -> int:
    from app.services.local_oauth import run_local_oauth

    creds = run_local_oauth()
    path = _token_path(args.token)
    save_credentials(path, apply_token_response(creds, creds))
    print(f"Token saved to {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Notion MCP client")
    parser.add_argument("--token", help="Path to token.json")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("catalog", help="Print the official 22-tool catalog")
    sub.add_parser("tools", help="List live tools from Notion MCP")
    sub.add_parser("whoami", help="Call notion-fetch id=self")
    sub.add_parser("auth", help="Run browser OAuth and save token.json")

    call = sub.add_parser("call", help="Call a Notion MCP tool")
    call.add_argument("tool", help="Tool name, e.g. notion-search")
    call.add_argument("--arguments", default="{}", help="JSON arguments")
    call.add_argument("--confirm", action="store_true", help="Required for write tools")
    call.add_argument(
        "--confirm-skill",
        action="store_true",
        help="Required for notion-convert-page-to-skill",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "catalog": cmd_catalog,
        "tools": cmd_tools,
        "whoami": cmd_whoami,
        "call": cmd_call,
        "auth": cmd_auth,
    }
    try:
        return commands[args.command](args)
    except NotionMcpError as exc:
        print(json.dumps(exc.to_dict(), indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
