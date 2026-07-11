#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tests for gh-apps.py — unit tests (no network) + live verification.

Usage:
    test_gh_apps.py              # run unit tests only
    test_gh_apps.py --live       # also run live verification
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import importlib
gh_apps = importlib.import_module("gh-apps")


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

_results: list[tuple[str, bool, str]] = []


def test(name: str):
    def decorator(fn):
        def wrapper():
            try:
                fn()
                _results.append((name, True, ""))
            except Exception as e:
                _results.append((name, False, str(e)))
        return wrapper
    return decorator


def run_tests(tests: list, label: str) -> bool:
    for t in tests:
        t()
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n=== {label}: {passed} passed, {failed} failed ===\n")
    for name, ok, err in _results:
        status = "PASS" if ok else "FAIL"
        line = f"  {status}  {name}"
        if err:
            line += f"  ({err})"
        print(line)
    return failed == 0


def _make_test_key() -> str:
    """Generate a throwaway RSA key, return path."""
    f = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    subprocess.run(
        ["openssl", "genrsa", "-out", f.name, "2048"],
        capture_output=True, check=True,
    )
    return f.name


# ---------------------------------------------------------------------------
# Unit tests — b64url
# ---------------------------------------------------------------------------

@test("b64url: standard encoding")
def test_b64url_standard():
    result = gh_apps._b64url(b'{"alg":"RS256","typ":"JWT"}')
    decoded = base64.urlsafe_b64decode(result + "==")
    assert decoded == b'{"alg":"RS256","typ":"JWT"}', f"roundtrip failed: {decoded}"


@test("b64url: no padding characters")
def test_b64url_no_padding():
    result = gh_apps._b64url(b"test")
    assert "=" not in result, f"padding found: {result}"


@test("b64url: url-safe characters only")
def test_b64url_urlsafe():
    data = bytes(range(256))
    result = gh_apps._b64url(data)
    assert "+" not in result, "contains +"
    assert "/" not in result, "contains /"


# ---------------------------------------------------------------------------
# Unit tests — JWT generation
# ---------------------------------------------------------------------------

@test("generate_jwt: produces 3-part token")
def test_jwt_structure():
    key_path = _make_test_key()
    try:
        jwt = gh_apps._generate_jwt("12345", key_path)
        parts = jwt.split(".")
        assert len(parts) == 3, f"expected 3 parts, got {len(parts)}"
    finally:
        os.unlink(key_path)


@test("generate_jwt: header has RS256 alg")
def test_jwt_header():
    key_path = _make_test_key()
    try:
        jwt = gh_apps._generate_jwt("12345", key_path)
        header = json.loads(base64.urlsafe_b64decode(jwt.split(".")[0] + "=="))
        assert header["alg"] == "RS256", f"alg={header['alg']}"
        assert header["typ"] == "JWT", f"typ={header['typ']}"
    finally:
        os.unlink(key_path)


@test("generate_jwt: iss is integer")
def test_jwt_iss_integer():
    key_path = _make_test_key()
    try:
        jwt = gh_apps._generate_jwt("12345", key_path)
        payload = json.loads(base64.urlsafe_b64decode(jwt.split(".")[1] + "=="))
        assert isinstance(payload["iss"], int), f"iss type={type(payload['iss'])}"
        assert payload["iss"] == 12345
    finally:
        os.unlink(key_path)


@test("generate_jwt: payload has iat and exp with correct bounds")
def test_jwt_timing():
    key_path = _make_test_key()
    try:
        jwt = gh_apps._generate_jwt("99999", key_path)
        payload = json.loads(base64.urlsafe_b64decode(jwt.split(".")[1] + "=="))
        assert "iat" in payload, "missing iat"
        assert "exp" in payload, "missing exp"
        assert payload["exp"] > payload["iat"], "exp must be after iat"
        assert payload["exp"] - payload["iat"] <= 660, "token validity too long"
    finally:
        os.unlink(key_path)


@test("generate_jwt: signature is non-empty")
def test_jwt_signature():
    key_path = _make_test_key()
    try:
        jwt = gh_apps._generate_jwt("12345", key_path)
        sig = jwt.split(".")[2]
        assert len(sig) > 100, f"signature too short: {len(sig)}"
    finally:
        os.unlink(key_path)


# ---------------------------------------------------------------------------
# Unit tests — credential resolution
# ---------------------------------------------------------------------------

@test("resolve_credentials: returns None when nothing configured")
def test_resolve_none():
    env_backup = {}
    for key in ["GH_APPS_APP_ID", "GH_APPS_PRIVATE_KEY_PATH", "GH_APPS_SLUG"]:
        env_backup[key] = os.environ.pop(key, None)

    with tempfile.TemporaryDirectory() as tmpdir:
        real_root = gh_apps.CONFIG_ROOT
        gh_apps.CONFIG_ROOT = Path(tmpdir) / "gh-apps"
        try:
            result = gh_apps._resolve_credentials("nonexistent")
            assert result is None, f"expected None, got {result}"
        finally:
            gh_apps.CONFIG_ROOT = real_root
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val


