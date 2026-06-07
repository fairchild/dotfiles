# GitHub App Manifest Schema

## Manifest JSON Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | App display name |
| `url` | string | **Yes** | App homepage URL |
| `hook_attributes` | object | No | `{url, active}` — webhook configuration |
| `redirect_url` | string | No | Post-registration redirect URL |
| `callback_urls` | array | No | Up to 10 OAuth callback URLs |
| `setup_url` | string | No | Setup redirect after install |
| `description` | string | No | App description |
| `public` | boolean | No | `true` = public, `false` = private (default) |
| `default_events` | array | No | Webhook events to subscribe to |
| `default_permissions` | object | No | Required API permissions |
| `request_oauth_on_install` | boolean | No | Prompt for OAuth on install |
| `setup_on_update` | boolean | No | Redirect to setup_url on updates |

## Manifest Flow Steps

### Step 1: POST manifest to GitHub

Personal: `POST https://github.com/settings/apps/new`
Org: `POST https://github.com/organizations/{ORG}/settings/apps/new`

Form field: `manifest` (JSON string)

### Step 2: User confirms on GitHub

GitHub shows the app details and user clicks "Create GitHub App".
GitHub redirects to `redirect_url?code=TEMPORARY_CODE`.

### Step 3: Exchange code for credentials

```
POST /app-manifests/{code}/conversions
```

No authentication required. Code expires in 1 hour.

### Response Fields

| Field | Description |
|-------|-------------|
| `id` | GitHub App ID (integer) |
| `slug` | URL-friendly name |
| `pem` | Private key (PEM format) |
| `webhook_secret` | Auto-generated webhook secret |
| `client_id` | OAuth client ID (e.g. `Iv1.abc123`) |
| `client_secret` | OAuth client secret |
| `name` | App display name |
| `owner` | Owner object with `login`, `id` |
| `html_url` | App settings URL |

## Example Manifests

### Issue Bot

```json
{
  "name": "my-issue-bot",
  "url": "https://github.com/apps/my-issue-bot",
  "default_permissions": {
    "issues": "write",
    "metadata": "read"
  },
  "default_events": ["issues", "issue_comment"]
}
```

### CI App

```json
{
  "name": "my-ci",
  "url": "https://github.com/apps/my-ci",
  "hook_attributes": {
    "url": "https://ci.example.com/webhook",
    "active": true
  },
  "default_permissions": {
    "checks": "write",
    "statuses": "write",
    "contents": "read",
    "metadata": "read"
  },
  "default_events": ["check_suite", "check_run", "push"]
}
```

### Discussion Coordinator

```json
{
  "name": "my-coordinator",
  "url": "https://github.com/apps/my-coordinator",
  "default_permissions": {
    "discussions": "write",
    "metadata": "read"
  },
  "default_events": ["discussion", "discussion_comment"]
}
```

### OAuth App (user sign-in)

```json
{
  "name": "my-oauth-app",
  "url": "https://myapp.example.com",
  "redirect_url": "https://myapp.example.com/auth/callback",
  "callback_urls": ["https://myapp.example.com/auth/callback"],
  "request_oauth_on_install": true,
  "public": true,
  "default_permissions": {
    "metadata": "read"
  }
}
```

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| "Code expired" | > 1 hour elapsed | Restart the flow |
| "Redirect mismatch" | `redirect_url` doesn't match | Ensure callback URL matches exactly |
| "Manifest invalid" | Bad JSON or missing `url` | Check manifest structure |
| "Name taken" | App name already exists | Choose a different name |
