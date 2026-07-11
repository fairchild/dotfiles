#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Create, authenticate, and manage GitHub Apps.

Usage:
    gh-apps.py create NAME [--org ORG] [--permissions K:V,...] [--events E,...] [--webhook-url URL] [--public] [--no-browser]
    gh-apps.py list
    gh-apps.py info [--app SLUG]
    gh-apps.py delete [--app SLUG]
    gh-apps.py jwt [--app SLUG]
    gh-apps.py token [--app SLUG] [--installation ID]
    gh-apps.py setup [--app SLUG]
    gh-apps.py installations [--app SLUG]
    gh-apps.py repos [--app SLUG] [--installation ID]
    gh-apps.py webhook-config [--app SLUG]
    gh-apps.py webhook-update [--app SLUG] --url URL [--secret SECRET] [--content-type TYPE]
    gh-apps.py deliveries [--app SLUG] [--limit N]
    gh-apps.py redeliver [--app SLUG] DELIVERY_ID
    gh-apps.py rotate-key [--app SLUG]
    gh-apps.py permissions [--app SLUG]

Credential storage:
    ~/.config/gh-apps/<slug>/app-id, app.pem, client-id, client-secret, webhook-secret
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import socket
import subprocess
import sys
import textwrap
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


# ---------------------------------------------------------------------------
# Credential storage — multi-app under ~/.config/gh-apps/<slug>/
# ---------------------------------------------------------------------------

CONFIG_ROOT = Path.home() / ".config" / "gh-apps"


class AppCredentials(NamedTuple):
    slug: str
    app_id: str
    key_path: str
    client_id: str | None = None
    client_secret: str | None = None
    webhook_secret: str | None = None


def _read_file(path: Path) -> str | None:
    if path.exists():
        return path.read_text().strip()
    return None


def _config_dir(slug: str | None = None) -> Path:
    """Resolve app config directory. Auto-selects if only one app exists."""
    if slug:
        return CONFIG_ROOT / slug

    env_slug = os.environ.get("GH_APPS_SLUG")
    if env_slug:
        return CONFIG_ROOT / env_slug

    if not CONFIG_ROOT.exists():
        return CONFIG_ROOT / "__none__"

    apps = [d for d in CONFIG_ROOT.iterdir() if d.is_dir() and (d / "app-id").exists()]
    if len(apps) == 1:
        return apps[0]
    if len(apps) == 0:
        print("error: no apps configured. Run 'gh-apps.py create' first.", file=sys.stderr)
        sys.exit(1)
    print("error: multiple apps found. Use --app SLUG to select one:", file=sys.stderr)
    for a in sorted(apps):
        print(f"  {a.name}", file=sys.stderr)
    sys.exit(1)


def _resolve_credentials(slug: str | None = None) -> AppCredentials | None:
    """Resolve credentials from env vars or config files."""
    app_id = os.environ.get("GH_APPS_APP_ID")
    key_path = os.environ.get("GH_APPS_PRIVATE_KEY_PATH")

    if app_id and key_path:
        if not Path(key_path).exists():
            print(f"error: private key not found: {key_path}", file=sys.stderr)
            sys.exit(1)
        return AppCredentials(
            slug=slug or "env",
            app_id=app_id,
            key_path=key_path,
            client_id=os.environ.get("GH_APPS_CLIENT_ID"),
            client_secret=os.environ.get("GH_APPS_CLIENT_SECRET"),
            webhook_secret=os.environ.get("GH_APPS_WEBHOOK_SECRET"),
        )

    d = _config_dir(slug)
    aid = _read_file(d / "app-id")
    pem = d / "app.pem"

    if not aid or not pem.exists():
        return None

    return AppCredentials(
        slug=d.name,
        app_id=aid,
        key_path=str(pem),
        client_id=_read_file(d / "client-id"),
        client_secret=_read_file(d / "client-secret"),
        webhook_secret=_read_file(d / "webhook-secret"),
    )