@test("resolve_credentials: reads from config files")
def test_resolve_config_files():
    env_backup = {}
    for key in ["GH_APPS_APP_ID", "GH_APPS_PRIVATE_KEY_PATH", "GH_APPS_SLUG"]:
        env_backup[key] = os.environ.pop(key, None)

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "gh-apps"
        config_dir = root / "test-app"
        config_dir.mkdir(parents=True)
        (config_dir / "app-id").write_text("111\n")
        pem = config_dir / "app.pem"
        pem.write_text("fake-key")
        (config_dir / "client-id").write_text("Iv1.abc123")

        real_root = gh_apps.CONFIG_ROOT
        gh_apps.CONFIG_ROOT = root
        try:
            result = gh_apps._resolve_credentials("test-app")
            assert result is not None, "expected credentials"
            assert result.app_id == "111", f"app_id={result.app_id}"
            assert result.key_path == str(pem), f"key_path={result.key_path}"
            assert result.client_id == "Iv1.abc123", f"client_id={result.client_id}"
            assert result.slug == "test-app"
        finally:
            gh_apps.CONFIG_ROOT = real_root
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val


@test("resolve_credentials: env vars override config files")
def test_resolve_env_override():
    with tempfile.TemporaryDirectory() as tmpdir:
        pem = Path(tmpdir) / "test.pem"
        pem.write_text("fake-key")

        env_backup = {}
        for key in ["GH_APPS_APP_ID", "GH_APPS_PRIVATE_KEY_PATH"]:
            env_backup[key] = os.environ.get(key)

        os.environ["GH_APPS_APP_ID"] = "env-app"
        os.environ["GH_APPS_PRIVATE_KEY_PATH"] = str(pem)

        try:
            result = gh_apps._resolve_credentials()
            assert result is not None
            assert result.app_id == "env-app", f"app_id={result.app_id}"
            assert result.slug == "env"
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val
                else:
                    os.environ.pop(key, None)


@test("resolve_credentials: partial config returns None")
def test_resolve_partial():
    env_backup = {}
    for key in ["GH_APPS_APP_ID", "GH_APPS_PRIVATE_KEY_PATH", "GH_APPS_SLUG"]:
        env_backup[key] = os.environ.pop(key, None)

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "gh-apps"
        config_dir = root / "partial-app"
        config_dir.mkdir(parents=True)
        (config_dir / "app-id").write_text("111\n")
        # Missing app.pem

        real_root = gh_apps.CONFIG_ROOT
        gh_apps.CONFIG_ROOT = root
        try:
            result = gh_apps._resolve_credentials("partial-app")
            assert result is None, f"expected None with partial creds, got {result}"
        finally:
            gh_apps.CONFIG_ROOT = real_root
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val


# ---------------------------------------------------------------------------
# Unit tests — config directory auto-selection
# ---------------------------------------------------------------------------

@test("config_dir: auto-selects single app")
def test_config_dir_single():
    env_backup = os.environ.pop("GH_APPS_SLUG", None)

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "gh-apps"
        app_dir = root / "only-app"
        app_dir.mkdir(parents=True)
        (app_dir / "app-id").write_text("123")

        real_root = gh_apps.CONFIG_ROOT
        gh_apps.CONFIG_ROOT = root
        try:
            result = gh_apps._config_dir(None)
            assert result.name == "only-app", f"got {result.name}"
        finally:
            gh_apps.CONFIG_ROOT = real_root
            if env_backup is not None:
                os.environ["GH_APPS_SLUG"] = env_backup


@test("config_dir: explicit slug overrides auto-select")
def test_config_dir_explicit():
    result = gh_apps._config_dir("my-slug")
    assert result.name == "my-slug"


# ---------------------------------------------------------------------------
# Unit tests — save credentials
# ---------------------------------------------------------------------------

@test("save_credentials: creates correct structure")
def test_save_credentials():
    with tempfile.TemporaryDirectory() as tmpdir:
        real_root = gh_apps.CONFIG_ROOT
        gh_apps.CONFIG_ROOT = Path(tmpdir)
        try:
            d = gh_apps._save_credentials(
                "test-save", "42", "-----BEGIN RSA PRIVATE KEY-----\nfake\n",
                "cid", "csec", "whsec",
            )
            assert (d / "app-id").read_text() == "42"
            assert (d / "app.pem").read_text().startswith("-----BEGIN")
            assert (d / "client-id").read_text() == "cid"
            assert (d / "client-secret").read_text() == "csec"
            assert (d / "webhook-secret").read_text() == "whsec"
            # Check PEM permissions
            import stat
            mode = (d / "app.pem").stat().st_mode
            assert not (mode & stat.S_IROTH), "PEM readable by others"
            assert not (mode & stat.S_IRGRP), "PEM readable by group"
        finally:
            gh_apps.CONFIG_ROOT = real_root


