# gh-apps

Create, authenticate, and manage GitHub Apps from the command line.

## When to use this

- You need a **GitHub App** instead of a personal access token — for CI bots, webhook receivers, org-wide automation, or anything that should act as its own identity rather than yours.
- You're tired of clicking through GitHub's web UI to register apps, generate JWTs, or debug webhook deliveries.
- You want Claude to handle the entire app lifecycle: create via manifest flow, save credentials locally, generate tokens on demand.

## What it does

A single executable Python script (`scripts/gh-apps.py`) that wraps the GitHub Apps API. Uses `uv` via shebang — no install step, just run it directly:

| Area | Commands |
|------|----------|
| **Create** | `create` — register a new app via manifest flow (opens browser, saves credentials) |
| **Auth** | `jwt`, `token` — generate JWTs and installation access tokens |
| **Inspect** | `info`, `installations`, `repos`, `list` — query app state |
| **Webhooks** | `webhook-config`, `webhook-update`, `deliveries`, `redeliver` — manage and debug webhooks |
| **Lifecycle** | `setup`, `rotate-key`, `permissions`, `delete` — validate, rotate, and teardown |

Credentials are stored as flat files under `~/.config/gh-apps/<slug>/` (app ID, PEM key, client ID/secret, webhook secret).

## Examples

```bash
# Create an app with specific permissions
scripts/gh-apps.py create my-bot --permissions issues:write,metadata:read --events issues

# Get an installation token for repo-scoped API calls
scripts/gh-apps.py token

# Debug a failed webhook
scripts/gh-apps.py deliveries --limit 10
scripts/gh-apps.py redeliver 12345678
```

## Reference docs

The `references/` directory has detailed docs on the manifest schema, API endpoints, and permission sets for common use cases.