def _save_credentials(
    slug: str, app_id: str, pem: str,
    client_id: str = "", client_secret: str = "", webhook_secret: str = "",
) -> Path:
    """Save app credentials to config directory."""
    d = CONFIG_ROOT / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "app-id").write_text(app_id)
    pem_path = d / "app.pem"
    pem_path.write_text(pem)
    pem_path.chmod(0o600)
    if client_id:
        (d / "client-id").write_text(client_id)
    if client_secret:
        (d / "client-secret").write_text(client_secret)
    if webhook_secret:
        (d / "webhook-secret").write_text(webhook_secret)
    return d


# ---------------------------------------------------------------------------
# JWT & token generation (RS256 via openssl)
# ---------------------------------------------------------------------------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _generate_jwt(app_id: str, key_path: str) -> str:
    """Generate a GitHub App JWT (10-min expiry) using openssl RS256."""
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": int(app_id),
    }).encode())
    signing_input = f"{header}.{payload}"

    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", key_path, "-binary"],
        input=signing_input.encode(),
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"error: JWT signing failed: {result.stderr.decode().strip()}", file=sys.stderr)
        sys.exit(1)

    return f"{signing_input}.{_b64url(result.stdout)}"


def _get_installation_token(app_id: str, installation_id: str, key_path: str) -> str:
    """Exchange JWT for an installation access token."""
    jwt = _generate_jwt(app_id, key_path)
    req = Request(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        method="POST",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())["token"]
    except Exception as e:
        print(f"error: installation token exchange failed: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _api_bearer(method: str, path: str, token: str, data: dict | None = None) -> Any:
    """Make an authenticated API request with Bearer token."""
    url = f"https://api.github.com{path}" if path.startswith("/") else path
    body = json.dumps(data).encode() if data else None
    req = Request(
        url, method=method, data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except Exception as e:
        print(f"error: API {method} {path}: {e}", file=sys.stderr)
        sys.exit(1)


def _api_jwt(method: str, path: str, creds: AppCredentials, data: dict | None = None) -> Any:
    """Make a JWT-authenticated API request."""
    jwt = _generate_jwt(creds.app_id, creds.key_path)
    return _api_bearer(method, path, jwt, data)


def _gh_api(path: str, method: str = "GET", data: dict | None = None) -> Any:
    """Make a request using the gh CLI (personal auth)."""
    cmd = ["gh", "api", path, "--method", method]
    if data:
        cmd.extend(["--input", "-"])
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        input=json.dumps(data) if data else None,
    )
    if result.returncode != 0:
        print(f"error: gh api {path}: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout) if result.stdout.strip() else {}


# ---------------------------------------------------------------------------
# Manifest flow — create a GitHub App via browser + local callback server
# ---------------------------------------------------------------------------

def _build_manifest(
    name: str, url: str, redirect_url: str,
    permissions: dict[str, str] | None = None,
    events: list[str] | None = None,
    webhook_url: str | None = None,
    public: bool = False,
    description: str = "",
) -> dict:
    """Build a GitHub App manifest JSON."""
    manifest: dict[str, Any] = {
        "name": name,
        "url": url,
        "redirect_url": redirect_url,
        "public": public,
    }
    if description:
        manifest["description"] = description
    if permissions:
        manifest["default_permissions"] = permissions
    if events:
        manifest["default_events"] = events
    if webhook_url:
        manifest["hook_attributes"] = {"url": webhook_url, "active": True}
    return manifest


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _ManifestCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler: serves manifest form at / and catches callback."""

    code: str | None = None

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_form()
        elif parsed.path == "/callback":
            self._handle_callback(parsed.query)
        else:
            self.send_error(404)

    def _serve_form(self) -> None:
        server: _ManifestServer = self.server  # type: ignore
        manifest_json = html.escape(json.dumps(server.manifest))
        target = server.github_url

        page = textwrap.dedent(f"""\
            <!DOCTYPE html>
            <html><head><title>Create GitHub App</title></head>
            <body>
            <h2>Creating GitHub App: {html.escape(server.manifest['name'])}</h2>
            <p>Submitting to GitHub...</p>
            <form id="f" action="{target}" method="post">
              <input type="hidden" name="manifest" value="{manifest_json}">
            </form>
            <script>document.getElementById('f').submit();</script>
            </body></html>
        """)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(page.encode())

    def _handle_callback(self, query: str) -> None:
        params = parse_qs(query)
        code = params.get("code", [None])[0]

        if code:
            _ManifestCallbackHandler.code = code
            page = "<html><body><h2>GitHub App created!</h2><p>You can close this tab.</p></body></html>"
        else:
            page = "<html><body><h2>Error: no code received</h2></body></html>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(page.encode())


class _ManifestServer(HTTPServer):
    """HTTP server carrying manifest data for the handler."""

    def __init__(self, port: int, manifest: dict, org: str | None = None):
        super().__init__(("127.0.0.1", port), _ManifestCallbackHandler)
        self.manifest = manifest
        if org:
            self.github_url = f"https://github.com/organizations/{org}/settings/apps/new"
        else:
            self.github_url = "https://github.com/settings/apps/new"
        self.timeout = 300


def _exchange_manifest_code(code: str) -> dict:
    """Exchange the temporary code for app credentials."""
    return _gh_api(f"/app-manifests/{code}/conversions", method="POST")


def _run_manifest_flow(
    name: str, org: str | None, permissions: dict[str, str] | None,
    events: list[str] | None, webhook_url: str | None, public: bool,
    description: str, no_browser: bool,
) -> None:
    """Run the full manifest flow: build -> serve -> exchange -> save."""
    slug = name.lower().replace(" ", "-")

    existing = CONFIG_ROOT / slug
    if existing.exists() and (existing / "app-id").exists():
        print(f"error: app '{slug}' already exists. Delete config at {existing} first.", file=sys.stderr)
        sys.exit(1)

    port = _find_free_port()
    callback_url = f"http://127.0.0.1:{port}/callback"

    manifest = _build_manifest(
        name=name,
        url=f"https://github.com/apps/{slug}",
        redirect_url=callback_url,
        permissions=permissions,
        events=events,
        webhook_url=webhook_url,
        public=public,
        description=description,
    )

    if no_browser:
        _run_manifest_flow_manual(manifest, org, slug)
        return

    server = _ManifestServer(port, manifest, org)
    local_url = f"http://127.0.0.1:{port}"

    print(f"Opening browser to create GitHub App '{name}'...")
    print(f"Local server: {local_url}")
    print("Waiting for GitHub callback (5 min timeout)...\n")

    webbrowser.open(local_url)

    _ManifestCallbackHandler.code = None
    while _ManifestCallbackHandler.code is None:
        server.handle_request()

    code = _ManifestCallbackHandler.code
    server.server_close()

    print("Received code, exchanging for credentials...")
    result = _exchange_manifest_code(code)
    _finish_create(result, slug)


def _run_manifest_flow_manual(manifest: dict, org: str | None, slug: str) -> None:
    """Manual flow: print manifest, ask user to paste the code."""
    if org:
        url = f"https://github.com/organizations/{org}/settings/apps/new"
    else:
        url = "https://github.com/settings/apps/new"

    print("Manual creation mode (--no-browser)")
    print(f"\n1. Go to: {url}")
    print(f"\n2. Paste this manifest JSON into the form:\n")
    print(json.dumps(manifest, indent=2))
    print(f"\n3. Click 'Create GitHub App'")
    print(f"\n4. Copy the 'code' parameter from the redirect URL and paste it here:")

    code = input("\nCode: ").strip()
    if not code:
        print("error: no code provided", file=sys.stderr)
        sys.exit(1)

    print("Exchanging code for credentials...")
    result = _exchange_manifest_code(code)
    _finish_create(result, slug)


def _finish_create(result: dict, slug: str) -> None:
    """Save credentials and print summary."""
    app_id = str(result.get("id", ""))
    pem = result.get("pem", "")
    webhook_secret = result.get("webhook_secret", "")
    client_id = result.get("client_id", "")
    client_secret = result.get("client_secret", "")
    app_name = result.get("name", slug)
    owner_login = result.get("owner", {}).get("login", "unknown")

    if not app_id or not pem:
        print(f"error: unexpected response:\n{json.dumps(result, indent=2)}", file=sys.stderr)
        sys.exit(1)

    config_path = _save_credentials(slug, app_id, pem, client_id, client_secret, webhook_secret)

    print(f"\nGitHub App created successfully!")
    print(f"  Name:           {app_name}")
    print(f"  App ID:         {app_id}")
    print(f"  Owner:          {owner_login}")
    print(f"  Slug:           {slug}")
    print(f"  Credentials:    {config_path}")
    print(f"\nNext steps:")
    print(f"  Install the app:  https://github.com/settings/apps/{slug}/installations")
    print(f"  Verify setup:     gh-apps.py setup --app {slug}")
    print(f"  Generate JWT:     gh-apps.py jwt --app {slug}")


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_create(args: argparse.Namespace) -> None:
    permissions = None
    if args.permissions:
        permissions = {}
        for pair in args.permissions.split(","):
            k, _, v = pair.strip().partition(":")
            if not v:
                v = "write"
            permissions[k.strip()] = v.strip()

    events = [e.strip() for e in args.events.split(",")] if args.events else None

    _run_manifest_flow(
        name=args.name,
        org=args.org,
        permissions=permissions,
        events=events,
        webhook_url=args.webhook_url,
        public=args.public,
        description=args.description or "",
        no_browser=args.no_browser,
    )


def cmd_list(args: argparse.Namespace) -> None:
    if not CONFIG_ROOT.exists():
        print("No apps configured.")
        return

    apps = sorted(d for d in CONFIG_ROOT.iterdir() if d.is_dir() and (d / "app-id").exists())
    if not apps:
        print("No apps configured.")
        return

    print(f"{'Slug':<30} {'App ID':<12} {'Has PEM':<10}")
    print("-" * 52)
    for d in apps:
        aid = _read_file(d / "app-id") or "?"
        has_pem = "yes" if (d / "app.pem").exists() else "no"
        print(f"{d.name:<30} {aid:<12} {has_pem:<10}")


def cmd_info(args: argparse.Namespace) -> None:
    creds = _require_creds(args)
    data = _api_jwt("GET", "/app", creds)
    print(json.dumps(data, indent=2))


def cmd_delete(args: argparse.Namespace) -> None:
    creds = _resolve_credentials(args.app)
    if creds:
        slug = creds.slug
    else:
        slug = args.app or "unknown"

    print("GitHub App deletion requires the web UI.")
    print(f"\n  1. Go to: https://github.com/settings/apps/{slug}")
    print(f"  2. Scroll to 'Danger Zone' and click 'Delete this GitHub App'")
    print(f"  3. Type the app name to confirm")
    if creds:
        print(f"\n  4. Remove local credentials:")
        print(f"     rm -rf {CONFIG_ROOT / slug}")


def cmd_jwt(args: argparse.Namespace) -> None:
    creds = _require_creds(args)
    jwt = _generate_jwt(creds.app_id, creds.key_path)
    print(jwt)


def cmd_token(args: argparse.Namespace) -> None:
    creds = _require_creds(args)
    installation_id = args.installation
    if not installation_id:
        installations = _api_jwt("GET", "/app/installations", creds)
        if not installations:
            print("error: no installations found. Install the app first.", file=sys.stderr)
            sys.exit(1)
        if len(installations) > 1:
            print("error: multiple installations. Use --installation ID:", file=sys.stderr)
            for inst in installations:
                account = inst.get("account", {}).get("login", "?")
                print(f"  {inst['id']}  ({account})", file=sys.stderr)
            sys.exit(1)
        installation_id = str(installations[0]["id"])

    token = _get_installation_token(creds.app_id, installation_id, creds.key_path)
    print(token)


def cmd_setup(args: argparse.Namespace) -> None:
    creds = _resolve_credentials(args.app)
    if not creds:
        d = _config_dir(args.app)
        print(f"No credentials found at {d}")
        print(f"\nExpected files:")
        print(f"  {d}/app-id       # GitHub App ID (number)")
        print(f"  {d}/app.pem      # Private key (PEM format)")
        print(f"\nOptional:")
        print(f"  {d}/client-id")
        print(f"  {d}/client-secret")
        print(f"  {d}/webhook-secret")
        sys.exit(1)

    print(f"App:          {creds.slug}")
    print(f"App ID:       {creds.app_id}")
    print(f"Private key:  {creds.key_path}")
    print(f"Client ID:    {creds.client_id or '(not set)'}")
    print(f"Webhook sec:  {'(set)' if creds.webhook_secret else '(not set)'}")

    print(f"\nTesting JWT generation...", end=" ")
    jwt = _generate_jwt(creds.app_id, creds.key_path)
    print(f"ok ({len(jwt)} chars)")

    print("Testing API access (GET /app)...", end=" ")
    try:
        data = _api_jwt("GET", "/app", creds)
        print(f"ok ({data.get('name', '?')})")
    except SystemExit:
        print("FAIL")
        return

    print("Checking installations...", end=" ")
    try:
        installations = _api_jwt("GET", "/app/installations", creds)
        if installations:
            print(f"ok ({len(installations)} installation(s))")
            for inst in installations:
                account = inst.get("account", {}).get("login", "?")
                print(f"  {inst['id']}  {account}  ({inst.get('target_type', '?')})")
        else:
            print("none — install the app to use installation tokens")
    except SystemExit:
        print("FAIL")

    print(f"\nSetup verified for '{creds.slug}'.")


def cmd_installations(args: argparse.Namespace) -> None:
    creds = _require_creds(args)
    data = _api_jwt("GET", "/app/installations", creds)
    if not data:
        print("No installations found.")
        return
    for inst in data:
        account = inst.get("account", {}).get("login", "?")
        target = inst.get("target_type", "?")
        perms = ", ".join(f"{k}:{v}" for k, v in inst.get("permissions", {}).items())
        print(f"  {inst['id']}  {account} ({target})  [{perms}]")


def cmd_repos(args: argparse.Namespace) -> None:
    creds = _require_creds(args)
    installation_id = args.installation
    if not installation_id:
        installations = _api_jwt("GET", "/app/installations", creds)
        if len(installations) == 1:
            installation_id = str(installations[0]["id"])
        else:
            print("error: use --installation ID", file=sys.stderr)
            sys.exit(1)

    token = _get_installation_token(creds.app_id, installation_id, creds.key_path)
    data = _api_bearer("GET", "/installation/repositories", token)
    repos = data.get("repositories", [])
    if not repos:
        print("No repositories accessible.")
        return
    for r in repos:
        print(f"  {r['full_name']}  ({'private' if r['private'] else 'public'})")


def cmd_webhook_config(args: argparse.Namespace) -> None:
    creds = _require_creds(args)
    data = _api_jwt("GET", "/app/hook/config", creds)
    print(json.dumps(data, indent=2))


def cmd_webhook_update(args: argparse.Namespace) -> None:
    creds = _require_creds(args)
    update: dict[str, Any] = {}
    if args.url:
        update["url"] = args.url
    if args.secret:
        update["secret"] = args.secret
    if args.content_type:
        update["content_type"] = args.content_type
    data = _api_jwt("PATCH", "/app/hook/config", creds, data=update)
    print(json.dumps(data, indent=2))


def cmd_deliveries(args: argparse.Namespace) -> None:
    creds = _require_creds(args)
    limit = args.limit or 10
    data = _api_jwt("GET", f"/app/hook/deliveries?per_page={limit}", creds)
    if not data:
        print("No deliveries.")
        return
    print(f"{'ID':<14} {'Event':<25} {'Status':<8} {'Delivered At'}")
    print("-" * 70)
    for d in data:
        status = "ok" if d.get("status_code", 0) == 200 else str(d.get("status_code", "?"))
        print(f"{d['id']:<14} {d.get('event', '?'):<25} {status:<8} {d.get('delivered_at', '?')}")


def cmd_redeliver(args: argparse.Namespace) -> None:
    creds = _require_creds(args)
    _api_jwt("POST", f"/app/hook/deliveries/{args.delivery_id}/attempts", creds)
    print(f"Redelivery requested for {args.delivery_id}.")


def cmd_rotate_key(args: argparse.Namespace) -> None:
    creds = _resolve_credentials(args.app)
    slug = creds.slug if creds else (args.app or "unknown")

    print("Private key rotation requires the web UI.")
    print(f"\n  1. Go to: https://github.com/settings/apps/{slug}")
    print(f"  2. Under 'Private keys', click 'Generate a private key'")
    print(f"  3. Download the new PEM file")
    print(f"  4. Replace the old key:")
    print(f"     cp ~/Downloads/*.pem {CONFIG_ROOT / slug / 'app.pem'}")
    print(f"     chmod 600 {CONFIG_ROOT / slug / 'app.pem'}")
    print(f"  5. Verify: gh-apps.py setup --app {slug}")
    print(f"  6. Delete the old key from the web UI")


def cmd_permissions(args: argparse.Namespace) -> None:
    creds = _resolve_credentials(args.app)
    slug = creds.slug if creds else (args.app or "unknown")

    print("Permission changes require the web UI.")
    print(f"\n  1. Go to: https://github.com/settings/apps/{slug}/permissions")
    print(f"  2. Update the desired permissions")
    print(f"  3. Save changes")
    print(f"\nNote: Existing installations must approve new permissions.")
    print(f"See: references/permissions-guide.md for common permission sets.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_creds(args: argparse.Namespace) -> AppCredentials:
    creds = _resolve_credentials(args.app)
    if not creds:
        print("error: no credentials found. Run 'gh-apps.py setup' for help.", file=sys.stderr)
        sys.exit(1)
    return creds


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gh-apps",
        description="Create, authenticate, and manage GitHub Apps.",
    )
    p.add_argument("--app", help="App slug (auto-detected if only one exists)")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create", help="Create a new GitHub App via manifest flow")
    c.add_argument("name", help="App name")
    c.add_argument("--org", help="Create under an organization")
    c.add_argument("--permissions", help="Comma-separated key:value (e.g. issues:write,contents:read)")
    c.add_argument("--events", help="Comma-separated webhook events")
    c.add_argument("--webhook-url", help="Webhook receiver URL")
    c.add_argument("--public", action="store_true", help="Make the app public")
    c.add_argument("--description", help="App description")
    c.add_argument("--no-browser", action="store_true", help="Manual mode (no browser)")

    sub.add_parser("list", help="List locally-registered apps")
    sub.add_parser("info", help="Show app info from GitHub API")
    sub.add_parser("delete", help="Guide through manual app deletion")
    sub.add_parser("jwt", help="Generate and print a JWT")

    t = sub.add_parser("token", help="Get an installation access token")
    t.add_argument("--installation", help="Installation ID (auto-detected if only one)")

    sub.add_parser("setup", help="Validate stored credentials")
    sub.add_parser("installations", help="List app installations")

    r = sub.add_parser("repos", help="List accessible repos for an installation")
    r.add_argument("--installation", help="Installation ID")

    sub.add_parser("webhook-config", help="Show webhook configuration")

    wu = sub.add_parser("webhook-update", help="Update webhook configuration")
    wu.add_argument("--url", help="New webhook URL")
    wu.add_argument("--secret", help="New webhook secret")
    wu.add_argument("--content-type", help="Content type (json or form)")

    d = sub.add_parser("deliveries", help="List recent webhook deliveries")
    d.add_argument("--limit", type=int, help="Number of deliveries (default: 10)")

    rd = sub.add_parser("redeliver", help="Redeliver a webhook event")
    rd.add_argument("delivery_id", help="Delivery ID to redeliver")

    sub.add_parser("rotate-key", help="Guide through private key rotation")
    sub.add_parser("permissions", help="Guide through permission changes")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "create": cmd_create,
        "list": cmd_list,
        "info": cmd_info,
        "delete": cmd_delete,
        "jwt": cmd_jwt,
        "token": cmd_token,
        "setup": cmd_setup,
        "installations": cmd_installations,
        "repos": cmd_repos,
        "webhook-config": cmd_webhook_config,
        "webhook-update": cmd_webhook_update,
        "deliveries": cmd_deliveries,
        "redeliver": cmd_redeliver,
        "rotate-key": cmd_rotate_key,
        "permissions": cmd_permissions,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
