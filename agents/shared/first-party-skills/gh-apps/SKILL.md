---
name: gh-apps
license: Apache-2.0
description: Create, authenticate, and manage GitHub Apps. Use for creating apps via manifest flow, generating JWTs, getting installation tokens, managing webhooks and installations, rotating keys. Triggers on "create github app", "github app", "manage github app", "github app JWT", "github installation token", "github app manifest", "github webhook deliveries", "register github app", "gh app".
---

# GitHub Apps Management

Script: `scripts/gh-apps.py`

## Quick Reference

| Command | Description |
|---------|-------------|
| `create NAME` | Create a GitHub App via manifest flow (opens browser) |
| `list` | List locally-registered apps |
| `info` | Show app info from GitHub API |
| `setup` | Validate stored credentials and test API access |
| `jwt` | Generate and print a JWT (10-min expiry) |
| `token` | Get an installation access token |
| `installations` | List app installations |
| `repos` | List accessible repos for an installation |
| `webhook-config` | Show webhook configuration |
| `webhook-update` | Update webhook URL/secret |
| `deliveries` | List recent webhook deliveries |
| `redeliver ID` | Redeliver a failed webhook |
| `rotate-key` | Guide through private key rotation (web UI) |
| `permissions` | Guide through permission changes (web UI) |
| `delete` | Guide through app deletion (web UI) |

Global flag: `--app SLUG` selects which app (auto-detected if only one exists).

## Credential Storage

```
~/.config/gh-apps/<slug>/
  app-id           # GitHub App ID
  app.pem          # Private key (chmod 600)
  client-id        # OAuth client ID
  client-secret    # OAuth client secret
  webhook-secret   # Auto-generated webhook secret
```

Env var overrides: `GH_APPS_APP_ID`, `GH_APPS_PRIVATE_KEY_PATH`, `GH_APPS_SLUG`.

## Common Workflows

### Create a new GitHub App

```bash
# Interactive browser flow — creates app and saves credentials automatically
scripts/gh-apps.py create my-bot --permissions issues:write,metadata:read --events issues,issue_comment

# Manual mode (no browser / headless)
scripts/gh-apps.py create my-bot --no-browser --permissions issues:write

# Create under an organization
scripts/gh-apps.py create org-bot --org my-org --permissions contents:read
```

### Authenticate and use

```bash
# Verify credentials
scripts/gh-apps.py setup

# Generate JWT for API calls
scripts/gh-apps.py jwt

# Get installation token (for repo-scoped operations)
scripts/gh-apps.py token
```

### Manage webhooks

```bash
scripts/gh-apps.py webhook-config
scripts/gh-apps.py deliveries --limit 20
scripts/gh-apps.py redeliver 12345678
```

## What Requires Manual Steps

These operations have no API — the script prints the URL and instructions:

- **Private key rotation**: `rotate-key` — generate new key in web UI, save PEM locally
- **Permission changes**: `permissions` — modify in web UI, installations must re-approve
- **App deletion**: `delete` — confirm in web UI, then remove local credentials

## References

- **Manifest schema + examples**: See `references/manifest-schema.md`
- **API endpoints**: See `references/api-endpoints.md`
- **Permission sets for common use cases**: See `references/permissions-guide.md`
