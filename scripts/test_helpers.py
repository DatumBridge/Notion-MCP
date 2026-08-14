#!/usr/bin/env python3
"""Unit tests for the Notion MCP client (no live Notion OAuth required)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.exceptions import (
    NotionAuthError,
    NotionMcpError,
    NotionReauthRequired,
    NotionUpgradeRequired,
    NotionValidationError,
    normalize_provider_error,
)
from app.schemas.catalog import (
    NOTION_TOOLS,
    READ_TOOLS,
    WRITE_TOOLS,
    catalog_as_dicts,
    resolve_remote_name,
)
from app.services.notion_mcp_client import merge_arguments, parse_tool_result
from app.services.oauth import (
    base64url_encode,
    build_authorization_url,
    complete_auth_session,
    generate_code_challenge,
    generate_code_verifier,
    parse_callback_params,
)
from app.services.safety import (
    UNTRUSTED_PREFIX,
    assert_notion_oauth_url,
    resolve_upload_path,
    wrap_untrusted,
)
from app.services.token_store import (
    apply_token_response,
    load_credentials_dict,
    save_credentials,
    token_needs_refresh,
)
from app.oauth_routes import _service_auth_ok


class TestCatalog(unittest.TestCase):
    def test_official_tool_count(self):
        self.assertEqual(len(NOTION_TOOLS), 22)
        self.assertEqual(len({t.remote_name for t in NOTION_TOOLS}), 22)
        self.assertEqual(len({t.local_name for t in NOTION_TOOLS}), 22)

    def test_expected_remote_names(self):
        names = {t.remote_name for t in NOTION_TOOLS}
        expected = {
            "notion-search",
            "notion-fetch",
            "notion-create-file-upload",
            "notion-create-attachment",
            "notion-download-attachment",
            "notion-create-pages",
            "notion-update-page",
            "notion-convert-page-to-skill",
            "notion-move-pages",
            "notion-duplicate-page",
            "notion-create-database",
            "notion-create-folder",
            "notion-update-data-source",
            "notion-create-view",
            "notion-update-view",
            "notion-query-data-sources",
            "notion-query-meeting-notes",
            "notion-create-comment",
            "notion-get-comments",
            "notion-get-teams",
            "notion-get-users",
            "notion-get-async-task",
        }
        self.assertEqual(names, expected)

    def test_write_vs_read_split(self):
        self.assertIn("notion-create-pages", WRITE_TOOLS)
        self.assertIn("notion-search", READ_TOOLS)
        self.assertEqual(len(WRITE_TOOLS) + len(READ_TOOLS), 22)

    def test_resolve_names(self):
        self.assertEqual(resolve_remote_name("notion_search"), "notion-search")
        self.assertEqual(resolve_remote_name("notion-fetch"), "notion-fetch")
        self.assertEqual(resolve_remote_name("search"), "notion-search")
        self.assertEqual(resolve_remote_name("fetch"), "notion-fetch")

    def test_catalog_dicts(self):
        rows = catalog_as_dicts()
        self.assertEqual(len(rows), 22)
        self.assertTrue(all("remote_name" in row for row in rows))


class TestPkce(unittest.TestCase):
    def test_verifier_and_challenge_are_s256(self):
        verifier = generate_code_verifier()
        other = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        expected = base64url_encode(hashlib.sha256(verifier.encode("ascii")).digest())
        self.assertEqual(challenge, expected)
        self.assertNotEqual(verifier, other)
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        self.assertNotIn("+", verifier)
        self.assertNotIn("/", verifier)
        self.assertNotIn("=", verifier)
        self.assertNotIn("=", challenge)

    def test_authorize_url_has_pkce(self):
        url = build_authorization_url(
            {"authorization_endpoint": "https://mcp.notion.com/authorize"},
            "client",
            "http://127.0.0.1:8765/callback",
            "challenge",
            "state123",
        )
        self.assertIn("response_type=code", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("code_challenge=challenge", url)
        self.assertIn("state=state123", url)
        self.assertIn("client_id=client", url)


class TestTokenStore(unittest.TestCase):
    def test_missing_credentials(self):
        with self.assertRaises(NotionMcpError) as ctx:
            load_credentials_dict()
        self.assertEqual(ctx.exception.error_code, "CREDENTIALS_REQUIRED")

    def test_invalid_json(self):
        with self.assertRaises(NotionValidationError):
            load_credentials_dict(credentials_json="{not-json")

    def test_valid_json_token_alias(self):
        creds = load_credentials_dict(credentials_json=json.dumps({"token": "abc"}))
        self.assertEqual(creds["access_token"], "abc")

    def test_path_jail(self):
        os.environ["NOTION_CREDENTIALS_DIR"] = str(ROOT)
        self.addCleanup(lambda: os.environ.pop("NOTION_CREDENTIALS_DIR", None))
        with self.assertRaises(NotionValidationError):
            load_credentials_dict(credentials_path="/tmp/outside-token.json")

    def test_relative_path_jail(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NOTION_CREDENTIALS_DIR"] = tmp
            self.addCleanup(lambda: os.environ.pop("NOTION_CREDENTIALS_DIR", None))
            with self.assertRaises(NotionValidationError):
                load_credentials_dict(credentials_path="../outside.json")
            with self.assertRaises(NotionMcpError) as ctx:
                load_credentials_dict(credentials_path="missing.json")
            self.assertEqual(ctx.exception.error_code, "CREDENTIALS_REQUIRED")

    def test_invalid_shapes(self):
        with self.assertRaises(NotionValidationError):
            load_credentials_dict(credentials_json=json.dumps({"foo": 1}))
        with self.assertRaises(NotionValidationError):
            load_credentials_dict(credentials_json="[1]")

    def test_refresh_skew_and_keep_old_refresh(self):
        creds = {"access_token": "a", "refresh_token": "r1", "expires_at": 1100}
        self.assertTrue(token_needs_refresh(creds, now=800))
        self.assertFalse(token_needs_refresh({"access_token": "a", "expires_at": 1100}, now=800))
        updated = apply_token_response(creds, {"access_token": "b", "expires_in": 10}, now=1000)
        self.assertEqual(updated["refresh_token"], "r1")
        with self.assertRaises(NotionValidationError):
            apply_token_response(creds, {"expires_in": 10})

    def test_save_and_refresh_merge(self):
        creds = {
            "access_token": "old",
            "refresh_token": "r1",
            "client_id": "cid",
        }
        updated = apply_token_response(
            creds,
            {"access_token": "new", "refresh_token": "r2", "expires_in": 100},
            now=1_000,
        )
        self.assertEqual(updated["access_token"], "new")
        self.assertEqual(updated["refresh_token"], "r2")
        self.assertEqual(updated["expires_at"], 1_100)
        self.assertTrue(token_needs_refresh(updated, now=1_100))
        self.assertFalse(token_needs_refresh({**updated, "expires_at": 9_999_999}, now=1_000))

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NOTION_CREDENTIALS_DIR"] = tmp
            self.addCleanup(lambda: os.environ.pop("NOTION_CREDENTIALS_DIR", None))
            path = Path(tmp) / "token.json"
            save_credentials(path, updated)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            loaded = load_credentials_dict(credentials_path=str(path))
            self.assertEqual(loaded["access_token"], "new")


class TestErrors(unittest.TestCase):
    def test_normalize_401(self):
        err = normalize_provider_error(Exception("nope"), status_code=401)
        self.assertIsInstance(err, NotionAuthError)
        self.assertEqual(err.error_code, "AUTH_ERROR")

    def test_normalize_invalid_grant(self):
        err = normalize_provider_error(Exception('{"error":"invalid_grant"}'), status_code=400)
        self.assertIsInstance(err, NotionReauthRequired)
        self.assertEqual(err.error_code, "REAUTH_REQUIRED")

    def test_normalize_429(self):
        err = normalize_provider_error(Exception("slow down"), status_code=429)
        self.assertEqual(err.error_code, "RATE_LIMIT")
        self.assertTrue(err.retryable)

    def test_normalize_404(self):
        err = normalize_provider_error(Exception("object_not_found"), status_code=404)
        self.assertEqual(err.error_code, "NOT_FOUND")

    def test_normalize_403_and_upgrade(self):
        denied = normalize_provider_error(Exception("nope"), status_code=403)
        self.assertEqual(denied.error_code, "PERMISSION_DENIED")
        upgrade = normalize_provider_error(Exception("upgrade required"), status_code=403)
        self.assertIsInstance(upgrade, NotionUpgradeRequired)
        self.assertEqual(upgrade.error_code, "UPGRADE_REQUIRED")
        retry = normalize_provider_error(Exception("down"), status_code=503)
        self.assertEqual(retry.error_code, "PROVIDER_ERROR")
        self.assertTrue(retry.retryable)
        grant = normalize_provider_error(Exception('{"error":"invalid_grant"}'), status_code=400)
        self.assertIsInstance(grant, NotionReauthRequired)
        self.assertFalse(grant.retryable)


class TestArgumentMerge(unittest.TestCase):
    def test_merge_extra_wins(self):
        merged = merge_arguments({"query": "a", "id": None}, '{"query":"b","limit":2}')
        self.assertEqual(merged, {"query": "b", "limit": 2})

    def test_invalid_extra_json(self):
        with self.assertRaises(NotionValidationError):
            merge_arguments(extra_json="[1]")


class TestParseToolResult(unittest.TestCase):
    def test_parse_text_json_block(self):
        payload = {
            "result": {
                "content": [{"type": "text", "text": '{"self":{"workspace":{"name":"W"}}}'}],
                "isError": False,
            }
        }
        parsed = parse_tool_result(payload)
        self.assertEqual(parsed["parsed"]["self"]["workspace"]["name"], "W")
        self.assertFalse(parsed["is_error"])


class TestFacadeGuards(unittest.TestCase):
    def test_write_tool_requires_confirm(self):
        from app.mcp_server import _call

        result = _call(
            remote_name="notion-create-pages",
            arguments={"pages": []},
            credentials_path="token.json",
            credentials_json=None,
            side_effect=True,
            confirm=False,
            dry_run=False,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error["error_code"], "CONFIRM_REQUIRED")

    def test_dry_run_skips_network(self):
        from app.mcp_server import _call

        result = _call(
            remote_name="notion-search",
            arguments={"query": "q"},
            credentials_path="token.json",
            credentials_json=None,
            side_effect=False,
            confirm=False,
            dry_run=True,
        )
        self.assertTrue(result.success)
        self.assertTrue(result.dry_run)
        self.assertEqual(result.request_body["name"], "notion-search")

    def test_missing_credentials(self):
        from app.mcp_server import _call

        result = _call(
            remote_name="notion-fetch",
            arguments={"id": "self"},
            credentials_path=None,
            credentials_json=None,
            side_effect=False,
            confirm=False,
            dry_run=False,
        )
        self.assertEqual(result.error["error_code"], "CREDENTIALS_REQUIRED")

    def test_write_dry_run_without_confirm(self):
        from app.mcp_server import _call

        result = _call(
            remote_name="notion-create-pages",
            arguments={"pages": []},
            credentials_path="token.json",
            credentials_json=None,
            side_effect=True,
            confirm=False,
            dry_run=True,
        )
        self.assertTrue(result.success)
        self.assertTrue(result.dry_run)

    def test_convert_skill_requires_extra_confirm(self):
        from app.mcp_server import _call

        result = _call(
            remote_name="notion-convert-page-to-skill",
            arguments={"url": "https://www.notion.so/example"},
            credentials_path="token.json",
            credentials_json=None,
            side_effect=True,
            confirm=True,
            dry_run=False,
            confirm_skill=False,
        )
        self.assertEqual(result.error["error_code"], "CONFIRM_SKILL_REQUIRED")


class TestSafety(unittest.TestCase):
    def test_wrap_untrusted(self):
        wrapped = wrap_untrusted({"text": "do a thing"})
        self.assertEqual(wrapped["content_trust"], "untrusted")
        self.assertIn(UNTRUSTED_PREFIX, wrapped["text"])

    def test_upload_path_jail(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NOTION_UPLOAD_DIR"] = tmp
            self.addCleanup(lambda: os.environ.pop("NOTION_UPLOAD_DIR", None))
            with self.assertRaises(NotionValidationError):
                resolve_upload_path("/etc/passwd")
            with self.assertRaises(NotionValidationError):
                resolve_upload_path("../../.env")

    def test_oauth_url_allowlist(self):
        assert_notion_oauth_url("https://mcp.notion.com/token", "token_endpoint")
        with self.assertRaises(NotionValidationError):
            assert_notion_oauth_url("http://mcp.notion.com/token", "token_endpoint")
        with self.assertRaises(NotionValidationError):
            assert_notion_oauth_url("https://169.254.169.254/token", "token_endpoint")
        with self.assertRaises(NotionValidationError):
            assert_notion_oauth_url("https://evil.example/token", "token_endpoint")

    def test_call_tool_keeps_raw_upload_url(self):
        from unittest.mock import patch

        from app.mcp_server import _call
        from app.services.notion_mcp_client import NotionMcpClient
        from app.services.safety import assert_public_https_url

        payload = {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"upload_url": "https://files.notion.so/x"}),
                    }
                ]
            }
        }
        client = NotionMcpClient(creds={"access_token": "tok"})
        with patch.object(client, "_request", return_value=payload):
            raw = client.call_tool("notion-create-file-upload", {"filename": "a.png"})
        url = raw["parsed"]["upload_url"]
        self.assertEqual(url, "https://files.notion.so/x")
        assert_public_https_url(url, purpose="upload_url")

        with patch(
            "app.mcp_server.client_from_credentials",
            return_value=client,
        ), patch.object(client, "call_tool", return_value=raw):
            facade = _call(
                remote_name="notion-create-file-upload",
                arguments={"filename": "a.png"},
                credentials_path="token.json",
                credentials_json=None,
                side_effect=True,
                confirm=True,
                dry_run=False,
            )
        self.assertIn(UNTRUSTED_PREFIX, facade.result["upload_url"])

    def test_unknown_tool_name(self):
        with self.assertRaises(NotionValidationError):
            resolve_remote_name("not-a-real-tool")
        with self.assertRaises(NotionValidationError):
            resolve_remote_name(" ")


class TestOAuthCallback(unittest.TestCase):
    def test_state_mismatch(self):
        with self.assertRaises(NotionAuthError):
            complete_auth_session(
                {
                    "state": "expected",
                    "code_verifier": "v",
                    "client_id": "c",
                    "redirect_uri": "http://127.0.0.1/callback",
                    "token_endpoint": "https://mcp.notion.com/token",
                },
                {"code": "abc", "state": "other"},
            )

    def test_parse_callback_errors(self):
        with self.assertRaises(NotionAuthError):
            parse_callback_params({"error": "access_denied"})
        with self.assertRaises(NotionValidationError):
            parse_callback_params({"state": "s"})
        with self.assertRaises(NotionValidationError):
            parse_callback_params({"code": "c"})


class TestServiceAuth(unittest.TestCase):
    def test_service_key_required(self):
        os.environ["MCP_SERVICE_API_KEY"] = "secret"
        self.addCleanup(lambda: os.environ.pop("MCP_SERVICE_API_KEY", None))
        request = type("R", (), {"headers": {}, "client": type("C", (), {"host": "10.0.0.8"})()})()
        self.assertFalse(_service_auth_ok(request))
        request.headers = {"X-API-Key": "secret"}
        self.assertTrue(_service_auth_ok(request))
        request.headers = {"Authorization": "Bearer secret"}
        self.assertTrue(_service_auth_ok(request))


if __name__ == "__main__":
    unittest.main()