# ---------------------------------------------------------------------------
# Unit tests — manifest building
# ---------------------------------------------------------------------------

@test("build_manifest: minimal manifest")
def test_manifest_minimal():
    m = gh_apps._build_manifest("test-app", "https://example.com", "http://localhost:1234/cb")
    assert m["name"] == "test-app"
    assert m["url"] == "https://example.com"
    assert m["redirect_url"] == "http://localhost:1234/cb"
    assert m["public"] is False
    assert "default_permissions" not in m
    assert "default_events" not in m
    assert "hook_attributes" not in m


@test("build_manifest: full manifest")
def test_manifest_full():
    m = gh_apps._build_manifest(
        "full-app", "https://example.com", "http://localhost:1234/cb",
        permissions={"issues": "write", "contents": "read"},
        events=["issues", "push"],
        webhook_url="https://example.com/hooks",
        public=True,
        description="A test app",
    )
    assert m["public"] is True
    assert m["description"] == "A test app"
    assert m["default_permissions"]["issues"] == "write"
    assert m["default_permissions"]["contents"] == "read"
    assert "issues" in m["default_events"]
    assert m["hook_attributes"]["url"] == "https://example.com/hooks"
    assert m["hook_attributes"]["active"] is True


# ---------------------------------------------------------------------------
# Unit tests — multi-app listing
# ---------------------------------------------------------------------------

@test("list: discovers apps in config dir")
def test_list_apps():
    import io
    with tempfile.TemporaryDirectory() as tmpdir:
        for slug in ["app-a", "app-b"]:
            d = Path(tmpdir) / slug
            d.mkdir()
            (d / "app-id").write_text(f"id-{slug}")
            (d / "app.pem").write_text("fake")

        real_root = gh_apps.CONFIG_ROOT
        gh_apps.CONFIG_ROOT = Path(tmpdir)

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            import argparse
            gh_apps.cmd_list(argparse.Namespace())
            output = sys.stdout.getvalue()
            assert "app-a" in output
            assert "app-b" in output
        finally:
            sys.stdout = old_stdout
            gh_apps.CONFIG_ROOT = real_root


# ---------------------------------------------------------------------------
# Test registry
# ---------------------------------------------------------------------------

UNIT_TESTS = [
    test_b64url_standard,
    test_b64url_no_padding,
    test_b64url_urlsafe,
    test_jwt_structure,
    test_jwt_header,
    test_jwt_iss_integer,
    test_jwt_timing,
    test_jwt_signature,
    test_resolve_none,
    test_resolve_config_files,
    test_resolve_env_override,
    test_resolve_partial,
    test_config_dir_single,
    test_config_dir_explicit,
    test_save_credentials,
    test_manifest_minimal,
    test_manifest_full,
    test_list_apps,
]


# ---------------------------------------------------------------------------
# Live verification
# ---------------------------------------------------------------------------

def run_live_verification() -> bool:
    """Test JWT generation and API access against a real app."""
    print("\n=== Live Verification ===\n")

    creds = gh_apps._resolve_credentials()
    if creds is None:
        print("SKIP  no app credentials configured")
        return True

    print(f"1. Using app: {creds.slug} (id={creds.app_id})")

    print("2. Generating JWT...", end=" ")
    jwt = gh_apps._generate_jwt(creds.app_id, creds.key_path)
    print(f"ok ({len(jwt)} chars)")

    print("3. Testing GET /app...", end=" ")
    try:
        data = gh_apps._api_jwt("GET", "/app", creds)
        print(f"ok ({data.get('name', '?')})")
    except SystemExit:
        print("FAIL")
        return False

    print("4. Listing installations...", end=" ")
    try:
        installations = gh_apps._api_jwt("GET", "/app/installations", creds)
        print(f"ok ({len(installations)} found)")
    except SystemExit:
        print("FAIL")
        return False

    if installations:
        inst = installations[0]
        inst_id = str(inst["id"])
        account = inst.get("account", {}).get("login", "?")
        print(f"5. Getting installation token for {account}...", end=" ")
        try:
            token = gh_apps._get_installation_token(creds.app_id, inst_id, creds.key_path)
            print(f"ok ({token[:8]}...)")
        except SystemExit:
            print("FAIL")
            return False

    print("\nLive verification passed.")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    live = "--live" in sys.argv

    ok = run_tests(UNIT_TESTS, "Unit Tests")

    if live:
        try:
            live_ok = run_live_verification()
            ok = ok and live_ok
        except SystemExit as e:
            print(f"\nLive verification aborted (exit code {e.code})")
            ok = False
        except Exception:
            traceback.print_exc()
            ok = False

    print()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
